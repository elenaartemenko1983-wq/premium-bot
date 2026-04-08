import asyncio
import random
import logging
import json
import os
import time
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError, UserPrivacyRestrictedError,
    PeerFloodError, SessionPasswordNeededError,
    PhoneCodeInvalidError, PhoneCodeExpiredError
)

logging.basicConfig(level=logging.INFO)

# ─── НАСТРОЙКИ ───────────────────────────────────────────────
BOT_TOKEN = "8400914956:AAFM-teR6OTN6C5p-dBsh_Mh110HqzRLaLU"
ACCOUNTS_FILE = "accounts.json"
USERS_FILE = "users.json"  # хранит подписки пользователей

TON_WALLET = "UQDHRwgOv-yu6q4b5kQ-Ba6ZGppGOcHp1u9l6rrWb67lPB7W"

DEFAULT_API_ID = 2040
DEFAULT_API_HASH = "b18441a1ff607e10a989891a5462e627"

PLANS = {
    "1d":  ("1 день",    1,   1),
    "3d":  ("3 дня",     3,   2),
    "7d":  ("Неделя",    7,   5),
    "30d": ("Месяц",     30,  15),
    "inf": ("Навсегда",  0,   35),
}

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

auth_clients: dict = {}

# ─── РАБОТА С ПОДПИСКАМИ ────────────────────────────────────
def load_users() -> dict:
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users: dict):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)

def get_user(user_id: int) -> dict:
    users = load_users()
    return users.get(str(user_id), {})

def set_user(user_id: int, data: dict):
    users = load_users()
    users[str(user_id)] = data
    save_users(users)

def has_active_subscription(user_id: int) -> bool:
    user = get_user(user_id)
    if not user:
        return False
    expires = user.get("expires")
    if expires == -1:
        return True
    if expires and time.time() < expires:
        return True
    return False

def get_subscription_text(user_id: int) -> str:
    user = get_user(user_id)
    if not user:
        return "❌ Нет подписки"
    expires = user.get("expires")
    if expires == -1:
        return "✅ Навсегда"
    if expires and time.time() < expires:
        remaining = int(expires - time.time())
        days = remaining // 86400
        hours = (remaining % 86400) // 3600
        return f"✅ Активна ещё {days}д {hours}ч"
    return "❌ Истекла"

def activate_subscription(user_id: int, plan_key: str):
    name, days, amount = PLANS[plan_key]
    user = get_user(user_id)
    now = time.time()
    if days == 0:
        expires = -1
    else:
        current_expires = user.get("expires", now)
        if current_expires == -1:
            expires = -1
        elif current_expires > now:
            expires = current_expires + days * 86400
        else:
            expires = now + days * 86400
    set_user(user_id, {"expires": expires, "plan": name})

# ─── РАБОТА С АККАУНТАМИ ─────────────────────────────────────
def load_accounts() -> dict:
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_accounts(accounts: dict):
    with open(ACCOUNTS_FILE, "w") as f:
        json.dump(accounts, f, ensure_ascii=False, indent=2)

def get_accounts(user_id: int) -> dict:
    accounts = load_accounts()
    return accounts.get(str(user_id), {})

def set_accounts(user_id: int, user_accounts: dict):
    accounts = load_accounts()
    accounts[str(user_id)] = user_accounts
    save_accounts(accounts)

# ─── ПРОВЕРКА ОПЛАТЫ TON ─────────────────────────────────────
async def check_ton_payment(amount_ton: float, comment: str) -> bool:
    url = f"https://toncenter.com/api/v2/getTransactions"
    params = {"address": TON_WALLET, "limit": 20}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                if not data.get("ok"):
                    return False
                txs = data.get("result", [])
                now = time.time()
                for tx in txs:
                    in_msg = tx.get("in_msg", {})
                    if not in_msg:
                        continue
                    utime = tx.get("utime", 0)
                    if now - utime > 1800:
                        continue
                    value = int(in_msg.get("value", 0))
                    expected = int(amount_ton * 1_000_000_000)
                    if abs(value - expected) > 10_000_000:
                        continue
                    msg_comment = in_msg.get("message", "").strip()
                    if comment.lower() in msg_comment.lower():
                        return True
    except Exception as e:
        logging.error(f"TON check error: {e}")
    return False

# ─── FSM СОСТОЯНИЯ ───────────────────────────────────────────
class AddAccount(StatesGroup):
    entering_phone = State()
    entering_code = State()
    entering_2fa = State()

class Mailing(StatesGroup):
    choosing_account = State()
    entering_messages = State()
    entering_users = State()
    confirming = State()

class Payment(StatesGroup):
    waiting_confirm = State()

# ─── КЛАВИАТУРЫ ──────────────────────────────────────────────
def main_menu_kb(user_id: int = None):
    kb = InlineKeyboardBuilder()
    if user_id and has_active_subscription(user_id):
        kb.button(text="🚀 Начать рассылку", callback_data="start_mailing")
        kb.button(text="👤 Управление аккаунтами", callback_data="manage_accounts")
    else:
        kb.button(text="💎 Купить подписку", callback_data="buy_sub")
    kb.button(text="📊 Моя подписка", callback_data="my_sub")
    kb.button(text="ℹ️ Помощь", callback_data="help")
    kb.adjust(1)
    return kb.as_markup()

def accounts_manage_kb(user_id: int):
    accounts = get_accounts(user_id)
    kb = InlineKeyboardBuilder()
    if accounts:
        for phone, info in accounts.items():
            status = "✅" if info.get("active") else "❌"
            kb.button(text=f"{status} {phone}", callback_data=f"acc_info_{phone}")
    kb.button(text="➕ Добавить аккаунт", callback_data="add_account")
    kb.button(text="◀️ Назад", callback_data="back_main")
    kb.adjust(1)
    return kb.as_markup()

def account_actions_kb(phone: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="🗑 Удалить аккаунт", callback_data=f"del_acc_{phone}")
    kb.button(text="◀️ Назад", callback_data="manage_accounts")
    kb.adjust(1)
    return kb.as_markup()

def choose_account_kb(user_id: int):
    accounts = get_accounts(user_id)
    kb = InlineKeyboardBuilder()
    if accounts:
        for phone, info in accounts.items():
            if info.get("active"):
                kb.button(text=f"✅ {phone}", callback_data=f"pick_acc_{phone}")
    kb.button(text="◀️ Назад", callback_data="back_main")
    kb.adjust(1)
    return kb.as_markup()

# ─── ДОБАВЛЕНИЕ АККАУНТА ─────────────────────────────────────
async def _finish_auth(message: Message, state: FSMContext, user_id: int, phone: str, session: str):
    client = auth_clients[user_id]["client"]
    me = await client.get_me()
    await client.disconnect()
    del auth_clients[user_id]
    accounts = get_accounts(user_id)
    accounts[phone] = {
        "session": session,

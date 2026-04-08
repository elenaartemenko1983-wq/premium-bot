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

# ─── НАЛАШТУВАННЯ ────────────────────────────────────────────
BOT_TOKEN = "8400914956:AAFM-teR6OTN6C5p-dBsh_Mh110HqzRLaLU"
ACCOUNTS_FILE = "accounts.json"
USERS_FILE = "users.json"

# Секретна команда для безкоштовного доступу назавжди
SECRET_CODE = "freeforever"

# TON-гаманець для прийому платежів
TON_WALLET = "UQDHRwgOv-yu6q4b5kQ-Ba6ZGppGOcHp1u9l6rrWb67lPB7W"

# API дані для авторизації нових акаунтів
DEFAULT_API_ID = 2040
DEFAULT_API_HASH = "b18441a1ff607e10a989891a5462e627"
# ─────────────────────────────────────────────────────────────

# Тарифи: (назва, днів, сума TON)
# днів = 0 → назавжди
PLANS = {
    "1d":  ("1 день",   1,   1),
    "3d":  ("3 дні",    3,   2),
    "7d":  ("Тиждень",  7,   5),
    "30d": ("Місяць",   30,  15),
    "inf": ("Назавжди", 0,   35),
}

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

auth_clients: dict = {}


# ─── ПІДПИСКИ ────────────────────────────────────────────────
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
        return "❌ Немає підписки"
    expires = user.get("expires")
    if expires == -1:
        return "✅ Назавжди"
    if expires and time.time() < expires:
        remaining = int(expires - time.time())
        days = remaining // 86400
        hours = (remaining % 86400) // 3600
        return f"✅ Активна ще {days}д {hours}г"
    return "❌ Закінчилась"


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


# ─── АКАУНТИ (окремі для кожного юзера) ─────────────────────
def load_all_accounts() -> dict:
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_all_accounts(all_accounts: dict):
    with open(ACCOUNTS_FILE, "w") as f:
        json.dump(all_accounts, f, ensure_ascii=False, indent=2)


def get_accounts(user_id: int) -> dict:
    all_accounts = load_all_accounts()
    return all_accounts.get(str(user_id), {})


def save_accounts(user_id: int, accounts: dict):
    all_accounts = load_all_accounts()
    all_accounts[str(user_id)] = accounts
    save_all_accounts(all_accounts)


# ─── ПЕРЕВІРКА ОПЛАТИ TON ────────────────────────────────────
async def check_ton_payment(amount_ton: float, comment: str) -> bool:
    url = f"https://toncenter.com/api/v2/getTransactions"
    params = {
        "address": TON_WALLET,
        "limit": 20,
    }
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


# ─── FSM СТАНИ ───────────────────────────────────────────────
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


# ─── КЛАВІАТУРИ ──────────────────────────────────────────────
def main_menu_kb(user_id: int = None):
    kb = InlineKeyboardBuilder()
    if user_id and has_active_subscription(user_id):
        kb.button(text="🚀 Почати розсилку", callback_data="start_mailing")
        kb.button(text="👤 Управління акаунтами", callback_data="manage_accounts")
    else:
        kb.button(text="💎 Купити підписку", callback_data="buy_sub")
    kb.button(text="📊 Моя підписка", callback_data="my_sub")
    kb.button(text="ℹ️ Допомога", callback_data="help")
    kb.adjust(1)
    return kb.as_markup()


def plans_kb():
    kb = InlineKeyboardBuilder()
    for key, (name, days, amount) in PLANS.items():
        kb.button(text=f"{name} — {amount} TON", callback_data=f"plan_{key}")
    kb.button(text="◀️ Назад", callback_data="back_main")
    kb.adjust(1)
    return kb.as_markup()


def payment_kb(plan_key: str):
    name, days, amount = PLANS[plan_key]
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Я оплатив!", callback_data=f"paid_{plan_key}")
    kb.button(text="◀️ Вибрати інший тариф", callback_data="buy_sub")
    kb.adjust(1)
    return kb.as_markup()


def accounts_manage_kb(user_id: int = 0):
    accounts = get_accounts(user_id)
    kb = InlineKeyboardBuilder()
    if accounts:
        for phone, info in accounts.items():
            status = "✅" if info.get("active") else "❌"
            kb.button(text=f"{status} {phone}", callback_data=f"acc_info_{phone}")
    kb.button(text="➕ Додати акаунт", callback_data="add_account")
    kb.button(text="◀️ Назад", callback_data="back_main")
    kb.adjust(1)
    return kb.as_markup()


def account_actions_kb(phone: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="🗑 Видалити акаунт", callback_data=f"del_acc_{phone}")
    kb.button(text="◀️ Назад", callback_data="manage_accounts")
    kb.adjust(1)
    return kb.as_markup()


def choose_account_kb(user_id: int = 0):
    accounts = get_accounts(user_id)
    kb = InlineKeyboardBuilder()
    if accounts:
        for phone, info in accounts.items():
            if info.get("active"):
                kb.button(text=f"✅ {phone}", callback_data=f"pick_acc_{phone}")
    kb.button(text="◀️ Назад", callback_data="back_main")
    kb.adjust(1)
    return kb.as_markup()


def cancel_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Скасувати", callback_data="cancel")
    return kb.as_markup()


def confirm_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Запустити", callback_data="run")
    kb.button(text="✏️ Змінити", callback_data="start_mailing")
    kb.button(text="❌ Скасувати", callback_data="cancel")
    kb.adjust(2, 1)
    return kb.as_markup()


# ─── /start ──────────────────────────────────────────────────
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    sub_text = get_subscription_text(user_id)
    await message.answer(
        "👋 <b>Smart Sender Bot</b>\n\n"
        "Розумна розсилка через Telegram із захистом від банів.\n\n"
        f"📊 Підписка: {sub_text}\n\n"
        "Вибери дію 👇",
        parse_mode="HTML",
        reply_markup=main_menu_kb(user_id)
    )


# ─── СЕКРЕТНА КОМАНДА ─────────────────────────────────────────
@dp.message(F.text.lower() == SECRET_CODE)
async def cmd_secret(message: Message):
    user_id = message.from_user.id
    if get_user(user_id).get("expires") == -1:
        await message.answer(
            "✅ <b>У тебе вже є безкоштовний доступ назавжди!</b>",
            parse_mode="HTML",
            reply_markup=main_menu_kb(user_id)
        )
        return
    set_user(user_id, {"expires": -1, "plan": "Назавжди (подарунок)"})
    await message.answer(
        "🎁 <b>Секретний код прийнято!</b>\n\n"
        "✅ Тобі активовано безкоштовний доступ <b>назавжди</b>!\n\n"
        "Вибери дію 👇",
        parse_mode="HTML",
        reply_markup=main_menu_kb(user_id)
    )


# ─── МОЯ ПІДПИСКА ────────────────────────────────────────────
@dp.callback_query(F.data == "my_sub")
async def cb_my_sub(call: CallbackQuery):
    user_id = call.from_user.id
    sub_text = get_subscription_text(user_id)
    kb = InlineKeyboardBuilder()
    if not has_active_subscription(user_id):
        kb.button(text="💎 Купити підписку", callback_data="buy_sub")
    kb.button(text="◀️ Назад", callback_data="back_main")
    kb.adjust(1)
    await call.message.edit_text(
        f"📊 <b>Твоя підписка</b>\n\n"
        f"Статус: {sub_text}",
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )


# ─── КУПІВЛЯ ПІДПИСКИ ────────────────────────────────────────
@dp.callback_query(F.data == "buy_sub")
async def cb_buy_sub(call: CallbackQuery):
    await call.message.edit_text(
        "💎 <b>Вибери тариф</b>\n\n"
        "🔹 1 день — 1 TON\n"
        "🔹 3 дні — 2 TON\n"
        "🔹 Тиждень — 5 TON\n"
        "🔹 Місяць — 15 TON\n"
        "🔹 Назавжди — 35 TON\n\n"
        "Натисни на потрібний тариф 👇",
        parse_mode="HTML",
        reply_markup=plans_kb()
    )


@dp.callback_query(F.data.startswith("plan_"))
async def cb_plan(call: CallbackQuery, state: FSMContext):
    plan_key = call.data.replace("plan_", "")
    if plan_key not in PLANS:
        await call.answer("Невірний тариф.")
        return

    name, days, amount = PLANS[plan_key]
    user_id = call.from_user.id
    comment = f"sub{user_id}{plan_key}"

    await state.set_state(Payment.waiting_confirm)
    await state.update_data(plan_key=plan_key, comment=comment, amount=amount)

    await call.message.edit_text(
        f"💳 <b>Оплата тарифу «{name}»</b>\n\n"
        f"Сума: <b>{amount} TON</b>\n\n"
        f"Переведи точно <b>{amount} TON</b> на гаманець:\n"
        f"<code>{TON_WALLET}</code>\n\n"
        f"📝 У коментарі до переказу обов'язково вкажи:\n"
        f"<code>{comment}</code>\n\n"
        "⚠️ Без коментаря платіж не буде знайдено!\n\n"
        "Після оплати натисни кнопку нижче 👇",
        parse_mode="HTML",
        reply_markup=payment_kb(plan_key)
    )


@dp.callback_query(F.data.startswith("paid_"), Payment.waiting_confirm)
async def cb_paid(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    plan_key = data.get("plan_key")
    comment = data.get("comment")
    amount = data.get("amount")

    if not plan_key or not comment:
        await call.answer("Помилка. Спробуй знову.")
        await state.clear()
        return

    await call.message.edit_text(
        "🔍 <b>Перевіряю оплату...</b>\n\nЦе займе кілька секунд.",
        parse_mode="HTML"
    )

    found = await check_ton_payment(float(amount), comment)

    if found:
        activate_subscription(call.from_user.id, plan_key)
        name, days, _ = PLANS[plan_key]
        await state.clear()
        await call.message.edit_text(
            f"🎉 <b>Оплату підтверджено!</b>\n\n"
            f"✅ Тариф «{name}» активовано.\n\n"
            f"Підписка: {get_subscription_text(call.from_user.id)}",
            parse_mode="HTML",
            reply_markup=main_menu_kb(call.from_user.id)
        )
    else:
        kb = InlineKeyboardBuilder()
        kb.button(text="🔄 Перевірити знову", callback_data=f"paid_{plan_key}")
        kb.button(text="◀️ Змінити тариф", callback_data="buy_sub")
        kb.adjust(1)
        await call.message.edit_text(
            "❌ <b>Платіж не знайдено</b>\n\n"
            "Можливі причини:\n"
            "• Переказ ще не пройшов (зачекай 1-2 хв)\n"
            "• Невірний коментар до переказу\n"
            "• Невірна сума\n\n"
            f"Коментар має бути: <code>{comment}</code>\n"
            f"Сума: <b>{amount} TON</b>\n\n"
            "Спробуй натиснути «Перевірити знову» через хвилину.",
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )


# ─── ДОПОМОГА ────────────────────────────────────────────────
@dp.callback_query(F.data == "help")
async def cb_help(call: CallbackQuery):
    await call.message.edit_text(
        "📖 <b>Інструкція:</b>\n\n"
        "1️⃣ Купи підписку через меню\n"
        "2️⃣ Зайди в <b>Управління акаунтами</b>\n"
        "3️⃣ Додай акаунт через номер телефону\n"
        "4️⃣ Введи код з Telegram <b>цифра через пробіл</b>:\n"
        "   <code>1 2 3 4 5</code>\n"
        "5️⃣ Натисни <b>Почати розсилку</b>\n"
        "6️⃣ Вибери акаунт, введи тексти і юзернейми\n\n"
        "⚙️ <b>Анти-бан:</b>\n"
        "• Затримка 1.5–3.5 сек між повідомленнями\n"
        "• Пауза 2 хв кожні 20 повідомлень\n"
        "• Випадковий вибір тексту\n\n"
        "💳 <b>Оплата:</b>\n"
        "• Переводь TON точною сумою\n"
        "• Обов'язково вкажи коментар\n"
        "• Натисни «Я оплатив» після переказу",
        parse_mode="HTML",
        reply_markup=InlineKeyboardBuilder().button(
            text="◀️ Назад", callback_data="back_main"
        ).as_markup()
    )


@dp.callback_query(F.data == "back_main")
async def cb_back_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = call.from_user.id
    sub_text = get_subscription_text(user_id)
    await call.message.edit_text(
        "👋 <b>Smart Sender Bot</b>\n\n"
        f"📊 Підписка: {sub_text}\n\n"
        "Вибери дію 👇",
        parse_mode="HTML",
        reply_markup=main_menu_kb(user_id)
    )


# ─── УПРАВЛІННЯ АКАУНТАМИ ─────────────────────────────────────
@dp.callback_query(F.data == "manage_accounts")
async def cb_manage_accounts(call: CallbackQuery, state: FSMContext):
    if not has_active_subscription(call.from_user.id):
        await call.answer("❌ Потрібна активна підписка!", show_alert=True)
        return
    await state.clear()
    user_id = call.from_user.id
    accounts = get_accounts(user_id)
    count = len(accounts)
    await call.message.edit_text(
        f"👤 <b>Управління акаунтами</b>\n\n"
        f"Додано акаунтів: <b>{count}</b>\n\n"
        "Вибери акаунт для управління або додай новий 👇",
        parse_mode="HTML",
        reply_markup=accounts_manage_kb(user_id)
    )


@dp.callback_query(F.data.startswith("acc_info_"))
async def cb_acc_info(call: CallbackQuery):
    phone = call.data.replace("acc_info_", "")
    accounts = get_accounts(call.from_user.id)
    info = accounts.get(phone, {})
    status = "✅ Активний" if info.get("active") else "❌ Не активний"
    await call.message.edit_text(
        f"📱 <b>Акаунт: {phone}</b>\n\n"
        f"Статус: {status}\n"
        f"Сесія: <code>{info.get('session', '—')}</code>",
        parse_mode="HTML",
        reply_markup=account_actions_kb(phone)
    )


@dp.callback_query(F.data.startswith("del_acc_"))
async def cb_del_acc(call: CallbackQuery):
    phone = call.data.replace("del_acc_", "")
    user_id = call.from_user.id
    accounts = get_accounts(user_id)
    session_file = accounts.get(phone, {}).get("session", "")
    if phone in accounts:
        del accounts[phone]
        save_accounts(user_id, accounts)
    for ext in [".session", ".session-journal"]:
        if os.path.exists(session_file + ext):
            os.remove(session_file + ext)
    await call.message.edit_text(
        f"🗑 <b>Акаунт {phone} видалено.</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardBuilder().button(
            text="◀️ Назад", callback_data="manage_accounts"
        ).as_markup()
    )


# ─── ДОДАВАННЯ АКАУНТУ ───────────────────────────────────────
@dp.callback_query(F.data == "add_account")
async def cb_add_account(call: CallbackQuery, state: FSMContext):
    if not has_active_subscription(call.from_user.id):
        await call.answer("❌ Потрібна активна підписка!", show_alert=True)
        return
    await state.set_state(AddAccount.entering_phone)
    await call.message.edit_text(
        "📱 <b>Додавання акаунту</b>\n\n"
        "Введи номер телефону у форматі:\n"
        "<code>+79991234567</code>",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )


@dp.message(AddAccount.entering_phone)
async def step_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    if not phone.startswith("+"):
        await message.answer("⚠️ Введи номер з +, наприклад: <code>+79991234567</code>", parse_mode="HTML")
        return

    session_name = f"session_{phone.replace('+', '').replace(' ', '')}_{message.from_user.id}"
    client = TelegramClient(session_name, DEFAULT_API_ID, DEFAULT_API_HASH)
    auth_clients[message.from_user.id] = {"client": client, "phone": phone, "session": session_name}

    await message.answer("⏳ Підключаюсь і відправляю код...")

    try:
        await client.connect()
        result = await client.send_code_request(phone)
        auth_clients[message.from_user.id]["phone_code_hash"] = result.phone_code_hash
        await state.update_data(phone=phone, session=session_name)
        await state.set_state(AddAccount.entering_code)
        await message.answer(
            "📨 <b>Код відправлено!</b>\n\n"
            "Введи код з Telegram <b>цифра через пробіл</b>:\n"
            "<code>1 2 3 4 5</code>",
            parse_mode="HTML",
            reply_markup=cancel_kb()
        )
    except Exception as e:
        await client.disconnect()
        del auth_clients[message.from_user.id]
        await message.answer(f"❌ Помилка: <code>{e}</code>", parse_mode="HTML", reply_markup=main_menu_kb(message.from_user.id))
        await state.clear()


@dp.message(AddAccount.entering_code)
async def step_code(message: Message, state: FSMContext):
    raw = message.text.strip()
    user_id = message.from_user.id

    # Перевіряємо формат: тільки "1 2 3 4 5" — цифри через пробіл
    parts = raw.split()
    if not all(p.isdigit() and len(p) == 1 for p in parts) or len(parts) < 4:
        await message.answer(
            "⚠️ <b>Невірний формат коду!</b>\n\n"
            "Введи код <b>цифра через пробіл</b>:\n"
            "<code>1 2 3 4 5</code>\n\n"
            "Кожна цифра окремо!",
            parse_mode="HTML",
            reply_markup=cancel_kb()
        )
        return

    code = "".join(parts)

    if user_id not in auth_clients:
        await state.clear()
        await message.answer("❌ Сесія закінчилась. Почни знову.", reply_markup=main_menu_kb(user_id))
        return

    auth_data = auth_clients[user_id]
    client: TelegramClient = auth_data["client"]
    phone = auth_data["phone"]
    phone_code_hash = auth_data["phone_code_hash"]

    try:
        await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
        await _finish_auth(message, state, user_id, phone, auth_data["session"])
    except SessionPasswordNeededError:
        await state.set_state(AddAccount.entering_2fa)
        await message.answer(
            "🔐 <b>Потрібен пароль 2FA</b>\n\nВведи пароль хмарного захисту:",
            parse_mode="HTML",
            reply_markup=cancel_kb()
        )
    except PhoneCodeInvalidError:
        await message.answer("❌ Невірний код. Спробуй ще раз:", reply_markup=cancel_kb())
    except PhoneCodeExpiredError:
        await client.disconnect()
        del auth_clients[user_id]
        await state.clear()
        await message.answer("❌ Код застарів. Почни додавання знову.", reply_markup=main_menu_kb(user_id))
    except Exception as e:
        await message.answer(f"❌ Помилка: <code>{e}</code>", parse_mode="HTML", reply_markup=cancel_kb())


@dp.message(AddAccount.entering_2fa)
async def step_2fa(message: Message, state: FSMContext):
    password = message.text.strip()
    user_id = message.from_user.id

    if user_id not in auth_clients:
        await state.clear()
        await message.answer("❌ Сесія закінчилась. Почни знову.", reply_markup=main_menu_kb(user_id))
        return

    auth_data = auth_clients[user_id]
    client: TelegramClient = auth_data["client"]

    try:
        await client.sign_in(password=password)
        await _finish_auth(message, state, user_id, auth_data["phone"], auth_data["session"])
    except Exception as e:
        await message.answer(f"❌ Невірний пароль: <code>{e}</code>", parse_mode="HTML", reply_markup=cancel_kb())


async def _finish_auth(message: Message, state: FSMContext, user_id: int, phone: str, session: str):
    client = auth_clients[user_id]["client"]
    me = await client.get_me()
    await client.disconnect()
    del auth_clients[user_id]

    accounts = get_accounts(user_id)
    accounts[phone] = {
        "session": session,
        "active": True,
        "name": f"{me.first_name or ''} {me.last_name or ''}".strip(),
        "username": me.username or ""
    }
    save_accounts(user_id, accounts)
    await state.clear()

    name = accounts[phone]["name"]
    uname = f"@{accounts[phone]['username']}" if accounts[phone]["username"] else ""
    await message.answer(
        f"✅ <b>Акаунт додано!</b>\n\n"
        f"👤 {name} {uname}\n"
        f"📱 {phone}",
        parse_mode="HTML",
        reply_markup=main_menu_kb(user_id)
    )


# ─── РОЗСИЛКА — КРОК 1: ВИБІР АКАУНТУ ───────────────────────
@dp.callback_query(F.data == "start_mailing")
async def cb_start_mailing(call: CallbackQuery, state: FSMContext):
    if not has_active_subscription(call.from_user.id):
        await call.answer("❌ Потрібна активна підписка!", show_alert=True)
        return
    user_id = call.from_user.id
    accounts = get_accounts(user_id)
    active = {p: i for p, i in accounts.items() if i.get("active")}
    if not active:
        await call.message.edit_text(
            "⚠️ <b>Нема активних акаунтів!</b>\n\nСпочатку додай акаунт.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardBuilder().button(
                text="➕ Додати акаунт", callback_data="add_account"
            ).button(text="◀️ Назад", callback_data="back_main").adjust(1).as_markup()
        )
        return
    await state.set_state(Mailing.choosing_account)
    await call.message.edit_text(
        "👤 <b>Крок 1 з 3 — Вибір акаунту</b>\n\nЗ якого акаунту відправляти?",
        parse_mode="HTML",
        reply_markup=choose_account_kb(user_id)
    )


@dp.callback_query(F.data.startswith("pick_acc_"), Mailing.choosing_account)
async def cb_pick_account(call: CallbackQuery, state: FSMContext):
    phone = call.data.replace("pick_acc_", "")
    await state.update_data(phone=phone)
    await state.set_state(Mailing.entering_messages)
    await call.message.edit_text(
        f"✅ Акаунт: <b>{phone}</b>\n\n"
        "✏️ <b>Крок 2 з 3 — Тексти повідомлень</b>\n\n"
        "Введи один або кілька варіантів тексту.\n"
        "Кожен варіант — з нового рядка.\n\n"
        "<i>Приклад:</i>\n<code>Привіт, як справи?\nГей, що нового?</code>",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )


# ─── КРОК 2: ТЕКСТИ ──────────────────────────────────────────
@dp.message(Mailing.entering_messages)
async def step_messages(message: Message, state: FSMContext):
    lines = [l.strip() for l in message.text.strip().splitlines() if l.strip()]
    if not lines:
        await message.answer("⚠️ Введи хоча б один текст.", reply_markup=cancel_kb())
        return
    await state.update_data(messages=lines)
    await state.set_state(Mailing.entering_users)
    await message.answer(
        f"✅ Збережено <b>{len(lines)}</b> варіант(ів).\n\n"
        "👥 <b>Крок 3 з 3 — Отримувачі</b>\n\n"
        "Введи юзернейми, кожен з нового рядка.\n"
        "Символ @ не потрібен.\n\n"
        "<i>Приклад:</i>\n<code>username1\nusername2</code>",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )


# ─── КРОК 3: ЮЗЕРНЕЙМИ ───────────────────────────────────────
@dp.message(Mailing.entering_users)
async def step_users(message: Message, state: FSMContext):
    users = []
    for line in message.text.strip().splitlines():
        clean = line.replace("✅", "").replace("@", "").strip()
        if clean:
            users.append(clean)
    if not users:
        await message.answer("⚠️ Введи хоча б один юзернейм.", reply_markup=cancel_kb())
        return
    await state.update_data(users=users)
    data = await state.get_data()
    await state.set_state(Mailing.confirming)

    msgs_preview = "\n".join(f"• {m[:50]}{'...' if len(m) > 50 else ''}" for m in data["messages"])
    users_preview = "\n".join(f"• @{u}" for u in users[:5])
    if len(users) > 5:
        users_preview += f"\n• ...і ще {len(users) - 5}"

    await message.answer(
        "📋 <b>Підтвердження</b>\n\n"
        f"📱 Акаунт: <b>{data['phone']}</b>\n"
        f"✉️ Варіантів: <b>{len(data['messages'])}</b>\n"
        f"{msgs_preview}\n\n"
        f"👥 Отримувачів: <b>{len(users)}</b>\n"
        f"{users_preview}\n\nВсе вірно?",
        parse_mode="HTML",
        reply_markup=confirm_kb()
    )


# ─── СКАСУВАННЯ ──────────────────────────────────────────────
@dp.callback_query(F.data == "cancel")
async def cb_cancel(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if user_id in auth_clients:
        try:
            await auth_clients[user_id]["client"].disconnect()
        except Exception:
            pass
        del auth_clients[user_id]
    await state.clear()
    await call.message.edit_text("❌ <b>Скасовано.</b>", parse_mode="HTML", reply_markup=main_menu_kb(user_id))


# ─── ЗАПУСК РОЗСИЛКИ ─────────────────────────────────────────
@dp.callback_query(F.data == "run", Mailing.confirming)
async def cb_run(call: CallbackQuery, state: FSMContext):
    if not has_active_subscription(call.from_user.id):
        await call.answer("❌ Підписка закінчилась!", show_alert=True)
        return

    data = await state.get_data()
    await state.clear()

    user_id = call.from_user.id
    phone = data["phone"]
    accounts = get_accounts(user_id)
    acc = accounts.get(phone)
    if not acc:
        await call.message.edit_text("❌ Акаунт не знайдено.", reply_markup=main_menu_kb(user_id))
        return

    users = data["users"]
    messages = data["messages"]

    status_msg = await call.message.edit_text(
        f"🚀 <b>Розсилку запущено!</b>\n\n"
        f"📱 Акаунт: <b>{phone}</b>\n"
        f"👥 Отримувачів: <b>{len(users)}</b>\n\n"
        "⏳ Підключаюсь до акаунту...",
        parse_mode="HTML"
    )

    client = TelegramClient(acc["session"], DEFAULT_API_ID, DEFAULT_API_HASH)

    try:
        await client.connect()
        if not await client.is_user_authorized():
            await status_msg.edit_text(
                "❌ <b>Акаунт не авторизований!</b>\n\nПереавторизуй акаунт у розділі управління.",
                parse_mode="HTML",
                reply_markup=main_menu_kb(user_id)
            )
            await client.disconnect()
            return
    except Exception as e:
        await status_msg.edit_text(
            f"❌ Помилка підключення: <code>{e}</code>",
            parse_mode="HTML",
            reply_markup=main_menu_kb(user_id)
        )
        return

    sent = 0
    failed = 0
    errors_log = []

    for i, user in enumerate(users):
        try:
            msg = random.choice(messages)
            await client.send_message(user, msg)
            sent += 1
        except FloodWaitError as e:
            errors_log.append(f"@{user}: FloodWait {e.seconds}s")
            failed += 1
            await asyncio.sleep(e.seconds)
        except UserPrivacyRestrictedError:
            errors_log.append(f"@{user}: приватність закрита")
            failed += 1
        except PeerFloodError:
            errors_log.append(f"@{user}: PeerFlood")
            failed += 1
            await asyncio.sleep(60)
        except Exception as e:
            errors_log.append(f"@{user}: {str(e)[:50]}")
            failed += 1

        if (i + 1) % 5 == 0 or (i + 1) == len(users):
            filled = int((i + 1) / len(users) * 10)
            bar = "▓" * filled + "░" * (10 - filled)
            try:
                await status_msg.edit_text(
                    f"🚀 <b>Розсилка йде...</b>\n\n"
                    f"[{bar}] {i+1}/{len(users)}\n\n"
                    f"✅ Успішно: <b>{sent}</b>\n"
                    f"❌ Помилки: <b>{failed}</b>",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        if (i + 1) % 20 == 0 and (i + 1) < len(users):
            try:
                await status_msg.edit_text(
                    f"⏸ <b>Пауза 2 хвилини (анти-бан)</b>\n\n"
                    f"{i+1}/{len(users)} | ✅ {sent} | ❌ {failed}",
                    parse_mode="HTML"
                )
            except Exception:
                pass
            await asyncio.sleep(120)
        else:
            await asyncio.sleep(random.uniform(1.5, 3.5))

    await client.disconnect()

    errors_text = ""
    if errors_log:
        errors_text = "\n\n<b>Останні помилки:</b>\n" + "\n".join(errors_log[-8:])
        if len(errors_log) > 8:
            errors_text += f"\n...і ще {len(errors_log) - 8}"

    await status_msg.edit_text(
        "🎉 <b>Розсилку завершено!</b>\n\n"
        f"👥 Всього: <b>{len(users)}</b>\n"
        f"✅ Успішно: <b>{sent}</b>\n"
        f"❌ Помилки: <b>{failed}</b>"
        f"{errors_text}",
        parse_mode="HTML",
        reply_markup=main_menu_kb(user_id)
    )


if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))

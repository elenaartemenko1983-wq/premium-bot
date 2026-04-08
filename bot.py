import asyncio
import random
import logging
import json
import os
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

# API данные для авторизации новых аккаунтов
DEFAULT_API_ID = 2040
DEFAULT_API_HASH = "b18441a1ff607e10a989891a5462e627"
# ─────────────────────────────────────────────────────────────

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Временное хранилище активных Telethon клиентов (для авторизации)
auth_clients: dict = {}


# ─── РАБОТА С АККАУНТАМИ ─────────────────────────────────────
def load_accounts() -> dict:
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_accounts(accounts: dict):
    with open(ACCOUNTS_FILE, "w") as f:
        json.dump(accounts, f, ensure_ascii=False, indent=2)


def get_accounts() -> dict:
    return load_accounts()


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


# ─── КЛАВИАТУРЫ ──────────────────────────────────────────────
def main_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🚀 Начать рассылку", callback_data="start_mailing")
    kb.button(text="👤 Управление аккаунтами", callback_data="manage_accounts")
    kb.button(text="ℹ️ Помощь", callback_data="help")
    kb.adjust(1)
    return kb.as_markup()


def accounts_manage_kb():
    accounts = get_accounts()
    kb = InlineKeyboardBuilder()
    if accounts:
        for phone, info in accounts.items():
            status = "✅" if info.get("active") else "❌"
            kb.button(
                text=f"{status} {phone}",
                callback_data=f"acc_info_{phone}"
            )
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


def choose_account_kb():
    accounts = get_accounts()
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
    kb.button(text="❌ Отмена", callback_data="cancel")
    return kb.as_markup()


def confirm_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Запустить", callback_data="run")
    kb.button(text="✏️ Изменить", callback_data="start_mailing")
    kb.button(text="❌ Отмена", callback_data="cancel")
    kb.adjust(2, 1)
    return kb.as_markup()


# ─── /start ──────────────────────────────────────────────────
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 <b>Smart Sender Bot</b>\n\n"
        "Умная рассылка через Telegram с защитой от банов.\n\n"
        "Выбери действие 👇",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )


# ─── ПОМОЩЬ ──────────────────────────────────────────────────
@dp.callback_query(F.data == "help")
async def cb_help(call: CallbackQuery):
    await call.message.edit_text(
        "📖 <b>Инструкция:</b>\n\n"
        "1️⃣ Зайди в <b>Управление аккаунтами</b>\n"
        "2️⃣ Добавь аккаунт через номер телефона\n"
        "3️⃣ Введи код из Telegram\n"
        "4️⃣ Нажми <b>Начать рассылку</b>\n"
        "5️⃣ Выбери аккаунт, введи тексты и юзернеймы\n\n"
        "⚙️ <b>Анти-бан:</b>\n"
        "• Задержка 1.5–3.5 сек между сообщениями\n"
        "• Пауза 2 мин каждые 20 сообщений\n"
        "• Случайный выбор текста",
        parse_mode="HTML",
        reply_markup=InlineKeyboardBuilder().button(
            text="◀️ Назад", callback_data="back_main"
        ).as_markup()
    )


@dp.callback_query(F.data == "back_main")
async def cb_back_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "👋 <b>Smart Sender Bot</b>\n\nВыбери действие 👇",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )


# ─── УПРАВЛЕНИЕ АККАУНТАМИ ───────────────────────────────────
@dp.callback_query(F.data == "manage_accounts")
async def cb_manage_accounts(call: CallbackQuery, state: FSMContext):
    await state.clear()
    accounts = get_accounts()
    count = len(accounts)
    await call.message.edit_text(
        f"👤 <b>Управление аккаунтами</b>\n\n"
        f"Добавлено аккаунтов: <b>{count}</b>\n\n"
        "Выбери аккаунт для управления или добавь новый 👇",
        parse_mode="HTML",
        reply_markup=accounts_manage_kb()
    )


@dp.callback_query(F.data.startswith("acc_info_"))
async def cb_acc_info(call: CallbackQuery):
    phone = call.data.replace("acc_info_", "")
    accounts = get_accounts()
    info = accounts.get(phone, {})
    status = "✅ Активен" if info.get("active") else "❌ Не активен"
    await call.message.edit_text(
        f"📱 <b>Аккаунт: {phone}</b>\n\n"
        f"Статус: {status}\n"
        f"Сессия: <code>{info.get('session', '—')}</code>",
        parse_mode="HTML",
        reply_markup=account_actions_kb(phone)
    )


@dp.callback_query(F.data.startswith("del_acc_"))
async def cb_del_acc(call: CallbackQuery):
    phone = call.data.replace("del_acc_", "")
    accounts = get_accounts()
    session_file = accounts.get(phone, {}).get("session", "")
    if phone in accounts:
        del accounts[phone]
        save_accounts(accounts)
    # Удаляем файл сессии если есть
    for ext in [".session", ".session-journal"]:
        if os.path.exists(session_file + ext):
            os.remove(session_file + ext)
    await call.message.edit_text(
        f"🗑 <b>Аккаунт {phone} удалён.</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardBuilder().button(
            text="◀️ Назад", callback_data="manage_accounts"
        ).as_markup()
    )


# ─── ДОБАВЛЕНИЕ АККАУНТА ─────────────────────────────────────
@dp.callback_query(F.data == "add_account")
async def cb_add_account(call: CallbackQuery, state: FSMContext):
    await state.set_state(AddAccount.entering_phone)
    await call.message.edit_text(
        "📱 <b>Добавление аккаунта</b>\n\n"
        "Введи номер телефона в формате:\n"
        "<code>+79991234567</code>",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )


@dp.message(AddAccount.entering_phone)
async def step_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    if not phone.startswith("+"):
        await message.answer("⚠️ Введи номер с +, например: <code>+79991234567</code>", parse_mode="HTML")
        return

    session_name = f"session_{phone.replace('+', '').replace(' ', '')}"
    client = TelegramClient(session_name, DEFAULT_API_ID, DEFAULT_API_HASH)
    auth_clients[message.from_user.id] = {"client": client, "phone": phone, "session": session_name}

    await message.answer("⏳ Подключаюсь и отправляю код...")

    try:
        await client.connect()
        result = await client.send_code_request(phone)
        auth_clients[message.from_user.id]["phone_code_hash"] = result.phone_code_hash
        await state.update_data(phone=phone, session=session_name)
        await state.set_state(AddAccount.entering_code)
        await message.answer(
            "📨 <b>Код отправлен!</b>\n\n"
            "Введи код из Telegram (цифры через пробел или слитно):\n"
            "<i>Пример: 12345 или 1 2 3 4 5</i>",
            parse_mode="HTML",
            reply_markup=cancel_kb()
        )
    except Exception as e:
        await client.disconnect()
        del auth_clients[message.from_user.id]
        await message.answer(f"❌ Ошибка: <code>{e}</code>", parse_mode="HTML", reply_markup=main_menu_kb())
        await state.clear()


@dp.message(AddAccount.entering_code)
async def step_code(message: Message, state: FSMContext):
    code = message.text.strip().replace(" ", "")
    user_id = message.from_user.id

    if user_id not in auth_clients:
        await state.clear()
        await message.answer("❌ Сессия истекла. Начни заново.", reply_markup=main_menu_kb())
        return

    auth_data = auth_clients[user_id]
    client: TelegramClient = auth_data["client"]
    phone = auth_data["phone"]
    phone_code_hash = auth_data["phone_code_hash"]

    try:
        await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
        # Успешная авторизация
        await _finish_auth(message, state, user_id, phone, auth_data["session"])
    except SessionPasswordNeededError:
        await state.set_state(AddAccount.entering_2fa)
        await message.answer(
            "🔐 <b>Требуется пароль 2FA</b>\n\nВведи пароль облачной защиты:",
            parse_mode="HTML",
            reply_markup=cancel_kb()
        )
    except PhoneCodeInvalidError:
        await message.answer("❌ Неверный код. Попробуй ещё раз:", reply_markup=cancel_kb())
    except PhoneCodeExpiredError:
        await client.disconnect()
        del auth_clients[user_id]
        await state.clear()
        await message.answer("❌ Код истёк. Начни добавление заново.", reply_markup=main_menu_kb())
    except Exception as e:
        await message.answer(f"❌ Ошибка: <code>{e}</code>", parse_mode="HTML", reply_markup=cancel_kb())


@dp.message(AddAccount.entering_2fa)
async def step_2fa(message: Message, state: FSMContext):
    password = message.text.strip()
    user_id = message.from_user.id

    if user_id not in auth_clients:
        await state.clear()
        await message.answer("❌ Сессия истекла. Начни заново.", reply_markup=main_menu_kb())
        return

    auth_data = auth_clients[user_id]
    client: TelegramClient = auth_data["client"]

    try:
        await client.sign_in(password=password)
        await _finish_auth(message, state, user_id, auth_data["phone"], auth_data["session"])
    except Exception as e:
        await message.answer(f"❌ Неверный пароль: <code>{e}</code>", parse_mode="HTML", reply_markup=cancel_kb())


async def _finish_auth(message: Message, state: FSMContext, user_id: int, phone: str, session: str):
    client = auth_clients[user_id]["client"]
    me = await client.get_me()
    await client.disconnect()
    del auth_clients[user_id]

    accounts = get_accounts()
    accounts[phone] = {
        "session": session,
        "active": True,
        "name": f"{me.first_name or ''} {me.last_name or ''}".strip(),
        "username": me.username or ""
    }
    save_accounts(accounts)
    await state.clear()

    name = accounts[phone]["name"]
    uname = f"@{accounts[phone]['username']}" if accounts[phone]["username"] else ""
    await message.answer(
        f"✅ <b>Аккаунт добавлен!</b>\n\n"
        f"👤 {name} {uname}\n"
        f"📱 {phone}",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )


# ─── РАССЫЛКА — ШАГ 1: ВЫБОР АККАУНТА ───────────────────────
@dp.callback_query(F.data == "start_mailing")
async def cb_start_mailing(call: CallbackQuery, state: FSMContext):
    accounts = get_accounts()
    active = {p: i for p, i in accounts.items() if i.get("active")}
    if not active:
        await call.message.edit_text(
            "⚠️ <b>Нет активных аккаунтов!</b>\n\nСначала добавь аккаунт.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardBuilder().button(
                text="➕ Добавить аккаунт", callback_data="add_account"
            ).button(text="◀️ Назад", callback_data="back_main").adjust(1).as_markup()
        )
        return
    await state.set_state(Mailing.choosing_account)
    await call.message.edit_text(
        "👤 <b>Шаг 1 из 3 — Выбор аккаунта</b>\n\nС какого аккаунта отправлять?",
        parse_mode="HTML",
        reply_markup=choose_account_kb()
    )


@dp.callback_query(F.data.startswith("pick_acc_"), Mailing.choosing_account)
async def cb_pick_account(call: CallbackQuery, state: FSMContext):
    phone = call.data.replace("pick_acc_", "")
    await state.update_data(phone=phone)
    await state.set_state(Mailing.entering_messages)
    await call.message.edit_text(
        f"✅ Аккаунт: <b>{phone}</b>\n\n"
        "✏️ <b>Шаг 2 из 3 — Тексты сообщений</b>\n\n"
        "Введи один или несколько вариантов текста.\n"
        "Каждый вариант — с новой строки.\n\n"
        "<i>Пример:</i>\n<code>Привет, как дела?\nХай, что нового?</code>",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )


# ─── ШАГ 2: ТЕКСТЫ ───────────────────────────────────────────
@dp.message(Mailing.entering_messages)
async def step_messages(message: Message, state: FSMContext):
    lines = [l.strip() for l in message.text.strip().splitlines() if l.strip()]
    if not lines:
        await message.answer("⚠️ Введи хотя бы один текст.", reply_markup=cancel_kb())
        return
    await state.update_data(messages=lines)
    await state.set_state(Mailing.entering_users)
    await message.answer(
        f"✅ Сохранено <b>{len(lines)}</b> вариант(ов).\n\n"
        "👥 <b>Шаг 3 из 3 — Получатели</b>\n\n"
        "Введи юзернеймы, каждый с новой строки.\n"
        "Символ @ не нужен.\n\n"
        "<i>Пример:</i>\n<code>username1\nusername2</code>",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )


# ─── ШАГ 3: ЮЗЕРНЕЙМЫ ────────────────────────────────────────
@dp.message(Mailing.entering_users)
async def step_users(message: Message, state: FSMContext):
    users = []
    for line in message.text.strip().splitlines():
        clean = line.replace("✅", "").replace("@", "").strip()
        if clean:
            users.append(clean)
    if not users:
        await message.answer("⚠️ Введи хотя бы один юзернейм.", reply_markup=cancel_kb())
        return
    await state.update_data(users=users)
    data = await state.get_data()
    await state.set_state(Mailing.confirming)

    msgs_preview = "\n".join(f"• {m[:50]}{'...' if len(m) > 50 else ''}" for m in data["messages"])
    users_preview = "\n".join(f"• @{u}" for u in users[:5])
    if len(users) > 5:
        users_preview += f"\n• ...и ещё {len(users) - 5}"

    await message.answer(
        "📋 <b>Подтверждение</b>\n\n"
        f"📱 Аккаунт: <b>{data['phone']}</b>\n"
        f"✉️ Вариантов: <b>{len(data['messages'])}</b>\n"
        f"{msgs_preview}\n\n"
        f"👥 Получателей: <b>{len(users)}</b>\n"
        f"{users_preview}\n\nВсё верно?",
        parse_mode="HTML",
        reply_markup=confirm_kb()
    )


# ─── ОТМЕНА ──────────────────────────────────────────────────
@dp.callback_query(F.data == "cancel")
async def cb_cancel(call: CallbackQuery, state: FSMContext):
    # Отключаем клиент авторизации если был
    user_id = call.from_user.id
    if user_id in auth_clients:
        try:
            await auth_clients[user_id]["client"].disconnect()
        except Exception:
            pass
        del auth_clients[user_id]
    await state.clear()
    await call.message.edit_text("❌ <b>Отменено.</b>", parse_mode="HTML", reply_markup=main_menu_kb())


# ─── ЗАПУСК РАССЫЛКИ ─────────────────────────────────────────
@dp.callback_query(F.data == "run", Mailing.confirming)
async def cb_run(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    phone = data["phone"]
    accounts = get_accounts()
    acc = accounts.get(phone)
    if not acc:
        await call.message.edit_text("❌ Аккаунт не найден.", reply_markup=main_menu_kb())
        return

    users = data["users"]
    messages = data["messages"]

    status_msg = await call.message.edit_text(
        f"🚀 <b>Рассылка запущена!</b>\n\n"
        f"📱 Аккаунт: <b>{phone}</b>\n"
        f"👥 Получателей: <b>{len(users)}</b>\n\n"
        "⏳ Подключаюсь к аккаунту...",
        parse_mode="HTML"
    )

    client = TelegramClient(acc["session"], DEFAULT_API_ID, DEFAULT_API_HASH)

    try:
        await client.connect()
        if not await client.is_user_authorized():
            await status_msg.edit_text(
                "❌ <b>Аккаунт не авторизован!</b>\n\nПереавторизуй аккаунт в разделе управления.",
                parse_mode="HTML",
                reply_markup=main_menu_kb()
            )
            await client.disconnect()
            return
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка подключения: <code>{e}</code>", parse_mode="HTML", reply_markup=main_menu_kb())
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
            errors_log.append(f"@{user}: приватность закрыта")
            failed += 1
        except PeerFloodError:
            errors_log.append(f"@{user}: PeerFlood")
            failed += 1
            await asyncio.sleep(60)
        except Exception as e:
            errors_log.append(f"@{user}: {str(e)[:50]}")
            failed += 1

        # Обновление статуса каждые 5 сообщений
        if (i + 1) % 5 == 0 or (i + 1) == len(users):
            filled = int((i + 1) / len(users) * 10)
            bar = "▓" * filled + "░" * (10 - filled)
            try:
                await status_msg.edit_text(
                    f"🚀 <b>Рассылка идёт...</b>\n\n"
                    f"[{bar}] {i+1}/{len(users)}\n\n"
                    f"✅ Успешно: <b>{sent}</b>\n"
                    f"❌ Ошибки: <b>{failed}</b>",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        if (i + 1) % 20 == 0 and (i + 1) < len(users):
            try:
                await status_msg.edit_text(
                    f"⏸ <b>Пауза 2 минуты (анти-бан)</b>\n\n"
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
        errors_text = "\n\n<b>Последние ошибки:</b>\n" + "\n".join(errors_log[-8:])
        if len(errors_log) > 8:
            errors_text += f"\n...и ещё {len(errors_log) - 8}"

    await status_msg.edit_text(
        "🎉 <b>Рассылка завершена!</b>\n\n"
        f"👥 Всего: <b>{len(users)}</b>\n"
        f"✅ Успешно: <b>{sent}</b>\n"
        f"❌ Ошибки: <b>{failed}</b>"
        f"{errors_text}",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )


if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))

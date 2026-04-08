import asyncio
import random
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from telethon import TelegramClient
from telethon.errors import FloodWaitError, UserPrivacyRestrictedError, PeerFloodError

logging.basicConfig(level=logging.INFO)

# ─── НАСТРОЙКИ ───────────────────────────────────────────────
BOT_TOKEN = "ВАШ_BOT_TOKEN"  # Токен от @BotFather

ACCOUNTS = {
    "1": {"api_id": 30293465,  "api_hash": "647d499195b4186f1068558e435772a9",  "session": "session1", "label": "Аккаунт 1"},
    "2": {"api_id": 37327123,  "api_hash": "795f38c137b8bae33ad44b493340aa92", "session": "session2", "label": "Аккаунт 2"},
}
# ─────────────────────────────────────────────────────────────

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


class Form(StatesGroup):
    choosing_account = State()
    entering_messages = State()
    entering_users = State()
    confirming = State()


def main_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🚀 Начать рассылку", callback_data="start_mailing")
    kb.button(text="ℹ️ Помощь", callback_data="help")
    kb.adjust(1)
    return kb.as_markup()


def accounts_kb():
    kb = InlineKeyboardBuilder()
    for key, acc in ACCOUNTS.items():
        kb.button(text=f"👤 {acc['label']}", callback_data=f"acc_{key}")
    kb.button(text="◀️ Назад", callback_data="back_main")
    kb.adjust(1)
    return kb.as_markup()


def confirm_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Запустить", callback_data="run")
    kb.button(text="✏️ Изменить", callback_data="start_mailing")
    kb.button(text="❌ Отмена", callback_data="cancel")
    kb.adjust(2, 1)
    return kb.as_markup()


def cancel_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="❌ Отмена", callback_data="cancel")
    return kb.as_markup()


# ─── /start ──────────────────────────────────────────────────
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 <b>Добро пожаловать в Smart Sender!</b>\n\n"
        "Умная рассылка сообщений через Telegram с защитой от блокировок.\n\n"
        "Выбери действие ниже 👇",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )


# ─── Помощь ──────────────────────────────────────────────────
@dp.callback_query(F.data == "help")
async def cb_help(call: CallbackQuery):
    await call.message.edit_text(
        "📖 <b>Как пользоваться:</b>\n\n"
        "1️⃣ Нажми <b>Начать рассылку</b>\n"
        "2️⃣ Выбери аккаунт отправителя\n"
        "3️⃣ Введи тексты сообщений (каждый с новой строки)\n"
        "4️⃣ Введи юзернеймы получателей (каждый с новой строки)\n"
        "5️⃣ Подтверди и запускай!\n\n"
        "⚙️ <b>Защита от бана:</b>\n"
        "• Случайная задержка 1.5–3.5 сек между сообщениями\n"
        "• Пауза 2 мин каждые 20 сообщений\n"
        "• Случайный выбор текста из списка",
        parse_mode="HTML",
        reply_markup=InlineKeyboardBuilder().button(text="◀️ Назад", callback_data="back_main").as_markup()
    )


@dp.callback_query(F.data == "back_main")
async def cb_back_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "👋 <b>Smart Sender</b>\n\nВыбери действие 👇",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )


# ─── ШАГ 1: Выбор аккаунта ───────────────────────────────────
@dp.callback_query(F.data == "start_mailing")
async def cb_start_mailing(call: CallbackQuery, state: FSMContext):
    await state.set_state(Form.choosing_account)
    await call.message.edit_text(
        "👤 <b>Шаг 1 из 3 — Выбор аккаунта</b>\n\nС какого аккаунта отправлять?",
        parse_mode="HTML",
        reply_markup=accounts_kb()
    )


@dp.callback_query(F.data.startswith("acc_"), Form.choosing_account)
async def cb_choose_account(call: CallbackQuery, state: FSMContext):
    key = call.data.split("_")[1]
    await state.update_data(account_key=key)
    await state.set_state(Form.entering_messages)
    await call.message.edit_text(
        f"✅ Выбран <b>{ACCOUNTS[key]['label']}</b>\n\n"
        "✏️ <b>Шаг 2 из 3 — Тексты сообщений</b>\n\n"
        "Введи один или несколько текстов сообщений.\n"
        "Каждый текст — с новой строки.\n"
        "Бот будет случайно выбирать один из них при каждой отправке.\n\n"
        "<i>Пример:</i>\n<code>Привет, как дела?\nХай! Что нового?</code>",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )


# ─── ШАГ 2: Тексты сообщений ─────────────────────────────────
@dp.message(Form.entering_messages)
async def step_messages(message: Message, state: FSMContext):
    lines = [l.strip() for l in message.text.strip().splitlines() if l.strip()]
    if not lines:
        await message.answer("⚠️ Введи хотя бы один текст.", reply_markup=cancel_kb())
        return
    await state.update_data(messages=lines)
    await state.set_state(Form.entering_users)
    await message.answer(
        f"✅ Сохранено <b>{len(lines)}</b> вариант(ов) сообщения.\n\n"
        "👥 <b>Шаг 3 из 3 — Получатели</b>\n\n"
        "Введи юзернеймы получателей, каждый с новой строки.\n"
        "Символ @ не нужен.\n\n"
        "<i>Пример:</i>\n<code>username1\nusername2\nusername3</code>",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )


# ─── ШАГ 3: Юзернеймы ────────────────────────────────────────
@dp.message(Form.entering_users)
async def step_users(message: Message, state: FSMContext):
    raw = message.text.strip().splitlines()
    users = []
    for line in raw:
        clean = line.replace("✅", "").replace("@", "").strip()
        if clean:
            users.append(clean)

    if not users:
        await message.answer("⚠️ Введи хотя бы один юзернейм.", reply_markup=cancel_kb())
        return

    await state.update_data(users=users)
    data = await state.get_data()
    await state.set_state(Form.confirming)

    msgs_preview = "\n".join(f"• {m[:50]}{'...' if len(m)>50 else ''}" for m in data["messages"])
    users_preview = "\n".join(f"• @{u}" for u in users[:5])
    if len(users) > 5:
        users_preview += f"\n• ...и ещё {len(users)-5}"

    await message.answer(
        "📋 <b>Подтверждение рассылки</b>\n\n"
        f"👤 Аккаунт: <b>{ACCOUNTS[data['account_key']]['label']}</b>\n"
        f"✉️ Вариантов сообщений: <b>{len(data['messages'])}</b>\n"
        f"{msgs_preview}\n\n"
        f"👥 Получателей: <b>{len(users)}</b>\n"
        f"{users_preview}\n\n"
        "Всё верно?",
        parse_mode="HTML",
        reply_markup=confirm_kb()
    )


# ─── Отмена ──────────────────────────────────────────────────
@dp.callback_query(F.data == "cancel")
async def cb_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "❌ <b>Отменено.</b>",
        parse_mode="HTML",
        reply_markup=main_menu_kb()
    )


# ─── ЗАПУСК РАССЫЛКИ ─────────────────────────────────────────
@dp.callback_query(F.data == "run", Form.confirming)
async def cb_run(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    acc = ACCOUNTS[data["account_key"]]
    users = data["users"]
    messages = data["messages"]

    status_msg = await call.message.edit_text(
        "🚀 <b>Рассылка запущена!</b>\n\n"
        f"👥 Получателей: <b>{len(users)}</b>\n"
        "⏳ Прогресс: <b>0 / {}</b>\n\n"
        "✅ Успешно: 0\n❌ Ошибки: 0".format(len(users)),
        parse_mode="HTML"
    )

    client = TelegramClient(acc["session"], acc["api_id"], acc["api_hash"])

    try:
        await client.start()
    except Exception as e:
        await status_msg.edit_text(f"❌ <b>Не удалось подключиться к аккаунту:</b>\n<code>{e}</code>", parse_mode="HTML")
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
            wait = e.seconds
            errors_log.append(f"@{user}: FloodWait {wait}s")
            failed += 1
            await asyncio.sleep(wait)
        except UserPrivacyRestrictedError:
            errors_log.append(f"@{user}: приватность закрыта")
            failed += 1
        except PeerFloodError:
            errors_log.append(f"@{user}: PeerFlood — слишком много запросов")
            failed += 1
            await asyncio.sleep(60)
        except Exception as e:
            errors_log.append(f"@{user}: {str(e)[:60]}")
            failed += 1

        # Обновляем статус каждые 5 сообщений
        if (i + 1) % 5 == 0 or (i + 1) == len(users):
            progress_bar = "▓" * int((i+1)/len(users)*10) + "░" * (10 - int((i+1)/len(users)*10))
            try:
                await status_msg.edit_text(
                    f"🚀 <b>Рассылка идёт...</b>\n\n"
                    f"[{progress_bar}] {i+1}/{len(users)}\n\n"
                    f"✅ Успешно: <b>{sent}</b>\n"
                    f"❌ Ошибки: <b>{failed}</b>",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        # Паузы анти-бан
        if (i + 1) % 20 == 0 and (i + 1) < len(users):
            try:
                await status_msg.edit_text(
                    f"⏸ <b>Пауза 2 минуты</b> (анти-бан)\n\n"
                    f"Отправлено: {i+1}/{len(users)}\n"
                    f"✅ {sent} | ❌ {failed}",
                    parse_mode="HTML"
                )
            except Exception:
                pass
            await asyncio.sleep(120)
        else:
            await asyncio.sleep(random.uniform(1.5, 3.5))

    await client.disconnect()

    # Итог
    errors_text = ""
    if errors_log:
        errors_text = "\n\n<b>Ошибки:</b>\n" + "\n".join(errors_log[-10:])
        if len(errors_log) > 10:
            errors_text += f"\n...и ещё {len(errors_log)-10}"

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


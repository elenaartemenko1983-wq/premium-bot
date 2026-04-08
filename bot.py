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
PROMO_FILE = "promos.json"
STATS_FILE = "stats.json"

# ─── АДМІНИ ──────────────────────────────────────────────────
# Додай Telegram user_id всіх адмінів
ADMIN_IDS = [7338481397, 8643268507]  # ← головний і другий адмін

TON_WALLET = "UQDHRwgOv-yu6q4b5kQ-Ba6ZGppGOcHp1u9l6rrWb67lPB7W"

DEFAULT_API_ID = 2040
DEFAULT_API_HASH = "b18441a1ff607e10a989891a5462e627"
# ─────────────────────────────────────────────────────────────

PLANS = {
    "1d":  {"uk": "1 день",    "ru": "1 день",    "en": "1 day",    "days": 1,  "amount": 1},
    "3d":  {"uk": "3 дні",     "ru": "3 дня",     "en": "3 days",   "days": 3,  "amount": 2},
    "7d":  {"uk": "Тиждень",   "ru": "Неделя",    "en": "Week",     "days": 7,  "amount": 5},
    "30d": {"uk": "Місяць",    "ru": "Месяц",     "en": "Month",    "days": 30, "amount": 15},
    "inf": {"uk": "Назавжди",  "ru": "Навсегда",  "en": "Forever",  "days": 0,  "amount": 35},
}

# ─── ПЕРЕКЛАДИ ───────────────────────────────────────────────
TEXTS = {
    "uk": {
        "welcome": "👋 <b>Smart Sender Bot</b>\n\nРозумна розсилка через Telegram із захистом від банів.\n\n📊 Підписка: {sub}\n\nВибери дію 👇",
        "sub_forever": "✅ Назавжди",
        "sub_active": "✅ Активна ще {days}д {hours}г",
        "sub_expired": "❌ Закінчилась",
        "sub_none": "❌ Немає підписки",
        "my_sub": "📊 <b>Твоя підписка</b>\n\nСтатус: {sub}",
        "buy_sub": "💎 <b>Вибери тариф</b>\n\nНатисни на потрібний тариф 👇",
        "secret_already": "✅ <b>У тебе вже є безкоштовний доступ назавжди!</b>",
        "secret_ok": "🎁 <b>Секретний код прийнято!</b>\n\n✅ Тобі активовано безкоштовний доступ <b>назавжди</b>!\n\nВибери дію 👇",
        "need_sub": "❌ Потрібна активна підписка!",
        "help": (
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
            "• Натисни «Я оплатив» після переказу"
        ),
        "manage_acc": "👤 <b>Управління акаунтами</b>\n\nДодано акаунтів: <b>{count}</b>\n\nВибери акаунт або додай новий 👇",
        "no_active_acc": "⚠️ <b>Нема активних акаунтів!</b>\n\nСпочатку додай акаунт.",
        "add_acc": "📱 <b>Додавання акаунту</b>\n\nВведи номер телефону у форматі:\n<code>+79991234567</code>",
        "code_sent": "📨 <b>Код відправлено!</b>\n\nВведи код з Telegram <b>цифра через пробіл</b>:\n<code>1 2 3 4 5</code>",
        "code_format_err": "⚠️ <b>Невірний формат коду!</b>\n\nВведи код <b>цифра через пробіл</b>:\n<code>1 2 3 4 5</code>\n\nКожна цифра окремо!",
        "need_2fa": "🔐 <b>Потрібен пароль 2FA</b>\n\nВведи пароль хмарного захисту:",
        "wrong_code": "❌ Невірний код. Спробуй ще раз:",
        "code_expired": "❌ Код застарів. Почни додавання знову.",
        "acc_added": "✅ <b>Акаунт додано!</b>\n\n👤 {name} {uname}\n📱 {phone}",
        "acc_deleted": "🗑 <b>Акаунт {phone} видалено.</b>",
        "acc_info": "📱 <b>Акаунт: {phone}</b>\n\nСтатус: {status}\nСесія: <code>{session}</code>",
        "acc_active": "✅ Активний",
        "acc_inactive": "❌ Не активний",
        "step1": "👤 <b>Крок 1 з 3 — Вибір акаунту</b>\n\nЗ якого акаунту відправляти?",
        "step2": "✅ Акаунт: <b>{phone}</b>\n\n✏️ <b>Крок 2 з 3 — Тексти повідомлень</b>\n\nВведи один або кілька варіантів тексту.\nКожен варіант — з нового рядка.\n\n<i>Приклад:</i>\n<code>Привіт, як справи?\nГей, що нового?</code>",
        "step3": "✅ Збережено <b>{count}</b> варіант(ів).\n\n👥 <b>Крок 3 з 3 — Отримувачі</b>\n\nВведи юзернейми, кожен з нового рядка.\nСимвол @ не потрібен.\n\n<i>Приклад:</i>\n<code>username1\nusername2</code>",
        "confirm": "📋 <b>Підтвердження</b>\n\n📱 Акаунт: <b>{phone}</b>\n✉️ Варіантів: <b>{msg_count}</b>\n{msgs}\n\n👥 Отримувачів: <b>{user_count}</b>\n{users}\n\nВсе вірно?",
        "more_users": "• ...і ще {n}",
        "cancelled": "❌ <b>Скасовано.</b>",
        "mailing_start": "🚀 <b>Розсилку запущено!</b>\n\n📱 Акаунт: <b>{phone}</b>\n👥 Отримувачів: <b>{count}</b>\n\n⏳ Підключаюсь до акаунту...",
        "mailing_progress": "🚀 <b>Розсилка йде...</b>\n\n[{bar}] {current}/{total}\n\n✅ Успішно: <b>{sent}</b>\n❌ Помилки: <b>{failed}</b>",
        "mailing_pause": "⏸ <b>Пауза 2 хвилини (анти-бан)</b>\n\n{current}/{total} | ✅ {sent} | ❌ {failed}",
        "mailing_done": "🎉 <b>Розсилку завершено!</b>\n\n👥 Всього: <b>{total}</b>\n✅ Успішно: <b>{sent}</b>\n❌ Помилки: <b>{failed}</b>",
        "mailing_errors": "\n\n<b>Останні помилки:</b>\n{errors}",
        "more_errors": "\n...і ще {n}",
        "not_authorized": "❌ <b>Акаунт не авторизований!</b>\n\nПереавторизуй акаунт у розділі управління.",
        "connect_err": "❌ Помилка підключення: <code>{err}</code>",
        "sub_expired_alert": "❌ Підписка закінчилась!",
        "acc_not_found": "❌ Акаунт не знайдено.",
        "connecting": "⏳ Підключаюсь і відправляю код...",
        "phone_format_err": "⚠️ Введи номер з +, наприклад: <code>+79991234567</code>",
        "wrong_pass": "❌ Невірний пароль: <code>{err}</code>",
        "session_expired": "❌ Сесія закінчилась. Почни знову.",
        "error": "❌ Помилка: <code>{err}</code>",
        "payment_text": (
            "💳 <b>Оплата тарифу «{name}»</b>\n\n"
            "Сума: <b>{amount} TON</b>\n\n"
            "Переведи точно <b>{amount} TON</b> на гаманець:\n"
            "<code>{wallet}</code>\n\n"
            "📝 У коментарі до переказу обов'язково вкажи:\n"
            "<code>{comment}</code>\n\n"
            "⚠️ Без коментаря платіж не буде знайдено!\n\n"
            "Після оплати натисни кнопку нижче 👇"
        ),
        "checking": "🔍 <b>Перевіряю оплату...</b>\n\nЦе займе кілька секунд.",
        "payment_ok": "🎉 <b>Оплату підтверджено!</b>\n\n✅ Тариф «{name}» активовано.\n\nПідписка: {sub}",
        "payment_fail": (
            "❌ <b>Платіж не знайдено</b>\n\n"
            "Можливі причини:\n"
            "• Переказ ще не пройшов (зачекай 1-2 хв)\n"
            "• Невірний коментар до переказу\n"
            "• Невірна сума\n\n"
            "Коментар має бути: <code>{comment}</code>\n"
            "Сума: <b>{amount} TON</b>\n\n"
            "Спробуй натиснути «Перевірити знову» через хвилину."
        ),
        "payment_err": "Помилка. Спробуй знову.",
        "invalid_plan": "Невірний тариф.",
        "settings": "⚙️ <b>Налаштування</b>\n\nВибери мову інтерфейсу 👇",
        "lang_set": "✅ Мову змінено на Українську 🇺🇦",
        # Buttons
        "btn_mailing": "🚀 Почати розсилку",
        "btn_manage": "👤 Управління акаунтами",
        "btn_buy": "💎 Купити підписку",
        "btn_my_sub": "📊 Моя підписка",
        "btn_help": "ℹ️ Допомога",
        "btn_settings": "⚙️ Налаштування",
        "btn_back": "◀️ Назад",
        "btn_paid": "✅ Я оплатив!",
        "btn_other_plan": "◀️ Вибрати інший тариф",
        "btn_check_again": "🔄 Перевірити знову",
        "btn_change_plan": "◀️ Змінити тариф",
        "btn_cancel": "❌ Скасувати",
        "btn_run": "✅ Запустити",
        "btn_edit": "✏️ Змінити",
        "btn_add_acc": "➕ Додати акаунт",
        "btn_del_acc": "🗑 Видалити акаунт",
        "btn_buy_sub": "💎 Купити підписку",
        "no_text": "⚠️ Введи хоча б один текст.",
        "no_users": "⚠️ Введи хоча б один юзернейм.",
        # Промокоди
        "enter_promo": "🎟 Введи промокод:",
        "promo_ok": "🎉 <b>Промокод активовано!</b>\n\n✅ Тариф «{name}» активовано.\n\nПідписка: {sub}",
        "promo_invalid": "❌ Невірний або вже використаний промокод.",
        "promo_expired": "❌ Строк дії промокоду закінчився.",
        "promo_used_up": "❌ Промокод вже вичерпано.",
        "btn_promo": "🎟 Ввести промокод",
        # Адмін
        "not_admin": "⛔ У тебе немає доступу до цього розділу.",
        "admin_panel": (
            "🛠 <b>Адмін-панель</b>\n\n"
            "👥 Всього користувачів: <b>{total}</b>\n"
            "✅ Активних підписок: <b>{active}</b>\n"
            "❌ Без підписки: <b>{inactive}</b>\n\n"
            "Вибери дію 👇"
        ),
        "admin_users_list": "👥 <b>Список користувачів</b> (стор. {page}/{pages}):\n\n{users}",
        "admin_user_info": (
            "👤 <b>Користувач {user_id}</b>\n"
            "📛 Ім'я: {name}\n"
            "🌐 Мова: {lang}\n"
            "📊 Підписка: {sub}\n"
            "🗓 Акаунтів: {acc_count}"
        ),
        "admin_sub_given": "✅ Підписку «{plan}» видано користувачу {user_id}.",
        "admin_promo_created": "✅ Промокод <code>{code}</code> створено.\nТариф: {plan}\nВикористань: {uses}",
        "admin_promo_deleted": "🗑 Промокод {code} видалено.",
        "admin_promos_list": "🎟 <b>Промокоди:</b>\n\n{promos}",
        "admin_no_promos": "Промокодів немає.",
        "admin_enter_uid": "Введи Telegram ID користувача:",
        "admin_uid_invalid": "❌ Невірний ID. Введи число.",
        "admin_user_not_found": "❌ Користувача не знайдено.",
        "admin_choose_plan": "Вибери тариф для видачі:",
        "admin_enter_promo_code": "Введи текст промокоду (латинські літери/цифри):",
        "admin_enter_promo_uses": "Скільки разів можна використати? (0 = безліміт):",
        "admin_enter_promo_plan": "Вибери тариф для промокоду:",
        "admin_broadcast_enter": "Введи текст для розсилки всім користувачам:",
        "admin_broadcast_done": "📢 Розсилку завершено. Відправлено: {sent}, помилок: {failed}.",
        "btn_admin": "🛠 Адмін-панель",
        "btn_admin_users": "👥 Користувачі",
        "btn_admin_give_sub": "🎁 Видати підписку",
        "btn_admin_promos": "🎟 Промокоди",
        "btn_admin_new_promo": "➕ Новий промокод",
        "btn_admin_broadcast": "📢 Розсилка",
        "btn_admin_del_promo": "🗑 Видалити",
        "btn_prev": "◀️",
        "btn_next": "▶️",
        # Реферальна система
        "referral_info": (
            "👥 <b>Реферальна програма</b>\n\n"
            "Запрошуй друзів — отримуй безкоштовні дні!\n\n"
            "🔗 Твоє реферальне посилання:\n<code>{link}</code>\n\n"
            "👤 Запрошено: <b>{count}</b> друзів\n"
            "🎁 Зароблено бонусів: <b>{bonus}</b> днів\n\n"
            "За кожного запрошеного друга, що купить підписку — <b>+3 дні</b> тобі!"
        ),
        "referral_bonus": "🎉 Твій друг купив підписку! Тобі нараховано <b>+3 дні</b> підписки.",
        "btn_referral": "👥 Реферальна програма",
        # Статистика розсилок
        "my_stats": (
            "📈 <b>Твоя статистика</b>\n\n"
            "🚀 Розсилок запущено: <b>{total_mailings}</b>\n"
            "✉️ Повідомлень відправлено: <b>{total_sent}</b>\n"
            "❌ Помилок всього: <b>{total_failed}</b>\n"
            "📊 Успішність: <b>{rate}%</b>"
        ),
        "btn_my_stats": "📈 Моя статистика",
        # Нотифікація про закінчення підписки
        "sub_expiry_warn": "⚠️ <b>Підписка закінчується через {hours} годин!</b>\n\nПродовж зараз 👇",
    },
    "ru": {
        "welcome": "👋 <b>Smart Sender Bot</b>\n\nУмная рассылка через Telegram с защитой от банов.\n\n📊 Подписка: {sub}\n\nВыбери действие 👇",
        "sub_forever": "✅ Навсегда",
        "sub_active": "✅ Активна ещё {days}д {hours}ч",
        "sub_expired": "❌ Истекла",
        "sub_none": "❌ Нет подписки",
        "my_sub": "📊 <b>Твоя подписка</b>\n\nСтатус: {sub}",
        "buy_sub": "💎 <b>Выбери тариф</b>\n\nНажми на нужный тариф 👇",
        "secret_already": "✅ <b>У тебя уже есть бесплатный доступ навсегда!</b>",
        "secret_ok": "🎁 <b>Секретный код принят!</b>\n\n✅ Тебе активирован бесплатный доступ <b>навсегда</b>!\n\nВыбери действие 👇",
        "need_sub": "❌ Нужна активная подписка!",
        "help": (
            "📖 <b>Инструкция:</b>\n\n"
            "1️⃣ Купи подписку через меню\n"
            "2️⃣ Зайди в <b>Управление аккаунтами</b>\n"
            "3️⃣ Добавь аккаунт через номер телефона\n"
            "4️⃣ Введи код из Telegram <b>цифра через пробел</b>:\n"
            "   <code>1 2 3 4 5</code>\n"
            "5️⃣ Нажми <b>Начать рассылку</b>\n"
            "6️⃣ Выбери аккаунт, введи тексты и юзернеймы\n\n"
            "⚙️ <b>Анти-бан:</b>\n"
            "• Задержка 1.5–3.5 сек между сообщениями\n"
            "• Пауза 2 мин каждые 20 сообщений\n"
            "• Случайный выбор текста\n\n"
            "💳 <b>Оплата:</b>\n"
            "• Переводи TON точной суммой\n"
            "• Обязательно укажи комментарий\n"
            "• Нажми «Я оплатил» после перевода"
        ),
        "manage_acc": "👤 <b>Управление аккаунтами</b>\n\nДобавлено аккаунтов: <b>{count}</b>\n\nВыбери аккаунт или добавь новый 👇",
        "no_active_acc": "⚠️ <b>Нет активных аккаунтов!</b>\n\nСначала добавь аккаунт.",
        "add_acc": "📱 <b>Добавление аккаунта</b>\n\nВведи номер телефона в формате:\n<code>+79991234567</code>",
        "code_sent": "📨 <b>Код отправлен!</b>\n\nВведи код из Telegram <b>цифра через пробел</b>:\n<code>1 2 3 4 5</code>",
        "code_format_err": "⚠️ <b>Неверный формат кода!</b>\n\nВведи код <b>цифра через пробел</b>:\n<code>1 2 3 4 5</code>\n\nКаждая цифра отдельно!",
        "need_2fa": "🔐 <b>Требуется пароль 2FA</b>\n\nВведи пароль облачной защиты:",
        "wrong_code": "❌ Неверный код. Попробуй ещё раз:",
        "code_expired": "❌ Код истёк. Начни добавление заново.",
        "acc_added": "✅ <b>Аккаунт добавлен!</b>\n\n👤 {name} {uname}\n📱 {phone}",
        "acc_deleted": "🗑 <b>Аккаунт {phone} удалён.</b>",
        "acc_info": "📱 <b>Аккаунт: {phone}</b>\n\nСтатус: {status}\nСессия: <code>{session}</code>",
        "acc_active": "✅ Активен",
        "acc_inactive": "❌ Не активен",
        "step1": "👤 <b>Шаг 1 из 3 — Выбор аккаунта</b>\n\nС какого аккаунта отправлять?",
        "step2": "✅ Аккаунт: <b>{phone}</b>\n\n✏️ <b>Шаг 2 из 3 — Тексты сообщений</b>\n\nВведи один или несколько вариантов текста.\nКаждый вариант — с новой строки.\n\n<i>Пример:</i>\n<code>Привет, как дела?\nХай, что нового?</code>",
        "step3": "✅ Сохранено <b>{count}</b> вариант(ов).\n\n👥 <b>Шаг 3 из 3 — Получатели</b>\n\nВведи юзернеймы, каждый с новой строки.\nСимвол @ не нужен.\n\n<i>Пример:</i>\n<code>username1\nusername2</code>",
        "confirm": "📋 <b>Подтверждение</b>\n\n📱 Аккаунт: <b>{phone}</b>\n✉️ Вариантов: <b>{msg_count}</b>\n{msgs}\n\n👥 Получателей: <b>{user_count}</b>\n{users}\n\nВсё верно?",
        "more_users": "• ...и ещё {n}",
        "cancelled": "❌ <b>Отменено.</b>",
        "mailing_start": "🚀 <b>Рассылка запущена!</b>\n\n📱 Аккаунт: <b>{phone}</b>\n👥 Получателей: <b>{count}</b>\n\n⏳ Подключаюсь к аккаунту...",
        "mailing_progress": "🚀 <b>Рассылка идёт...</b>\n\n[{bar}] {current}/{total}\n\n✅ Успешно: <b>{sent}</b>\n❌ Ошибки: <b>{failed}</b>",
        "mailing_pause": "⏸ <b>Пауза 2 минуты (анти-бан)</b>\n\n{current}/{total} | ✅ {sent} | ❌ {failed}",
        "mailing_done": "🎉 <b>Рассылка завершена!</b>\n\n👥 Всего: <b>{total}</b>\n✅ Успешно: <b>{sent}</b>\n❌ Ошибки: <b>{failed}</b>",
        "mailing_errors": "\n\n<b>Последние ошибки:</b>\n{errors}",
        "more_errors": "\n...и ещё {n}",
        "not_authorized": "❌ <b>Аккаунт не авторизован!</b>\n\nПереавторизуй аккаунт в разделе управления.",
        "connect_err": "❌ Ошибка подключения: <code>{err}</code>",
        "sub_expired_alert": "❌ Подписка истекла!",
        "acc_not_found": "❌ Аккаунт не найден.",
        "connecting": "⏳ Подключаюсь и отправляю код...",
        "phone_format_err": "⚠️ Введи номер с +, например: <code>+79991234567</code>",
        "wrong_pass": "❌ Неверный пароль: <code>{err}</code>",
        "session_expired": "❌ Сессия истекла. Начни заново.",
        "error": "❌ Ошибка: <code>{err}</code>",
        "payment_text": (
            "💳 <b>Оплата тарифа «{name}»</b>\n\n"
            "Сумма: <b>{amount} TON</b>\n\n"
            "Переведи точно <b>{amount} TON</b> на кошелёк:\n"
            "<code>{wallet}</code>\n\n"
            "📝 В комментарии к переводу обязательно укажи:\n"
            "<code>{comment}</code>\n\n"
            "⚠️ Без комментария платёж не будет найден!\n\n"
            "После оплаты нажми кнопку ниже 👇"
        ),
        "checking": "🔍 <b>Проверяю оплату...</b>\n\nЭто займёт несколько секунд.",
        "payment_ok": "🎉 <b>Оплата подтверждена!</b>\n\n✅ Тариф «{name}» активирован.\n\nПодписка: {sub}",
        "payment_fail": (
            "❌ <b>Платёж не найден</b>\n\n"
            "Возможные причины:\n"
            "• Перевод ещё не прошёл (подожди 1-2 мин)\n"
            "• Неверный комментарий к переводу\n"
            "• Неверная сумма\n\n"
            "Комментарий должен быть: <code>{comment}</code>\n"
            "Сумма: <b>{amount} TON</b>\n\n"
            "Попробуй нажать «Проверить снова» через минуту."
        ),
        "payment_err": "Ошибка. Попробуй заново.",
        "invalid_plan": "Неверный тариф.",
        "settings": "⚙️ <b>Настройки</b>\n\nВыбери язык интерфейса 👇",
        "lang_set": "✅ Язык изменён на Русский 🇷🇺",
        "btn_mailing": "🚀 Начать рассылку",
        "btn_manage": "👤 Управление аккаунтами",
        "btn_buy": "💎 Купить подписку",
        "btn_my_sub": "📊 Моя подписка",
        "btn_help": "ℹ️ Помощь",
        "btn_settings": "⚙️ Настройки",
        "btn_back": "◀️ Назад",
        "btn_paid": "✅ Я оплатил!",
        "btn_other_plan": "◀️ Выбрать другой тариф",
        "btn_check_again": "🔄 Проверить снова",
        "btn_change_plan": "◀️ Изменить тариф",
        "btn_cancel": "❌ Отмена",
        "btn_run": "✅ Запустить",
        "btn_edit": "✏️ Изменить",
        "btn_add_acc": "➕ Добавить аккаунт",
        "btn_del_acc": "🗑 Удалить аккаунт",
        "btn_buy_sub": "💎 Купить подписку",
        "no_text": "⚠️ Введи хотя бы один текст.",
        "no_users": "⚠️ Введи хотя бы один юзернейм.",
        # Промокоды
        "enter_promo": "🎟 Введи промокод:",
        "promo_ok": "🎉 <b>Промокод активирован!</b>\n\n✅ Тариф «{name}» активирован.\n\nПодписка: {sub}",
        "promo_invalid": "❌ Неверный или уже использованный промокод.",
        "promo_expired": "❌ Срок действия промокода истёк.",
        "promo_used_up": "❌ Промокод уже исчерпан.",
        "btn_promo": "🎟 Ввести промокод",
        # Админ
        "not_admin": "⛔ У тебя нет доступа к этому разделу.",
        "admin_panel": (
            "🛠 <b>Админ-панель</b>\n\n"
            "👥 Всего пользователей: <b>{total}</b>\n"
            "✅ Активных подписок: <b>{active}</b>\n"
            "❌ Без подписки: <b>{inactive}</b>\n\n"
            "Выбери действие 👇"
        ),
        "admin_users_list": "👥 <b>Список пользователей</b> (стр. {page}/{pages}):\n\n{users}",
        "admin_user_info": (
            "👤 <b>Пользователь {user_id}</b>\n"
            "📛 Имя: {name}\n"
            "🌐 Язык: {lang}\n"
            "📊 Подписка: {sub}\n"
            "🗓 Аккаунтов: {acc_count}"
        ),
        "admin_sub_given": "✅ Подписка «{plan}» выдана пользователю {user_id}.",
        "admin_promo_created": "✅ Промокод <code>{code}</code> создан.\nТариф: {plan}\nИспользований: {uses}",
        "admin_promo_deleted": "🗑 Промокод {code} удалён.",
        "admin_promos_list": "🎟 <b>Промокоды:</b>\n\n{promos}",
        "admin_no_promos": "Промокодов нет.",
        "admin_enter_uid": "Введи Telegram ID пользователя:",
        "admin_uid_invalid": "❌ Неверный ID. Введи число.",
        "admin_user_not_found": "❌ Пользователь не найден.",
        "admin_choose_plan": "Выбери тариф для выдачи:",
        "admin_enter_promo_code": "Введи текст промокода (латинские буквы/цифры):",
        "admin_enter_promo_uses": "Сколько раз можно использовать? (0 = безлимит):",
        "admin_enter_promo_plan": "Выбери тариф для промокода:",
        "admin_broadcast_enter": "Введи текст для рассылки всем пользователям:",
        "admin_broadcast_done": "📢 Рассылка завершена. Отправлено: {sent}, ошибок: {failed}.",
        "btn_admin": "🛠 Админ-панель",
        "btn_admin_users": "👥 Пользователи",
        "btn_admin_give_sub": "🎁 Выдать подписку",
        "btn_admin_promos": "🎟 Промокоды",
        "btn_admin_new_promo": "➕ Новый промокод",
        "btn_admin_broadcast": "📢 Рассылка",
        "btn_admin_del_promo": "🗑 Удалить",
        "btn_prev": "◀️",
        "btn_next": "▶️",
        # Реферальная система
        "referral_info": (
            "👥 <b>Реферальная программа</b>\n\n"
            "Приглашай друзей — получай бесплатные дни!\n\n"
            "🔗 Твоя реферальная ссылка:\n<code>{link}</code>\n\n"
            "👤 Приглашено: <b>{count}</b> друзей\n"
            "🎁 Заработано бонусов: <b>{bonus}</b> дней\n\n"
            "За каждого приглашённого друга, купившего подписку — <b>+3 дня</b> тебе!"
        ),
        "referral_bonus": "🎉 Твой друг купил подписку! Тебе начислено <b>+3 дня</b> подписки.",
        "btn_referral": "👥 Реферальная программа",
        # Статистика рассылок
        "my_stats": (
            "📈 <b>Твоя статистика</b>\n\n"
            "🚀 Рассылок запущено: <b>{total_mailings}</b>\n"
            "✉️ Сообщений отправлено: <b>{total_sent}</b>\n"
            "❌ Ошибок всего: <b>{total_failed}</b>\n"
            "📊 Успешность: <b>{rate}%</b>"
        ),
        "btn_my_stats": "📈 Моя статистика",
        # Уведомление об истечении подписки
        "sub_expiry_warn": "⚠️ <b>Подписка истекает через {hours} часов!</b>\n\nПродли сейчас 👇",
    },
    "en": {
        "welcome": "👋 <b>Smart Sender Bot</b>\n\nSmart Telegram mailing with anti-ban protection.\n\n📊 Subscription: {sub}\n\nChoose an action 👇",
        "sub_forever": "✅ Forever",
        "sub_active": "✅ Active for {days}d {hours}h",
        "sub_expired": "❌ Expired",
        "sub_none": "❌ No subscription",
        "my_sub": "📊 <b>Your subscription</b>\n\nStatus: {sub}",
        "buy_sub": "💎 <b>Choose a plan</b>\n\nTap the plan you want 👇",
        "secret_already": "✅ <b>You already have free forever access!</b>",
        "secret_ok": "🎁 <b>Secret code accepted!</b>\n\n✅ You got free access <b>forever</b>!\n\nChoose an action 👇",
        "need_sub": "❌ Active subscription required!",
        "help": (
            "📖 <b>Instructions:</b>\n\n"
            "1️⃣ Buy a subscription via the menu\n"
            "2️⃣ Go to <b>Account Management</b>\n"
            "3️⃣ Add an account via phone number\n"
            "4️⃣ Enter the Telegram code <b>digit by digit with spaces</b>:\n"
            "   <code>1 2 3 4 5</code>\n"
            "5️⃣ Press <b>Start Mailing</b>\n"
            "6️⃣ Choose account, enter texts and usernames\n\n"
            "⚙️ <b>Anti-ban:</b>\n"
            "• 1.5–3.5 sec delay between messages\n"
            "• 2 min pause every 20 messages\n"
            "• Random text selection\n\n"
            "💳 <b>Payment:</b>\n"
            "• Send exact TON amount\n"
            "• Always include the comment\n"
            "• Press 'I paid' after transfer"
        ),
        "manage_acc": "👤 <b>Account Management</b>\n\nAccounts added: <b>{count}</b>\n\nSelect an account or add a new one 👇",
        "no_active_acc": "⚠️ <b>No active accounts!</b>\n\nPlease add an account first.",
        "add_acc": "📱 <b>Add Account</b>\n\nEnter phone number in format:\n<code>+79991234567</code>",
        "code_sent": "📨 <b>Code sent!</b>\n\nEnter the Telegram code <b>digit by digit with spaces</b>:\n<code>1 2 3 4 5</code>",
        "code_format_err": "⚠️ <b>Wrong code format!</b>\n\nEnter the code <b>digit by digit with spaces</b>:\n<code>1 2 3 4 5</code>\n\nEach digit separately!",
        "need_2fa": "🔐 <b>2FA password required</b>\n\nEnter your cloud password:",
        "wrong_code": "❌ Wrong code. Try again:",
        "code_expired": "❌ Code expired. Start adding the account again.",
        "acc_added": "✅ <b>Account added!</b>\n\n👤 {name} {uname}\n📱 {phone}",
        "acc_deleted": "🗑 <b>Account {phone} deleted.</b>",
        "acc_info": "📱 <b>Account: {phone}</b>\n\nStatus: {status}\nSession: <code>{session}</code>",
        "acc_active": "✅ Active",
        "acc_inactive": "❌ Inactive",
        "step1": "👤 <b>Step 1 of 3 — Choose Account</b>\n\nWhich account to send from?",
        "step2": "✅ Account: <b>{phone}</b>\n\n✏️ <b>Step 2 of 3 — Message Texts</b>\n\nEnter one or more message variants.\nEach variant on a new line.\n\n<i>Example:</i>\n<code>Hey, how are you?\nHi, what's new?</code>",
        "step3": "✅ Saved <b>{count}</b> variant(s).\n\n👥 <b>Step 3 of 3 — Recipients</b>\n\nEnter usernames, one per line.\nNo @ needed.\n\n<i>Example:</i>\n<code>username1\nusername2</code>",
        "confirm": "📋 <b>Confirmation</b>\n\n📱 Account: <b>{phone}</b>\n✉️ Variants: <b>{msg_count}</b>\n{msgs}\n\n👥 Recipients: <b>{user_count}</b>\n{users}\n\nEverything correct?",
        "more_users": "• ...and {n} more",
        "cancelled": "❌ <b>Cancelled.</b>",
        "mailing_start": "🚀 <b>Mailing started!</b>\n\n📱 Account: <b>{phone}</b>\n👥 Recipients: <b>{count}</b>\n\n⏳ Connecting to account...",
        "mailing_progress": "🚀 <b>Mailing in progress...</b>\n\n[{bar}] {current}/{total}\n\n✅ Sent: <b>{sent}</b>\n❌ Errors: <b>{failed}</b>",
        "mailing_pause": "⏸ <b>2 minute pause (anti-ban)</b>\n\n{current}/{total} | ✅ {sent} | ❌ {failed}",
        "mailing_done": "🎉 <b>Mailing completed!</b>\n\n👥 Total: <b>{total}</b>\n✅ Sent: <b>{sent}</b>\n❌ Errors: <b>{failed}</b>",
        "mailing_errors": "\n\n<b>Last errors:</b>\n{errors}",
        "more_errors": "\n...and {n} more",
        "not_authorized": "❌ <b>Account not authorized!</b>\n\nRe-authorize the account in management.",
        "connect_err": "❌ Connection error: <code>{err}</code>",
        "sub_expired_alert": "❌ Subscription expired!",
        "acc_not_found": "❌ Account not found.",
        "connecting": "⏳ Connecting and sending code...",
        "phone_format_err": "⚠️ Enter number with +, for example: <code>+79991234567</code>",
        "wrong_pass": "❌ Wrong password: <code>{err}</code>",
        "session_expired": "❌ Session expired. Start again.",
        "error": "❌ Error: <code>{err}</code>",
        "payment_text": (
            "💳 <b>Payment for «{name}» plan</b>\n\n"
            "Amount: <b>{amount} TON</b>\n\n"
            "Send exactly <b>{amount} TON</b> to wallet:\n"
            "<code>{wallet}</code>\n\n"
            "📝 In the transfer comment write:\n"
            "<code>{comment}</code>\n\n"
            "⚠️ Without the comment the payment won't be found!\n\n"
            "After payment press the button below 👇"
        ),
        "checking": "🔍 <b>Checking payment...</b>\n\nThis will take a few seconds.",
        "payment_ok": "🎉 <b>Payment confirmed!</b>\n\n✅ Plan «{name}» activated.\n\nSubscription: {sub}",
        "payment_fail": (
            "❌ <b>Payment not found</b>\n\n"
            "Possible reasons:\n"
            "• Transfer not processed yet (wait 1-2 min)\n"
            "• Wrong comment in transfer\n"
            "• Wrong amount\n\n"
            "Comment must be: <code>{comment}</code>\n"
            "Amount: <b>{amount} TON</b>\n\n"
            "Try pressing 'Check again' in a minute."
        ),
        "payment_err": "Error. Try again.",
        "invalid_plan": "Invalid plan.",
        "settings": "⚙️ <b>Settings</b>\n\nChoose interface language 👇",
        "lang_set": "✅ Language changed to English 🇬🇧",
        "btn_mailing": "🚀 Start Mailing",
        "btn_manage": "👤 Account Management",
        "btn_buy": "💎 Buy Subscription",
        "btn_my_sub": "📊 My Subscription",
        "btn_help": "ℹ️ Help",
        "btn_settings": "⚙️ Settings",
        "btn_back": "◀️ Back",
        "btn_paid": "✅ I paid!",
        "btn_other_plan": "◀️ Choose another plan",
        "btn_check_again": "🔄 Check again",
        "btn_change_plan": "◀️ Change plan",
        "btn_cancel": "❌ Cancel",
        "btn_run": "✅ Launch",
        "btn_edit": "✏️ Edit",
        "btn_add_acc": "➕ Add Account",
        "btn_del_acc": "🗑 Delete Account",
        "btn_buy_sub": "💎 Buy Subscription",
        "no_text": "⚠️ Enter at least one text.",
        "no_users": "⚠️ Enter at least one username.",
        # Promo codes
        "enter_promo": "🎟 Enter promo code:",
        "promo_ok": "🎉 <b>Promo code activated!</b>\n\n✅ Plan «{name}» activated.\n\nSubscription: {sub}",
        "promo_invalid": "❌ Invalid or already used promo code.",
        "promo_expired": "❌ Promo code has expired.",
        "promo_used_up": "❌ Promo code has been fully used.",
        "btn_promo": "🎟 Enter promo code",
        # Admin
        "not_admin": "⛔ You don't have access to this section.",
        "admin_panel": (
            "🛠 <b>Admin Panel</b>\n\n"
            "👥 Total users: <b>{total}</b>\n"
            "✅ Active subscriptions: <b>{active}</b>\n"
            "❌ No subscription: <b>{inactive}</b>\n\n"
            "Choose action 👇"
        ),
        "admin_users_list": "👥 <b>Users list</b> (page {page}/{pages}):\n\n{users}",
        "admin_user_info": (
            "👤 <b>User {user_id}</b>\n"
            "📛 Name: {name}\n"
            "🌐 Language: {lang}\n"
            "📊 Subscription: {sub}\n"
            "🗓 Accounts: {acc_count}"
        ),
        "admin_sub_given": "✅ Subscription «{plan}» granted to user {user_id}.",
        "admin_promo_created": "✅ Promo code <code>{code}</code> created.\nPlan: {plan}\nUses: {uses}",
        "admin_promo_deleted": "🗑 Promo code {code} deleted.",
        "admin_promos_list": "🎟 <b>Promo codes:</b>\n\n{promos}",
        "admin_no_promos": "No promo codes.",
        "admin_enter_uid": "Enter user Telegram ID:",
        "admin_uid_invalid": "❌ Invalid ID. Enter a number.",
        "admin_user_not_found": "❌ User not found.",
        "admin_choose_plan": "Choose plan to grant:",
        "admin_enter_promo_code": "Enter promo code text (latin letters/digits):",
        "admin_enter_promo_uses": "How many times can it be used? (0 = unlimited):",
        "admin_enter_promo_plan": "Choose plan for this promo code:",
        "admin_broadcast_enter": "Enter text to broadcast to all users:",
        "admin_broadcast_done": "📢 Broadcast done. Sent: {sent}, errors: {failed}.",
        "btn_admin": "🛠 Admin Panel",
        "btn_admin_users": "👥 Users",
        "btn_admin_give_sub": "🎁 Grant subscription",
        "btn_admin_promos": "🎟 Promo codes",
        "btn_admin_new_promo": "➕ New promo code",
        "btn_admin_broadcast": "📢 Broadcast",
        "btn_admin_del_promo": "🗑 Delete",
        "btn_prev": "◀️",
        "btn_next": "▶️",
        # Referral system
        "referral_info": (
            "👥 <b>Referral Program</b>\n\n"
            "Invite friends — get free days!\n\n"
            "🔗 Your referral link:\n<code>{link}</code>\n\n"
            "👤 Invited: <b>{count}</b> friends\n"
            "🎁 Bonuses earned: <b>{bonus}</b> days\n\n"
            "For every friend who buys a subscription — <b>+3 days</b> for you!"
        ),
        "referral_bonus": "🎉 Your friend bought a subscription! You received <b>+3 days</b>.",
        "btn_referral": "👥 Referral Program",
        # Mailing stats
        "my_stats": (
            "📈 <b>Your Statistics</b>\n\n"
            "🚀 Mailings launched: <b>{total_mailings}</b>\n"
            "✉️ Messages sent: <b>{total_sent}</b>\n"
            "❌ Total errors: <b>{total_failed}</b>\n"
            "📊 Success rate: <b>{rate}%</b>"
        ),
        "btn_my_stats": "📈 My Statistics",
        # Subscription expiry warning
        "sub_expiry_warn": "⚠️ <b>Subscription expires in {hours} hours!</b>\n\nRenew now 👇",
    }
}

def t(user_id: int, key: str, **kwargs) -> str:
    lang = get_user_lang(user_id)
    text = TEXTS.get(lang, TEXTS["uk"]).get(key, key)
    if kwargs:
        text = text.format(**kwargs)
    return text

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
    # Зберігаємо мову якщо вона є
    existing = users.get(str(user_id), {})
    if "lang" in existing and "lang" not in data:
        data["lang"] = existing["lang"]
    users[str(user_id)] = data
    save_users(users)


def get_user_lang(user_id: int) -> str:
    return get_user(user_id).get("lang", "uk")


def set_user_lang(user_id: int, lang: str):
    users = load_users()
    if str(user_id) not in users:
        users[str(user_id)] = {}
    users[str(user_id)]["lang"] = lang
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
    if not user or "expires" not in user:
        return t(user_id, "sub_none")
    expires = user.get("expires")
    if expires == -1:
        return t(user_id, "sub_forever")
    if expires and time.time() < expires:
        remaining = int(expires - time.time())
        days = remaining // 86400
        hours = (remaining % 86400) // 3600
        return t(user_id, "sub_active", days=days, hours=hours)
    return t(user_id, "sub_expired")


def activate_subscription(user_id: int, plan_key: str):
    plan = PLANS[plan_key]
    days = plan["days"]
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

    lang = user.get("lang", "uk")
    set_user(user_id, {"expires": expires, "plan": plan[lang], "lang": lang})


# ─── ПРОМОКОДИ ───────────────────────────────────────────────
def load_promos() -> dict:
    if os.path.exists(PROMO_FILE):
        with open(PROMO_FILE, "r") as f:
            return json.load(f)
    return {}


def save_promos(promos: dict):
    with open(PROMO_FILE, "w") as f:
        json.dump(promos, f, ensure_ascii=False, indent=2)


def create_promo(code: str, plan_key: str, max_uses: int = 1, expires_ts: float = 0) -> dict:
    """Create a new promo code. max_uses=0 means unlimited."""
    promos = load_promos()
    promo = {
        "plan": plan_key,
        "max_uses": max_uses,
        "used_count": 0,
        "used_by": [],
        "expires": expires_ts,  # 0 = no expiry
        "created": time.time()
    }
    promos[code.upper()] = promo
    save_promos(promos)
    return promo


def use_promo(user_id: int, code: str):
    """
    Try to apply a promo code for user_id.
    Returns (True, plan_key) on success or (False, reason_key) on failure.
    """
    promos = load_promos()
    code = code.upper().strip()
    promo = promos.get(code)
    if not promo:
        return False, "promo_invalid"
    # Check expiry
    if promo["expires"] and time.time() > promo["expires"]:
        return False, "promo_expired"
    # Check max uses
    if promo["max_uses"] > 0 and promo["used_count"] >= promo["max_uses"]:
        return False, "promo_used_up"
    # Check if already used by this user
    if user_id in promo["used_by"]:
        return False, "promo_invalid"
    # Apply
    promo["used_count"] += 1
    promo["used_by"].append(user_id)
    save_promos(promos)
    return True, promo["plan"]


# ─── СТАТИСТИКА РОЗСИЛОК ─────────────────────────────────────
def load_stats() -> dict:
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_stats(stats: dict):
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


def record_mailing_result(user_id: int, sent: int, failed: int):
    stats = load_stats()
    uid_str = str(user_id)
    if uid_str not in stats:
        stats[uid_str] = {"mailings": 0, "sent": 0, "failed": 0}
    stats[uid_str]["mailings"] += 1
    stats[uid_str]["sent"] += sent
    stats[uid_str]["failed"] += failed
    save_stats(stats)


def get_user_stats(user_id: int) -> dict:
    stats = load_stats()
    return stats.get(str(user_id), {"mailings": 0, "sent": 0, "failed": 0})


# ─── РЕФЕРАЛЬНА СИСТЕМА ──────────────────────────────────────
def get_referrer(user_id: int) -> int | None:
    """Returns referrer user_id if this user was invited by someone."""
    user = get_user(user_id)
    return user.get("referrer")


def set_referrer(user_id: int, referrer_id: int):
    users = load_users()
    uid_str = str(user_id)
    if uid_str not in users:
        users[uid_str] = {}
    if "referrer" not in users[uid_str]:
        users[uid_str]["referrer"] = referrer_id
        # Increment referrer's invited count
        ref_str = str(referrer_id)
        if ref_str in users:
            users[ref_str]["ref_count"] = users[ref_str].get("ref_count", 0) + 1
    save_users(users)


def add_referral_bonus(referrer_id: int):
    """Add 3 bonus days to referrer when their invited user buys a subscription."""
    users = load_users()
    ref_str = str(referrer_id)
    if ref_str not in users:
        return
    now = time.time()
    current = users[ref_str].get("expires", now)
    if current == -1:
        return  # Already forever
    bonus_days = 3
    if current and current > now:
        users[ref_str]["expires"] = current + bonus_days * 86400
    else:
        users[ref_str]["expires"] = now + bonus_days * 86400
    users[ref_str]["ref_bonus_days"] = users[ref_str].get("ref_bonus_days", 0) + bonus_days
    save_users(users)


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
    url = "https://toncenter.com/api/v2/getTransactions"
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


class PromoInput(StatesGroup):
    entering_code = State()


class AdminGiveSub(StatesGroup):
    entering_uid = State()
    choosing_plan = State()


class AdminCreatePromo(StatesGroup):
    entering_code = State()
    entering_uses = State()
    choosing_plan = State()


class AdminBroadcast(StatesGroup):
    entering_text = State()


# ─── КЛАВІАТУРИ ──────────────────────────────────────────────
def main_menu_kb(user_id: int = None):
    kb = InlineKeyboardBuilder()
    if user_id and has_active_subscription(user_id):
        kb.button(text=t(user_id, "btn_mailing"), callback_data="start_mailing")
        kb.button(text=t(user_id, "btn_manage"), callback_data="manage_accounts")
    else:
        kb.button(text=t(user_id, "btn_buy"), callback_data="buy_sub")
        kb.button(text=t(user_id, "btn_promo"), callback_data="enter_promo")
    kb.button(text=t(user_id, "btn_my_sub"), callback_data="my_sub")
    kb.button(text=t(user_id, "btn_my_stats"), callback_data="my_stats")
    kb.button(text=t(user_id, "btn_referral"), callback_data="referral")
    kb.button(text=t(user_id, "btn_help"), callback_data="help")
    kb.button(text=t(user_id, "btn_settings"), callback_data="settings")
    if user_id and user_id in ADMIN_IDS:
        kb.button(text=t(user_id, "btn_admin"), callback_data="admin_panel")
    kb.adjust(1)
    return kb.as_markup()


def plans_kb(user_id: int = 0):
    lang = get_user_lang(user_id)
    kb = InlineKeyboardBuilder()
    for key, plan in PLANS.items():
        kb.button(text=f"{plan[lang]} — {plan['amount']} TON", callback_data=f"plan_{key}")
    kb.button(text=t(user_id, "btn_back"), callback_data="back_main")
    kb.adjust(1)
    return kb.as_markup()


def payment_kb(user_id: int, plan_key: str):
    kb = InlineKeyboardBuilder()
    kb.button(text=t(user_id, "btn_paid"), callback_data=f"paid_{plan_key}")
    kb.button(text=t(user_id, "btn_other_plan"), callback_data="buy_sub")
    kb.adjust(1)
    return kb.as_markup()


def accounts_manage_kb(user_id: int = 0):
    accounts = get_accounts(user_id)
    kb = InlineKeyboardBuilder()
    if accounts:
        for phone, info in accounts.items():
            status = "✅" if info.get("active") else "❌"
            kb.button(text=f"{status} {phone}", callback_data=f"acc_info_{phone}")
    kb.button(text=t(user_id, "btn_add_acc"), callback_data="add_account")
    kb.button(text=t(user_id, "btn_back"), callback_data="back_main")
    kb.adjust(1)
    return kb.as_markup()


def account_actions_kb(user_id: int, phone: str):
    kb = InlineKeyboardBuilder()
    kb.button(text=t(user_id, "btn_del_acc"), callback_data=f"del_acc_{phone}")
    kb.button(text=t(user_id, "btn_back"), callback_data="manage_accounts")
    kb.adjust(1)
    return kb.as_markup()


def choose_account_kb(user_id: int = 0):
    accounts = get_accounts(user_id)
    kb = InlineKeyboardBuilder()
    if accounts:
        for phone, info in accounts.items():
            if info.get("active"):
                kb.button(text=f"✅ {phone}", callback_data=f"pick_acc_{phone}")
    kb.button(text=t(user_id, "btn_back"), callback_data="back_main")
    kb.adjust(1)
    return kb.as_markup()


def cancel_kb(user_id: int = 0):
    kb = InlineKeyboardBuilder()
    kb.button(text=t(user_id, "btn_cancel"), callback_data="cancel")
    return kb.as_markup()


def confirm_kb(user_id: int = 0):
    kb = InlineKeyboardBuilder()
    kb.button(text=t(user_id, "btn_run"), callback_data="run")
    kb.button(text=t(user_id, "btn_edit"), callback_data="start_mailing")
    kb.button(text=t(user_id, "btn_cancel"), callback_data="cancel")
    kb.adjust(2, 1)
    return kb.as_markup()


def lang_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🇺🇦 Українська", callback_data="setlang_uk")
    kb.button(text="🇷🇺 Русский",    callback_data="setlang_ru")
    kb.button(text="🇬🇧 English",    callback_data="setlang_en")
    kb.adjust(1)
    return kb.as_markup()


def admin_panel_kb(user_id: int):
    kb = InlineKeyboardBuilder()
    kb.button(text=t(user_id, "btn_admin_users"),    callback_data="admin_users_0")
    kb.button(text=t(user_id, "btn_admin_give_sub"), callback_data="admin_give_sub")
    kb.button(text=t(user_id, "btn_admin_promos"),   callback_data="admin_promos")
    kb.button(text=t(user_id, "btn_admin_broadcast"),callback_data="admin_broadcast")
    kb.button(text=t(user_id, "btn_back"),           callback_data="back_main")
    kb.adjust(1)
    return kb.as_markup()


def admin_plans_kb(user_id: int, prefix: str):
    """Plans keyboard for admin actions (prefix used as callback prefix)."""
    lang = get_user_lang(user_id)
    kb = InlineKeyboardBuilder()
    for key, plan in PLANS.items():
        kb.button(text=f"{plan[lang]} — {plan['amount']} TON", callback_data=f"{prefix}{key}")
    kb.button(text=t(user_id, "btn_back"), callback_data="admin_panel")
    kb.adjust(1)
    return kb.as_markup()


def admin_promos_kb(user_id: int):
    promos = load_promos()
    kb = InlineKeyboardBuilder()
    for code, info in promos.items():
        uses_str = f"{info['used_count']}/{'∞' if info['max_uses']==0 else info['max_uses']}"
        kb.button(text=f"🎟 {code} [{uses_str}]", callback_data=f"admin_del_promo_{code}")
    kb.button(text=t(user_id, "btn_admin_new_promo"), callback_data="admin_new_promo")
    kb.button(text=t(user_id, "btn_back"), callback_data="admin_panel")
    kb.adjust(1)
    return kb.as_markup()


def admin_users_nav_kb(user_id: int, page: int, total_pages: int):
    kb = InlineKeyboardBuilder()
    nav = []
    if page > 0:
        nav.append(kb.button(text=t(user_id, "btn_prev"), callback_data=f"admin_users_{page-1}"))
    if page < total_pages - 1:
        nav.append(kb.button(text=t(user_id, "btn_next"), callback_data=f"admin_users_{page+1}"))
    kb.button(text=t(user_id, "btn_back"), callback_data="admin_panel")
    kb.adjust(2, 1)
    return kb.as_markup()


# ─── /start ──────────────────────────────────────────────────
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    # Зберігаємо ім'я користувача
    users = load_users()
    uid_str = str(user_id)
    if uid_str not in users:
        users[uid_str] = {}
    name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()
    users[uid_str]["name"] = name or "—"
    if "lang" not in users[uid_str]:
        users[uid_str]["lang"] = "uk"
    save_users(users)

    # Обробка реферального посилання /start ref_12345678
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1].replace("ref_", ""))
            if referrer_id != user_id:
                set_referrer(user_id, referrer_id)
        except ValueError:
            pass

    sub_text = get_subscription_text(user_id)
    await message.answer(
        t(user_id, "welcome", sub=sub_text),
        parse_mode="HTML",
        reply_markup=main_menu_kb(user_id)
    )


# ─── НАЛАШТУВАННЯ / МОВА ─────────────────────────────────────
@dp.callback_query(F.data == "settings")
async def cb_settings(call: CallbackQuery):
    await call.message.edit_text(
        t(call.from_user.id, "settings"),
        parse_mode="HTML",
        reply_markup=lang_kb()
    )


@dp.callback_query(F.data.startswith("setlang_"))
async def cb_setlang(call: CallbackQuery):
    lang = call.data.replace("setlang_", "")
    user_id = call.from_user.id
    set_user_lang(user_id, lang)
    await call.message.edit_text(
        t(user_id, "lang_set"),
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
        kb.button(text=t(user_id, "btn_buy_sub"), callback_data="buy_sub")
    kb.button(text=t(user_id, "btn_back"), callback_data="back_main")
    kb.adjust(1)
    await call.message.edit_text(
        t(user_id, "my_sub", sub=sub_text),
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )


# ─── КУПІВЛЯ ПІДПИСКИ ────────────────────────────────────────
@dp.callback_query(F.data == "buy_sub")
async def cb_buy_sub(call: CallbackQuery):
    user_id = call.from_user.id
    await call.message.edit_text(
        t(user_id, "buy_sub"),
        parse_mode="HTML",
        reply_markup=plans_kb(user_id)
    )


@dp.callback_query(F.data.startswith("plan_"))
async def cb_plan(call: CallbackQuery, state: FSMContext):
    plan_key = call.data.replace("plan_", "")
    user_id = call.from_user.id
    if plan_key not in PLANS:
        await call.answer(t(user_id, "invalid_plan"))
        return

    plan = PLANS[plan_key]
    lang = get_user_lang(user_id)
    amount = plan["amount"]
    name = plan[lang]
    comment = f"sub{user_id}{plan_key}"

    await state.set_state(Payment.waiting_confirm)
    await state.update_data(plan_key=plan_key, comment=comment, amount=amount)

    await call.message.edit_text(
        t(user_id, "payment_text", name=name, amount=amount, wallet=TON_WALLET, comment=comment),
        parse_mode="HTML",
        reply_markup=payment_kb(user_id, plan_key)
    )


@dp.callback_query(F.data.startswith("paid_"), Payment.waiting_confirm)
async def cb_paid(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    data = await state.get_data()
    plan_key = data.get("plan_key")
    comment = data.get("comment")
    amount = data.get("amount")

    if not plan_key or not comment:
        await call.answer(t(user_id, "payment_err"))
        await state.clear()
        return

    await call.message.edit_text(t(user_id, "checking"), parse_mode="HTML")

    found = await check_ton_payment(float(amount), comment)

    if found:
        activate_subscription(user_id, plan_key)
        lang = get_user_lang(user_id)
        name = PLANS[plan_key][lang]
        # Нараховуємо бонус реферреру
        referrer_id = get_referrer(user_id)
        if referrer_id:
            add_referral_bonus(referrer_id)
            try:
                await bot.send_message(referrer_id, t(referrer_id, "referral_bonus"), parse_mode="HTML")
            except Exception:
                pass
        await state.clear()
        await call.message.edit_text(
            t(user_id, "payment_ok", name=name, sub=get_subscription_text(user_id)),
            parse_mode="HTML",
            reply_markup=main_menu_kb(user_id)
        )
    else:
        kb = InlineKeyboardBuilder()
        kb.button(text=t(user_id, "btn_check_again"), callback_data=f"paid_{plan_key}")
        kb.button(text=t(user_id, "btn_change_plan"), callback_data="buy_sub")
        kb.adjust(1)
        await call.message.edit_text(
            t(user_id, "payment_fail", comment=comment, amount=amount),
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )


# ─── ДОПОМОГА ────────────────────────────────────────────────
@dp.callback_query(F.data == "help")
async def cb_help(call: CallbackQuery):
    user_id = call.from_user.id
    kb = InlineKeyboardBuilder()
    kb.button(text=t(user_id, "btn_back"), callback_data="back_main")
    await call.message.edit_text(
        t(user_id, "help"),
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )


@dp.callback_query(F.data == "back_main")
async def cb_back_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = call.from_user.id
    sub_text = get_subscription_text(user_id)
    await call.message.edit_text(
        t(user_id, "welcome", sub=sub_text),
        parse_mode="HTML",
        reply_markup=main_menu_kb(user_id)
    )


# ─── УПРАВЛІННЯ АКАУНТАМИ ─────────────────────────────────────
@dp.callback_query(F.data == "manage_accounts")
async def cb_manage_accounts(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not has_active_subscription(user_id):
        await call.answer(t(user_id, "need_sub"), show_alert=True)
        return
    await state.clear()
    accounts = get_accounts(user_id)
    count = len(accounts)
    await call.message.edit_text(
        t(user_id, "manage_acc", count=count),
        parse_mode="HTML",
        reply_markup=accounts_manage_kb(user_id)
    )


@dp.callback_query(F.data.startswith("acc_info_"))
async def cb_acc_info(call: CallbackQuery):
    user_id = call.from_user.id
    phone = call.data.replace("acc_info_", "")
    accounts = get_accounts(user_id)
    info = accounts.get(phone, {})
    status = t(user_id, "acc_active") if info.get("active") else t(user_id, "acc_inactive")
    await call.message.edit_text(
        t(user_id, "acc_info", phone=phone, status=status, session=info.get("session", "—")),
        parse_mode="HTML",
        reply_markup=account_actions_kb(user_id, phone)
    )


@dp.callback_query(F.data.startswith("del_acc_"))
async def cb_del_acc(call: CallbackQuery):
    user_id = call.from_user.id
    phone = call.data.replace("del_acc_", "")
    accounts = get_accounts(user_id)
    session_file = accounts.get(phone, {}).get("session", "")
    if phone in accounts:
        del accounts[phone]
        save_accounts(user_id, accounts)
    for ext in [".session", ".session-journal"]:
        if os.path.exists(session_file + ext):
            os.remove(session_file + ext)
    kb = InlineKeyboardBuilder()
    kb.button(text=t(user_id, "btn_back"), callback_data="manage_accounts")
    await call.message.edit_text(
        t(user_id, "acc_deleted", phone=phone),
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )


# ─── ДОДАВАННЯ АКАУНТУ ───────────────────────────────────────
@dp.callback_query(F.data == "add_account")
async def cb_add_account(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not has_active_subscription(user_id):
        await call.answer(t(user_id, "need_sub"), show_alert=True)
        return
    await state.set_state(AddAccount.entering_phone)
    await call.message.edit_text(
        t(user_id, "add_acc"),
        parse_mode="HTML",
        reply_markup=cancel_kb(user_id)
    )


@dp.message(AddAccount.entering_phone)
async def step_phone(message: Message, state: FSMContext):
    user_id = message.from_user.id
    phone = message.text.strip()
    if not phone.startswith("+"):
        await message.answer(t(user_id, "phone_format_err"), parse_mode="HTML")
        return

    session_name = f"session_{phone.replace('+', '').replace(' ', '')}_{user_id}"
    client = TelegramClient(session_name, DEFAULT_API_ID, DEFAULT_API_HASH)
    auth_clients[user_id] = {"client": client, "phone": phone, "session": session_name}

    await message.answer(t(user_id, "connecting"))

    try:
        await client.connect()
        result = await client.send_code_request(phone)
        auth_clients[user_id]["phone_code_hash"] = result.phone_code_hash
        await state.update_data(phone=phone, session=session_name)
        await state.set_state(AddAccount.entering_code)
        await message.answer(
            t(user_id, "code_sent"),
            parse_mode="HTML",
            reply_markup=cancel_kb(user_id)
        )
    except Exception as e:
        await client.disconnect()
        del auth_clients[user_id]
        await message.answer(t(user_id, "error", err=e), parse_mode="HTML", reply_markup=main_menu_kb(user_id))
        await state.clear()


@dp.message(AddAccount.entering_code)
async def step_code(message: Message, state: FSMContext):
    user_id = message.from_user.id
    raw = message.text.strip()

    parts = raw.split()
    if not all(p.isdigit() and len(p) == 1 for p in parts) or len(parts) < 4:
        await message.answer(
            t(user_id, "code_format_err"),
            parse_mode="HTML",
            reply_markup=cancel_kb(user_id)
        )
        return

    code = "".join(parts)

    if user_id not in auth_clients:
        await state.clear()
        await message.answer(t(user_id, "session_expired"), reply_markup=main_menu_kb(user_id))
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
        await message.answer(t(user_id, "need_2fa"), parse_mode="HTML", reply_markup=cancel_kb(user_id))
    except PhoneCodeInvalidError:
        await message.answer(t(user_id, "wrong_code"), reply_markup=cancel_kb(user_id))
    except PhoneCodeExpiredError:
        await client.disconnect()
        del auth_clients[user_id]
        await state.clear()
        await message.answer(t(user_id, "code_expired"), reply_markup=main_menu_kb(user_id))
    except Exception as e:
        await message.answer(t(user_id, "error", err=e), parse_mode="HTML", reply_markup=cancel_kb(user_id))


@dp.message(AddAccount.entering_2fa)
async def step_2fa(message: Message, state: FSMContext):
    user_id = message.from_user.id
    password = message.text.strip()

    if user_id not in auth_clients:
        await state.clear()
        await message.answer(t(user_id, "session_expired"), reply_markup=main_menu_kb(user_id))
        return

    auth_data = auth_clients[user_id]
    client: TelegramClient = auth_data["client"]

    try:
        await client.sign_in(password=password)
        await _finish_auth(message, state, user_id, auth_data["phone"], auth_data["session"])
    except Exception as e:
        await message.answer(t(user_id, "wrong_pass", err=e), parse_mode="HTML", reply_markup=cancel_kb(user_id))


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
        t(user_id, "acc_added", name=name, uname=uname, phone=phone),
        parse_mode="HTML",
        reply_markup=main_menu_kb(user_id)
    )


# ─── РОЗСИЛКА — КРОК 1 ───────────────────────────────────────
@dp.callback_query(F.data == "start_mailing")
async def cb_start_mailing(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not has_active_subscription(user_id):
        await call.answer(t(user_id, "need_sub"), show_alert=True)
        return
    accounts = get_accounts(user_id)
    active = {p: i for p, i in accounts.items() if i.get("active")}
    if not active:
        kb = InlineKeyboardBuilder()
        kb.button(text=t(user_id, "btn_add_acc"), callback_data="add_account")
        kb.button(text=t(user_id, "btn_back"), callback_data="back_main")
        kb.adjust(1)
        await call.message.edit_text(
            t(user_id, "no_active_acc"),
            parse_mode="HTML",
            reply_markup=kb.as_markup()
        )
        return
    await state.set_state(Mailing.choosing_account)
    await call.message.edit_text(
        t(user_id, "step1"),
        parse_mode="HTML",
        reply_markup=choose_account_kb(user_id)
    )


@dp.callback_query(F.data.startswith("pick_acc_"), Mailing.choosing_account)
async def cb_pick_account(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    phone = call.data.replace("pick_acc_", "")
    await state.update_data(phone=phone)
    await state.set_state(Mailing.entering_messages)
    await call.message.edit_text(
        t(user_id, "step2", phone=phone),
        parse_mode="HTML",
        reply_markup=cancel_kb(user_id)
    )


# ─── КРОК 2 ──────────────────────────────────────────────────
@dp.message(Mailing.entering_messages)
async def step_messages(message: Message, state: FSMContext):
    user_id = message.from_user.id
    lines = [l.strip() for l in message.text.strip().splitlines() if l.strip()]
    if not lines:
        await message.answer(t(user_id, "no_text"), reply_markup=cancel_kb(user_id))
        return
    await state.update_data(messages=lines)
    await state.set_state(Mailing.entering_users)
    await message.answer(
        t(user_id, "step3", count=len(lines)),
        parse_mode="HTML",
        reply_markup=cancel_kb(user_id)
    )


# ─── КРОК 3 ──────────────────────────────────────────────────
@dp.message(Mailing.entering_users)
async def step_users(message: Message, state: FSMContext):
    user_id = message.from_user.id
    users = []
    for line in message.text.strip().splitlines():
        clean = line.replace("✅", "").replace("@", "").strip()
        if clean:
            users.append(clean)
    if not users:
        await message.answer(t(user_id, "no_users"), reply_markup=cancel_kb(user_id))
        return
    await state.update_data(users=users)
    data = await state.get_data()
    await state.set_state(Mailing.confirming)

    msgs_preview = "\n".join(f"• {m[:50]}{'...' if len(m) > 50 else ''}" for m in data["messages"])
    users_preview = "\n".join(f"• @{u}" for u in users[:5])
    if len(users) > 5:
        users_preview += "\n" + t(user_id, "more_users", n=len(users) - 5)

    await message.answer(
        t(user_id, "confirm",
          phone=data["phone"],
          msg_count=len(data["messages"]),
          msgs=msgs_preview,
          user_count=len(users),
          users=users_preview),
        parse_mode="HTML",
        reply_markup=confirm_kb(user_id)
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
    await call.message.edit_text(
        t(user_id, "cancelled"),
        parse_mode="HTML",
        reply_markup=main_menu_kb(user_id)
    )


# ─── ЗАПУСК РОЗСИЛКИ ─────────────────────────────────────────
@dp.callback_query(F.data == "run", Mailing.confirming)
async def cb_run(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not has_active_subscription(user_id):
        await call.answer(t(user_id, "sub_expired_alert"), show_alert=True)
        return

    data = await state.get_data()
    await state.clear()

    phone = data["phone"]
    accounts = get_accounts(user_id)
    acc = accounts.get(phone)
    if not acc:
        await call.message.edit_text(t(user_id, "acc_not_found"), reply_markup=main_menu_kb(user_id))
        return

    users = data["users"]
    messages = data["messages"]

    status_msg = await call.message.edit_text(
        t(user_id, "mailing_start", phone=phone, count=len(users)),
        parse_mode="HTML"
    )

    client = TelegramClient(acc["session"], DEFAULT_API_ID, DEFAULT_API_HASH)

    try:
        await client.connect()
        if not await client.is_user_authorized():
            await status_msg.edit_text(
                t(user_id, "not_authorized"),
                parse_mode="HTML",
                reply_markup=main_menu_kb(user_id)
            )
            await client.disconnect()
            return
    except Exception as e:
        await status_msg.edit_text(
            t(user_id, "connect_err", err=e),
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
            errors_log.append(f"@{user}: privacy")
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
                    t(user_id, "mailing_progress", bar=bar, current=i+1, total=len(users), sent=sent, failed=failed),
                    parse_mode="HTML"
                )
            except Exception:
                pass

        if (i + 1) % 20 == 0 and (i + 1) < len(users):
            try:
                await status_msg.edit_text(
                    t(user_id, "mailing_pause", current=i+1, total=len(users), sent=sent, failed=failed),
                    parse_mode="HTML"
                )
            except Exception:
                pass
            await asyncio.sleep(120)
        else:
            await asyncio.sleep(random.uniform(1.5, 3.5))

    await client.disconnect()

    # Записуємо статистику
    record_mailing_result(user_id, sent, failed)

    errors_text = ""
    if errors_log:
        errors_text = t(user_id, "mailing_errors", errors="\n".join(errors_log[-8:]))
        if len(errors_log) > 8:
            errors_text += t(user_id, "more_errors", n=len(errors_log) - 8)

    await status_msg.edit_text(
        t(user_id, "mailing_done", total=len(users), sent=sent, failed=failed) + errors_text,
        parse_mode="HTML",
        reply_markup=main_menu_kb(user_id)
    )


# ─── ПРОМОКОДИ (КОРИСТУВАЧ) ──────────────────────────────────
@dp.callback_query(F.data == "enter_promo")
async def cb_enter_promo(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    await state.set_state(PromoInput.entering_code)
    kb = InlineKeyboardBuilder()
    kb.button(text=t(user_id, "btn_cancel"), callback_data="cancel_promo")
    await call.message.edit_text(
        t(user_id, "enter_promo"),
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )


@dp.callback_query(F.data == "cancel_promo")
async def cb_cancel_promo(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = call.from_user.id
    sub_text = get_subscription_text(user_id)
    await call.message.edit_text(
        t(user_id, "welcome", sub=sub_text),
        parse_mode="HTML",
        reply_markup=main_menu_kb(user_id)
    )


@dp.message(PromoInput.entering_code)
async def step_promo_code(message: Message, state: FSMContext):
    user_id = message.from_user.id
    code = message.text.strip()
    ok, result = use_promo(user_id, code)
    if ok:
        plan_key = result
        activate_subscription(user_id, plan_key)
        lang = get_user_lang(user_id)
        name = PLANS[plan_key][lang]
        await state.clear()
        await message.answer(
            t(user_id, "promo_ok", name=name, sub=get_subscription_text(user_id)),
            parse_mode="HTML",
            reply_markup=main_menu_kb(user_id)
        )
    else:
        reason = result  # promo_invalid / promo_expired / promo_used_up
        await state.clear()
        await message.answer(
            t(user_id, reason),
            parse_mode="HTML",
            reply_markup=main_menu_kb(user_id)
        )


# ─── АДМІН-ПАНЕЛЬ ────────────────────────────────────────────
def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@dp.callback_query(F.data == "admin_panel")
async def cb_admin_panel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = call.from_user.id
    if not is_admin(user_id):
        await call.answer(t(user_id, "not_admin"), show_alert=True)
        return
    users = load_users()
    total = len(users)
    active = sum(1 for u in users.values() if has_active_subscription(int(list(users.keys())[list(users.values()).index(u)])))
    # recalculate properly
    active = 0
    for uid_str, udata in users.items():
        exp = udata.get("expires")
        if exp == -1 or (exp and time.time() < exp):
            active += 1
    inactive = total - active
    await call.message.edit_text(
        t(user_id, "admin_panel", total=total, active=active, inactive=inactive),
        parse_mode="HTML",
        reply_markup=admin_panel_kb(user_id)
    )


# ─── АДМІН: СПИСОК КОРИСТУВАЧІВ ──────────────────────────────
PAGE_SIZE = 10

@dp.callback_query(F.data.startswith("admin_users_"))
async def cb_admin_users(call: CallbackQuery):
    user_id = call.from_user.id
    if not is_admin(user_id):
        await call.answer(t(user_id, "not_admin"), show_alert=True)
        return
    page = int(call.data.replace("admin_users_", ""))
    users = load_users()
    all_accounts = load_all_accounts()
    uids = list(users.keys())
    total_pages = max(1, (len(uids) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    chunk = uids[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]

    lines = []
    for uid_str in chunk:
        udata = users[uid_str]
        exp = udata.get("expires")
        if exp == -1:
            sub_icon = "♾"
        elif exp and time.time() < exp:
            days_left = int((exp - time.time()) // 86400)
            sub_icon = f"✅{days_left}д"
        else:
            sub_icon = "❌"
        name = udata.get("name", "—")
        acc_count = len(all_accounts.get(uid_str, {}))
        lines.append(f"<code>{uid_str}</code> {sub_icon} 👤{name} 📱{acc_count}")

    text = t(user_id, "admin_users_list",
             page=page+1, pages=total_pages,
             users="\n".join(lines) if lines else "—")
    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_users_nav_kb(user_id, page, total_pages)
    )


# ─── АДМІН: ВИДАТИ ПІДПИСКУ ───────────────────────────────────
@dp.callback_query(F.data == "admin_give_sub")
async def cb_admin_give_sub(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not is_admin(user_id):
        await call.answer(t(user_id, "not_admin"), show_alert=True)
        return
    await state.set_state(AdminGiveSub.entering_uid)
    kb = InlineKeyboardBuilder()
    kb.button(text=t(user_id, "btn_back"), callback_data="admin_panel")
    await call.message.edit_text(
        t(user_id, "admin_enter_uid"),
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )


@dp.message(AdminGiveSub.entering_uid)
async def admin_give_sub_uid(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    raw = message.text.strip()
    if not raw.isdigit():
        await message.answer(t(user_id, "admin_uid_invalid"))
        return
    target_uid = int(raw)
    # Check user exists
    if not get_user(target_uid):
        await message.answer(t(user_id, "admin_user_not_found"))
        await state.clear()
        return
    await state.update_data(target_uid=target_uid)
    await state.set_state(AdminGiveSub.choosing_plan)
    await message.answer(
        t(user_id, "admin_choose_plan"),
        parse_mode="HTML",
        reply_markup=admin_plans_kb(user_id, "admin_givesub_plan_")
    )


@dp.callback_query(F.data.startswith("admin_givesub_plan_"), AdminGiveSub.choosing_plan)
async def admin_give_sub_plan(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not is_admin(user_id):
        await call.answer()
        return
    plan_key = call.data.replace("admin_givesub_plan_", "")
    data = await state.get_data()
    target_uid = data["target_uid"]
    activate_subscription(target_uid, plan_key)
    lang = get_user_lang(user_id)
    plan_name = PLANS[plan_key][lang]
    await state.clear()
    await call.message.edit_text(
        t(user_id, "admin_sub_given", plan=plan_name, user_id=target_uid),
        parse_mode="HTML",
        reply_markup=admin_panel_kb(user_id)
    )
    # Notify the user
    try:
        await bot.send_message(
            target_uid,
            f"🎁 Вам видана підписка «{plan_name}»!\n\nПідписка: {get_subscription_text(target_uid)}"
        )
    except Exception:
        pass


# ─── АДМІН: ПРОМОКОДИ ─────────────────────────────────────────
@dp.callback_query(F.data == "admin_promos")
async def cb_admin_promos(call: CallbackQuery):
    user_id = call.from_user.id
    if not is_admin(user_id):
        await call.answer(t(user_id, "not_admin"), show_alert=True)
        return
    promos = load_promos()
    if promos:
        lines = []
        for code, info in promos.items():
            uses_str = f"{info['used_count']}/{'∞' if info['max_uses']==0 else info['max_uses']}"
            exp_str = f" exp:{int(info['expires'])}" if info.get("expires") else ""
            lines.append(f"• <code>{code}</code> [{uses_str}] plan:{info['plan']}{exp_str}")
        text = t(user_id, "admin_promos_list", promos="\n".join(lines))
    else:
        text = t(user_id, "admin_no_promos")
    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_promos_kb(user_id)
    )


@dp.callback_query(F.data.startswith("admin_del_promo_"))
async def cb_admin_del_promo(call: CallbackQuery):
    user_id = call.from_user.id
    if not is_admin(user_id):
        await call.answer(t(user_id, "not_admin"), show_alert=True)
        return
    code = call.data.replace("admin_del_promo_", "")
    promos = load_promos()
    if code in promos:
        del promos[code]
        save_promos(promos)
    await call.answer(t(user_id, "admin_promo_deleted", code=code))
    # Refresh promo list
    if promos:
        lines = []
        for c, info in promos.items():
            uses_str = f"{info['used_count']}/{'∞' if info['max_uses']==0 else info['max_uses']}"
            lines.append(f"• <code>{c}</code> [{uses_str}] plan:{info['plan']}")
        text = t(user_id, "admin_promos_list", promos="\n".join(lines))
    else:
        text = t(user_id, "admin_no_promos")
    await call.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=admin_promos_kb(user_id)
    )


@dp.callback_query(F.data == "admin_new_promo")
async def cb_admin_new_promo(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not is_admin(user_id):
        await call.answer(t(user_id, "not_admin"), show_alert=True)
        return
    await state.set_state(AdminCreatePromo.entering_code)
    kb = InlineKeyboardBuilder()
    kb.button(text=t(user_id, "btn_back"), callback_data="admin_promos")
    await call.message.edit_text(
        t(user_id, "admin_enter_promo_code"),
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )


@dp.message(AdminCreatePromo.entering_code)
async def admin_promo_code_input(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    code = message.text.strip().upper()
    await state.update_data(promo_code=code)
    await state.set_state(AdminCreatePromo.entering_uses)
    kb = InlineKeyboardBuilder()
    kb.button(text=t(user_id, "btn_cancel"), callback_data="admin_promos")
    await message.answer(
        t(user_id, "admin_enter_promo_uses"),
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )


@dp.message(AdminCreatePromo.entering_uses)
async def admin_promo_uses_input(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    raw = message.text.strip()
    if not raw.isdigit():
        await message.answer("❌ Введи число.")
        return
    max_uses = int(raw)
    await state.update_data(max_uses=max_uses)
    await state.set_state(AdminCreatePromo.choosing_plan)
    await message.answer(
        t(user_id, "admin_enter_promo_plan"),
        parse_mode="HTML",
        reply_markup=admin_plans_kb(user_id, "admin_promo_plan_")
    )


@dp.callback_query(F.data.startswith("admin_promo_plan_"), AdminCreatePromo.choosing_plan)
async def admin_promo_plan_chosen(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not is_admin(user_id):
        await call.answer()
        return
    plan_key = call.data.replace("admin_promo_plan_", "")
    data = await state.get_data()
    code = data["promo_code"]
    max_uses = data["max_uses"]
    create_promo(code, plan_key, max_uses)
    lang = get_user_lang(user_id)
    plan_name = PLANS[plan_key][lang]
    uses_str = str(max_uses) if max_uses > 0 else "∞"
    await state.clear()
    await call.message.edit_text(
        t(user_id, "admin_promo_created", code=code, plan=plan_name, uses=uses_str),
        parse_mode="HTML",
        reply_markup=admin_panel_kb(user_id)
    )


# ─── АДМІН: РОЗСИЛКА ─────────────────────────────────────────
@dp.callback_query(F.data == "admin_broadcast")
async def cb_admin_broadcast(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not is_admin(user_id):
        await call.answer(t(user_id, "not_admin"), show_alert=True)
        return
    await state.set_state(AdminBroadcast.entering_text)
    kb = InlineKeyboardBuilder()
    kb.button(text=t(user_id, "btn_back"), callback_data="admin_panel")
    await call.message.edit_text(
        t(user_id, "admin_broadcast_enter"),
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )


@dp.message(AdminBroadcast.entering_text)
async def admin_broadcast_send(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    text = message.text.strip()
    users = load_users()
    await state.clear()
    sent = 0
    failed = 0
    for uid_str in users.keys():
        try:
            await bot.send_message(int(uid_str), text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)  # Flood prevention
    await message.answer(
        t(user_id, "admin_broadcast_done", sent=sent, failed=failed),
        parse_mode="HTML",
        reply_markup=admin_panel_kb(user_id)
    )


# ─── АДМІН: /admin команда ───────────────────────────────────
@dp.message(lambda m: m.text and m.text.strip() == "/admin")
async def cmd_admin(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer(t(user_id, "not_admin"))
        return
    await state.clear()
    users = load_users()
    total = len(users)
    active = 0
    for uid_str, udata in users.items():
        exp = udata.get("expires")
        if exp == -1 or (exp and time.time() < exp):
            active += 1
    inactive = total - active
    await message.answer(
        t(user_id, "admin_panel", total=total, active=active, inactive=inactive),
        parse_mode="HTML",
        reply_markup=admin_panel_kb(user_id)
    )


# ─── МОЯ СТАТИСТИКА ──────────────────────────────────────────
@dp.callback_query(F.data == "my_stats")
async def cb_my_stats(call: CallbackQuery):
    user_id = call.from_user.id
    s = get_user_stats(user_id)
    total = s["sent"] + s["failed"]
    rate = round(s["sent"] / total * 100) if total > 0 else 0
    kb = InlineKeyboardBuilder()
    kb.button(text=t(user_id, "btn_back"), callback_data="back_main")
    await call.message.edit_text(
        t(user_id, "my_stats",
          total_mailings=s["mailings"],
          total_sent=s["sent"],
          total_failed=s["failed"],
          rate=rate),
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )


# ─── РЕФЕРАЛЬНА ПРОГРАМА ─────────────────────────────────────
@dp.callback_query(F.data == "referral")
async def cb_referral(call: CallbackQuery):
    user_id = call.from_user.id
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"
    user = get_user(user_id)
    count = user.get("ref_count", 0)
    bonus = user.get("ref_bonus_days", 0)
    kb = InlineKeyboardBuilder()
    kb.button(text=t(user_id, "btn_back"), callback_data="back_main")
    await call.message.edit_text(
        t(user_id, "referral_info", link=link, count=count, bonus=bonus),
        parse_mode="HTML",
        reply_markup=kb.as_markup()
    )


# ─── ФОНОВА ЗАДАЧА: НОТИФІКАЦІЇ ПРО ЗАКІНЧЕННЯ ПІДПИСКИ ─────
async def subscription_expiry_notifier():
    """Sends warnings 24h before subscription expires. Runs every hour."""
    notified_key = "expiry_notified"
    while True:
        await asyncio.sleep(3600)  # Run every hour
        users = load_users()
        now = time.time()
        for uid_str, udata in users.items():
            exp = udata.get("expires")
            if not exp or exp == -1:
                continue
            hours_left = (exp - now) / 3600
            # Notify at 24h and 2h before expiry, once each
            for threshold in [24, 2]:
                flag = f"{notified_key}_{threshold}"
                if 0 < hours_left <= threshold and not udata.get(flag):
                    try:
                        uid = int(uid_str)
                        kb = InlineKeyboardBuilder()
                        kb.button(text=t(uid, "btn_buy_sub"), callback_data="buy_sub")
                        await bot.send_message(
                            uid,
                            t(uid, "sub_expiry_warn", hours=int(hours_left)),
                            parse_mode="HTML",
                            reply_markup=kb.as_markup()
                        )
                        users[uid_str][flag] = True
                        save_users(users)
                    except Exception:
                        pass
                    break


# ─── ЗАПУСК ───────────────────────────────────────────────────
async def on_startup():
    asyncio.create_task(subscription_expiry_notifier())


if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot, on_startup=on_startup))

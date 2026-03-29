import asyncio
import re
from telethon import TelegramClient, events
from telethon.errors import UsernameNotOccupiedError, UsernameInvalidError

API_ID = 39343656
API_HASH = "53a398cd93b13272900671b8f5a9280d"
BOT_TOKEN = "8400914956:AAFM-teR6OTN6C5p-dBsh_Mh110HqzRLaLU"

bot = TelegramClient("bot", API_ID, API_HASH)

@bot.on(events.NewMessage(pattern="/start"))
async def start(event):
    await event.respond("Привет! Отправь мне список с @username и я проверю у кого есть Premium 👑")

@bot.on(events.NewMessage)
async def check(event):
    if event.text.startswith("/"):
        return
    usernames = re.findall(r'@(\w+)', event.text)
    if not usernames:
        await event.respond("Не нашёл ни одного @username!")
        return
    await event.respond(f"Проверяю {len(usernames)} аккаунтов, подожди...")
    premium = []
    no_premium = []
    not_found = []
    for username in usernames:
        try:
            user = await bot.get_entity(username)
            if getattr(user, "premium", False):
                premium.append(f"✅ @{username}")
            else:
                no_premium.append(f"❌ @{username}")
        except Exception:
            not_found.append(f"⚠️ @{username}")
        await asyncio.sleep(1)
    result = "ИТОГ:\n\n"
    if premium:
        result += "С Premium:\n" + "\n".join(premium) + "\n\n"
    if no_premium:
        result += "Без Premium:\n" + "\n".join(no_premium) + "\n\n"
    if not_found:
        result += "Не найдены:\n" + "\n".join(not_found)
    await event.respond(result)

bot.start(bot_token=BOT_TOKEN)
bot.run_until_disconnected()

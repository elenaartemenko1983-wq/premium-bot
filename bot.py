import asyncio
import re
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError

API_ID = 39343656
API_HASH = "53a398cd93b13272900671b8f5a9280d"
BOT_TOKEN = "8400914956:AAFM-teR6OTN6C5p-dBsh_Mh110HqzRLaLU"
SESSION_STRING = "1ApWapzMBu8IAoYueqgAmpzyqhepsplmlOUyEYLvBWL1k_02atZokNPi96u6_D-mvnOqFpI2y1szl0y7sYPAQ0V3TnIKq_HGEAK5V-0t6J0S8Ey3evuLYRNaCDDkQSswaf-nrOcZUlBwrGYUl37gWvo-nhOJDpR3LJYw1tNM-p7B89LDo9Vsz2dsBll72jOuxCf69_mKde0JqJlOSe7mKCRLAH-iy_XU6r_MjWrsn96-QEZ0WsM21wH4o-_B0urGHDUioc6mfRcYAXK_YH2ZRKsycNQHOpoIzTqICGRN-t9fTJcaRvsST90Yqt95lZVDAT_OpTnEX5c1wjqFY_32VkdutZqZbvto="

bot = TelegramClient("bot", API_ID, API_HASH)
user_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

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
    paid_messages = []
    no_premium = []
    not_found = []
    for username in usernames:
        try:
            user = await user_client.get_entity(username)
            has_premium = getattr(user, "premium", False)
            stars_amount = getattr(user, "send_paid_messages_stars", None)
            if stars_amount:
                paid_messages.append(f"💫 @{username} — {stars_amount} звёзд")
            elif has_premium:
                premium.append(f"✅ @{username}")
            else:
                no_premium.append(f"❌ @{username}")
        except FloodWaitError as e:
            await event.respond(f"⏳ Telegram просит подождать {e.seconds} сек, продолжаю...")
            await asyncio.sleep(e.seconds)
            try:
                user = await user_client.get_entity(username)
                has_premium = getattr(user, "premium", False)
                stars_amount = getattr(user, "send_paid_messages_stars", None)
                if stars_amount:
                    paid_messages.append(f"💫 @{username} — {stars_amount} звёзд")
                elif has_premium:
                    premium.append(f"✅ @{username}")
                else:
                    no_premium.append(f"❌ @{username}")
            except Exception:
                not_found.append(f"⚠️ @{username}")
        except Exception:
            not_found.append(f"⚠️ @{username}")
        await asyncio.sleep(3)
    result = "ИТОГ:\n\n"
    if premium:
        result += "С Premium:\n" + "\n".join(premium) + "\n\n"
    if paid_messages:
        result += "Платные сообщения:\n" + "\n".join(paid_messages) + "\n\n"
    if no_premium:
        result += "Без Premium:\n" + "\n".join(no_premium) + "\n\n"
    if not_found:
        result += "Не найдены:\n" + "\n".join(not_found)
    await event.respond(result)

async def main():
    await user_client.start()
    await bot.start(bot_token=BOT_TOKEN)
    print("Бот запущен!")
    await bot.run_until_disconnected()

asyncio.run(main())

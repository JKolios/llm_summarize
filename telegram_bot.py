import asyncio
import os

import telegram

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", None)
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", None)


def send_message(message):
    asyncio.run(async_send_message(message))


async def async_send_message(message):
    bot = telegram.Bot(BOT_TOKEN)
    async with bot:
        await bot.send_message(text=message, chat_id=CHAT_ID)


if __name__ == "__main__":
    asyncio.run(async_send_message("Test message"))

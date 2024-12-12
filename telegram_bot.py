import asyncio
import os

import telegram


def send_message(message, token, chat_id):
    asyncio.run(async_send_message(message, token, chat_id))


async def async_send_message(message, token, chat_id):
    bot = telegram.Bot(token)
    async with bot:
        await bot.send_message(text=message, chat_id=chat_id)

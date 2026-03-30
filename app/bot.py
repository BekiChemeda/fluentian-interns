from telebot.async_telebot import AsyncTeleBot
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

bot = AsyncTeleBot(os.getenv("API_TOKEN"))

@bot.message_handler(commands=['start'])
async def start(message):
    await bot.send_message(message.chat.id, "Hello! I'm your friendly neighborhood bot. How can I assist you today?")


asyncio.run(bot.infinity_polling())
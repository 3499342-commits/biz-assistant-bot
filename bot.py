import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start_handler(message: Message):
    await message.answer(
        "👋 Добро пожаловать в Biz Assistant!\n\n"
        "Пока доступна первая версия.\n\n"
        "/tasks - мои задачи\n"
        "/add - добавить задачу\n"
        "/today - задачи на сегодня"
    )

@dp.message(Command("tasks"))
async def tasks_handler(message: Message):
    await message.answer("📋 Список задач пока пуст.")

@dp.message(Command("today"))
async def today_handler(message: Message):
    await message.answer("🗓 На сегодня задач пока нет.")

@dp.message(Command("add"))
async def add_handler(message: Message):
    await message.answer(
        "✍️ В следующей версии здесь будет добавление задач."
    )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

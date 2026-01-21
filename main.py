import asyncio
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from handlers.start import start_router
from handlers.messages import messages_router
from handlers.admin import admin_router
from handlers.callbacks import callbacks_router

async def main():
    bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher()

    dp.include_router(start_router)
    dp.include_router(admin_router)
    dp.include_router(callbacks_router)
    dp.include_router(messages_router)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.redis import RedisStorage

# ✅ COMPREHENSIVE LOGGING
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from config import BOT_TOKEN, REDIS_URL
from handlers.start import start_router
from handlers.messages import messages_router
from handlers.admin import admin_router
from handlers.callbacks import callbacks_router

async def main():
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    storage = RedisStorage.from_url(REDIS_URL)
    dp = Dispatcher(storage=storage)
    
    dp.include_router(start_router)
    dp.include_router(admin_router)
    dp.include_router(messages_router)
    dp.include_router(callbacks_router)

    logger.info("🚀 Bot fully started - ready for downloads!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

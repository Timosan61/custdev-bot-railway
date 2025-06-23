import asyncio
import logging
import sys
from os import getenv

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv
from loguru import logger

from src.bot.handlers import router
from src.bot.middlewares import LoggingMiddleware
from src.services.supabase_service import SupabaseService
from src.services.zep_service import ZepService
from src.utils.config import Config

load_dotenv()

TOKEN = getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
    sys.exit(1)

async def main() -> None:
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Initialize services
    supabase_service = SupabaseService()
    zep_service = ZepService()
    
    # Initialize Bot instance
    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Initialize Dispatcher
    dp = Dispatcher()
    
    # Store services in dispatcher data
    dp["supabase"] = supabase_service
    dp["zep"] = zep_service
    
    # Register middlewares
    dp.message.middleware(LoggingMiddleware())
    
    # Include routers
    dp.include_router(router)
    
    # Start polling
    logger.info("Bot starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
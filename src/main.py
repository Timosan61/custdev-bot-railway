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
from src.utils.config import Config

load_dotenv()

TOKEN = getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
    sys.exit(1)

# Временные заглушки для тестирования
class MockSupabaseService:
    def __init__(self):
        logger.info("Mock Supabase service initialized (disabled for testing)")
    
    def create_interview(self, fields): return {"id": "mock_interview_id"}
    def update_interview(self, interview_id, data): return {"id": interview_id}
    def get_interview(self, interview_id): return {"id": interview_id}
    def create_session(self, user_id, session_type, interview_id=None): return {"id": "mock_session_id"}
    def update_session(self, session_id, state_update): return {"id": session_id}
    def get_active_session(self, user_id): return {"id": "mock_session_id"}
    def save_answer(self, interview_id, user_id, question, answer): return {"id": "mock_answer_id"}
    def get_interview_answers(self, interview_id): return []

class MockZepService:
    def __init__(self):
        logger.info("Mock Zep service initialized (disabled for testing)")
    
    async def create_session(self, session_id, metadata=None): return True
    async def add_message(self, session_id, role, content, metadata=None): pass
    async def get_memory(self, session_id, last_n=10): return []
    async def search_memory(self, session_id, query, limit=5): return []
    async def get_session(self, session_id): return {"session_id": session_id}
    async def update_session_metadata(self, session_id, metadata): pass

async def main() -> None:
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Условная инициализация сервисов
    supabase_url = getenv("SUPABASE_URL")
    supabase_key = getenv("SUPABASE_KEY") 
    zep_api_key = getenv("ZEP_API_KEY")
    
    if supabase_url and supabase_key:
        try:
            from src.services.supabase_service import SupabaseService
            supabase_service = SupabaseService()
            logger.info("✅ Real Supabase service initialized")
        except Exception as e:
            logger.warning(f"⚠️ Supabase failed, using mock: {e}")
            supabase_service = MockSupabaseService()
    else:
        logger.warning("🚧 SUPABASE_URL/SUPABASE_KEY not set, using mock service")
        supabase_service = MockSupabaseService()
        
    if zep_api_key:
        try:
            from src.services.zep_service import ZepService
            zep_service = ZepService()
            logger.info("✅ Real Zep service initialized")
        except Exception as e:
            logger.warning(f"⚠️ Zep failed, using mock: {e}")
            zep_service = MockZepService()
    else:
        logger.warning("🚧 ZEP_API_KEY not set, using mock service")
        zep_service = MockZepService()
    
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
    logger.info("🤖 Bot starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
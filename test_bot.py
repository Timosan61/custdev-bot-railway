#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работоспособности бота
"""
import asyncio
import sys
import os
from pathlib import Path

# Добавляем путь к src
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from loguru import logger

# Загружаем переменные окружения
load_dotenv()

async def test_services():
    """Проверка работы сервисов"""
    logger.info("=== Тестирование сервисов ===")
    
    # Проверка Supabase
    try:
        from src.services.supabase_service import SupabaseService
        supabase = SupabaseService()
        logger.success("✅ Supabase подключен")
        
        # Проверка таблиц
        tables = supabase.client.table("interviews").select("id").limit(1).execute()
        logger.success("✅ Таблица interviews доступна")
    except Exception as e:
        logger.error(f"❌ Ошибка Supabase: {e}")
        return False
    
    # Проверка Zep
    try:
        from src.services.zep_service import ZepService
        zep = ZepService()
        logger.success("✅ Zep Cloud подключен")
    except Exception as e:
        logger.error(f"❌ Ошибка Zep: {e}")
        return False
    
    # Проверка OpenAI
    try:
        from src.services.whisper_service import WhisperService
        whisper = WhisperService()
        logger.success("✅ OpenAI API подключен")
    except Exception as e:
        logger.error(f"❌ Ошибка OpenAI: {e}")
        return False
    
    return True

async def test_bot_start():
    """Проверка запуска бота"""
    logger.info("=== Тестирование запуска бота ===")
    
    try:
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties
        from aiogram.enums import ParseMode
        
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            logger.error("❌ TELEGRAM_BOT_TOKEN не найден")
            return False
        
        # Создаем бота
        bot = Bot(
            token=token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        
        # Проверяем информацию о боте
        bot_info = await bot.get_me()
        logger.success(f"✅ Бот запущен: @{bot_info.username}")
        
        # Закрываем сессию
        await bot.session.close()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска бота: {e}")
        return False

async def main():
    logger.info("🚀 Начинаем тестирование...")
    
    # Проверка переменных окружения
    required_vars = [
        "TELEGRAM_BOT_TOKEN",
        "OPENAI_API_KEY", 
        "ZEP_API_KEY",
        "SUPABASE_URL",
        "SUPABASE_KEY"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"❌ Отсутствуют переменные окружения: {', '.join(missing_vars)}")
        return
    
    logger.success("✅ Все переменные окружения найдены")
    
    # Тестируем сервисы
    services_ok = await test_services()
    if not services_ok:
        logger.error("❌ Тесты сервисов провалены")
        return
    
    # Тестируем бота
    bot_ok = await test_bot_start()
    if not bot_ok:
        logger.error("❌ Тест запуска бота провален")
        return
    
    logger.success("✅ Все тесты пройдены успешно!")
    logger.info("💡 Теперь можно запустить бота: python -m src.main")

if __name__ == "__main__":
    asyncio.run(main())
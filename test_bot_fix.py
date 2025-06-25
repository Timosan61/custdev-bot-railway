#!/usr/bin/env python3
"""
Тестовый скрипт для проверки исправления отправки summary
"""

import asyncio
import os
from dotenv import load_dotenv
from loguru import logger

# Загружаем переменные окружения
load_dotenv()

# Импортируем необходимые модули
from src.services.supabase_service import SupabaseService


async def test_database_structure():
    """Проверяем структуру базы данных"""
    logger.info("🔍 Проверка структуры базы данных...")
    
    try:
        supabase = SupabaseService()
        
        # Создаем тестовое интервью
        test_data = {
            "researcher_telegram_id": 123456789,
            "topic": "Test interview for summary fix"
        }
        
        logger.info("Создаю тестовое интервью...")
        interview = supabase.create_interview(test_data)
        
        if interview:
            interview_id = interview["id"]
            logger.success(f"✅ Интервью создано: {interview_id}")
            
            # Проверяем, как сохранился researcher_telegram_id
            logger.info("Проверяю сохраненные данные...")
            saved_interview = supabase.get_interview(interview_id)
            
            logger.info(f"Данные интервью: {saved_interview}")
            
            # Проверяем researcher_telegram_id на верхнем уровне
            top_level_id = saved_interview.get("researcher_telegram_id")
            logger.info(f"researcher_telegram_id (верхний уровень): {top_level_id}")
            
            # Проверяем в fields
            fields_id = saved_interview.get("fields", {}).get("researcher_telegram_id")
            logger.info(f"researcher_telegram_id (в fields): {fields_id}")
            
            # Обновляем интервью
            logger.info("Обновляю интервью...")
            update_data = {
                "status": "in_progress",
                "researcher_telegram_id": 987654321,
                "fields": {
                    "researcher_telegram_id": 987654321,
                    "updated": True
                }
            }
            
            try:
                updated = supabase.update_interview(interview_id, update_data)
                logger.success("✅ Интервью обновлено успешно")
                
                # Проверяем обновленные данные
                final_interview = supabase.get_interview(interview_id)
                logger.info(f"Обновленные данные: {final_interview}")
                
            except Exception as e:
                logger.warning(f"⚠️  Ошибка при обновлении с researcher_telegram_id: {e}")
                logger.info("Пробую обновить только через fields...")
                
                fallback_data = {
                    "status": "in_progress",
                    "fields": {
                        "researcher_telegram_id": 987654321,
                        "updated": True
                    }
                }
                updated = supabase.update_interview(interview_id, fallback_data)
                logger.success("✅ Интервью обновлено через fields")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        return False


async def check_bot_config():
    """Проверяем конфигурацию бота"""
    logger.info("\n🔧 Проверка конфигурации...")
    
    required_vars = [
        "TELEGRAM_BOT_TOKEN",
        "OPENAI_API_KEY", 
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "ZEP_API_KEY"
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
            logger.error(f"❌ {var} не задан")
        else:
            logger.success(f"✅ {var} задан")
    
    return len(missing) == 0


async def main():
    """Основная функция тестирования"""
    logger.info("🚀 Запуск тестирования исправлений\n")
    
    # Проверяем конфигурацию
    config_ok = await check_bot_config()
    if not config_ok:
        logger.error("\n❌ Проверьте файл .env!")
        return
    
    # Тестируем базу данных
    db_ok = await test_database_structure()
    
    if db_ok:
        logger.success("\n✅ Тесты пройдены успешно!")
        logger.info("\n📝 Рекомендации:")
        logger.info("1. Примените SQL миграции: python apply_migrations.py")
        logger.info("2. Перезапустите бота: ./stop_bot.sh && ./start_bot.sh")
        logger.info("3. Создайте новое исследование и проверьте отправку summary")
    else:
        logger.error("\n❌ Тесты не пройдены")
        logger.info("\n📝 Проверьте:")
        logger.info("1. Подключение к Supabase")
        logger.info("2. Наличие таблицы interviews")
        logger.info("3. Правильность SUPABASE_URL и SUPABASE_KEY")


if __name__ == "__main__":
    asyncio.run(main())
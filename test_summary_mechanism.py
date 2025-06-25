#!/usr/bin/env python3
"""
Тест механизма создания и отправки summary после завершения опроса
"""

import asyncio
import json
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.agents.respondent_agent import RespondentAgent
from src.services.supabase_service import SupabaseService
from src.services.zep_service import ZepService
from aiogram import types
from aiogram.fsm.context import FSMContext


class TestSummaryMechanism:
    """Тестирование механизма создания и отправки summary"""
    
    def __init__(self):
        self.setup_complete = False
        
    async def setup(self):
        """Настройка тестового окружения"""
        print("🔧 Настройка тестового окружения...")
        
        # Мокаем Supabase
        self.mock_supabase = Mock(spec=SupabaseService)
        self.mock_supabase.update_session = Mock()
        self.mock_supabase.get_interview = Mock()
        
        # Мокаем Zep
        self.mock_zep = Mock(spec=ZepService)
        
        # Мокаем переменные окружения
        os.environ["TELEGRAM_BOT_TOKEN"] = "test_bot_token"
        os.environ["OPENAI_API_KEY"] = "test_openai_key"
        
        # Создаем агента респондента с патчингом voice_handler и ChatOpenAI
        with patch('src.agents.respondent_agent.VoiceMessageHandler'), \
             patch('src.agents.respondent_agent.ChatOpenAI') as mock_chat:
            # Настраиваем мок для ChatOpenAI
            mock_chat.return_value = AsyncMock()
            self.agent = RespondentAgent(self.mock_supabase, self.mock_zep)
            
        # Мокаем LLM агента
        self.agent.llm = AsyncMock()
        self.agent.llm.ainvoke = AsyncMock()
        
        # Мокаем message и state
        self.mock_message = Mock(spec=types.Message)
        self.mock_message.from_user = Mock()
        self.mock_message.from_user.username = "test_user"
        self.mock_message.answer = AsyncMock()
        self.mock_message.bot = Mock()
        self.mock_message.bot.send_message = AsyncMock()
        
        self.mock_state = Mock(spec=FSMContext)
        self.mock_state.get_data = AsyncMock()
        self.mock_state.clear = AsyncMock()
        
        self.setup_complete = True
        print("✅ Настройка завершена")
        
    async def test_summary_generation(self):
        """Тест генерации summary"""
        print("\n📝 Тест 1: Генерация summary из ответов")
        
        # Подготавливаем тестовые ответы
        test_answers = {
            "Какую проблему вы пытаетесь решить?": "Трудно находить время для изучения новых технологий",
            "Как сейчас решаете эту проблему?": "Читаю статьи по выходным, смотрю видео на YouTube",
            "Что вас не устраивает в текущем решении?": "Нет системного подхода, информация разрозненная",
            "Какое решение было бы идеальным?": "Структурированные курсы с практическими заданиями"
        }
        
        # Мокаем ответ LLM
        mock_response = Mock()
        mock_response.content = (
            "Респондент испытывает трудности с поиском времени для изучения новых технологий. "
            "Текущий подход через чтение статей и YouTube видео не систематизирован. "
            "Основная боль - отсутствие структурированного подхода к обучению. "
            "Идеальным решением видит курсы с практическими заданиями."
        )
        self.agent.llm.ainvoke.return_value = mock_response
        
        # Вызываем метод генерации summary
        summary = await self.agent._generate_summary(test_answers)
        
        print(f"✅ Summary успешно сгенерирован:")
        print(f"   {summary[:100]}...")
        
        # Проверяем, что LLM был вызван с правильными данными
        assert self.agent.llm.ainvoke.called
        call_args = self.agent.llm.ainvoke.call_args[0][0]
        assert "Какую проблему вы пытаетесь решить?" in call_args
        assert "Трудно находить время" in call_args
        
        return summary
        
    async def test_finish_interview_flow(self):
        """Тест полного процесса завершения интервью"""
        print("\n🔄 Тест 2: Полный процесс завершения интервью")
        
        # Настраиваем данные состояния
        test_data = {
            "session_id": "test_session_123",
            "interview_id": "test_interview_456",
            "answers": {
                "Вопрос 1": "Ответ 1",
                "Вопрос 2": "Ответ 2"
            }
        }
        self.mock_state.get_data.return_value = test_data
        
        # Настраиваем данные интервью с ID исследователя
        test_interview = {
            "id": "test_interview_456",
            "fields": {
                "researcher_telegram_id": 123456789,
                "topic": "Test Interview"
            }
        }
        self.mock_supabase.get_interview.return_value = test_interview
        
        # Мокаем генерацию summary
        mock_summary = "Тестовое резюме интервью"
        with patch.object(self.agent, '_generate_summary', return_value=mock_summary):
            # Вызываем метод завершения интервью
            await self.agent._finish_interview(self.mock_message, self.mock_state)
        
        print("✅ Проверка вызовов:")
        
        # 1. Проверяем обновление сессии
        assert self.mock_supabase.update_session.called
        update_args = self.mock_supabase.update_session.call_args
        assert update_args[0][0] == "test_session_123"
        assert update_args[0][1]["status"] == "completed"
        assert update_args[0][1]["summary"] == mock_summary
        print("   ✓ Сессия обновлена со статусом 'completed'")
        
        # 2. Проверяем получение данных интервью
        assert self.mock_supabase.get_interview.called
        assert self.mock_supabase.get_interview.call_args[0][0] == "test_interview_456"
        print("   ✓ Данные интервью получены")
        
        # 3. Проверяем отправку сообщения исследователю
        assert self.mock_message.bot.send_message.called
        send_args = self.mock_message.bot.send_message.call_args
        assert send_args[0][0] == 123456789  # researcher_id
        assert "Новый ответ на исследование" in send_args[0][1]
        assert "@test_user" in send_args[0][1]
        assert mock_summary in send_args[0][1]
        print("   ✓ Summary отправлен исследователю")
        
        # 4. Проверяем благодарность респонденту
        assert self.mock_message.answer.called
        thank_args = self.mock_message.answer.call_args
        assert "Спасибо за участие" in thank_args[0][0]
        print("   ✓ Благодарность отправлена респонденту")
        
        # 5. Проверяем очистку состояния
        assert self.mock_state.clear.called
        print("   ✓ Состояние очищено")
        
    async def test_researcher_id_fallback(self):
        """Тест различных вариантов хранения researcher_id"""
        print("\n🔍 Тест 3: Поиск researcher_id в разных местах")
        
        # Настраиваем базовые данные
        test_data = {
            "session_id": "test_session",
            "interview_id": "test_interview",
            "answers": {"Q": "A"}
        }
        self.mock_state.get_data.return_value = test_data
        
        # Тест 1: researcher_id на верхнем уровне
        print("   • Проверка researcher_id на верхнем уровне...")
        test_interview = {
            "researcher_telegram_id": 111111111
        }
        self.mock_supabase.get_interview.return_value = test_interview
        
        with patch.object(self.agent, '_generate_summary', return_value="Summary"):
            await self.agent._finish_interview(self.mock_message, self.mock_state)
        
        assert self.mock_message.bot.send_message.call_args[0][0] == 111111111
        print("     ✓ Найден на верхнем уровне")
        
        # Тест 2: researcher_id в fields
        print("   • Проверка researcher_id в fields...")
        test_interview = {
            "fields": {
                "researcher_telegram_id": 222222222
            }
        }
        self.mock_supabase.get_interview.return_value = test_interview
        self.mock_message.bot.send_message.reset_mock()
        
        with patch.object(self.agent, '_generate_summary', return_value="Summary"):
            await self.agent._finish_interview(self.mock_message, self.mock_state)
        
        assert self.mock_message.bot.send_message.call_args[0][0] == 222222222
        print("     ✓ Найден в fields")
        
        # Тест 3: researcher_id отсутствует
        print("   • Проверка отсутствия researcher_id...")
        test_interview = {
            "fields": {
                "topic": "Test"
            }
        }
        self.mock_supabase.get_interview.return_value = test_interview
        self.mock_message.bot.send_message.reset_mock()
        
        with patch.object(self.agent, '_generate_summary', return_value="Summary"):
            await self.agent._finish_interview(self.mock_message, self.mock_state)
        
        # Проверяем, что сообщение исследователю НЕ отправлено
        assert not self.mock_message.bot.send_message.called
        print("     ✓ Сообщение не отправлено (как и ожидалось)")
        
    async def run_all_tests(self):
        """Запуск всех тестов"""
        print("🚀 Запуск тестов механизма summary\n")
        print("="*50)
        
        if not self.setup_complete:
            await self.setup()
            
        try:
            # Тест 1
            summary = await self.test_summary_generation()
            
            # Тест 2
            await self.test_finish_interview_flow()
            
            # Тест 3
            await self.test_researcher_id_fallback()
            
            print("\n" + "="*50)
            print("✅ ВСЕ ТЕСТЫ УСПЕШНО ПРОЙДЕНЫ!")
            print("\n📊 Результаты:")
            print("• Summary генерируется корректно")
            print("• Процесс завершения интервью работает правильно")
            print("• Отправка исследователю функционирует")
            print("• Обработка различных форматов данных корректна")
            
        except Exception as e:
            print(f"\n❌ ОШИБКА В ТЕСТАХ: {str(e)}")
            import traceback
            traceback.print_exc()


async def main():
    """Основная функция запуска тестов"""
    tester = TestSummaryMechanism()
    await tester.run_all_tests()


if __name__ == "__main__":
    # Запускаем тесты
    asyncio.run(main())
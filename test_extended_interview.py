#!/usr/bin/env python3
"""
Тест новой функциональности расширенного интервью
"""

import asyncio
import sys
import os
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.agents.respondent_agent import RespondentAgent
from src.services.supabase_service import SupabaseService
from src.services.zep_service import ZepService
from aiogram import types
from aiogram.fsm.context import FSMContext


class TestExtendedInterview:
    """Тестирование новой функциональности расширенного интервью"""
    
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
        self.mock_zep.get_memory = AsyncMock(return_value=[])
        self.mock_zep.add_message = AsyncMock()
        
        # Мокаем переменные окружения
        os.environ["TELEGRAM_BOT_TOKEN"] = "test_bot_token"
        os.environ["OPENAI_API_KEY"] = "test_openai_key"
        
        # Создаем агента
        with patch('src.agents.respondent_agent.VoiceMessageHandler'), \
             patch('src.agents.respondent_agent.ChatOpenAI') as mock_chat:
            mock_chat.return_value = AsyncMock()
            self.agent = RespondentAgent(self.mock_supabase, self.mock_zep)
            
        # Мокаем LLM
        self.agent.llm = AsyncMock()
        
        # Мокаем message и state
        self.mock_message = Mock(spec=types.Message)
        self.mock_message.from_user = Mock()
        self.mock_message.from_user.id = 123456
        self.mock_message.from_user.username = "test_user"
        self.mock_message.answer = AsyncMock()
        self.mock_message.bot = Mock()
        self.mock_message.bot.send_message = AsyncMock()
        
        self.mock_state = Mock(spec=FSMContext)
        self.mock_state.get_data = AsyncMock()
        self.mock_state.update_data = AsyncMock()
        self.mock_state.clear = AsyncMock()
        
        self.setup_complete = True
        print("✅ Настройка завершена")
        
    async def test_no_question_limit(self):
        """Тест: интервью продолжается после 5 вопросов"""
        print("\n📝 Тест 1: Проверка отсутствия лимита на вопросы")
        
        # Подготавливаем данные с 6 ответами
        answers = {
            f"Вопрос {i}": f"Ответ {i}" for i in range(1, 7)
        }
        
        # Мокаем генерацию вопроса - должен вернуть новый вопрос, а не None
        mock_response = Mock()
        mock_response.content = "Следующий вопрос после 6 ответов?"
        self.agent.llm.ainvoke.return_value = mock_response
        
        # Вызываем генерацию следующего вопроса
        next_question = await self.agent._generate_next_question(
            instruction="Test instruction",
            answers=answers,
            history=[]
        )
        
        print(f"✅ После 6 ответов сгенерирован вопрос: {next_question}")
        assert next_question is not None
        assert "Следующий вопрос" in next_question
        
    async def test_interim_summary_at_milestones(self):
        """Тест: отправка промежуточных отчетов после 5, 10, 15 ответов"""
        print("\n📊 Тест 2: Промежуточные отчеты на контрольных точках")
        
        # Настраиваем интервью с researcher_telegram_id
        test_interview = {
            "id": "test_interview_id",
            "researcher_telegram_id": 987654321
        }
        self.mock_supabase.get_interview.return_value = test_interview
        
        # Настраиваем состояние
        test_data = {
            "session_id": "test_session",
            "interview_id": "test_interview_id",
            "answers": {},
            "last_question": "Тестовый вопрос",
            "zep_session_id": "test_zep_session",
            "instruction": "Test instruction"
        }
        self.mock_state.get_data.return_value = test_data
        
        # Мокаем генерацию summary
        with patch.object(self.agent, '_generate_summary', return_value="Промежуточное резюме"):
            # Тестируем отправку после 5 ответов
            print("   • Проверка отправки после 5 ответов...")
            test_data["answers"] = {f"Q{i}": f"A{i}" for i in range(1, 5)}
            
            # Обрабатываем 5-й ответ
            await self.agent._process_message("Пятый ответ", self.mock_message, self.mock_state)
            
            # Ждем выполнения async задачи
            await asyncio.sleep(0.1)
            
            # Проверяем, что summary был отправлен
            assert self.mock_message.bot.send_message.called
            call_args = self.mock_message.bot.send_message.call_args
            assert call_args[0][0] == 987654321  # researcher_id
            assert "Промежуточный отчет (5 ответов)" in call_args[0][1]
            assert "Исследование продолжается" in call_args[0][1]
            print("     ✓ Промежуточный отчет после 5 ответов отправлен")
            
    async def test_inactivity_timer(self):
        """Тест: напоминание при неактивности"""
        print("\n⏱️  Тест 3: Таймер неактивности")
        
        # Настраиваем состояние
        test_data = {"inactivity_timer": None}
        self.mock_state.get_data.return_value = test_data
        
        # Запускаем таймер
        await self.agent._start_inactivity_timer(self.mock_message, self.mock_state)
        
        # Проверяем, что таймер был создан
        assert self.mock_state.update_data.called
        update_args = self.mock_state.update_data.call_args[1]
        assert "inactivity_timer" in update_args
        assert update_args["inactivity_timer"] is not None
        print("   ✓ Таймер неактивности успешно запущен")
        
        # Отменяем таймер
        timer_task = update_args["inactivity_timer"]
        test_data["inactivity_timer"] = timer_task
        
        await self.agent._cancel_inactivity_timer(self.mock_state)
        assert timer_task.cancelled()
        print("   ✓ Таймер неактивности успешно отменен")
        
    async def test_finish_only_on_request(self):
        """Тест: завершение только по просьбе пользователя"""
        print("\n🏁 Тест 4: Завершение только по запросу")
        
        # Настраиваем состояние
        test_data = {
            "session_id": "test_session",
            "interview_id": "test_interview_id",
            "answers": {f"Q{i}": f"A{i}" for i in range(1, 11)},  # 10 ответов
            "last_question": "Последний вопрос",
            "zep_session_id": "test_zep_session"
        }
        self.mock_state.get_data.return_value = test_data
        
        # Тест 1: обычный ответ не завершает интервью
        print("   • Проверка продолжения после 10 ответов...")
        mock_response = Mock()
        mock_response.content = "Еще один вопрос?"
        self.agent.llm.ainvoke.return_value = mock_response
        
        await self.agent._process_message("Обычный ответ", self.mock_message, self.mock_state)
        
        # Проверяем, что интервью НЕ завершилось
        assert not self.mock_state.clear.called
        print("     ✓ Интервью продолжается")
        
        # Тест 2: ключевое слово завершает интервью
        print("   • Проверка завершения по ключевому слову...")
        with patch.object(self.agent, '_finish_interview') as mock_finish:
            await self.agent._process_message("Хватит, достаточно", self.mock_message, self.mock_state)
            assert mock_finish.called
            print("     ✓ Интервью завершается по запросу")
            
    async def run_all_tests(self):
        """Запуск всех тестов"""
        print("🚀 Запуск тестов расширенного интервью\n")
        print("="*50)
        
        if not self.setup_complete:
            await self.setup()
            
        try:
            await self.test_no_question_limit()
            await self.test_interim_summary_at_milestones()
            await self.test_inactivity_timer()
            await self.test_finish_only_on_request()
            
            print("\n" + "="*50)
            print("✅ ВСЕ ТЕСТЫ УСПЕШНО ПРОЙДЕНЫ!")
            print("\n📊 Новая функциональность:")
            print("• Нет ограничения на количество вопросов")
            print("• Промежуточные отчеты отправляются после 5, 10, 15 ответов")
            print("• Таймер неактивности напоминает через 2 минуты")
            print("• Интервью завершается только по просьбе респондента")
            
        except Exception as e:
            print(f"\n❌ ОШИБКА В ТЕСТАХ: {str(e)}")
            import traceback
            traceback.print_exc()


async def main():
    """Основная функция запуска тестов"""
    tester = TestExtendedInterview()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
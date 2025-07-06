from abc import ABC, abstractmethod
from typing import Dict, Optional, List
from aiogram import types, Bot
from aiogram.fsm.context import FSMContext
from loguru import logger
import os
import asyncio
from datetime import datetime

from src.services.supabase_service import SupabaseService
from src.services.zep_service import ZepService
from src.services.voice_handler import VoiceMessageHandler
from src.state.user_states import RespondentStates


class BaseRespondentAgent(ABC):
    """Базовый класс для агента респондента с абстрактными методами для LLM операций"""
    
    def __init__(self, supabase: SupabaseService, zep: ZepService):
        self.supabase = supabase
        self.zep = zep
        # Initialize voice handler with bot token
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.voice_handler = VoiceMessageHandler(bot_token=bot_token)
    
    @abstractmethod
    async def generate_first_question(self, instruction: str) -> str:
        """Генерирует первый вопрос для респондента - должен быть реализован в наследниках"""
        pass
    
    @abstractmethod
    async def generate_next_question(self, instruction: str, answers: Dict, history: List) -> Optional[str]:
        """Генерирует следующий вопрос на основе контекста - должен быть реализован в наследниках"""
        pass
    
    @abstractmethod
    async def generate_summary(self, answers: Dict) -> str:
        """Генерирует резюме интервью - должен быть реализован в наследниках"""
        pass
    
    async def start_interview(self, message: types.Message, state: FSMContext, interview_id: str):
        """Начинает интервью с респондентом"""
        user_id = message.from_user.id
        
        # Check if we already have an active session
        current_data = await state.get_data()
        if current_data.get("session_id") and current_data.get("interview_id") == interview_id:
            logger.info(f"Session already active for user {user_id}, interview {interview_id}")
            return
        
        # Get interview details
        interview = self.supabase.get_interview(interview_id)
        if not interview:
            await message.answer("❌ Интервью не найдено")
            return
        
        # Create session for respondent (instead of response record)
        session = self.supabase.create_session(
            user_id=user_id,
            session_type="respondent",
            interview_id=interview_id
        )
        if not session:
            await message.answer("❌ Ошибка создания сессии")
            return
        session_id = session["id"]
        
        # Create Zep session
        zep_session_id = f"respondent_{user_id}_{interview_id}_{session_id}"
        await self.zep.create_session(zep_session_id, {
            "user_id": user_id,
            "interview_id": interview_id,
            "session_id": session_id,
            "type": "respondent"
        })
        
        # Save to state
        await state.update_data(
            interview_id=interview_id,
            session_id=session_id,
            zep_session_id=zep_session_id,
            instruction=interview.get("instruction") or interview.get("fields", {}).get("instruction", ""),
            answers={},
            inactivity_timer=None
        )
        
        # Get instruction
        instruction = interview.get("instruction") or interview.get("fields", {}).get("instruction", "")
        
        # Send welcome message with instruction
        welcome_text = (
            "👋 <b>Добро пожаловать на интервью!</b>\n\n"
            f"{instruction}\n\n"
            "Я буду задавать вам вопросы, а вы можете отвечать текстом или голосом.\n"
            "Отвечайте развернуто и честно - это поможет нам лучше понять ваши потребности.\n\n"
            "Когда захотите закончить, скажите 'хватит' или нажмите кнопку завершения."
        )
        
        await message.answer(welcome_text, reply_markup=types.ReplyKeyboardRemove())
        
        # Generate and ask first question
        first_question = await self.generate_first_question(instruction)
        await message.answer(first_question)
        
        # Save first question in state
        await state.update_data(last_question=first_question)
        
        # Log to Zep
        await self.zep.add_message(zep_session_id, "assistant", welcome_text)
        await self.zep.add_message(zep_session_id, "assistant", first_question)
        
        # Start inactivity timer
        await self._start_inactivity_timer(message, state)
    
    async def process_text_message(self, message: types.Message, state: FSMContext):
        """Обрабатывает текстовое сообщение"""
        await self._process_message(message.text, message, state)
    
    async def process_voice_message(self, message: types.Message, state: FSMContext, bot: Bot):
        """Обрабатывает голосовое сообщение"""
        # Send processing indicator
        processing_msg = await message.answer("🎤 Обрабатываю голосовое сообщение...")
        
        # Process voice message
        result = await self.voice_handler.process_voice_message(
            file_id=message.voice.file_id,
            duration=message.voice.duration
        )
        
        # Delete processing message
        await bot.delete_message(message.chat.id, processing_msg.message_id)
        
        if result["success"]:
            text = result["transcription"]
            logger.info(f"Voice transcribed: {text}")
            
            # Process the message
            await self._process_message(text, message, state)
        else:
            error = result.get("error", "Unknown error")
            logger.error(f"Voice processing failed: {error}")
            await message.answer("❌ Не удалось распознать голосовое сообщение. Попробуйте еще раз или отправьте текстом.")
    
    async def _process_message(self, text: str, message: types.Message, state: FSMContext):
        """Основная логика обработки сообщений респондента"""
        data = await state.get_data()
        user_id = message.from_user.id
        session_id = data.get("session_id")
        zep_session_id = data.get("zep_session_id")
        instruction = data.get("instruction", "")
        answers = data.get("answers", {})
        last_question = data.get("last_question", "")
        finish_attempts = data.get("finish_attempts", 0)
        last_finish_attempt = data.get("last_finish_attempt", 0)
        
        logger.info(f"Processing respondent message from user {user_id}: {text[:50]}...")
        
        # Log user message to Zep
        await self.zep.add_message(zep_session_id, "user", text)
        
        # Check if user wants to finish
        wants_to_finish = any(word in text.lower() for word in ["хватит", "достаточно", "все", "стоп", "закончить"])
        
        if wants_to_finish:
            current_time = datetime.now().timestamp()
            
            # Reset counter if more than 5 minutes passed since last attempt
            if current_time - last_finish_attempt > 300:  # 5 minutes
                finish_attempts = 0
            
            finish_attempts += 1
            await state.update_data(
                finish_attempts=finish_attempts, 
                last_finish_attempt=current_time
            )
            
            logger.info(f"User wants to finish. Attempt {finish_attempts}")
            
            if finish_attempts >= 2:
                await self._finish_interview(message, state)
                return
            else:
                confirmation_text = (
                    "🤔 <b>Вы уверены, что хотите завершить интервью?</b>\n\n"
                    "Ваши ответы очень ценны для исследования. "
                    "Если действительно хотите закончить, скажите 'хватит' еще раз.\n\n"
                    "Или продолжим - я задам еще несколько важных вопросов."
                )
                await message.answer(confirmation_text)
                await self.zep.add_message(zep_session_id, "assistant", confirmation_text)
                return
        else:
            # Reset finish attempts if user continues normally
            if finish_attempts > 0:
                await state.update_data(finish_attempts=0)
                logger.debug("Reset finish attempts - user continues interview")
        
        # Save answer
        answers[last_question] = text
        await state.update_data(answers=answers)
        
        # Update session in database
        self.supabase.update_session(session_id, {"answers": answers})
        
        # Check if we need to send interim summary (after 5, 10, 15 answers)
        answers_count = len(answers)
        if answers_count in [5, 10, 15]:
            asyncio.create_task(self._send_interim_summary(message, state, answers_count))
        
        # Get conversation history
        history = await self.zep.get_memory(zep_session_id, last_n=10)
        
        # Generate next question
        logger.info(f"Generating next question. Answers count: {len(answers)}, Instruction: {instruction[:100]}...")
        next_question = await self.generate_next_question(instruction, answers, history)
        logger.info(f"Generated question: {next_question}")
        
        if next_question:
            await message.answer(next_question)
            await self.zep.add_message(zep_session_id, "assistant", next_question)
            # Save the question for context
            await state.update_data(last_question=next_question)
            # Start inactivity timer for next response
            await self._start_inactivity_timer(message, state)
        else:
            logger.info("Finishing interview - no more questions")
            await self._finish_interview(message, state)
    
    async def _finish_interview(self, message: types.Message, state: FSMContext):
        """Завершает интервью и отправляет резюме"""
        logger.info("Starting interview finish process")
        data = await state.get_data()
        session_id = data.get("session_id")
        interview_id = data.get("interview_id")
        answers = data.get("answers", {})
        
        logger.info(f"Finishing interview {interview_id} with {len(answers)} answers")
        logger.info(f"Session ID: {session_id}")
        logger.info(f"User: {message.from_user.id} (@{message.from_user.username})")
        
        # Generate summary
        summary = await self.generate_summary(answers)
        logger.info(f"Generated summary: {summary[:100]}...")
        
        # Update session
        self.supabase.update_session(session_id, {
            "status": "completed",
            "summary": summary,
            "answers": answers
        })
        
        # Send to researcher
        interview = self.supabase.get_interview(interview_id)
        logger.info(f"Interview data: {interview}")
        
        researcher_id = None
        
        # Попробуем получить ID исследователя из разных мест
        if interview:
            # Сначала проверяем на верхнем уровне
            researcher_id = interview.get("researcher_telegram_id")
            logger.info(f"Checking top-level researcher_telegram_id: {researcher_id}")
            
            # Затем в полях
            if not researcher_id and "fields" in interview:
                researcher_id = interview["fields"].get("researcher_telegram_id")
                logger.info(f"Checking fields.researcher_telegram_id: {researcher_id}")
            
            # Преобразуем в int если это строка
            if researcher_id and isinstance(researcher_id, str):
                try:
                    researcher_id = int(researcher_id)
                    logger.info(f"Converted researcher_id to int: {researcher_id}")
                except ValueError:
                    logger.error(f"Cannot convert researcher_id to int: {researcher_id}")
                    researcher_id = None
        
        if researcher_id:
            summary_text = (
                f"📊 <b>Новый ответ на исследование</b>\n\n"
                f"<b>Респондент:</b> @{message.from_user.username or 'anonymous'}\n\n"
                f"<b>Краткое резюме:</b>\n{summary}\n\n"
                f"<b>Полные ответы сохранены в базе данных.</b>"
            )
            
            try:
                await message.bot.send_message(researcher_id, summary_text, parse_mode="HTML")
                logger.info(f"Summary sent to researcher {researcher_id}")
            except Exception as e:
                logger.error(f"Failed to send summary to researcher {researcher_id}: {e}")
        
        # Check for reward link
        reward_link = None
        if interview and "fields" in interview:
            reward_link = interview["fields"].get("reward_link")
        
        # Thank respondent with reward if available
        if reward_link:
            thank_text = (
                "🙏 <b>Спасибо за участие в интервью!</b>\n\n"
                "Ваши ответы очень важны для нас и помогут улучшить наш продукт.\n\n"
                "🎁 <b>В благодарность за ваше время, мы подготовили для вас полезный материал:</b>\n"
                f"{reward_link}\n\n"
                "Хорошего дня!"
            )
        else:
            thank_text = (
                "🙏 <b>Спасибо за участие в интервью!</b>\n\n"
                "Ваши ответы очень важны для нас и помогут улучшить наш продукт.\n"
                "Хорошего дня!"
            )
        
        await message.answer(thank_text, reply_markup=types.ReplyKeyboardRemove())
        
        # Cancel inactivity timer before clearing state
        await self._cancel_inactivity_timer(state)
        
        await state.clear()
    
    async def _send_interim_summary(self, message: types.Message, state: FSMContext, answers_count: int):
        """Отправить промежуточный отчет исследователю"""
        data = await state.get_data()
        interview_id = data.get("interview_id")
        answers = data.get("answers", {})
        
        logger.info(f"Sending interim summary after {answers_count} answers")
        
        # Генерируем промежуточное резюме
        summary = await self.generate_summary(answers)
        
        # Получаем ID исследователя
        researcher_id = await self._get_researcher_id(interview_id)
        if not researcher_id:
            logger.error(f"Researcher ID not found for interview {interview_id}")
            return
        
        # Формируем текст отчета
        interim_text = self._format_interim_report(answers_count, message.from_user.username, summary)
        
        # Отправляем отчет
        await self._send_message_to_researcher(researcher_id, interim_text, message.bot)
    
    async def _send_inactivity_reminder(self, message: types.Message, state: FSMContext, reminder_number: int = 1):
        """Отправить напоминание о неактивности"""
        data = await state.get_data()
        
        # Check if reminder was already sent
        reminders_sent = data.get("reminders_sent", [])
        if reminder_number in reminders_sent:
            logger.debug(f"Reminder {reminder_number} already sent, skipping")
            return
        
        if reminder_number == 1:
            reminder_text = (
                "👋 <b>Вы еще здесь?</b>\n\n"
                "Похоже, вы немного отвлеклись. Давайте продолжим наше интервью!\n"
                "Если хотите закончить, просто скажите «хватит» или нажмите кнопку завершения."
            )
        else:
            reminder_text = (
                "⏰ <b>Прошел уже час с момента вашей последней активности</b>\n\n"
                "Если вы хотите продолжить интервью, пожалуйста, ответьте на последний вопрос.\n"
                "Или скажите «хватит», чтобы завершить интервью."
            )
        
        try:
            await message.answer(reminder_text)
            logger.info(f"Inactivity reminder {reminder_number} sent to user {message.from_user.id}")
            
            # Mark reminder as sent
            reminders_sent.append(reminder_number)
            await state.update_data(reminders_sent=reminders_sent)
            
            # If this was first reminder, schedule second one after 1 hour
            if reminder_number == 1:
                await self._start_second_inactivity_timer(message, state)
        except Exception as e:
            logger.error(f"Failed to send inactivity reminder: {e}")
    
    async def _start_inactivity_timer(self, message: types.Message, state: FSMContext):
        """Запустить таймер неактивности"""
        # Отменяем предыдущие таймеры, если они есть
        await self._cancel_all_timers(state)
        
        # Reset reminders sent when user is active
        await state.update_data(reminders_sent=[])
        
        # Создаем новый таймер на 2 минуты
        async def timer_callback():
            await asyncio.sleep(120)  # 2 минуты
            await self._send_inactivity_reminder(message, state, reminder_number=1)
        
        timer_task = asyncio.create_task(timer_callback())
        await state.update_data(inactivity_timer=timer_task)
        logger.debug(f"Inactivity timer started for user {message.from_user.id}")
    
    async def _start_second_inactivity_timer(self, message: types.Message, state: FSMContext):
        """Запустить второй таймер неактивности (1 час)"""
        # Создаем таймер на 1 час
        async def timer_callback():
            await asyncio.sleep(3600)  # 1 час
            await self._send_inactivity_reminder(message, state, reminder_number=2)
        
        timer_task = asyncio.create_task(timer_callback())
        await state.update_data(second_inactivity_timer=timer_task)
        logger.debug(f"Second inactivity timer started for user {message.from_user.id}")
    
    async def _cancel_all_timers(self, state: FSMContext):
        """Отменить все таймеры неактивности"""
        data = await state.get_data()
        
        # Cancel first timer
        timer_task = data.get("inactivity_timer")
        if timer_task and not timer_task.done():
            timer_task.cancel()
            logger.debug("First inactivity timer cancelled")
        
        # Cancel second timer
        second_timer_task = data.get("second_inactivity_timer")
        if second_timer_task and not second_timer_task.done():
            second_timer_task.cancel()
            logger.debug("Second inactivity timer cancelled")
    
    async def _cancel_inactivity_timer(self, state: FSMContext):
        """Отменить таймер неактивности (для обратной совместимости)"""
        await self._cancel_all_timers(state)
    
    async def _get_researcher_id(self, interview_id: str) -> Optional[int]:
        """Получить ID исследователя из интервью"""
        interview = self.supabase.get_interview(interview_id)
        if not interview:
            return None
        
        # Проверяем ID на верхнем уровне
        researcher_id = interview.get("researcher_telegram_id")
        
        # Если не нашли, проверяем в fields
        if not researcher_id and "fields" in interview:
            researcher_id = interview["fields"].get("researcher_telegram_id")
        
        # Преобразуем в int если это строка
        if researcher_id and isinstance(researcher_id, str):
            try:
                researcher_id = int(researcher_id)
            except ValueError:
                logger.error(f"Cannot convert researcher_id to int: {researcher_id}")
                return None
        
        return researcher_id
    
    def _format_interim_report(self, answers_count: int, username: str, summary: str) -> str:
        """Форматировать промежуточный отчет"""
        return (
            f"📊 <b>Промежуточный отчет ({answers_count} ответов)</b>\n\n"
            f"<b>Респондент:</b> @{username or 'anonymous'}\n\n"
            f"<b>Текущее резюме:</b>\n{summary}\n\n"
            f"<i>⏳ Исследование продолжается...</i>"
        )
    
    async def _send_message_to_researcher(self, researcher_id: int, text: str, bot: Bot):
        """Отправить сообщение исследователю"""
        try:
            await bot.send_message(researcher_id, text, parse_mode="HTML")
            logger.info(f"Message sent to researcher {researcher_id}")
        except Exception as e:
            logger.error(f"Failed to send message to researcher {researcher_id}: {e}")
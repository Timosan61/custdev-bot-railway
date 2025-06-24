from typing import Dict, Optional, List
from aiogram import types, Bot
from aiogram.fsm.context import FSMContext
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from loguru import logger
import json
import os
import asyncio
from datetime import datetime

from src.services.supabase_service import SupabaseService
from src.services.zep_service import ZepService
from src.services.voice_handler import VoiceMessageHandler
from src.utils.keyboards import get_finish_keyboard
from src.state.user_states import RespondentStates

class RespondentAgent:
    def __init__(self, supabase: SupabaseService, zep: ZepService):
        self.supabase = supabase
        self.zep = zep
        # Initialize voice handler with bot token
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.voice_handler = VoiceMessageHandler(bot_token=bot_token)
        self.llm = ChatOpenAI(model_name="gpt-4o", temperature=0.7)
    
    async def start_interview(self, message: types.Message, state: FSMContext, interview_id: str):
        user_id = message.from_user.id
        
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
            instruction=interview.get("fields", {}).get("instruction", interview.get("instruction", "")),
            answers={},
            inactivity_timer=None
        )
        
        # Send welcome message
        welcome_text = (
            "👋 <b>Добро пожаловать на интервью!</b>\n\n"
            "Я буду задавать вам вопросы, а вы можете отвечать текстом или голосом.\n"
            "Отвечайте развернуто и честно - это поможет нам лучше понять ваши потребности.\n\n"
            "Когда захотите закончить, скажите 'хватит' или нажмите кнопку завершения."
        )
        
        await message.answer(welcome_text, reply_markup=get_finish_keyboard())
        
        # Generate and ask first question
        first_question = await self._generate_first_question(interview.get("fields", {}).get("instruction", interview.get("instruction", "")))
        await message.answer(first_question)
        
        # Save first question in state
        await state.update_data(last_question=first_question)
        
        # Log to Zep
        await self.zep.add_message(zep_session_id, "assistant", welcome_text)
        await self.zep.add_message(zep_session_id, "assistant", first_question)
        
        # Start inactivity timer
        await self._start_inactivity_timer(message, state)
    
    async def process_text_message(self, message: types.Message, state: FSMContext):
        await self._process_message(message.text, message, state)
    
    async def process_voice_message(self, message: types.Message, state: FSMContext, bot: Bot):
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
            
            # Show what was recognized
            await message.answer(f"✅ Распознано: <i>{text}</i>")
            
            # Process the message
            await self._process_message(text, message, state)
        else:
            error = result.get("error", "Unknown error")
            logger.error(f"Voice processing failed: {error}")
            await message.answer("❌ Не удалось распознать голосовое сообщение. Попробуйте еще раз или отправьте текстом.")
    
    async def _process_message(self, text: str, message: types.Message, state: FSMContext):
        data = await state.get_data()
        user_id = message.from_user.id
        session_id = data.get("session_id")
        zep_session_id = data.get("zep_session_id")
        instruction = data.get("instruction", "")
        answers = data.get("answers", {})
        last_question = data.get("last_question", "")
        
        logger.info(f"Processing respondent message from user {user_id}: {text[:50]}...")
        
        # Log user message to Zep
        await self.zep.add_message(zep_session_id, "user", text)
        
        # Check if user wants to finish
        if any(word in text.lower() for word in ["хватит", "достаточно", "все", "✅ завершить"]):
            await self._finish_interview(message, state)
            return
        
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
        next_question = await self._generate_next_question(instruction, answers, history)
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
    
    async def _generate_first_question(self, instruction: str) -> str:
        prompt = PromptTemplate(
            input_variables=["instruction"],
            template="""
            Ты проводишь кастдев-интервью по следующей инструкции:
            {instruction}
            
            Сгенерируй первый вопрос для респондента.
            Вопрос должен быть открытым, дружелюбным и располагать к развернутому ответу.
            
            Верни только текст вопроса, без лишних пояснений.
            """
        )
        
        response = await self.llm.ainvoke(prompt.format(instruction=instruction))
        return response.content
    
    async def _generate_next_question(self, instruction: str, answers: Dict, history: List) -> Optional[str]:
        # No limit on questions - interview continues until user asks to stop
        
        history_text = "\n".join([
            f"{msg.role}: {msg.content}" 
            for msg in history[-6:]  # Last 3 exchanges
        ])
        
        prompt = PromptTemplate(
            input_variables=["instruction", "history", "answers_count"],
            template="""
            Ты проводишь кастдев-интервью по следующей инструкции:
            {instruction}
            
            История диалога:
            {history}
            
            Уже задано вопросов: {answers_count}
            
            Сгенерируй следующий вопрос, который:
            1. Начинается с краткого подтверждения понимания последнего ответа
            2. Логично вытекает из предыдущего ответа
            3. Углубляет понимание темы
            4. Побуждает к развернутому ответу
            5. Соответствует инструкции исследования
            
            Примеры хороших ответов:
            - "Понимаю, для вас важна экономия времени. А какие еще факторы влияют на ваш выбор?"
            - "Интересно, что вы упомянули качество материалов. Расскажите подробнее, с какими проблемами вы сталкивались?"
            
            ВАЖНО: Продолжай задавать уточняющие вопросы для получения максимально полной информации.
            Верни "FINISH" ТОЛЬКО если:
            - Респондент явно просит закончить (говорит "хватит", "достаточно", "все" и т.п.)
            - ИЛИ респондент перестал давать содержательные ответы
            
            Верни только текст вопроса или "FINISH", без лишних пояснений.
            """
        )
        
        response = await self.llm.ainvoke(
            prompt.format(
                instruction=instruction,
                history=history_text,
                answers_count=len(answers)
            )
        )
        
        content = response.content.strip()
        if content == "FINISH":
            return None
        return content
    
    async def _finish_interview(self, message: types.Message, state: FSMContext):
        logger.info("Starting interview finish process")
        data = await state.get_data()
        session_id = data.get("session_id")
        interview_id = data.get("interview_id")
        answers = data.get("answers", {})
        
        logger.info(f"Finishing interview {interview_id} with {len(answers)} answers")
        logger.info(f"Session ID: {session_id}")
        logger.info(f"User: {message.from_user.id} (@{message.from_user.username})")
        
        # Generate summary
        summary = await self._generate_summary(answers)
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
            
            # Для отладки - выведем полную структуру интервью
            logger.debug(f"Full interview structure: {json.dumps(interview, indent=2, ensure_ascii=False)}")
            logger.info(f"Final researcher ID: {researcher_id}")
            
            # Дополнительная проверка типа
            if researcher_id:
                logger.info(f"Researcher ID type: {type(researcher_id)}, value: {researcher_id}")
                # Преобразуем в int если это строка
                if isinstance(researcher_id, str):
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
        
        # Thank respondent
        thank_text = (
            "🙏 <b>Спасибо за участие в интервью!</b>\n\n"
            "Ваши ответы очень важны для нас и помогут улучшить наш продукт.\n"
            "Хорошего дня!"
        )
        
        await message.answer(thank_text, reply_markup=types.ReplyKeyboardRemove())
        
        # Cancel inactivity timer before clearing state
        await self._cancel_inactivity_timer(state)
        
        await state.clear()
    
    async def _generate_summary(self, answers: Dict) -> str:
        qa_text = "\n\n".join([
            f"Вопрос: {q}\nОтвет: {a}" 
            for q, a in answers.items()
        ])
        
        prompt = PromptTemplate(
            input_variables=["qa_text"],
            template="""
            Проанализируй ответы респондента и создай краткое резюме (3-5 предложений).
            
            Вопросы и ответы:
            {qa_text}
            
            Выдели ключевые инсайты, боли, потребности и пожелания респондента.
            Пиши кратко и по существу.
            """
        )
        
        response = await self.llm.ainvoke(prompt.format(qa_text=qa_text))
        return response.content
    
    async def _send_interim_summary(self, message: types.Message, state: FSMContext, answers_count: int):
        """Отправить промежуточный отчет исследователю"""
        data = await state.get_data()
        interview_id = data.get("interview_id")
        answers = data.get("answers", {})
        
        logger.info(f"Sending interim summary after {answers_count} answers")
        
        # Генерируем промежуточное резюме
        summary = await self._generate_summary(answers)
        
        # Получаем ID исследователя
        researcher_id = await self._get_researcher_id(interview_id)
        if not researcher_id:
            logger.error(f"Researcher ID not found for interview {interview_id}")
            return
        
        # Формируем текст отчета
        interim_text = self._format_interim_report(answers_count, message.from_user.username, summary)
        
        # Отправляем отчет
        await self._send_message_to_researcher(researcher_id, interim_text, message.bot)
    
    async def _send_inactivity_reminder(self, message: types.Message, state: FSMContext):
        """Отправить напоминание о неактивности"""
        reminder_text = (
            "👋 <b>Вы еще здесь?</b>\n\n"
            "Похоже, вы немного отвлеклись. Давайте продолжим наше интервью!\n"
            "Если хотите закончить, просто скажите «хватит» или нажмите кнопку завершения."
        )
        
        try:
            await message.answer(reminder_text, reply_markup=get_finish_keyboard())
            logger.info(f"Inactivity reminder sent to user {message.from_user.id}")
        except Exception as e:
            logger.error(f"Failed to send inactivity reminder: {e}")
    
    async def _start_inactivity_timer(self, message: types.Message, state: FSMContext):
        """Запустить таймер неактивности"""
        # Отменяем предыдущий таймер, если он есть
        await self._cancel_inactivity_timer(state)
        
        # Создаем новый таймер на 2 минуты
        async def timer_callback():
            await asyncio.sleep(120)  # 2 минуты
            await self._send_inactivity_reminder(message, state)
        
        timer_task = asyncio.create_task(timer_callback())
        await state.update_data(inactivity_timer=timer_task)
        logger.debug(f"Inactivity timer started for user {message.from_user.id}")
    
    async def _cancel_inactivity_timer(self, state: FSMContext):
        """Отменить таймер неактивности"""
        data = await state.get_data()
        timer_task = data.get("inactivity_timer")
        
        if timer_task and not timer_task.done():
            timer_task.cancel()
            logger.debug("Inactivity timer cancelled")
    
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
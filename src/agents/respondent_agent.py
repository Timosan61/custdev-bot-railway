from typing import Dict, Optional, List
from aiogram import types, Bot
from aiogram.fsm.context import FSMContext
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from loguru import logger
import json
import os

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
        
        # Create response record
        response = self.supabase.create_response({
            "interview_id": interview_id,
            "respondent_telegram_id": user_id,
            "answers": {}
        })
        if not response:
            await message.answer("❌ Ошибка создания записи")
            return
        response_id = response["id"]
        
        # Create Zep session
        zep_session_id = f"respondent_{user_id}_{interview_id}_{response_id}"
        await self.zep.create_session(zep_session_id, {
            "user_id": user_id,
            "interview_id": interview_id,
            "response_id": response_id,
            "type": "respondent"
        })
        
        # Save to state
        await state.update_data(
            interview_id=interview_id,
            response_id=response_id,
            zep_session_id=zep_session_id,
            instruction=interview.get("fields", {}).get("instruction", interview.get("instruction", "")),
            answers={}
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
        response_id = data.get("response_id")
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
        
        # Update response in database
        self.supabase.update_response(response_id, {"answers": answers})
        
        # Get conversation history
        history = await self.zep.get_memory(zep_session_id, last_n=10)
        
        # Generate next question
        next_question = await self._generate_next_question(instruction, answers, history)
        
        if next_question:
            await message.answer(next_question)
            await self.zep.add_message(zep_session_id, "assistant", next_question)
            # Save the question for context
            await state.update_data(last_question=next_question)
        else:
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
        # Check if we have enough information
        if len(answers) >= 5:  # Limit to 5 questions
            return None
        
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
            
            Если информации достаточно или задано 5 вопросов, верни "FINISH".
            
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
        data = await state.get_data()
        response_id = data.get("response_id")
        interview_id = data.get("interview_id")
        answers = data.get("answers", {})
        
        # Generate summary
        summary = await self._generate_summary(answers)
        
        # Update response
        self.supabase.update_response(response_id, {
            "status": "completed",
            "summary": summary
        })
        
        # Send to researcher
        interview = self.supabase.get_interview(interview_id)
        if interview and interview.get("researcher_telegram_id"):
            researcher_id = interview["researcher_telegram_id"]
            
            summary_text = (
                f"📊 <b>Новый ответ на исследование</b>\n\n"
                f"<b>Респондент:</b> @{message.from_user.username or 'anonymous'}\n\n"
                f"<b>Краткое резюме:</b>\n{summary}\n\n"
                f"<b>Полные ответы сохранены в базе данных.</b>"
            )
            
            try:
                await message.bot.send_message(researcher_id, summary_text)
            except Exception as e:
                logger.error(f"Failed to send summary to researcher: {e}")
        
        # Thank respondent
        thank_text = (
            "🙏 <b>Спасибо за участие в интервью!</b>\n\n"
            "Ваши ответы очень важны для нас и помогут улучшить наш продукт.\n"
            "Хорошего дня!"
        )
        
        await message.answer(thank_text, reply_markup=types.ReplyKeyboardRemove())
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
from typing import Dict, Optional
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
from src.state.user_states import ResearcherStates

class ResearcherAgent:
    def __init__(self, supabase: SupabaseService, zep: ZepService):
        self.supabase = supabase
        self.zep = zep
        # Initialize voice handler with bot token
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.voice_handler = VoiceMessageHandler(bot_token=bot_token)
        self.llm = ChatOpenAI(model_name="gpt-4o", temperature=0.7)
        
        self.fields_to_collect = {
            "research_goal": "Цель исследования",
            "audience": "Целевая аудитория",
            "hypotheses": "Гипотезы для проверки",
            "style": "Стиль общения",
            "topic": "Тема и контекст"
        }
    
    async def start_dialog(self, message: types.Message, state: FSMContext):
        user_id = message.from_user.id
        
        # Create new interview
        interview = self.supabase.create_interview({})
        if not interview:
            await message.answer("❌ Ошибка создания интервью")
            return
        interview_id = interview["id"]
        
        # Create Zep session
        zep_session_id = f"researcher_{user_id}_{interview_id}"
        await self.zep.create_session(zep_session_id, {
            "user_id": user_id,
            "interview_id": interview_id,
            "type": "researcher"
        })
        
        # Save to state
        await state.update_data(
            interview_id=interview_id,
            zep_session_id=zep_session_id,
            collected_fields={}
        )
        
        # Send welcome message and first question
        welcome_text = (
            "🔬 <b>Создание нового исследования</b>\n\n"
            "Привет! Я помогу вам создать кастдев-интервью.\n\n"
            "Отвечайте на мои вопросы в свободной форме текстом или голосом. "
            "Когда закончите, скажите 'хватит' или нажмите кнопку завершения."
        )
        
        await message.answer(welcome_text, reply_markup=get_finish_keyboard())
        
        # Ask first question
        first_question = "Какова основная цель вашего исследования? Что вы хотите узнать или понять?"
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
        interview_id = data.get("interview_id")
        zep_session_id = data.get("zep_session_id")
        collected_fields = data.get("collected_fields", {})
        last_question = data.get("last_question", "")
        
        logger.info(f"Processing message from user {user_id}: {text[:50]}...")
        logger.debug(f"Current collected fields: {collected_fields}")
        logger.debug(f"Last question was: {last_question}")
        
        # Log user message to Zep
        await self.zep.add_message(zep_session_id, "user", text)
        
        # Check if user wants to finish
        if any(word in text.lower() for word in ["хватит", "достаточно", "все", "✅ завершить"]):
            await self._finish_collection(message, state)
            return
        
        # Analyze message and extract fields
        extracted = await self._analyze_message(text, collected_fields, last_question)
        logger.info(f"Extracted fields: {extracted}")
        
        if extracted:
            collected_fields.update(extracted)
            logger.info(f"Updated collected fields: {collected_fields}")
        
        # Update state with new fields and last question
        await state.update_data(collected_fields=collected_fields)
        
        # Generate next question with context of last answer
        next_question = await self._generate_next_question(collected_fields, text)
        
        if next_question:
            await message.answer(next_question)
            await self.zep.add_message(zep_session_id, "assistant", next_question)
            # Save the question for context
            await state.update_data(last_question=next_question)
        else:
            await self._finish_collection(message, state)
    
    async def _analyze_message(self, text: str, current_fields: Dict, last_question: str = "") -> Dict:
        prompt = PromptTemplate(
            input_variables=["text", "current_fields", "all_fields", "last_question"],
            template="""
            Проанализируй ответ пользователя на вопрос и извлеки информацию для полей кастдев-исследования.
            
            Последний заданный вопрос:
            {last_question}
            
            Ответ пользователя:
            {text}
            
            Уже собранные поля:
            {current_fields}
            
            Все необходимые поля и их описания:
            {all_fields}
            
            ВАЖНО: Пользователь может отвечать неточно или кратко. Попробуй понять смысл ответа в контексте заданного вопроса.
            
            Примеры сопоставления:
            - Вопрос о цели -> "узнать боли клиентов" = research_goal: "Выявление болей и потребностей клиентов"
            - Вопрос о цели -> "аудитория моих клиентов" = research_goal: "Исследование целевой аудитории"
            - Вопрос об аудитории -> "предприниматели" = audience: "Предприниматели"
            
            Верни ТОЛЬКО валидный JSON объект с извлеченными полями (без markdown разметки). 
            Если не удалось извлечь поля, верни пустой объект {{}}.
            
            Пример ответа: {{"research_goal": "Изучить потребности клиентов"}}
            """
        )
        
        try:
            response = await self.llm.ainvoke(
                prompt.format(
                    text=text,
                    current_fields=json.dumps(current_fields, ensure_ascii=False),
                    all_fields=json.dumps(self.fields_to_collect, ensure_ascii=False),
                    last_question=last_question
                )
            )
            
            logger.debug(f"LLM response: {response.content}")
            
            # Extract JSON from markdown code blocks if present
            content = response.content.strip()
            if content.startswith("```json") and content.endswith("```"):
                content = content[7:-3].strip()
            elif content.startswith("```") and content.endswith("```"):
                content = content[3:-3].strip()
            
            result = json.loads(content)
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from LLM: {e}")
            logger.error(f"LLM response was: {response.content if 'response' in locals() else 'No response'}")
            return {}
        except Exception as e:
            logger.error(f"Error in analyze_message: {e}")
            return {}
    
    async def _generate_next_question(self, collected_fields: Dict, last_answer: str = "") -> Optional[str]:
        missing_fields = [
            field for field in self.fields_to_collect 
            if field not in collected_fields or not collected_fields[field]
        ]
        
        if not missing_fields:
            return None
        
        prompt = PromptTemplate(
            input_variables=["collected", "missing", "descriptions", "last_answer"],
            template="""
            Сгенерируй естественный уточняющий вопрос для сбора недостающей информации.
            
            Последний ответ пользователя:
            {last_answer}
            
            Уже собрано:
            {collected}
            
            Недостает:
            {missing}
            
            Описания полей:
            {descriptions}
            
            ВАЖНО: Начни ответ с подтверждения того, что ты понял последний ответ пользователя.
            Затем задай конкретный вопрос о ОДНОМ из недостающих полей.
            
            Примеры хороших ответов:
            - "Понял, вы хотите исследовать потребности мамочек 30-40 лет. Какие конкретно аспекты их поведения или предпочтений вас интересуют?"
            - "Отлично, ваша цель - выявить боли клиентов в сфере детских товаров. Какие гипотезы вы хотите проверить в ходе исследования?"
            - "Хорошо, я понял что вы работаете с предпринимателями. В каком стиле должен общаться бот с респондентами - более формальном или дружеском?"
            
            Будь естественным и покажи, что ты внимательно слушаешь собеседника.
            """
        )
        
        response = await self.llm.ainvoke(
            prompt.format(
                last_answer=last_answer,
                collected=collected_fields,
                missing=missing_fields,
                descriptions=self.fields_to_collect
            )
        )
        
        return response.content
    
    async def _finish_collection(self, message: types.Message, state: FSMContext):
        data = await state.get_data()
        interview_id = data.get("interview_id")
        collected_fields = data.get("collected_fields", {})
        
        # Generate instruction
        instruction = await self._generate_instruction(collected_fields)
        
        # Update interview
        update_data = {
            "status": "in_progress",
            "fields": collected_fields
        }
        
        # Пока не добавлена колонка instruction, сохраняем её в fields
        if instruction:
            update_data["fields"]["instruction"] = instruction
            
        self.supabase.update_interview(interview_id, update_data)
        
        # Generate interview link
        bot_username = (await message.bot.me()).username
        interview_link = f"https://t.me/{bot_username}?start=interview_{interview_id}"
        
        # Send result
        result_text = (
            "✅ <b>Исследование создано!</b>\n\n"
            f"<b>Инструкция для интервью:</b>\n{instruction}\n\n"
            f"<b>Ссылка для респондентов:</b>\n"
            f"<code>{interview_link}</code>\n\n"
            "Отправьте эту ссылку вашим респондентам для прохождения интервью."
        )
        
        await message.answer(result_text, reply_markup=types.ReplyKeyboardRemove())
        await state.clear()
    
    async def _generate_instruction(self, fields: Dict) -> str:
        with open("src/prompts/instruction_generator.txt", "r") as f:
            template = f.read()
        
        prompt = PromptTemplate(
            input_variables=["fields"],
            template=template
        )
        
        response = await self.llm.ainvoke(prompt.format(fields=fields))
        return response.content
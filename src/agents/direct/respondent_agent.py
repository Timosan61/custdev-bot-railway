from typing import Dict, Optional, List
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from loguru import logger

from src.agents.base import BaseRespondentAgent
from src.services.supabase_service import SupabaseService
from src.services.zep_service import ZepService


class DirectRespondentAgent(BaseRespondentAgent):
    """Direct implementation of RespondentAgent using OpenAI API directly"""
    
    def __init__(self, supabase: SupabaseService, zep: ZepService):
        super().__init__(supabase, zep)
        self.llm = ChatOpenAI(model_name="gpt-4o", temperature=0.7)
    
    async def generate_first_question(self, instruction: str) -> str:
        """Генерирует первый вопрос для респондента используя прямой вызов LLM"""
        # Extract style and target from instruction for better question generation
        style = "friendly"  # default
        target = ""
        
        # Simple extraction from instruction text
        if "дружелюб" in instruction.lower():
            style = "friendly"
        elif "нейтрал" in instruction.lower() or "делов" in instruction.lower():
            style = "neutral"
        elif "эксперт" in instruction.lower():
            style = "expert"
        
        with open("src/prompts/first_question_generator.txt", "r") as f:
            template = f.read()
        
        prompt = PromptTemplate(
            input_variables=["instruction", "style", "target"],
            template=template
        )
        
        response = await self.llm.ainvoke(
            prompt.format(
                instruction=instruction,
                style=style,
                target=target
            )
        )
        return response.content.strip()
    
    async def generate_next_question(self, instruction: str, answers: Dict, history: List) -> Optional[str]:
        """Генерирует следующий вопрос на основе контекста используя прямой вызов LLM"""
        # Ensure minimum 8 questions before allowing finish
        answers_count = len(answers)
        if answers_count < 8:
            logger.info(f"Only {answers_count} questions asked, forcing continuation (minimum 8)")
        
        # No limit on questions - interview continues until user asks to stop
        
        history_text = "\n".join([
            f"{msg.role}: {msg.content}" 
            for msg in history[-6:]  # Last 3 exchanges
        ])
        
        # Extract style from instruction
        style = "friendly"  # default
        if "дружелюб" in instruction.lower():
            style = "friendly"
        elif "нейтрал" in instruction.lower() or "делов" in instruction.lower():
            style = "neutral"
        elif "эксперт" in instruction.lower():
            style = "expert"
        
        with open("src/prompts/next_question_generator.txt", "r") as f:
            template = f.read()
        
        prompt = PromptTemplate(
            input_variables=["instruction", "history", "questions_count", "style"],
            template=template
        )
        
        response = await self.llm.ainvoke(
            prompt.format(
                instruction=instruction,
                history=history_text,
                questions_count=len(answers),
                style=style
            )
        )
        
        content = response.content.strip()
        
        # Дополнительная защита: если задано менее 8 вопросов, никогда не заканчиваем
        if answers_count < 8 and content.upper() == "FINISH":
            logger.warning(f"LLM tried to finish after only {answers_count} questions, forcing continuation")
            # Генерируем простой follow-up вопрос
            return "Расскажите подробнее об этом. Что еще важно знать?"
        
        # Убираем проверку на FINISH - интервью заканчивается только когда пользователь говорит "хватит"
        return content
    
    async def generate_summary(self, answers: Dict) -> str:
        """Генерирует резюме интервью используя прямой вызов LLM"""
        answers_count = len(answers)
        
        if answers_count == 0:
            return "Респондент не ответил ни на один вопрос."
        elif answers_count < 3:
            return f"Респондент ответил только на {answers_count} вопрос(а) и завершил интервью досрочно."
        
        qa_text = "\n\n".join([
            f"Вопрос: {q}\nОтвет: {a}" 
            for q, a in answers.items()
        ])
        
        with open("src/prompts/interview_summary_generator.txt", "r") as f:
            template = f.read()
        
        prompt = PromptTemplate(
            input_variables=["qa_text", "answers_count"],
            template=template
        )
        
        response = await self.llm.ainvoke(prompt.format(qa_text=qa_text, answers_count=answers_count))
        return response.content
from typing import Dict, Optional, List
import os
import aiohttp
from loguru import logger

from src.agents.base import BaseRespondentAgent
from src.services.supabase_service import SupabaseService
from src.services.zep_service import ZepService


class AIRespondentAgent(BaseRespondentAgent):
    """n8n workflow implementation of RespondentAgent"""
    
    def __init__(self, supabase: SupabaseService, zep: ZepService):
        super().__init__(supabase, zep)
        self.n8n_webhook_url = os.getenv("N8N_WEBHOOK_URL", "").rstrip("/")
        self.n8n_api_key = os.getenv("N8N_API_KEY", "")
        
        if not self.n8n_webhook_url:
            raise ValueError("N8N_WEBHOOK_URL not configured")
    
    async def _call_ai_orchestrator(self, data: Dict) -> Dict:
        """Call AI orchestrator in n8n"""
        url = f"{self.n8n_webhook_url}-ai/respondent"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.n8n_api_key}"
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=data, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        logger.error(f"N8n AI webhook error: {response.status} - {error_text}")
                        raise Exception(f"N8n webhook returned {response.status}")
            except Exception as e:
                logger.error(f"Error calling n8n AI webhook: {e}")
                raise
    
    async def generate_first_question(self, instruction: str) -> str:
        """Генерирует первый вопрос через AI orchestrator"""
        try:
            response = await self._call_ai_orchestrator({
                "type": "start_interview",
                "instruction": instruction,
                "question_count": 0,
                "session_id": self.current_session_id
            })
            
            return response.get("next_question", "Расскажите о себе и вашем опыте.")
        except Exception as e:
            logger.error(f"Error in generate_first_question via AI: {e}")
            return "Расскажите, пожалуйста, немного о себе и вашем опыте."
    
    async def generate_next_question(self, instruction: str, answers: Dict, history: List) -> Optional[str]:
        """Генерирует следующий вопрос через AI orchestrator"""
        try:
            # Подготовка данных для AI
            response = await self._call_ai_orchestrator({
                "type": "continue_interview",
                "instruction": instruction,
                "question_count": len(answers),
                "max_questions": self.max_questions,
                "last_answer": list(answers.values())[-1] if answers else "",
                "session_id": self.current_session_id
            })
            
            # Проверяем, нужно ли продолжать
            if not response.get("continue_interview", True):
                return None
                
            return response.get("next_question")
            
        except Exception as e:
            logger.error(f"Error in generate_next_question via AI: {e}")
            # Fallback логика
            if len(answers) < 8:
                return "Расскажите подробнее об этом аспекте."
            return None
    
    async def generate_summary(self, answers: Dict) -> str:
        """Генерирует резюме интервью через AI orchestrator"""
        try:
            answers_count = len(answers)
            
            if answers_count == 0:
                return "Респондент не ответил ни на один вопрос."
            
            # Подготовка данных для AI
            qa_pairs = [{"question": q, "answer": a} for q, a in answers.items()]
            
            response = await self._call_ai_orchestrator({
                "type": "create_summary",
                "qa_pairs": qa_pairs,
                "answers_count": answers_count,
                "session_id": self.current_session_id
            })
            
            return response.get("final_message", self._generate_fallback_summary(answers))
            
        except Exception as e:
            logger.error(f"Error in generate_summary via AI: {e}")
            return self._generate_fallback_summary(answers)
    
    def _generate_fallback_summary(self, answers: Dict) -> str:
        """Генерирует простое резюме в случае ошибки"""
        answers_count = len(answers)
        
        if answers_count < 3:
            return f"Респондент ответил только на {answers_count} вопрос(а)."
        
        # Берем первые ответы для базового резюме
        summary_parts = []
        for i, (q, a) in enumerate(list(answers.items())[:3]):
            summary_parts.append(f"- {q}: {a[:100]}...")
            
        return f"""
Интервью завершено. Респондент ответил на {answers_count} вопросов.

Ключевые моменты:
{chr(10).join(summary_parts)}

Полное резюме будет создано с помощью AI.
"""
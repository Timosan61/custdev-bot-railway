from typing import Dict, Optional, List
import os
import aiohttp
from loguru import logger

from src.agents.base import BaseRespondentAgent
from src.services.supabase_service import SupabaseService
from src.services.zep_service import ZepService


class N8nRespondentAgent(BaseRespondentAgent):
    """N8n implementation of RespondentAgent using webhook calls"""
    
    def __init__(self, supabase: SupabaseService, zep: ZepService):
        super().__init__(supabase, zep)
        self.n8n_webhook_url = os.getenv("N8N_WEBHOOK_URL", "").rstrip("/")
        self.n8n_api_key = os.getenv("N8N_API_KEY", "")
        
        if not self.n8n_webhook_url:
            raise ValueError("N8N_WEBHOOK_URL not configured")
    
    async def _call_n8n_webhook(self, operation: str, data: Dict) -> Dict:
        """Make HTTP request to unified n8n webhook"""
        url = f"{self.n8n_webhook_url}/respondent"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.n8n_api_key}"
        }
        
        payload = {
            "operation": operation,
            "data": data
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("result", {})
                    else:
                        error_text = await response.text()
                        logger.error(f"N8n webhook error: {response.status} - {error_text}")
                        raise Exception(f"N8n webhook returned {response.status}")
            except Exception as e:
                logger.error(f"Error calling n8n webhook: {e}")
                raise
    
    async def generate_first_question(self, instruction: str) -> str:
        """Генерирует первый вопрос через n8n webhook"""
        try:
            # Extract style from instruction
            style = self._extract_style(instruction)
            
            response = await self._call_n8n_webhook("generate_first_question", {
                "instruction": instruction,
                "style": style
            })
            
            return response.get("question", "Расскажите немного о себе и вашем опыте.")
        except Exception as e:
            logger.error(f"Error in generate_first_question via n8n: {e}")
            return "Расскажите, пожалуйста, немного о себе и вашем опыте в данной области."
    
    async def generate_next_question(self, instruction: str, answers: Dict, history: List) -> Optional[str]:
        """Генерирует следующий вопрос через n8n webhook"""
        try:
            # Extract style from instruction
            style = self._extract_style(instruction)
            
            # Format history for n8n
            history_text = "\n".join([
                f"{msg.role}: {msg.content}" 
                for msg in history[-6:]  # Last 3 exchanges
            ])
            
            response = await self._call_n8n_webhook("generate_next_question", {
                "instruction": instruction,
                "answers_count": len(answers),
                "history": history_text,
                "style": style
            })
            
            question = response.get("question")
            
            # Ensure minimum 8 questions
            if len(answers) < 8 and not question:
                return "Расскажите подробнее об этом. Что еще важно знать?"
            
            return question
        except Exception as e:
            logger.error(f"Error in generate_next_question via n8n: {e}")
            # Fallback question
            if len(answers) < 8:
                return "Расскажите подробнее. Какие еще аспекты важно учесть?"
            return "Что еще вы хотели бы добавить по этой теме?"
    
    async def generate_summary(self, answers: Dict) -> str:
        """Генерирует резюме интервью через n8n webhook"""
        try:
            answers_count = len(answers)
            
            if answers_count == 0:
                return "Респондент не ответил ни на один вопрос."
            elif answers_count < 3:
                return f"Респондент ответил только на {answers_count} вопрос(а) и завершил интервью досрочно."
            
            # Format Q&A for n8n
            qa_pairs = [{"question": q, "answer": a} for q, a in answers.items()]
            
            response = await self._call_n8n_webhook("generate_summary", {
                "qa_pairs": qa_pairs,
                "answers_count": answers_count
            })
            
            return response.get("summary", self._generate_fallback_summary(answers))
        except Exception as e:
            logger.error(f"Error in generate_summary via n8n: {e}")
            return self._generate_fallback_summary(answers)
    
    def _extract_style(self, instruction: str) -> str:
        """Извлекает стиль общения из инструкции"""
        instruction_lower = instruction.lower()
        
        if "дружелюб" in instruction_lower:
            return "friendly"
        elif "нейтрал" in instruction_lower or "делов" in instruction_lower:
            return "neutral"
        elif "эксперт" in instruction_lower:
            return "expert"
        else:
            return "friendly"
    
    def _generate_fallback_summary(self, answers: Dict) -> str:
        """Генерирует простое резюме в случае ошибки"""
        answers_count = len(answers)
        
        # Take first few answers for basic summary
        summary_parts = []
        for i, (q, a) in enumerate(list(answers.items())[:3]):
            summary_parts.append(f"- На вопрос '{q}' ответил: {a[:100]}...")
            
        return f"""
Респондент ответил на {answers_count} вопросов.

Основные моменты:
{chr(10).join(summary_parts)}

Полные ответы сохранены в базе данных.
"""
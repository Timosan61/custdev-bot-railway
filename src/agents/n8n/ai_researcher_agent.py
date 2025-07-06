from typing import Dict
import os
import aiohttp
import json
from loguru import logger

from src.agents.base import BaseResearcherAgent
from src.services.supabase_service import SupabaseService
from src.services.zep_service import ZepService


class AIResearcherAgent(BaseResearcherAgent):
    """n8n workflow implementation of ResearcherAgent"""
    
    def __init__(self, supabase: SupabaseService, zep: ZepService):
        super().__init__(supabase, zep)
        self.n8n_webhook_url = os.getenv("N8N_WEBHOOK_URL", "").rstrip("/")
        self.n8n_api_key = os.getenv("N8N_API_KEY", "")
        
        if not self.n8n_webhook_url:
            raise ValueError("N8N_WEBHOOK_URL not configured")
    
    async def _call_ai_orchestrator(self, data: Dict) -> Dict:
        """Call AI orchestrator in n8n"""
        url = f"{self.n8n_webhook_url}-ai/research"
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
    
    async def evaluate_answer_quality(self, field: str, answer: str) -> Dict:
        """Оценивает качество ответа через AI orchestrator"""
        try:
            response = await self._call_ai_orchestrator({
                "type": "evaluate_answer",
                "field": field,
                "answer": answer,
                "question": self.static_questions.get(field, ""),
                "field_description": self._get_field_description(field)
            })
            
            result = response.get("result", {})
            return {
                "is_complete": result.get("field_complete", False),
                "confidence": result.get("score", 0) / 10,
                "missing_aspects": result.get("missing_aspects", []),
                "extracted_value": answer if result.get("field_complete") else None,
                "feedback": result.get("feedback", "")
            }
        except Exception as e:
            logger.error(f"Error in evaluate_answer_quality via AI: {e}")
            return {
                "is_complete": False,
                "confidence": 0.0,
                "missing_aspects": ["Ошибка при анализе"],
                "extracted_value": None
            }
    
    async def generate_clarification(self, field: str, answer: str, missing_aspects: list) -> str:
        """Генерирует уточняющий вопрос через AI orchestrator"""
        try:
            response = await self._call_ai_orchestrator({
                "type": "generate_clarification",
                "field": field,
                "answer": answer,
                "missing_aspects": missing_aspects
            })
            
            return response.get("next_message", "Пожалуйста, уточните ваш ответ.")
        except Exception as e:
            logger.error(f"Error in generate_clarification via AI: {e}")
            return "Пожалуйста, расскажите подробнее."
    
    async def generate_interview_brief(self, fields: Dict) -> str:
        """Генерирует интервью-бриф через AI orchestrator"""
        try:
            response = await self._call_ai_orchestrator({
                "type": "generate_brief",
                "fields": fields
            })
            
            return response.get("result", {}).get("brief", self._generate_fallback_brief(fields))
        except Exception as e:
            logger.error(f"Error in generate_interview_brief via AI: {e}")
            return self._generate_fallback_brief(fields)
    
    async def generate_instruction(self, fields: Dict) -> str:
        """Генерирует инструкцию для респондентов через AI orchestrator"""
        try:
            response = await self._call_ai_orchestrator({
                "type": "generate_instruction",
                "fields": fields
            })
            
            return response.get("result", {}).get("instruction", "Добро пожаловать на интервью!")
        except Exception as e:
            logger.error(f"Error in generate_instruction via AI: {e}")
            return "Добро пожаловать на интервью! Отвечайте честно и подробно."
    
    def _get_field_description(self, field: str) -> str:
        """Получить описание поля"""
        descriptions = {
            "name": "Имя или обращение к исследователю",
            "industry": "Сфера деятельности или ниша бизнеса",
            "target": "Целевая аудитория или объект исследования",
            "hypotheses": "Конкретные гипотезы для проверки",
            "style": "Стиль общения с респондентами",
            "success_metric": "Метрики успеха исследования",
            "constraints": "Ограничения и требования",
            "existing_data": "Существующие данные или исследования"
        }
        return descriptions.get(field, "")
    
    def _generate_fallback_brief(self, fields: Dict) -> str:
        """Генерирует простой бриф в случае ошибки"""
        return f"""
# Интервью-бриф

**Исследователь:** {fields.get('name', 'Не указано')}
**Сфера:** {fields.get('industry', 'Не указано')}
**Целевая аудитория:** {fields.get('target', 'Не указано')}
**Гипотезы:** {fields.get('hypotheses', 'Не указано')}

Интервью создано с помощью AI.
"""
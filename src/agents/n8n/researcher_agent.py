from typing import Dict
import os
import aiohttp
import json
from loguru import logger

from src.agents.base import BaseResearcherAgent
from src.services.supabase_service import SupabaseService
from src.services.zep_service import ZepService


class N8nResearcherAgent(BaseResearcherAgent):
    """N8n implementation of ResearcherAgent using webhook calls"""
    
    def __init__(self, supabase: SupabaseService, zep: ZepService):
        super().__init__(supabase, zep)
        self.n8n_webhook_url = os.getenv("N8N_WEBHOOK_URL", "").rstrip("/")
        self.n8n_api_key = os.getenv("N8N_API_KEY", "")
        
        if not self.n8n_webhook_url:
            raise ValueError("N8N_WEBHOOK_URL not configured")
    
    async def _call_n8n_webhook(self, operation: str, data: Dict) -> Dict:
        """Make HTTP request to unified n8n webhook"""
        url = f"{self.n8n_webhook_url}/researcher"
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
    
    async def evaluate_answer_quality(self, field: str, answer: str) -> Dict:
        """Оценивает качество ответа через n8n webhook"""
        try:
            response = await self._call_n8n_webhook("analyze_answer", {
                "field": field,
                "answer": answer,
                "question": self.static_questions.get(field, ""),
                "field_description": self._get_field_description(field)
            })
            
            return response or {
                "is_complete": False,
                "confidence": 0.0,
                "missing_aspects": ["Не удалось проанализировать ответ"],
                "extracted_value": None
            }
        except Exception as e:
            logger.error(f"Error in evaluate_answer_quality via n8n: {e}")
            return {
                "is_complete": False,
                "confidence": 0.0,
                "missing_aspects": ["Ошибка при анализе через n8n"],
                "extracted_value": None
            }
    
    async def generate_clarification(self, field: str, answer: str, missing_aspects: list) -> str:
        """Генерирует уточняющий вопрос через n8n webhook"""
        try:
            response = await self._call_n8n_webhook("generate_clarification", {
                "field": field,
                "original_question": self.static_questions[field],
                "answer": answer,
                "missing_aspects": missing_aspects
            })
            
            return response.get("clarification", "Не удалось сгенерировать уточнение. Пожалуйста, попробуйте ответить более подробно.")
        except Exception as e:
            logger.error(f"Error in generate_clarification via n8n: {e}")
            return "Пожалуйста, уточните ваш ответ."
    
    async def generate_interview_brief(self, fields: Dict) -> str:
        """Генерирует интервью-бриф через n8n webhook"""
        try:
            response = await self._call_n8n_webhook("generate_brief", {
                "fields": fields
            })
            
            return response.get("brief", "Не удалось сгенерировать бриф.")
        except Exception as e:
            logger.error(f"Error in generate_interview_brief via n8n: {e}")
            # Fallback to basic brief
            return self._generate_fallback_brief(fields)
    
    async def generate_instruction(self, fields: Dict) -> str:
        """Генерирует инструкцию для респондентов через n8n webhook"""
        try:
            response = await self._call_n8n_webhook("generate_instruction", {
                "fields": fields
            })
            
            return response.get("instruction", "Добро пожаловать на интервью!")
        except Exception as e:
            logger.error(f"Error in generate_instruction via n8n: {e}")
            return "Добро пожаловать на интервью! Отвечайте на вопросы честно и подробно."
    
    def _get_field_description(self, field: str) -> str:
        """Получить описание поля"""
        descriptions = {
            "name": "Имя или обращение к исследователю",
            "industry": "Сфера деятельности или ниша бизнеса",
            "target": "Целевая аудитория или объект исследования с конкретными характеристиками",
            "hypotheses": "Конкретные гипотезы в формате если...то...",
            "style": "Стиль общения с респондентами",
            "success_metric": "Метрики успеха исследования",
            "constraints": "Ограничения по времени, темам или другие требования",
            "existing_data": "Информация о существующих данных или исследованиях"
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
**Стиль общения:** {fields.get('style', 'Не указано')}

### Первое сообщение респонденту:
Добро пожаловать на интервью! Мы изучаем {fields.get('industry', 'вашу сферу')}.
"""
from typing import Dict
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from loguru import logger
import json

from src.agents.base import BaseResearcherAgent
from src.services.supabase_service import SupabaseService
from src.services.zep_service import ZepService


class DirectResearcherAgent(BaseResearcherAgent):
    """Direct implementation of ResearcherAgent using OpenAI API directly"""
    
    def __init__(self, supabase: SupabaseService, zep: ZepService):
        super().__init__(supabase, zep)
        self.llm = ChatOpenAI(model_name="gpt-4o", temperature=0.7)
    
    async def evaluate_answer_quality(self, field: str, answer: str) -> Dict:
        """Оценивает качество ответа на вопрос используя прямой вызов LLM"""
        with open("src/prompts/field_analyzer.txt", "r") as f:
            template = f.read()
        
        prompt = PromptTemplate(
            input_variables=["field_name", "field_description", "question", "answer"],
            template=template
        )
        
        field_description = {
            "name": "Имя или обращение к исследователю",
            "industry": "Сфера деятельности или ниша бизнеса",
            "target": "Целевая аудитория или объект исследования с конкретными характеристиками",
            "hypotheses": "Конкретные гипотезы в формате если...то...",
            "style": "Стиль общения с респондентами",
            "success_metric": "Метрики успеха исследования",
            "constraints": "Ограничения по времени, темам или другие требования",
            "existing_data": "Информация о существующих данных или исследованиях"
        }
        
        try:
            response = await self.llm.ainvoke(
                prompt.format(
                    field_name=field,
                    field_description=field_description.get(field, ""),
                    question=self.static_questions.get(field, ""),
                    answer=answer
                )
            )
            
            # Parse JSON response
            content = response.content.strip()
            logger.debug(f"LLM response for {field}: {content[:200]}...")
            
            # Clean up the response - remove markdown code blocks
            if content.startswith("```json") and content.endswith("```"):
                content = content[7:-3].strip()
            elif content.startswith("```") and content.endswith("```"):
                content = content[3:-3].strip()
            
            # Additional cleanup for common LLM formatting issues
            content = content.strip()
            
            # If content doesn't start with { or [, try to find JSON object
            if not content.startswith('{') and not content.startswith('['):
                # Try to find the first { and extract from there
                json_start = content.find('{')
                if json_start != -1:
                    content = content[json_start:]
                    logger.warning(f"Extracted JSON from position {json_start}")
            
            result = json.loads(content)
            logger.debug(f"Parsed result for {field}: {result}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in evaluate_answer_quality: {e}")
            logger.error(f"Response content: {content[:200]}...")
            # При ошибке парсинга JSON не принимаем ответ автоматически
            return {
                "is_complete": False,
                "confidence": 0.0,
                "missing_aspects": ["Не удалось проанализировать ответ"],
                "extracted_value": None
            }
        except Exception as e:
            logger.error(f"Error evaluating answer quality: {e}")
            logger.error(f"Original response content: {repr(response.content) if 'response' in locals() else 'No response'}")
            # При других ошибках тоже не принимаем ответ автоматически
            return {
                "is_complete": False,
                "confidence": 0.0,
                "missing_aspects": ["Произошла ошибка при анализе"],
                "extracted_value": None
            }
    
    async def generate_clarification(self, field: str, answer: str, missing_aspects: list) -> str:
        """Генерирует уточняющий вопрос используя прямой вызов LLM"""
        with open("src/prompts/clarification_generator.txt", "r") as f:
            template = f.read()
        
        prompt = PromptTemplate(
            input_variables=["field_name", "original_question", "answer", "missing_aspects", "conversation_history"],
            template=template
        )
        
        response = await self.llm.ainvoke(
            prompt.format(
                field_name=field,
                original_question=self.static_questions[field],
                answer=answer,
                missing_aspects=missing_aspects,
                conversation_history=""  # Can be enhanced with actual history
            )
        )
        
        return response.content.strip()
    
    async def generate_interview_brief(self, fields: Dict) -> str:
        """Генерирует интервью-бриф на основе собранных данных используя прямой вызов LLM"""
        with open("src/prompts/interview_brief_generator.txt", "r") as f:
            template = f.read()
        
        prompt = PromptTemplate(
            input_variables=["answers"],
            template=template
        )
        
        # Just pass the fields as they are, let the LLM handle formatting
        response = await self.llm.ainvoke(
            prompt.format(answers=json.dumps(fields, ensure_ascii=False, indent=2))
        )
        
        return response.content
    
    async def generate_instruction(self, fields: Dict) -> str:
        """Генерирует инструкцию для респондентов используя прямой вызов LLM"""
        with open("src/prompts/instruction_generator.txt", "r") as f:
            template = f.read()
        
        prompt = PromptTemplate(
            input_variables=["fields"],
            template=template
        )
        
        response = await self.llm.ainvoke(prompt.format(fields=fields))
        return response.content
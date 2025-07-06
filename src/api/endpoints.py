from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
from loguru import logger
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
import json

# Create router
router = APIRouter()

# Initialize LLM (will be used by n8n endpoints)
llm = ChatOpenAI(model_name="gpt-4o", temperature=0.7)


# Request/Response models
class AnalyzeAnswerRequest(BaseModel):
    field: str
    answer: str
    question: str
    field_description: str


class AnalyzeAnswerResponse(BaseModel):
    result: Dict


class GenerateClarificationRequest(BaseModel):
    field: str
    original_question: str
    answer: str
    missing_aspects: List[str]


class GenerateClarificationResponse(BaseModel):
    clarification: str


class GenerateBriefRequest(BaseModel):
    fields: Dict


class GenerateBriefResponse(BaseModel):
    brief: str


class GenerateInstructionRequest(BaseModel):
    fields: Dict


class GenerateInstructionResponse(BaseModel):
    instruction: str


class GenerateFirstQuestionRequest(BaseModel):
    instruction: str
    style: str


class GenerateFirstQuestionResponse(BaseModel):
    question: str


class GenerateNextQuestionRequest(BaseModel):
    instruction: str
    answers_count: int
    history: str
    style: str


class GenerateNextQuestionResponse(BaseModel):
    question: Optional[str]


class GenerateSummaryRequest(BaseModel):
    qa_pairs: List[Dict[str, str]]
    answers_count: int


class GenerateSummaryResponse(BaseModel):
    summary: str


# Endpoints for ResearcherAgent
@router.post("/analyze-answer", response_model=AnalyzeAnswerResponse)
async def analyze_answer(request: AnalyzeAnswerRequest):
    """Analyze answer quality for researcher"""
    try:
        with open("src/prompts/field_analyzer.txt", "r") as f:
            template = f.read()
        
        prompt = PromptTemplate(
            input_variables=["field_name", "field_description", "question", "answer"],
            template=template
        )
        
        response = await llm.ainvoke(
            prompt.format(
                field_name=request.field,
                field_description=request.field_description,
                question=request.question,
                answer=request.answer
            )
        )
        
        # Parse JSON response
        content = response.content.strip()
        
        # Clean up the response
        if content.startswith("```json") and content.endswith("```"):
            content = content[7:-3].strip()
        elif content.startswith("```") and content.endswith("```"):
            content = content[3:-3].strip()
        
        result = json.loads(content)
        return AnalyzeAnswerResponse(result=result)
        
    except Exception as e:
        logger.error(f"Error in analyze_answer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-clarification", response_model=GenerateClarificationResponse)
async def generate_clarification(request: GenerateClarificationRequest):
    """Generate clarification question for researcher"""
    try:
        with open("src/prompts/clarification_generator.txt", "r") as f:
            template = f.read()
        
        prompt = PromptTemplate(
            input_variables=["field_name", "original_question", "answer", "missing_aspects", "conversation_history"],
            template=template
        )
        
        response = await llm.ainvoke(
            prompt.format(
                field_name=request.field,
                original_question=request.original_question,
                answer=request.answer,
                missing_aspects=request.missing_aspects,
                conversation_history=""
            )
        )
        
        return GenerateClarificationResponse(clarification=response.content.strip())
        
    except Exception as e:
        logger.error(f"Error in generate_clarification: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-brief", response_model=GenerateBriefResponse)
async def generate_brief(request: GenerateBriefRequest):
    """Generate interview brief"""
    try:
        with open("src/prompts/interview_brief_generator.txt", "r") as f:
            template = f.read()
        
        prompt = PromptTemplate(
            input_variables=["answers"],
            template=template
        )
        
        response = await llm.ainvoke(
            prompt.format(answers=json.dumps(request.fields, ensure_ascii=False, indent=2))
        )
        
        return GenerateBriefResponse(brief=response.content)
        
    except Exception as e:
        logger.error(f"Error in generate_brief: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-instruction", response_model=GenerateInstructionResponse)
async def generate_instruction(request: GenerateInstructionRequest):
    """Generate instruction for respondents"""
    try:
        with open("src/prompts/instruction_generator.txt", "r") as f:
            template = f.read()
        
        prompt = PromptTemplate(
            input_variables=["fields"],
            template=template
        )
        
        response = await llm.ainvoke(prompt.format(fields=request.fields))
        
        return GenerateInstructionResponse(instruction=response.content)
        
    except Exception as e:
        logger.error(f"Error in generate_instruction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Endpoints for RespondentAgent
@router.post("/generate-first-question", response_model=GenerateFirstQuestionResponse)
async def generate_first_question(request: GenerateFirstQuestionRequest):
    """Generate first question for respondent"""
    try:
        with open("src/prompts/first_question_generator.txt", "r") as f:
            template = f.read()
        
        prompt = PromptTemplate(
            input_variables=["instruction", "style", "target"],
            template=template
        )
        
        response = await llm.ainvoke(
            prompt.format(
                instruction=request.instruction,
                style=request.style,
                target=""
            )
        )
        
        return GenerateFirstQuestionResponse(question=response.content.strip())
        
    except Exception as e:
        logger.error(f"Error in generate_first_question: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-next-question", response_model=GenerateNextQuestionResponse)
async def generate_next_question(request: GenerateNextQuestionRequest):
    """Generate next question for respondent"""
    try:
        with open("src/prompts/next_question_generator.txt", "r") as f:
            template = f.read()
        
        prompt = PromptTemplate(
            input_variables=["instruction", "history", "questions_count", "style"],
            template=template
        )
        
        response = await llm.ainvoke(
            prompt.format(
                instruction=request.instruction,
                history=request.history,
                questions_count=request.answers_count,
                style=request.style
            )
        )
        
        content = response.content.strip()
        
        # Check for minimum questions
        if request.answers_count < 8 and content.upper() == "FINISH":
            return GenerateNextQuestionResponse(question="Расскажите подробнее об этом. Что еще важно знать?")
        
        return GenerateNextQuestionResponse(question=content)
        
    except Exception as e:
        logger.error(f"Error in generate_next_question: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-summary", response_model=GenerateSummaryResponse)
async def generate_summary(request: GenerateSummaryRequest):
    """Generate interview summary"""
    try:
        qa_text = "\n\n".join([
            f"Вопрос: {pair['question']}\nОтвет: {pair['answer']}" 
            for pair in request.qa_pairs
        ])
        
        with open("src/prompts/interview_summary_generator.txt", "r") as f:
            template = f.read()
        
        prompt = PromptTemplate(
            input_variables=["qa_text", "answers_count"],
            template=template
        )
        
        response = await llm.ainvoke(
            prompt.format(qa_text=qa_text, answers_count=request.answers_count)
        )
        
        return GenerateSummaryResponse(summary=response.content)
        
    except Exception as e:
        logger.error(f"Error in generate_summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
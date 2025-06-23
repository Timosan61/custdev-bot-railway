from aiogram import Router, types, F, Bot
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from loguru import logger
from typing import Dict, Any

from src.agents.researcher_agent import ResearcherAgent
from src.agents.respondent_agent import RespondentAgent
from src.state.user_states import ResearcherStates, RespondentStates
from src.utils.keyboards import get_main_menu_keyboard, get_cancel_keyboard

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext, bot: Bot, **kwargs):
    args = message.text.split()
    
    # Check if user came with interview link
    if len(args) > 1 and args[1].startswith("interview_"):
        interview_id = args[1].replace("interview_", "")
        await start_respondent_interview(message, state, interview_id, **kwargs)
    else:
        await show_main_menu(message, state, **kwargs)

async def show_main_menu(message: types.Message, state: FSMContext, **kwargs):
    await state.clear()
    text = (
        "👋 <b>Добро пожаловать в Кастдев-бот!</b>\n\n"
        "Я помогу вам провести кастдев-интервью:\n"
        "• 🔬 <b>Исследователь</b> - создать новое исследование\n"
        "• 📊 <b>Респондент</b> - пройти интервью\n\n"
        "Выберите, что вы хотите сделать:"
    )
    await message.answer(text, reply_markup=get_main_menu_keyboard())

async def start_respondent_interview(message: types.Message, state: FSMContext, interview_id: str, bot: Bot, **kwargs):
    logger.info(f"Starting respondent interview: {interview_id}")
    supabase = kwargs.get("supabase")
    
    # Get interview data
    interview = supabase.get_interview(interview_id)
    if not interview or interview["status"] != "in_progress":
        await message.answer("❌ Интервью не найдено или уже завершено")
        await show_main_menu(message, state, **kwargs)
        return
    
    # Initialize respondent agent
    agent = RespondentAgent(kwargs.get("supabase"), kwargs.get("zep"))
    await state.update_data(agent=agent, interview_id=interview_id)
    await state.set_state(RespondentStates.answering)
    
    # Start interview
    await agent.start_interview(message, state, interview_id)

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        "📖 <b>Помощь по использованию бота</b>\n\n"
        "<b>Для исследователей:</b>\n"
        "1. Нажмите 'Создать исследование'\n"
        "2. Ответьте на вопросы бота\n"
        "3. Получите ссылку для респондентов\n\n"
        "<b>Для респондентов:</b>\n"
        "1. Перейдите по ссылке от исследователя\n"
        "2. Отвечайте на вопросы\n"
        "3. Используйте кнопки для навигации\n\n"
        "<b>Команды:</b>\n"
        "/start - главное меню\n"
        "/help - эта справка\n"
        "/cancel - отменить текущее действие"
    )
    await message.answer(help_text)

@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нечего отменять")
        return
    
    await state.clear()
    await message.answer("❌ Действие отменено", reply_markup=types.ReplyKeyboardRemove())
    await show_main_menu(message, state)

@router.message(F.text == "🔬 Создать исследование")
async def start_research(message: types.Message, state: FSMContext, **kwargs):
    logger.info(f"User {message.from_user.id} starting new research")
    
    # Initialize researcher agent
    agent = ResearcherAgent(kwargs.get("supabase"), kwargs.get("zep"))
    await state.update_data(agent=agent)
    await state.set_state(ResearcherStates.collecting_info)
    
    # Start research dialog
    await agent.start_dialog(message, state)

@router.message(F.text == "📊 Мои исследования")
async def show_my_researches(message: types.Message, **kwargs):
    supabase = kwargs.get("supabase")
    # This feature can be implemented later
    await message.answer("🚧 Эта функция будет доступна в следующей версии")

@router.message(ResearcherStates.collecting_info)
async def process_researcher_message(message: types.Message, state: FSMContext, **kwargs):
    data = await state.get_data()
    agent: ResearcherAgent = data.get("agent")
    
    if not agent:
        await state.clear()
        await show_main_menu(message, state, **kwargs)
        return
    
    # Process message (text or voice)
    if message.voice:
        await agent.process_voice_message(message, state, message.bot)
    else:
        await agent.process_text_message(message, state)

@router.message(RespondentStates.answering)
async def process_respondent_message(message: types.Message, state: FSMContext, **kwargs):
    data = await state.get_data()
    agent: RespondentAgent = data.get("agent")
    
    if not agent:
        await state.clear()
        await show_main_menu(message, state, **kwargs)
        return
    
    # Process answer
    if message.voice:
        await agent.process_voice_message(message, state, message.bot)
    else:
        await agent.process_text_message(message, state)

@router.message()
async def echo_handler(message: types.Message):
    await message.answer("Используйте /start для начала работы")
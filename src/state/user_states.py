from aiogram.fsm.state import State, StatesGroup

class ResearcherStates(StatesGroup):
    collecting_info = State()
    reviewing_instruction = State()
    finished = State()

class RespondentStates(StatesGroup):
    answering = State()
    reviewing_answer = State()
    finished = State()
from aiogram import types

def get_main_menu_keyboard() -> types.ReplyKeyboardMarkup:
    keyboard = [
        [types.KeyboardButton(text="🔬 Создать исследование")],
        [types.KeyboardButton(text="📊 Мои исследования")]
    ]
    return types.ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )

def get_cancel_keyboard() -> types.ReplyKeyboardMarkup:
    keyboard = [
        [types.KeyboardButton(text="❌ Отмена")]
    ]
    return types.ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )

# Removed get_finish_keyboard function as per requirement

def get_respondent_keyboard() -> types.ReplyKeyboardMarkup:
    keyboard = [
        [types.KeyboardButton(text="⏭ Пропустить вопрос")],
        [types.KeyboardButton(text="◀️ Назад")],
        [types.KeyboardButton(text="🛑 Завершить интервью")]
    ]
    return types.ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=False
    )
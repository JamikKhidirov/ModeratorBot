from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Реклама"), KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="❓ Помощь")],
        ],
        resize_keyboard=True,
    )


def admin_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📢 Реклама")],
            [KeyboardButton(text="👥 Пользователи"), KeyboardButton(text="⚙️ Настройки")],
            [KeyboardButton(text="🔙 Назад в меню")],
        ],
        resize_keyboard=True,
    )


def remove_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()

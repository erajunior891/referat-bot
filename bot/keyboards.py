"""
Клавиатуры (InlineKeyboard) для Telegram-бота.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from templates.registry import get_all_templates


def get_template_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора шаблона реферата."""
    buttons = []
    for template in get_all_templates():
        buttons.append([
            InlineKeyboardButton(
                text=template.name,
                callback_data=f"template:{template.id}",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_plan_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура: отправить план или пропустить."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="⏭ Пропустить (без плана)",
                callback_data="skip_plan",
            )
        ]
    ])


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой отмены."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="cancel",
            )
        ]
    ])


def get_new_essay_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после завершения генерации."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📝 Новый реферат",
                callback_data="new_essay",
            )
        ]
    ])

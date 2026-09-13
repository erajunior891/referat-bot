"""
Клавиатуры (InlineKeyboard) для Telegram-бота.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from templates.registry import get_all_templates


def get_language_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора языка реферата."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇰🇿 Қазақша", callback_data="lang:kk"),
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="lang:en"),
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
        ],
    ])


def get_pages_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора объёма реферата в страницах."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="5 страниц", callback_data="pages:5"),
            InlineKeyboardButton(text="8 страниц", callback_data="pages:8"),
        ],
        [
            InlineKeyboardButton(text="10 страниц", callback_data="pages:10"),
            InlineKeyboardButton(text="12 страниц", callback_data="pages:12"),
        ],
        [
            InlineKeyboardButton(text="15 страниц", callback_data="pages:15"),
            InlineKeyboardButton(text="20 страниц", callback_data="pages:20"),
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"),
        ],
    ])


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
    buttons.append([
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
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
        ],
        [
            InlineKeyboardButton(
                text="❌ Отмена",
                callback_data="cancel",
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

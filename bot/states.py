"""
FSM-состояния для диалога с пользователем.
"""

from aiogram.fsm.state import State, StatesGroup


class EssayStates(StatesGroup):
    """Состояния конечного автомата для генерации реферата."""

    # Пользователь выбирает язык (Қазақша / Русский / English)
    choosing_language = State()

    # Пользователь выбирает объём в страницах (5 / 8 / 10 / 12 / 15 / 20)
    choosing_pages = State()

    # Пользователь выбирает шаблон
    choosing_template = State()

    # Пользователь вводит тему реферата
    waiting_topic = State()

    # Пользователь вводит план (опционально)
    waiting_plan = State()

    # Идёт генерация реферата
    generating = State()

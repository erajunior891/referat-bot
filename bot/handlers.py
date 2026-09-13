"""
Обработчики команд и сообщений Telegram-бота.
"""

import asyncio
import logging
import os
from pathlib import Path

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext

from bot.states import EssayStates
from bot.keyboards import (
    get_template_keyboard,
    get_plan_keyboard,
    get_new_essay_keyboard,
)
from templates.registry import get_template
from services.orchestrator import generate_essay

logger = logging.getLogger(__name__)

router = Router()

# Хранилище активных генераций (user_id -> True)
_active_users: set[int] = set()

# Текст приветствия
WELCOME_TEXT = """
🎓 *Привет! Я — бот для генерации рефератов.*

Я помогу тебе создать структурированный реферат на любую тему.

*Как это работает:*
1️⃣ Выбери шаблон оформления
2️⃣ Отправь тему реферата
3️⃣ (Опционально) Укажи план или требования
4️⃣ Получи готовый файл `.docx`

🔍 Я ищу информацию в интернете (DuckDuckGo + Википедия) для повышения качества.
🤖 Текст генерируется локальной нейросетью.

⚠️ *Важно:* бот — помощник для подготовки черновика, а не инструмент для сдачи готовых работ.

Нажми кнопку ниже, чтобы выбрать шаблон и начать! 👇
"""

HELP_TEXT = """
📖 *Справка по использованию*

*Команды:*
/start — Начать работу / Новый реферат
/help — Эта справка
/cancel — Отменить текущую операцию

*Шаблоны:*
📄 *Стандартный школьный* — введение, основная часть (3–4 раздела), заключение, список литературы
🎓 *Вузовский с содержанием* — расширенный реферат с нумерацией глав по ГОСТу

*Советы:*
• Указывай тему конкретно: «Причины Первой мировой войны» лучше, чем «Война»
• Можешь добавить свой план — тогда реферат будет следовать твоей структуре
• Генерация занимает 2–5 минут в зависимости от темы
"""


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start."""
    await state.clear()
    await message.answer(
        WELCOME_TEXT,
        parse_mode="Markdown",
        reply_markup=get_template_keyboard(),
    )
    await state.set_state(EssayStates.choosing_template)


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help."""
    await message.answer(HELP_TEXT, parse_mode="Markdown")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Обработчик команды /cancel."""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нечего отменять. Нажми /start чтобы начать.")
        return

    user_id = message.from_user.id
    _active_users.discard(user_id)
    await state.clear()
    await message.answer(
        "❌ Операция отменена.\n\nНажми /start чтобы начать заново.",
    )


@router.callback_query(F.data == "new_essay")
async def cb_new_essay(callback: CallbackQuery, state: FSMContext):
    """Начать новый реферат."""
    await state.clear()
    await callback.message.answer(
        "Выбери шаблон для нового реферата:",
        reply_markup=get_template_keyboard(),
    )
    await state.set_state(EssayStates.choosing_template)
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена через кнопку."""
    user_id = callback.from_user.id
    _active_users.discard(user_id)
    await state.clear()
    await callback.message.answer(
        "❌ Операция отменена.\n\nНажми /start чтобы начать заново.",
    )
    await callback.answer()


# === Выбор шаблона ===

@router.callback_query(F.data.startswith("template:"), EssayStates.choosing_template)
async def cb_template_selected(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора шаблона."""
    template_id = callback.data.split(":")[1]
    template = get_template(template_id)

    if not template:
        await callback.answer("❌ Шаблон не найден", show_alert=True)
        return

    await state.update_data(template_id=template_id)
    await callback.message.answer(
        f"✅ Выбран шаблон: *{template.name}*\n\n"
        f"_{template.description}_\n\n"
        f"Теперь отправь мне *тему реферата*:",
        parse_mode="Markdown",
    )
    await state.set_state(EssayStates.waiting_topic)
    await callback.answer()


# === Получение темы ===

@router.message(EssayStates.waiting_topic)
async def handle_topic(message: Message, state: FSMContext):
    """Обработчик получения темы реферата."""
    topic = message.text.strip()

    if not topic or len(topic) < 3:
        await message.answer(
            "⚠️ Тема слишком короткая. Пожалуйста, укажи тему подробнее."
        )
        return

    if len(topic) > 500:
        await message.answer(
            "⚠️ Тема слишком длинная (макс. 500 символов). Сократи, пожалуйста."
        )
        return

    await state.update_data(topic=topic)
    await message.answer(
        f"📌 Тема: *{topic}*\n\n"
        f"Теперь можешь отправить *план или особые требования*.\n"
        f"Или нажми кнопку ниже, чтобы пропустить этот шаг.",
        parse_mode="Markdown",
        reply_markup=get_plan_keyboard(),
    )
    await state.set_state(EssayStates.waiting_plan)


# === Получение плана ===

@router.callback_query(F.data == "skip_plan", EssayStates.waiting_plan)
async def cb_skip_plan(callback: CallbackQuery, state: FSMContext, settings=None):
    """Пропуск плана — сразу запуск генерации."""
    await state.update_data(plan=None)
    await callback.answer()
    await _start_generation(callback.message, state, callback.from_user.id, settings)


@router.message(EssayStates.waiting_plan)
async def handle_plan(message: Message, state: FSMContext, settings=None):
    """Обработчик получения плана."""
    plan = message.text.strip()
    await state.update_data(plan=plan)
    await _start_generation(message, state, message.from_user.id, settings)


# === Генерация ===

async def _start_generation(message: Message, state: FSMContext, user_id: int, settings):
    """Запуск процесса генерации реферата."""

    # Проверка на дублирование запросов
    if user_id in _active_users:
        await message.answer(
            "⏳ У тебя уже есть активный запрос. Дождись его завершения или нажми /cancel."
        )
        return

    _active_users.add(user_id)
    await state.set_state(EssayStates.generating)

    data = await state.get_data()
    topic = data["topic"]
    plan = data.get("plan")
    template_id = data["template_id"]

    # Статусное сообщение, которое будем обновлять
    status_msg = await message.answer(
        "⏳ Начинаю генерацию реферата…\n\n"
        f"📌 Тема: {topic}\n"
        f"📋 Шаблон: {get_template(template_id).name}\n"
        f"📄 План: {plan or 'автоматический'}",
    )

    async def update_status(text: str):
        """Обновление статусного сообщения."""
        try:
            await status_msg.edit_text(
                f"{text}\n\n"
                f"📌 Тема: {topic}"
            )
        except Exception:
            pass  # Игнорируем ошибки обновления сообщения

    try:
        # Запускаем генерацию
        doc_path = await generate_essay(
            topic=topic,
            plan=plan,
            template_id=template_id,
            settings=settings,
            status_callback=update_status,
        )

        # Отправляем файл
        document = FSInputFile(str(doc_path), filename=doc_path.name)
        await message.answer_document(
            document=document,
            caption=f"✅ Реферат на тему «{topic}» готов!",
            reply_markup=get_new_essay_keyboard(),
        )

        # Удаляем временный файл
        try:
            os.remove(doc_path)
            logger.info(f"Временный файл удалён: {doc_path}")
        except OSError as e:
            logger.warning(f"Не удалось удалить временный файл: {e}")

    except ConnectionError as e:
        logger.error(f"Ошибка подключения к AI-сервису: {e}")
        await message.answer(
            "❌ *Ошибка подключения к нейросети*\n\n"
            f"Не удалось подключиться к AI-провайдеру ({settings.llm_provider}).\n\n"
            f"Подробности: `{e}`\n\n"
            "Нажми /start чтобы попробовать снова.",
            parse_mode="Markdown",
        )

    except FileNotFoundError as e:
        logger.error(f"Файл шаблона не найден: {e}")
        await message.answer(
            f"❌ *Ошибка шаблона*\n\n{e}\n\nНажми /start чтобы попробовать снова.",
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Ошибка генерации: {e}", exc_info=True)
        await message.answer(
            "❌ *Произошла ошибка при генерации реферата*\n\n"
            f"Подробности: `{str(e)[:200]}`\n\n"
            "Нажми /start чтобы попробовать снова.",
            parse_mode="Markdown",
        )

    finally:
        _active_users.discard(user_id)
        await state.clear()


# === Обработка неожиданных сообщений ===

@router.message()
async def handle_unknown(message: Message, state: FSMContext):
    """Обработчик для сообщений вне контекста."""
    current_state = await state.get_state()

    if current_state == EssayStates.generating.state:
        await message.answer(
            "⏳ Подожди, идёт генерация реферата…\n"
            "Нажми /cancel если хочешь отменить."
        )
    else:
        await message.answer(
            "🤔 Я не понимаю эту команду.\n"
            "Нажми /start чтобы начать создание реферата."
        )

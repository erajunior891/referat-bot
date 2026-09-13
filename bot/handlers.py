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
    get_language_keyboard,
    get_pages_keyboard,
    get_template_keyboard,
    get_plan_keyboard,
    get_cancel_keyboard,
    get_new_essay_keyboard,
)
from templates.registry import get_template
from services.orchestrator import generate_essay

logger = logging.getLogger(__name__)

router = Router()

# Хранилище активных генераций (user_id -> True)
_active_users: set[int] = set()

# Сопоставление кодов языков для красивого вывода
LANG_TITLES = {
    "ru": "🇷🇺 Русский",
    "kk": "🇰🇿 Қазақша",
    "en": "🇬🇧 English",
}

# Текст приветствия
WELCOME_TEXT = """
🎓 *Привет! Я — бот для автоматической генерации рефератов.*

Я помогу тебе создать структурированный реферат по стандартам оформления.

*Как это работает:*
1️⃣ Выбери язык реферата (Қазақша / Русский / English)
2️⃣ Выбери желаемый объём в страницах
3️⃣ Выбери шаблон оформления (стандартный / вузовский / доклад)
4️⃣ Отправь тему работы
5️⃣ (Опционально) Укажи свой план или требования
6️⃣ Получи готовый документ `.docx`

🔍 Я собираю актуальную информацию в DuckDuckGo и Википедии.
🤖 Текст генерируется нейросетью с академической структурой.

⚠️ *Важно:* бот помогает подготовить качественный черновик для дальнейшей работы.

Для начала выбери *язык реферата* ниже: 👇
"""

HELP_TEXT = """
📖 *Справка по использованию бота*

*Команды:*
/start — Начать работу / Новый реферат
/help — Эта справка
/cancel — Прервать текущую операцию

*Поддерживаемые языки:*
• 🇰🇿 Қазақша
• 🇷🇺 Русский
• 🇬🇧 English

*Шаблоны:*
📄 *Стандартный реферат* — введение, разделы, заключение, литература
🎓 *Вузовский (ГОСТ)* — аннотация, расширенное содержание, строгие рубрики
🎤 *Краткий доклад* — тезисный структурированный материал для устного выступления

*Советы:*
• Формулируй тему конкретно: «Причины Первой мировой войны» лучше, чем «Война»
• При необходимости отправляй свой план по пунктам
• Генерация занимает 1–3 минуты в зависимости от выбранного объёма
"""


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start."""
    user_id = message.from_user.id
    _active_users.discard(user_id)
    await state.clear()
    await message.answer(
        WELCOME_TEXT,
        parse_mode="Markdown",
        reply_markup=get_language_keyboard(),
    )
    await state.set_state(EssayStates.choosing_language)


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help."""
    await message.answer(HELP_TEXT, parse_mode="Markdown")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Обработчик команды /cancel."""
    current_state = await state.get_state()
    user_id = message.from_user.id
    _active_users.discard(user_id)
    await state.clear()

    if current_state is None:
        await message.answer("Нечего отменять. Нажми /start, чтобы начать.")
    else:
        await message.answer(
            "❌ Операция отменена.\n\nНажми /start, чтобы начать заново.",
        )


@router.callback_query(F.data == "new_essay")
async def cb_new_essay(callback: CallbackQuery, state: FSMContext):
    """Начать новый реферат."""
    user_id = callback.from_user.id
    _active_users.discard(user_id)
    await state.clear()
    await callback.message.answer(
        "🌐 Выбери язык для нового реферата:",
        reply_markup=get_language_keyboard(),
    )
    await state.set_state(EssayStates.choosing_language)
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext):
    """Отмена через inline-кнопку."""
    user_id = callback.from_user.id
    _active_users.discard(user_id)
    await state.clear()
    await callback.message.answer(
        "❌ Действие отменено.\n\nНажми /start, чтобы начать сначала.",
    )
    await callback.answer()


# === 1. Выбор языка ===

@router.callback_query(F.data.startswith("lang:"), EssayStates.choosing_language)
async def cb_language_selected(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора языка."""
    lang_code = callback.data.split(":")[1]
    if lang_code not in LANG_TITLES:
        lang_code = "ru"

    await state.update_data(language=lang_code)
    lang_label = LANG_TITLES.get(lang_code, lang_code)

    await callback.message.answer(
        f"✅ Язык выбран: *{lang_label}*\n\n"
        f"Теперь укажи желаемый *объём реферата* (в страницах):",
        parse_mode="Markdown",
        reply_markup=get_pages_keyboard(),
    )
    await state.set_state(EssayStates.choosing_pages)
    await callback.answer()


# === 2. Выбор объёма (страниц) ===

@router.callback_query(F.data.startswith("pages:"), EssayStates.choosing_pages)
async def cb_pages_selected(callback: CallbackQuery, state: FSMContext):
    """Обработчик выбора объёма работы."""
    try:
        pages_count = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        pages_count = 10

    await state.update_data(pages_count=pages_count)

    await callback.message.answer(
        f"✅ Объём работы: *{pages_count} страниц*\n\n"
        f"Выбери подходящий *шаблон оформления*:",
        parse_mode="Markdown",
        reply_markup=get_template_keyboard(),
    )
    await state.set_state(EssayStates.choosing_template)
    await callback.answer()


# === 3. Выбор шаблона ===

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
        f"Теперь отправь мне *тему реферата* текстом сообщением:",
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard(),
    )
    await state.set_state(EssayStates.waiting_topic)
    await callback.answer()


# === 4. Получение темы ===

@router.message(EssayStates.waiting_topic)
async def handle_topic(message: Message, state: FSMContext):
    """Обработчик получения темы реферата."""
    topic = (message.text or "").strip()

    if not topic or len(topic) < 3:
        await message.answer(
            "⚠️ Тема слишком короткая. Пожалуйста, укажи тему подробнее (минимум 3 символа):",
            reply_markup=get_cancel_keyboard(),
        )
        return

    if len(topic) > 500:
        await message.answer(
            "⚠️ Тема слишком длинная (максимум 500 символов). Пожалуйста, сократи формулировку:",
            reply_markup=get_cancel_keyboard(),
        )
        return

    await state.update_data(topic=topic)
    await message.answer(
        f"📌 Тема: *{topic}*\n\n"
        f"Теперь можешь отправить *план или особые пожелания* отдельным сообщением.\n"
        f"Если плана нет, нажми кнопку ниже для автоматического построения структуры.",
        parse_mode="Markdown",
        reply_markup=get_plan_keyboard(),
    )
    await state.set_state(EssayStates.waiting_plan)


# === 5. Получение плана ===

@router.callback_query(F.data == "skip_plan", EssayStates.waiting_plan)
async def cb_skip_plan(callback: CallbackQuery, state: FSMContext, settings=None):
    """Пропуск плана — переход к генерации."""
    await state.update_data(plan=None)
    await callback.answer()
    await _start_generation(callback.message, state, callback.from_user.id, settings)


@router.message(EssayStates.waiting_plan)
async def handle_plan(message: Message, state: FSMContext, settings=None):
    """Обработчик пользовательского плана."""
    plan = (message.text or "").strip()
    await state.update_data(plan=plan)
    await _start_generation(message, state, message.from_user.id, settings)


# === 6. Генерация реферата ===

async def _start_generation(message: Message, state: FSMContext, user_id: int, settings):
    """Запуск процесса оркестрации и генерации документа."""

    # Проверка на дублирование запросов
    if user_id in _active_users:
        await message.answer(
            "⏳ У тебя уже есть активная генерация. Пожалуйста, дождись её завершения или нажми /cancel."
        )
        return

    _active_users.add(user_id)
    await state.set_state(EssayStates.generating)

    data = await state.get_data()
    topic = data.get("topic", "Без темы")
    plan = data.get("plan")
    template_id = data.get("template_id", "standard")
    language = data.get("language", "ru")
    pages_count = int(data.get("pages_count", 10))

    lang_title = LANG_TITLES.get(language, language)
    template_obj = get_template(template_id)
    template_name = template_obj.name if template_obj else template_id

    # Статусное сообщение
    status_msg = await message.answer(
        "⏳ *Начинаю генерацию реферата…*\n\n"
        f"📌 *Тема:* {topic}\n"
        f"🌐 *Язык:* {lang_title}\n"
        f"📑 *Объём:* {pages_count} стр.\n"
        f"📋 *Шаблон:* {template_name}\n"
        f"📄 *План:* {plan or 'автоматический'}",
        parse_mode="Markdown",
    )

    async def update_status(text: str):
        """Обновление статусного сообщения для пользователя."""
        try:
            await status_msg.edit_text(
                f"{text}\n\n"
                f"📌 *Тема:* {topic}\n"
                f"📑 *Объём:* {pages_count} стр. ({lang_title})",
                parse_mode="Markdown",
            )
        except Exception:
            pass

    doc_path: Path | None = None
    try:
        # Запуск оркестратора с полной сигнатурой параметров
        doc_path = await generate_essay(
            topic=topic,
            plan=plan,
            template_id=template_id,
            language=language,
            pages_count=pages_count,
            settings=settings,
            status_callback=update_status,
        )

        # Отправка готового документа пользователю
        document = FSInputFile(str(doc_path), filename=doc_path.name)
        await message.answer_document(
            document=document,
            caption=(
                f"✅ *Реферат готов!*\n\n"
                f"📌 *Тема:* {topic}\n"
                f"🌐 *Язык:* {lang_title}\n"
                f"📑 *Объём:* ~{pages_count} страниц\n"
                f"📋 *Шаблон:* {template_name}"
            ),
            parse_mode="Markdown",
            reply_markup=get_new_essay_keyboard(),
        )

    except ConnectionError as e:
        logger.error(f"Ошибка подключения к AI-сервису: {e}")
        provider_name = getattr(settings, "llm_provider", "нейросеть")
        await message.answer(
            "❌ *Ошибка подключения к нейросети*\n\n"
            f"Не удалось связаться с AI-провайдером ({provider_name}).\n\n"
            f"Подробности: `{e}`\n\n"
            "Нажми /start, чтобы попробовать снова.",
            parse_mode="Markdown",
        )

    except FileNotFoundError as e:
        logger.error(f"Файл шаблона или промпта не найден: {e}")
        await message.answer(
            f"❌ *Ошибка конфигурации шаблона*\n\n`{e}`\n\nНажми /start, чтобы попробовать снова.",
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error(f"Ошибка генерации: {e}", exc_info=True)
        await message.answer(
            "❌ *Произошла ошибка при генерации реферата*\n\n"
            f"Подробности: `{str(e)[:300]}`\n\n"
            "Нажми /start, чтобы попробовать снова.",
            parse_mode="Markdown",
        )

    finally:
        # Гарантированное удаление временного файла
        if doc_path and isinstance(doc_path, Path) and doc_path.exists():
            try:
                os.remove(doc_path)
                logger.info(f"Временный файл удалён: {doc_path}")
            except OSError as e:
                logger.warning(f"Не удалось удалить временный файл {doc_path}: {e}")

        _active_users.discard(user_id)
        await state.clear()


# === Обработка неизвестных / повторных сообщений ===

@router.message()
async def handle_unknown(message: Message, state: FSMContext):
    """Обработчик сообщений вне ожидаемого контекста."""
    current_state = await state.get_state()

    if current_state == EssayStates.generating.state:
        await message.answer(
            "⏳ Идёт генерация реферата, пожалуйста, подожди…\n"
            "Нажми /cancel, если хочешь прервать процесс."
        )
    else:
        await message.answer(
            "🤔 Сообщение не распознано в текущем шаге.\n"
            "Нажми /start, чтобы начать оформление реферата."
        )

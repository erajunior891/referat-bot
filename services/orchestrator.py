"""
Оркестратор — основная бизнес-логика генерации рефератов (ТЗ v2.1).
Координирует мультиязычный поиск информации, DeepSeek-генерацию с Prompt Caching
и программное формирование Word-документов.
"""

import logging
from pathlib import Path
from typing import Callable, Awaitable

from services.search import gather_context
from services.ai_client import get_ai_client
from services.docx_generator import create_document
from templates.registry import load_prompt, load_system_prompt

logger = logging.getLogger(__name__)

# Тип для callback-функции статуса
StatusCallback = Callable[[str], Awaitable[None]]

# Словарный перевод статусных сообщений
STATUS_TEXTS = {
    "ru": {
        "searching": "🔍 Ищу информацию по теме в интернете (DuckDuckGo + Википедия)…",
        "preparing": "📝 Формирую запрос к DeepSeek AI…",
        "generating": "🧠 Генерирую текст реферата ({pages} страниц)… Это может занять пару минут.",
        "formatting": "📄 Формирую Word-документ (.docx)…",
        "done": "✅ Реферат готов! Отправляю файл…",
    },
    "kk": {
        "searching": "🔍 Ғаламтордан ақпарат іздеудемін (DuckDuckGo + Уикипедия)…",
        "preparing": "📝 DeepSeek AI сұранысын дайындаудамын…",
        "generating": "🧠 Реферат мәтінін генерациялаудамын ({pages} бет)… Бирнеше минут алуы мүмкін.",
        "formatting": "📄 Word құжатын қалыптастырудамын (.docx)…",
        "done": "✅ Реферат дайын! Файлды жіберемін…",
    },
    "en": {
        "searching": "🔍 Searching information on the web (DuckDuckGo + Wikipedia)…",
        "preparing": "📝 Preparing prompt for DeepSeek AI…",
        "generating": "🧠 Generating essay content ({pages} pages)… This may take a couple of minutes.",
        "formatting": "📄 Formatting Word document (.docx)…",
        "done": "✅ Essay is ready! Sending file…",
    },
}

LANGUAGE_NAMES = {
    "ru": "Русский",
    "kk": "Қазақша",
    "en": "English",
}


async def generate_essay(
    topic: str,
    plan: str | None,
    template_id: str,
    language: str,
    pages_count: int,
    settings,
    status_callback: StatusCallback,
) -> Path:
    """
    Полный цикл генерации реферата.

    Args:
        topic: Тема реферата
        plan: План пользователя (может быть None)
        template_id: ID выбранного шаблона
        language: Код языка ('ru', 'kk', 'en')
        pages_count: Количество страниц (5, 8, 10, 12, 15, 20)
        settings: Объект настроек (config.Settings)
        status_callback: Асинхронная функция для отправки статусов

    Returns:
        Путь к готовому .docx файлу
    """
    lang = language if language in STATUS_TEXTS else "ru"
    txt = STATUS_TEXTS[lang]

    plan_text = plan if plan else "Не указан (сгенерировать автоматически)"
    target_chars_count = pages_count * 1900

    # === Этап 1: Поиск информации ===
    await status_callback(txt["searching"])
    logger.info(f"Начинаю мультиязычный поиск ({lang}) для темы: '{topic}'")

    context = await gather_context(
        topic=topic,
        lang=lang,
        max_total_chars=settings.max_context_chars,
    )

    # === Этап 2: Формирование промптов (DeepSeek Prompt Cache Hit Optimization) ===
    await status_callback(txt["preparing"])
    logger.info("Загружаю системный промпт (Prompt Caching) и пользовательский промпт")

    system_prompt = load_system_prompt(settings.templates_dir)
    user_prompt_template = load_prompt(template_id, settings.templates_dir)

    user_prompt = user_prompt_template.format(
        language=LANGUAGE_NAMES.get(lang, "Русский"),
        pages_count=pages_count,
        target_chars_count=target_chars_count,
        topic=topic,
        plan=plan_text,
        context=context,
    )

    logger.info(f"System Prompt: {len(system_prompt)} символов, User Prompt: {len(user_prompt)} символов")

    # === Этап 3: Генерация текста ===
    await status_callback(txt["generating"].format(pages=pages_count))
    logger.info(f"Отправляю запрос к AI-провайдеру ({settings.llm_provider})")

    ai_client = get_ai_client(settings)
    generated_text = await ai_client.generate(
        prompt=user_prompt,
        system_prompt=system_prompt,
    )

    logger.info(f"Текст сгенерирован: {len(generated_text)} символов")

    # === Этап 4: Создание документа ===
    await status_callback(txt["formatting"])
    logger.info("Создаю .docx документ")

    doc_path = create_document(
        text=generated_text,
        template_id=template_id,
        topic=topic,
        output_dir=settings.temp_dir,
    )

    await status_callback(txt["done"])
    logger.info(f"Документ готов: {doc_path}")

    return doc_path

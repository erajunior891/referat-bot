"""
Модуль поиска информации.
Мультиязычный поиск в DuckDuckGo и Википедии (Қазақша / Русский / English)
согласно ТЗ v2.1 (раздел 5).
"""

import asyncio
import logging
import re
from typing import Any

from duckduckgo_search import DDGS
import wikipediaapi

logger = logging.getLogger(__name__)


def generate_search_queries(topic: str, lang: str = "ru") -> list[str]:
    """Генерирует 3–5 поисковых запросов на основе темы и языка."""
    clean_topic = topic.strip()
    queries = [clean_topic]

    if lang == "kk":
        queries.extend([
            f"{clean_topic} ғылыми жұмыс",
            f"{clean_topic} реферат мақала",
            f"{clean_topic} тарихы теориясы",
        ])
    elif lang == "en":
        queries.extend([
            f"{clean_topic} research overview",
            f"{clean_topic} theory and concepts",
            f"{clean_topic} academic analysis",
        ])
    else:  # ru
        queries.extend([
            f"{clean_topic} исследование теория",
            f"{clean_topic} реферат статья",
            f"{clean_topic} понятие история",
        ])

    return list(dict.fromkeys(queries))  # Сохраняем порядок, убираем дубли


async def search_duckduckgo(queries: list[str], lang: str = "ru", max_results_per_query: int = 4) -> list[dict[str, str]]:
    """
    Поиск информации по нескольким запросам в DuckDuckGo.
    """
    region_map = {"ru": "ru-ru", "kk": "kz-kz", "en": "us-en"}
    region = region_map.get(lang, "ru-ru")

    results = []
    seen_urls = set()

    try:
        raw_results = await asyncio.to_thread(
            _ddg_multi_search, queries, region, max_results_per_query
        )
        for r in raw_results:
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                results.append(r)

        logger.info(f"DuckDuckGo ({lang}): найдено {len(results)} уникальных результатов по {len(queries)} запросам")
    except Exception as e:
        logger.error(f"Ошибка поиска DuckDuckGo: {e}")

    return results


def _ddg_multi_search(queries: list[str], region: str, max_results: int) -> list[dict[str, str]]:
    """Синхронный поиск по нескольким запросам."""
    results = []
    try:
        with DDGS() as ddgs:
            for q in queries:
                try:
                    for r in ddgs.text(q, region=region, max_results=max_results):
                        results.append({
                            "title": r.get("title", ""),
                            "snippet": r.get("body", ""),
                            "url": r.get("href", ""),
                        })
                except Exception as ex:
                    logger.warning(f"Ошибка DDG для запроса '{q}': {ex}")
    except Exception as e:
        logger.error(f"DDG internal error: {e}")
    return results


async def search_wikipedia(topic: str, ddg_results: list[dict[str, str]], lang: str = "ru", max_chars: int = 3500) -> str:
    """
    Умный поиск информации в Википедии (kk, ru, en) с использованием результатов DDG при необходимости.
    """
    wiki_lang_map = {"ru": "ru", "kk": "kk", "en": "en"}
    wiki_lang = wiki_lang_map.get(lang, "ru")

    try:
        text = await asyncio.to_thread(
            _wiki_smart_search, topic, ddg_results, wiki_lang, max_chars
        )
        if text:
            logger.info(f"Wikipedia ({wiki_lang}): найдена статья ({len(text)} символов)")
        else:
            logger.info(f"Wikipedia ({wiki_lang}): статья не найдена")
        return text
    except Exception as e:
        logger.error(f"Ошибка поиска Wikipedia: {e}")
        return ""


def _wiki_smart_search(topic: str, ddg_results: list[dict[str, str]], lang: str, max_chars: int) -> str:
    """Синхронный умный поиск по Википедии."""
    wiki = wikipediaapi.Wikipedia(
        user_agent="ReferatBot/2.1 (educational project)",
        language=lang,
    )

    page = wiki.page(topic)

    # Если страница по прямому названию не найдена — ищем упоминания Википедии в результатах DDG
    if not page.exists():
        found_title = None
        for r in ddg_results:
            url = r.get("url", "")
            if f"{lang}.wikipedia.org/wiki/" in url:
                # Извлекаем название статьи из URL
                match = re.search(r"/wiki/([^#?]+)", url)
                if match:
                    import urllib.parse
                    found_title = urllib.parse.unquote(match.group(1)).replace("_", " ")
                    break

        if found_title:
            page = wiki.page(found_title)

    if not page.exists():
        # Попробуем первое слово/главную часть темы
        simple_topic = topic.split(".")[0].split(",")[0].strip()
        page = wiki.page(simple_topic)
        if not page.exists():
            return ""

    parts = []

    # Аннотация/Введение статьи
    if page.summary:
        parts.append(f"## {page.title}\n{page.summary}")

    # Основные ключевые разделы (до 4 разделов)
    sections_added = 0
    for section in page.sections:
        if sections_added >= 4:
            break
        if section.text and len(section.text) > 80:
            parts.append(f"### {section.title}\n{section.text}")
            sections_added += 1

    full_text = "\n\n".join(parts)

    if len(full_text) > max_chars:
        cut_pos = full_text.rfind(". ", 0, max_chars)
        if cut_pos == -1:
            cut_pos = max_chars
        full_text = full_text[: cut_pos + 1]

    return full_text


async def gather_context(topic: str, lang: str = "ru", max_total_chars: int = 6000) -> str:
    """
    Собирает контекст из всех источников (DuckDuckGo + Wikipedia) с учетом языка.

    Args:
        topic: Тема реферата
        lang: Код языка ('ru', 'kk', 'en')
        max_total_chars: Максимальная длина контекстного блока

    Returns:
        Объединённый контекстный текст
    """
    queries = generate_search_queries(topic, lang)
    ddg_results = await search_duckduckgo(queries, lang=lang)
    wiki_text = await search_wikipedia(topic, ddg_results, lang=lang)

    parts = []

    if wiki_text:
        header = {
            "ru": "=== Информация из Википедии ===",
            "kk": "=== Уикипедиядан алынған мәліметтер ===",
            "en": "=== Wikipedia Information ===",
        }.get(lang, "=== Информация из Википедии ===")
        parts.append(header)
        parts.append(wiki_text)

    if ddg_results:
        header = {
            "ru": "=== Результаты поиска в Интернете (DuckDuckGo) ===",
            "kk": "=== Ғаламтордан табыған мәліметтер (DuckDuckGo) ===",
            "en": "=== Web Search Results (DuckDuckGo) ===",
        }.get(lang, "=== Результаты поиска в Интернете (DuckDuckGo) ===")
        parts.append(f"\n{header}")
        for i, r in enumerate(ddg_results[:6], 1):
            parts.append(f"{i}. {r['title']}")
            parts.append(f"   {r['snippet']}")
            if r["url"]:
                parts.append(f"   Источник: {r['url']}")

    context = "\n".join(parts)

    if len(context) > max_total_chars:
        cut_pos = context.rfind(". ", 0, max_total_chars)
        if cut_pos == -1:
            cut_pos = max_total_chars
        context = context[: cut_pos + 1]

    if not context.strip():
        context = "Контекст из внешнего поиска ограничен. Пожалуйста, опирайся на проверенные академические данные по этой теме."

    logger.info(f"Итоговый контекст ({lang}): {len(context)} символов")
    return context

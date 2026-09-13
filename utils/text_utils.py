"""
Утилиты для работы с текстом.
Транслитерация, очистка имён файлов, парсинг markdown-ответа модели.
"""

import re
import unicodedata


# Таблица транслитерации кириллицы
_TRANSLIT_TABLE = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def transliterate(text: str) -> str:
    """Транслитерация кириллического текста в латиницу."""
    result = []
    for char in text:
        lower = char.lower()
        if lower in _TRANSLIT_TABLE:
            translit = _TRANSLIT_TABLE[lower]
            # Сохраняем регистр первой буквы
            if char.isupper() and translit:
                translit = translit[0].upper() + translit[1:]
            result.append(translit)
        else:
            result.append(char)
    return "".join(result)


def sanitize_filename(topic: str, max_length: int = 80) -> str:
    """
    Создаёт безопасное имя файла из темы реферата.
    Пробелы заменяются на подчёркивания, спецсимволы удаляются.
    """
    # Убираем лишние пробелы
    name = " ".join(topic.split())
    # Заменяем пробелы на подчёркивания
    name = name.replace(" ", "_")
    # Удаляем всё, кроме букв, цифр, подчёркиваний и дефисов
    name = re.sub(r"[^\w\-]", "", name, flags=re.UNICODE)
    # Обрезаем
    if len(name) > max_length:
        name = name[:max_length]
    return name or "referat"


def truncate_text(text: str, max_chars: int = 4000) -> str:
    """
    Обрезает текст до max_chars символов, стараясь не обрывать посреди слова.
    """
    if len(text) <= max_chars:
        return text
    # Ищем последний пробел перед лимитом
    cut_pos = text.rfind(" ", 0, max_chars)
    if cut_pos == -1:
        cut_pos = max_chars
    return text[:cut_pos] + "…"


def parse_generated_text(text: str) -> list[dict]:
    """
    Парсит markdown-ответ модели в структурированный список.

    Возвращает список словарей вида:
    - {"type": "heading1", "text": "..."}
    - {"type": "heading2", "text": "..."}
    - {"type": "heading3", "text": "..."}
    - {"type": "paragraph", "text": "..."}
    - {"type": "list_item", "text": "..."}
    """
    lines = text.split("\n")
    result = []
    current_paragraph = []

    def flush_paragraph():
        if current_paragraph:
            para_text = " ".join(current_paragraph).strip()
            if para_text:
                result.append({"type": "paragraph", "text": para_text})
            current_paragraph.clear()

    for line in lines:
        stripped = line.strip()

        # Пустая строка — конец абзаца
        if not stripped:
            flush_paragraph()
            continue

        # Заголовки
        if stripped.startswith("### "):
            flush_paragraph()
            result.append({"type": "heading3", "text": stripped[4:].strip()})
        elif stripped.startswith("## "):
            flush_paragraph()
            result.append({"type": "heading2", "text": stripped[3:].strip()})
        elif stripped.startswith("# "):
            flush_paragraph()
            result.append({"type": "heading1", "text": stripped[2:].strip()})
        # Элементы списка
        elif re.match(r"^[-•*]\s+", stripped):
            flush_paragraph()
            item_text = re.sub(r"^[-•*]\s+", "", stripped)
            result.append({"type": "list_item", "text": item_text})
        elif re.match(r"^\d+[.)]\s+", stripped):
            flush_paragraph()
            item_text = re.sub(r"^\d+[.)]\s+", "", stripped)
            result.append({"type": "list_item", "text": item_text})
        else:
            # Обычный текст — часть абзаца
            # Убираем markdown-разметку (жирный, курсив)
            cleaned = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", stripped)
            current_paragraph.append(cleaned)

    flush_paragraph()
    return result

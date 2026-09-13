"""
Реестр шаблонов рефератов.
Каждый шаблон содержит промпт для генерации и docx-шаблон для оформления.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Template:
    """Описание шаблона реферата."""
    id: str
    name: str
    description: str
    prompt_file: str   # Относительный путь к промпт-файлу
    docx_template: str | None  # Относительный путь к .docx шаблону (None = программная генерация)


# Реестр всех доступных шаблонов
TEMPLATES: dict[str, Template] = {
    "standard": Template(
        id="standard",
        name="📄 Стандартный реферат",
        description="Классический реферат: введение, основная часть, заключение, список литературы",
        prompt_file="prompts/standard.txt",
        docx_template=None,  # Генерируется программно
    ),
    "university": Template(
        id="university",
        name="🎓 Вузовский (ГОСТ)",
        description="Расширенный академический реферат с аннотацией, содержанием и подробной структурой",
        prompt_file="prompts/university.txt",
        docx_template=None,  # Генерируется программно
    ),
    "report": Template(
        id="report",
        name="🎤 Краткий доклад",
        description="Лаконичный структурированный доклад для устного выступления на семинаре или уроке",
        prompt_file="prompts/report.txt",
        docx_template=None,  # Генерируется программно
    ),
}


def get_template(template_id: str) -> Template | None:
    """Получить шаблон по ID."""
    return TEMPLATES.get(template_id)


def get_all_templates() -> list[Template]:
    """Получить список всех доступных шаблонов."""
    return list(TEMPLATES.values())


def get_template_ids() -> list[str]:
    """Получить список ID всех шаблонов."""
    return list(TEMPLATES.keys())


def load_system_prompt(templates_dir: Path) -> str:
    """Загружает статический системный промпт для DeepSeek Prompt Caching (Cache Hit)."""
    sys_prompt_path = templates_dir / "prompts/system_base.txt"
    if not sys_prompt_path.exists():
        raise FileNotFoundError(f"Системный промпт не найден: {sys_prompt_path}")
    return sys_prompt_path.read_text(encoding="utf-8")


def load_prompt(template_id: str, templates_dir: Path) -> str:
    """
    Загружает текст пользовательского промпта из файла для указанного шаблона.

    Args:
        template_id: ID шаблона
        templates_dir: Путь к директории templates/

    Returns:
        Текст промпта

    Raises:
        FileNotFoundError: Если файл промпта не найден
        ValueError: Если шаблон с таким ID не существует
    """
    template = get_template(template_id)
    if not template:
        raise ValueError(f"Шаблон '{template_id}' не найден")

    prompt_path = templates_dir / template.prompt_file
    if not prompt_path.exists():
        raise FileNotFoundError(f"Файл промпта не найден: {prompt_path}")

    return prompt_path.read_text(encoding="utf-8")

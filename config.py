"""
Конфигурация проекта.
Загружает параметры из .env файла и предоставляет dataclass Settings.
"""

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Корневая директория проекта
BASE_DIR = Path(__file__).resolve().parent

# Загрузка .env
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    """Настройки приложения."""

    # Telegram
    bot_token: str

    # AI Provider ('ollama', 'openai', 'openrouter', 'groq', 'deepseek')
    llm_provider: str

    # Ollama
    ollama_url: str
    ollama_model: str

    # Cloud API (OpenAI / OpenRouter / Groq / DeepSeek)
    api_key: str
    api_base_url: str
    api_model: str

    # Лимиты и параметры генерации
    num_predict: int
    max_context_chars: int
    request_timeout: int

    # Пути
    base_dir: Path
    templates_dir: Path
    temp_dir: Path


def load_settings() -> Settings:
    """Загружает и валидирует настройки из переменных окружения."""
    bot_token = os.getenv("BOT_TOKEN", "")
    if not bot_token or bot_token == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("❌ ОШИБКА: Укажите BOT_TOKEN в файле .env")
        print("   Получите токен у @BotFather в Telegram")
        sys.exit(1)

    llm_provider = os.getenv("LLM_PROVIDER", "deepseek").lower().strip()

    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

    api_key = os.getenv("API_KEY", "")
    api_base_url = os.getenv("API_BASE_URL", "")
    api_model = os.getenv("API_MODEL", "DeepSeek-V4-Pro")

    # Определение дефолтных URL для провайдеров, если API_BASE_URL не переопределен
    if not api_base_url:
        if llm_provider == "openrouter":
            api_base_url = "https://openrouter.ai/api/v1"
        elif llm_provider == "groq":
            api_base_url = "https://api.groq.com/openai/v1"
        elif llm_provider == "deepseek":
            api_base_url = "https://api.deepseek.com"
        elif llm_provider == "openai":
            api_base_url = "https://api.openai.com/v1"
        elif llm_provider == "runpod":
            # Пример для vLLM / OpenAI на RunPod Serverless
            api_base_url = "https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/openai/v1"

    num_predict = int(os.getenv("NUM_PREDICT", "4096"))
    max_context_chars = int(os.getenv("MAX_CONTEXT_CHARS", "6000"))
    request_timeout = int(os.getenv("REQUEST_TIMEOUT", "300"))

    templates_dir = BASE_DIR / "templates"
    temp_dir = BASE_DIR / "temp"
    temp_dir.mkdir(exist_ok=True)

    return Settings(
        bot_token=bot_token,
        llm_provider=llm_provider,
        ollama_url=ollama_url,
        ollama_model=ollama_model,
        api_key=api_key,
        api_base_url=api_base_url,
        api_model=api_model,
        num_predict=num_predict,
        max_context_chars=max_context_chars,
        request_timeout=request_timeout,
        base_dir=BASE_DIR,
        templates_dir=templates_dir,
        temp_dir=temp_dir,
    )


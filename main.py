"""
Точка входа — запуск Telegram-бота для генерации рефератов.
"""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import load_settings
from bot.handlers import router
from services.ai_client import get_ai_client


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


class SettingsMiddleware:
    """Middleware для передачи settings во все обработчики."""

    def __init__(self, settings):
        self.settings = settings

    async def __call__(self, handler, event, data):
        data["settings"] = self.settings
        return await handler(event, data)


async def main():
    """Главная функция запуска бота."""
    # Загрузка конфигурации
    settings = load_settings()
    logger.info("✅ Конфигурация загружена")
    logger.info(f"   Провайдер AI: {settings.llm_provider.upper()}")

    ai_client = get_ai_client(settings)

    if settings.llm_provider == "ollama":
        logger.info(f"   Ollama URL: {settings.ollama_url} / модель: {settings.ollama_model}")
        if await ai_client.check_connection():
            models = await ai_client.list_models()
            logger.info(f"✅ Ollama доступен. Доступные модели: {', '.join(models) or 'не найдены'}")

            if settings.ollama_model not in models:
                logger.warning(
                    f"⚠️  Модель '{settings.ollama_model}' не найдена в Ollama. "
                    f"Скачайте: ollama pull {settings.ollama_model}"
                )
        else:
            logger.warning(
                "⚠️  Ollama недоступен! Бот запустится, но локальная генерация не сработает. "
                "Убедитесь, что запущен 'ollama serve'."
            )
    else:
        logger.info(f"   Cloud API Base: {settings.api_base_url} / модель: {settings.api_model}")
        if await ai_client.check_connection():
            logger.info(f"✅ Подключение к Cloud API ({settings.llm_provider}) успешно!")
        else:
            if not settings.api_key:
                logger.warning("⚠️  API_KEY не заполнен в .env! Генерация через Cloud API не сработает.")
            else:
                logger.warning("⚠️  Не удалось подключиться к Cloud API (проверьте API_KEY и доступность сети).")


    # Инициализация бота
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Подключение middleware для передачи settings
    dp.message.middleware(SettingsMiddleware(settings))
    dp.callback_query.middleware(SettingsMiddleware(settings))

    # Подключение роутера с обработчиками
    dp.include_router(router)

    # Запуск
    logger.info("🚀 Бот запущен! Ожидаю сообщения…")
    logger.info("   Нажмите Ctrl+C для остановки")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("👋 Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

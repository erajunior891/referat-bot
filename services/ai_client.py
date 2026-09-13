"""
Клиент для работы с AI (Ollama REST API и OpenAI-совместимые облачные API).
"""

import json
import logging
from abc import ABC, abstractmethod

import aiohttp

logger = logging.getLogger(__name__)


class BaseAIClient(ABC):
    """Абстрактный интерфейс AI-клиента."""

    @abstractmethod
    async def generate(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.3) -> str:
        """Генерация текста по промпту."""
        pass

    @abstractmethod
    async def check_connection(self) -> bool:
        """Проверка доступности сервиса."""
        pass


class OllamaClient(BaseAIClient):
    """Асинхронный клиент к локальному Ollama REST API."""

    def __init__(
        self,
        base_url: str,
        model: str,
        num_predict: int = 2500,
        timeout: int = 300,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.num_predict = num_predict
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def generate(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.3) -> str:
        url = f"{self.base_url}/api/generate"
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": self.num_predict,
            },
        }

        logger.info(
            f"Отправка запроса к Ollama ({self.model}), промпт: {len(full_prompt)} символов, num_predict: {self.num_predict}"
        )

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise RuntimeError(
                            f"Ollama вернул ошибку {response.status}: {error_text}"
                        )

                    data = await response.json()
                    generated_text = data.get("response", "")

                    if not generated_text.strip():
                        raise RuntimeError("Ollama вернул пустой ответ")

                    logger.info(
                        f"Получен ответ от Ollama: {len(generated_text)} символов"
                    )
                    return generated_text.strip()

        except aiohttp.ClientConnectorError:
            raise ConnectionError(
                f"Не удалось подключиться к Ollama по адресу {self.base_url}. "
                f"Убедитесь, что Ollama запущен (ollama serve)."
            )
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Ошибка HTTP-запроса к Ollama: {e}")

    async def check_connection(self) -> bool:
        try:
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.base_url}/api/tags") as response:
                    return response.status == 200
        except Exception:
            return False

    async def list_models(self) -> list[str]:
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.base_url}/api/tags") as response:
                    if response.status == 200:
                        data = await response.json()
                        return [m["name"] for m in data.get("models", [])]
        except Exception:
            pass
        return []


class CloudAIClient(BaseAIClient):
    """Клиент для OpenAI-совместимых облачных API (DeepSeek, OpenAI, OpenRouter, Groq)."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        num_predict: int = 2500,
        timeout: int = 300,
    ):
        self.base_url = base_url.rstrip("/")
        if not self.base_url.endswith("/v1") and not "/v1" in self.base_url and "deepseek" not in self.base_url:
            self.base_url += "/v1"
        self.api_key = api_key
        self.model = model
        self.num_predict = num_predict
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def generate(self, prompt: str, system_prompt: str | None = None, temperature: float = 0.3) -> str:
        if not self.api_key:
            raise RuntimeError("API_KEY не указан в файле .env для облачного провайдера")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.num_predict,
            "temperature": temperature,
        }

        logger.info(
            f"Отправка запроса к Cloud API ({self.model}), system_prompt: {len(system_prompt or '')} символов, user_prompt: {len(prompt)} символов (Cache-optimized)"
        )

        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.post(url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise RuntimeError(
                            f"Cloud API вернул ошибку {response.status}: {error_text}"
                        )

                    data = await response.json()
                    choices = data.get("choices", [])
                    if not choices:
                        raise RuntimeError("Cloud API вернул пустой список ответов (choices)")

                    generated_text = choices[0].get("message", {}).get("content", "")

                    if not generated_text.strip():
                        raise RuntimeError("Cloud API вернул пустой текст ответа")

                    logger.info(
                        f"Получен ответ от Cloud API: {len(generated_text)} символов"
                    )
                    return generated_text.strip()

        except aiohttp.ClientConnectorError as e:
            raise ConnectionError(
                f"Не удалось подключиться к Cloud API ({self.base_url}): {e}"
            )
        except aiohttp.ClientError as e:
            raise RuntimeError(f"Ошибка HTTP-запроса к Cloud API: {e}")

    async def check_connection(self) -> bool:
        if not self.api_key:
            return False
        try:
            url = f"{self.base_url}/models"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, headers=headers) as response:
                    return response.status == 200
        except Exception:
            return False


def get_ai_client(settings) -> BaseAIClient:
    """Фабричная функция создания AI-клиента на основе настроек."""
    provider = settings.llm_provider.lower()
    if provider == "ollama":
        return OllamaClient(
            base_url=settings.ollama_url,
            model=settings.ollama_model,
            num_predict=settings.num_predict,
            timeout=settings.request_timeout,
        )
    else:
        return CloudAIClient(
            base_url=settings.api_base_url,
            api_key=settings.api_key,
            model=settings.api_model,
            num_predict=settings.num_predict,
            timeout=settings.request_timeout,
        )


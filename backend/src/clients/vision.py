import json
import logging
from typing import Protocol, runtime_checkable

import httpx

from src.clients.retry import (
    RetryDecision,
    classify,
    log_attempt,
    sleep_before_retry,
    worst_case_seconds,
)
from src.exceptions.knowledge import KnowledgeProviderError
from src.knowledge.images import build_image_data_url
from src.prompts.vision import VISION_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)
API_NAME = "vision API"


@runtime_checkable
class VisionCapability(Protocol):
    """Способность извлечь текст из изображения.

    Отдельный protocol нужен, чтобы выключенное распознавание было явным
    объектом, а не `None`: сервис получает обязательную зависимость и не
    содержит ветки `if client is not None`.
    """

    async def extract_image_text(self, *, filename: str, content: bytes) -> str | None:
        """Возвращает текст изображения либо ``None``, если распознавание недоступно."""
        ...


class VisionClient:
    """Клиент OpenAI-совместимого chat API для распознавания изображений."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        url: str,
        headers: dict[str, str],
        model: str,
        timeout: int,
        retries: int,
        max_tokens: int,
        prompt: str = VISION_EXTRACTION_PROMPT,
    ) -> None:
        self.http_client = http_client
        self.url = url
        self.headers = headers
        self.model = model
        self.timeout = timeout
        self.retries = retries
        self.max_tokens = max_tokens
        self.prompt = prompt

    @property
    def worst_case_seconds(self) -> float:
        """Верхняя оценка длительности одного вызова с учётом повторов."""
        return worst_case_seconds(timeout=self.timeout, attempts=self.retries)

    async def extract_image_text(self, *, filename: str, content: bytes) -> str | None:
        """Кодирует изображение и возвращает распознанный моделью текст.

        Args:
            filename: Имя файла, определяющее MIME-тип изображения.
            content: Бинарное содержимое изображения.

        Returns:
            Извлечённый текст; пустая строка, если модель ничего не нашла.

        Raises:
            ValueError: Если расширение не поддерживается или файл пуст.
            KnowledgeProviderError: Если API недоступен или ответ не разобран.
        """
        image_data_url = build_image_data_url(filename, content)
        return await self.extract_text(image_data_url=image_data_url)

    async def extract_text(self, *, image_data_url: str) -> str:
        """Возвращает распознанный моделью текст изображения.

        Повторяются сеть, таймаут, 429 и 5xx, а также неразобранный ответ.
        Обычные 4xx завершаются сразу.

        Args:
            image_data_url: Исходное изображение как data URL с корректным MIME-типом.

        Returns:
            Извлечённый текст; пустая строка, если модель ничего не нашла.

        Raises:
            KnowledgeProviderError: Если API недоступен или ответ не разобран.
        """
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_data_url},
                        },
                    ],
                }
            ],
            "max_completion_tokens": self.max_tokens,
            "stream": False,
        }
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                response = await self.http_client.post(
                    self.url,
                    headers=self.headers,
                    content=json.dumps(payload, ensure_ascii=False),
                    timeout=self.timeout,
                )
                response.raise_for_status()
                text = _parse_content(response.json()["choices"][0]["message"]["content"])
                logger.info("✅ Vision-модель %s вернула %s символов.", self.model, len(text))
                return text
            except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
                last_error = error
                decision = classify(error)
                log_attempt(
                    api_name=API_NAME,
                    decision=decision,
                    attempt=attempt,
                    attempts=self.retries,
                    error=error,
                )
                if decision is RetryDecision.FAIL_FAST:
                    break
                if attempt < self.retries:
                    await sleep_before_retry(attempt)
        raise KnowledgeProviderError(str(last_error))


class DisabledVisionCapability:
    """Распознавание изображений выключено настройкой.

    Явный объект вместо ``None``: зависимость остаётся обязательной, а
    решение «изображения не индексируются» видно в месте сборки графа, а не
    внутри условия в сервисе.
    """

    async def extract_image_text(self, *, filename: str, content: bytes) -> str | None:
        """Сообщает вызывающему, что текст изображения недоступен."""
        logger.info("ℹ️ Vision-модель отключена, изображение %s не индексируется.", filename)
        return None


def _parse_content(content: object) -> str:
    """Разбирает content ответа: строку или список текстовых частей."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict)).strip()
    raise ValueError("Vision API вернул content неподдерживаемого формата.")

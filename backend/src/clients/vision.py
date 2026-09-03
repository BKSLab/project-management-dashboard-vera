import asyncio
import json
import logging
import random

import httpx

from src.exceptions.knowledge import KnowledgeProviderError

logger = logging.getLogger(__name__)

DEFAULT_VISION_PROMPT = (
    "Извлеки из изображения весь читаемый текст и данные таблиц. "
    "Сохраняй исходный язык и порядок блоков. "
    "Если текста нет, кратко опиши, что изображено, одной строкой. "
    "Отвечай только извлечённым содержимым, без пояснений и обрамления."
)


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
        prompt: str = DEFAULT_VISION_PROMPT,
    ) -> None:
        self.http_client = http_client
        self.url = url
        self.headers = headers
        self.model = model
        self.timeout = timeout
        self.retries = retries
        self.max_tokens = max_tokens
        self.prompt = prompt

    async def extract_text(self, *, image_base64: str) -> str:
        """Возвращает распознанный моделью текст изображения.

        Args:
            image_base64: JPEG-изображение в base64 без префикса data URL.

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
                            "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
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
                logger.warning(
                    "⚠️ Ошибка vision API, попытка %s/%s: %s",
                    attempt,
                    self.retries,
                    error,
                )
                if attempt < self.retries:
                    await asyncio.sleep((2 ** (attempt - 1)) + random.random() * 0.2)
        raise KnowledgeProviderError(str(last_error))


def _parse_content(content: object) -> str:
    """Разбирает content ответа: строку или список текстовых частей."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict)).strip()
    raise ValueError("Vision API вернул content неподдерживаемого формата.")

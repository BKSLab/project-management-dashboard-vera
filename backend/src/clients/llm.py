import asyncio
import json
import logging
import random
import re
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from src.exceptions.knowledge import KnowledgeProviderError

logger = logging.getLogger(__name__)
PydanticModel = TypeVar("PydanticModel", bound=BaseModel)
CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", flags=re.IGNORECASE)


class LlmClient:
    """OpenAI Chat Completions client со structured output и retry."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient,
        url: str,
        headers: dict[str, str],
        model: str,
        timeout: int,
        retries: int,
    ) -> None:
        self.http_client = http_client
        self.url = url
        self.headers = headers
        self.model = model
        self.timeout = timeout
        self.retries = retries

    async def get_structured_response(
        self,
        *,
        system_prompt: str,
        content: str,
        schema: type[PydanticModel],
        max_completion_tokens: int = 4000,
    ) -> PydanticModel:
        """Запрашивает JSON и валидирует его Pydantic-схемой."""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            "max_completion_tokens": max_completion_tokens,
            "response_format": {"type": "json_object"},
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
                content_value = response.json()["choices"][0]["message"]["content"]
                if not isinstance(content_value, str) or not content_value.strip():
                    raise ValueError("LLM вернул пустой content.")
                normalized = CODE_FENCE.sub("", content_value.strip()).strip()
                return schema.model_validate_json(normalized)
            except (
                httpx.HTTPError,
                KeyError,
                IndexError,
                TypeError,
                ValueError,
                ValidationError,
            ) as error:
                last_error = error
                logger.warning(
                    "⚠️ Ошибка LLM, попытка %s/%s: %s",
                    attempt,
                    self.retries,
                    error,
                )
                if attempt < self.retries:
                    await asyncio.sleep((2 ** (attempt - 1)) + random.random() * 0.2)
        raise KnowledgeProviderError(str(last_error))

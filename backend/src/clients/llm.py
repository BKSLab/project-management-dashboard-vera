import json
import logging
import re
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from src.clients.retry import (
    RetryDecision,
    classify,
    log_attempt,
    sleep_before_retry,
    worst_case_seconds,
)
from src.exceptions.knowledge import KnowledgeProviderError

logger = logging.getLogger(__name__)
PydanticModel = TypeVar("PydanticModel", bound=BaseModel)
CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", flags=re.IGNORECASE)
API_NAME = "LLM API"


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

    @property
    def worst_case_seconds(self) -> float:
        """Верхняя оценка длительности одного вызова с учётом повторов."""
        return worst_case_seconds(timeout=self.timeout, attempts=self.retries)

    async def get_structured_response(
        self,
        *,
        system_prompt: str,
        content: str,
        schema: type[PydanticModel],
        max_completion_tokens: int = 4000,
    ) -> PydanticModel:
        """Запрашивает JSON и валидирует его Pydantic-схемой.

        Повторяются только сеть, таймаут, 429 и 5xx, а также неразобранный
        ответ модели. Обычные 4xx завершаются сразу: повтор их не исправит,
        а бюджет вызова умножит на число попыток.

        Args:
            system_prompt: Системная инструкция модели.
            content: Пользовательская часть запроса.
            schema: Схема, которой должен соответствовать ответ.
            max_completion_tokens: Предел длины ответа модели.

        Returns:
            Разобранный и провалидированный ответ модели.

        Raises:
            KnowledgeProviderError: Если API недоступен или ответ не разобран.
        """
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

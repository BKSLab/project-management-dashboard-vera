"""Политика повторов LLM-клиента и расчёт бюджета вызова.

Повтор неретраебельной ошибки не исправляет результат, но умножает
worst-case на число попыток. Разделение категорий проверяется здесь,
потому что именно оно определяет фактический timeout budget.
"""

import json

import httpx
import pytest
from pydantic import BaseModel

from src.clients.llm import LlmClient
from src.clients.retry import RetryDecision, classify, worst_case_seconds
from src.exceptions.clients import LlmClientError


class AnswerSchema(BaseModel):
    """Минимальная схема структурированного ответа."""

    answer: str


def build_client(handler, *, retries: int = 2) -> LlmClient:
    """Собирает клиент поверх httpx-транспорта с подменённым обработчиком."""
    return LlmClient(
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        url="https://llm.test/v1/chat/completions",
        headers={"Authorization": "Bearer test"},
        model="test-model",
        timeout=5,
        retries=retries,
    )


def build_response(content: str) -> httpx.Response:
    """Ответ chat completions с заданным содержимым."""
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


async def _ask(client: LlmClient) -> AnswerSchema:
    """Выполняет типовой запрос структурированного ответа."""
    return await client.get_structured_response(
        system_prompt="Отвечай JSON.",
        content="Вопрос",
        schema=AnswerSchema,
    )


async def test_returns_validated_structured_answer() -> None:
    """Корректный JSON разбирается схемой."""
    client = build_client(lambda request: build_response(json.dumps({"answer": "готово"})))

    assert (await _ask(client)).answer == "готово"


async def test_strips_code_fence_around_json() -> None:
    """Модель нередко оборачивает JSON в ```json — обёртка снимается."""
    payload = "```json\n" + json.dumps({"answer": "готово"}) + "\n```"
    client = build_client(lambda request: build_response(payload))

    assert (await _ask(client)).answer == "готово"


async def test_client_error_is_not_retried() -> None:
    """Обычная 4xx завершается сразу и не тратит остальные попытки."""
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(403, json={"error": "forbidden"})

    with pytest.raises(LlmClientError):
        await _ask(build_client(handler, retries=3))

    assert attempts["count"] == 1


@pytest.mark.parametrize("status_code", [429, 500, 503])
async def test_retryable_statuses_are_retried(status_code: int) -> None:
    """429 и 5xx повторяются: причина сбоя на стороне сервера."""
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(status_code, json={"error": "retry"})
        return build_response(json.dumps({"answer": "готово"}))

    assert (await _ask(build_client(handler, retries=3))).answer == "готово"
    assert attempts["count"] == 2


async def test_transport_error_is_retried() -> None:
    """Сетевой сбой повторяется как транспортная ошибка."""
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise httpx.ConnectError("нет соединения", request=request)
        return build_response(json.dumps({"answer": "готово"}))

    assert (await _ask(build_client(handler, retries=3))).answer == "готово"
    assert attempts["count"] == 2


async def test_schema_violation_is_retried_as_content_failure() -> None:
    """Ответ, не прошедший схему, повторяется отдельной категорией."""
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return build_response(json.dumps({"wrong_field": 1}))
        return build_response(json.dumps({"answer": "готово"}))

    assert (await _ask(build_client(handler, retries=3))).answer == "готово"
    assert attempts["count"] == 2


async def test_worst_case_is_computed_from_timeout_and_attempts() -> None:
    """Бюджет вызова доступен как свойство клиента."""
    client = build_client(lambda request: build_response("{}"), retries=3)

    assert client.worst_case_seconds == pytest.approx(
        worst_case_seconds(timeout=5, attempts=3)
    )


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (400, RetryDecision.FAIL_FAST),
        (401, RetryDecision.FAIL_FAST),
        (403, RetryDecision.FAIL_FAST),
        (404, RetryDecision.FAIL_FAST),
        (408, RetryDecision.RETRY_TRANSPORT),
        (429, RetryDecision.RETRY_TRANSPORT),
        (500, RetryDecision.RETRY_TRANSPORT),
        (503, RetryDecision.RETRY_TRANSPORT),
    ],
)
def test_status_classification(status_code: int, expected: RetryDecision) -> None:
    """Классификация HTTP-статусов зафиксирована явно."""
    request = httpx.Request("POST", "https://llm.test")
    error = httpx.HTTPStatusError(
        "ошибка",
        request=request,
        response=httpx.Response(status_code, request=request),
    )

    assert classify(error) is expected


def test_non_http_error_is_content_failure() -> None:
    """Ошибка разбора относится к содержимому, а не к транспорту."""
    assert classify(ValueError("плохой JSON")) is RetryDecision.RETRY_CONTENT


def test_worst_case_requires_at_least_one_attempt() -> None:
    """Ноль попыток — некорректный бюджет, а не мгновенный вызов."""
    with pytest.raises(ValueError):
        worst_case_seconds(timeout=5, attempts=0)


def test_worst_case_matches_documented_production_budget() -> None:
    """Продовые значения дают известный worst case не менее 900 секунд.

    Это число зафиксировано в docs/AI_TIMEOUT_BUDGET_DECISION.md и служит
    основанием follow-up по асинхронному контракту.
    """
    assert worst_case_seconds(timeout=300, attempts=3) >= 900

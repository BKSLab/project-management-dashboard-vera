"""Классификация ошибок внешних API и расчёт worst-case бюджета вызова.

Общий `httpx.HTTPError` не годится как условие повтора: под ним лежат и
таймаут, который стоит повторить, и `401`, повтор которого бесполезен и
только умножает потраченное время на величину `retries`.
"""

import asyncio
import logging
import random
from enum import Enum

import httpx

logger = logging.getLogger(__name__)

# Коды, при которых повтор осмыслен: сервер сам просит подождать либо
# сломался на своей стороне.
RETRYABLE_STATUS_CODES = frozenset({408, 409, 425, 429})
BACKOFF_JITTER_SECONDS = 0.2


class RetryDecision(Enum):
    """Что делать с конкретной ошибкой внешнего вызова."""

    RETRY_TRANSPORT = "transport"
    """Сеть, таймаут, 429 или 5xx: повторяем."""

    RETRY_CONTENT = "content"
    """Ответ получен, но не разобран или не прошёл валидацию: повторяем
    отдельной категорией, потому что причина не в транспорте."""

    FAIL_FAST = "fail_fast"
    """Ошибка запроса, которую повтор не исправит: обычные 4xx."""


def classify(error: Exception) -> RetryDecision:
    """Определяет, стоит ли повторять вызов после этой ошибки.

    Args:
        error: Исключение, пойманное вокруг одного обращения к API.

    Returns:
        Решение о повторе.
    """
    if isinstance(error, httpx.HTTPStatusError):
        status_code = error.response.status_code
        if status_code >= 500 or status_code in RETRYABLE_STATUS_CODES:
            return RetryDecision.RETRY_TRANSPORT
        if 400 <= status_code < 500:
            return RetryDecision.FAIL_FAST
        return RetryDecision.RETRY_TRANSPORT
    if isinstance(error, httpx.HTTPError):
        # Таймауты и транспортные сбои: сюда же попадают TimeoutException,
        # ConnectError и прочие сетевые ошибки httpx.
        return RetryDecision.RETRY_TRANSPORT
    return RetryDecision.RETRY_CONTENT


def backoff_seconds(attempt: int) -> float:
    """Возвращает паузу перед следующей попыткой с джиттером.

    Args:
        attempt: Номер завершившейся попытки, начиная с единицы.

    Returns:
        Длительность паузы в секундах.
    """
    return (2 ** (attempt - 1)) + random.random() * BACKOFF_JITTER_SECONDS


async def sleep_before_retry(attempt: int) -> None:
    """Выжидает паузу перед повтором."""
    await asyncio.sleep(backoff_seconds(attempt))


def worst_case_seconds(*, timeout: float, attempts: int) -> float:
    """Считает верхнюю оценку длительности вызова с учётом повторов.

    Формула из [PAT-CLIENT]: ``timeout × attempts + суммарный backoff``.
    Значение используется, чтобы сверять бюджет клиента с timeout-ами
    прокси и не выяснять это уже в проде.

    Args:
        timeout: Таймаут одного обращения в секундах.
        attempts: Максимальное число попыток.

    Returns:
        Верхняя оценка длительности вызова в секундах.
    """
    if attempts < 1:
        raise ValueError("Число попыток должно быть не меньше одной.")
    backoff = sum(2 ** (attempt - 1) for attempt in range(1, attempts))
    jitter = BACKOFF_JITTER_SECONDS * (attempts - 1)
    return timeout * attempts + backoff + jitter


def log_attempt(*, api_name: str, decision: RetryDecision, attempt: int, attempts: int, error: Exception) -> None:
    """Пишет попытку в лог, разделяя транспортные и содержательные сбои."""
    if decision is RetryDecision.RETRY_CONTENT:
        logger.warning(
            "⚠️ %s вернул неразобранный ответ, попытка %s/%s: %s",
            api_name,
            attempt,
            attempts,
            error,
        )
        return
    if decision is RetryDecision.FAIL_FAST:
        logger.error("❌ %s отклонил запрос без права на повтор: %s", api_name, error)
        return
    logger.warning("⚠️ Ошибка %s, попытка %s/%s: %s", api_name, attempt, attempts, error)

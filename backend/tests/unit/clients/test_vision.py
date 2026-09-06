import json

import httpx
import pytest

from src.clients.vision import DisabledVisionCapability, VisionCapability, VisionClient
from src.exceptions.clients import VisionClientError


def build_client(handler, *, retries: int = 2) -> VisionClient:
    """Собирает клиент поверх httpx-транспорта с подменённым обработчиком."""
    return VisionClient(
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        url="https://llm.test/v1/chat/completions",
        headers={"Authorization": "Bearer test"},
        model="vision-model",
        timeout=5,
        retries=retries,
        max_tokens=1000,
    )


def build_response(content) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


async def test_vision_retries_transient_failures_only() -> None:
    """Временный сбой повторяется, исчерпание попыток даёт ошибку провайдера, ошибка клиента не повторяется."""

    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(503, json={"error": "overloaded"})
        return build_response("Готово")

    assert (
        await build_client(handler).extract_text(
            image_data_url="data:image/jpeg;base64,QUJD"
        )
        == "Готово"
    )
    assert attempts["count"] == 2

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    with pytest.raises(VisionClientError):
        await build_client(handler).extract_text(
            image_data_url="data:image/jpeg;base64,QUJD"
        )
    # Обычная 4xx завершается сразу: повтор её не исправит. Раньше `401` повторялся наравне с таймаутом и умножал бюджет вызова на число попыток, ничего не меняя в результате.
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        return httpx.Response(401, json={"error": "unauthorized"})

    with pytest.raises(VisionClientError):
        await build_client(handler, retries=3).extract_text(
            image_data_url="data:image/jpeg;base64,QUJD"
        )

    assert attempts["count"] == 1


async def test_worst_case_accounts_for_every_attempt() -> None:
    """Бюджет вызова считается по формуле timeout × попытки плюс backoff."""
    client = build_client(lambda request: build_response("ok"), retries=3)

    # 5 × 3 = 15 секунд ожидания плюс backoff 1 + 2 секунды между попытками.
    assert client.worst_case_seconds >= 18
    assert client.worst_case_seconds < 19


async def test_disabled_capability_reports_no_text() -> None:
    """Выключенное распознавание — объект, а не отсутствие зависимости."""
    capability = DisabledVisionCapability()

    assert await capability.extract_image_text(filename="схема.png", content=b"ABC") is None
    assert isinstance(capability, VisionCapability)


async def test_vision_retries_every_transient_category() -> None:
    """Ограничение частоты, timeout и неразбираемый ответ повторяются как отдельные категории."""
    # 429 повторяется: сервер сам просит подождать.
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(429, json={"error": "slow down"})
        return build_response("Готово")

    text = await build_client(handler, retries=3).extract_text(
        image_data_url="data:image/jpeg;base64,QUJD"
    )

    assert text == "Готово"
    assert attempts["count"] == 2
    # Таймаут повторяется как транспортная ошибка.
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise httpx.ReadTimeout("timeout", request=request)
        return build_response("Готово")

    text = await build_client(handler, retries=3).extract_text(
        image_data_url="data:image/jpeg;base64,QUJD"
    )

    assert text == "Готово"
    assert attempts["count"] == 2
    # Неразобранный ответ повторяется, но не считается сбоем транспорта.
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(200, json={"choices": [{"message": {"content": 42}}]})
        return build_response("Готово")

    text = await build_client(handler, retries=3).extract_text(
        image_data_url="data:image/jpeg;base64,QUJD"
    )

    assert text == "Готово"
    assert attempts["count"] == 2


async def test_vision_sends_images_as_data_urls() -> None:
    """Изображение уходит data-URL, многочастный ответ склеивается, извлечение строит data-URL само."""

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return build_response("  Схема узла  ")

    text = await build_client(handler).extract_text(
        image_data_url="data:image/png;base64,QUJD"
    )

    assert text == "Схема узла"
    assert captured["model"] == "vision-model"
    image_part = captured["messages"][0]["content"][1]
    assert image_part["image_url"]["url"] == "data:image/png;base64,QUJD"

    def handler(request: httpx.Request) -> httpx.Response:
        return build_response([{"type": "text", "text": "Первая. "}, {"text": "Вторая."}])

    assert (
        await build_client(handler).extract_text(
            image_data_url="data:image/webp;base64,QUJD"
        )
        == "Первая. Вторая."
    )
    # Кодирование изображения принадлежит клиенту, а не вызывающему коду.
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return build_response("Схема узла")

    text = await build_client(handler).extract_image_text(
        filename="схема.png",
        content=b"ABC",
    )

    assert text == "Схема узла"
    image_part = captured["messages"][0]["content"][1]
    assert image_part["image_url"]["url"] == "data:image/png;base64,QUJD"

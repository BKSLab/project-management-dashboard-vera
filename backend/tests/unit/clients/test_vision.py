import json

import httpx
import pytest

from src.clients.vision import VisionClient
from src.exceptions.knowledge import KnowledgeProviderError


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


async def test_sends_image_as_data_url_and_returns_text() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return build_response("  Схема узла  ")

    text = await build_client(handler).extract_text(image_base64="QUJD")

    assert text == "Схема узла"
    assert captured["model"] == "vision-model"
    image_part = captured["messages"][0]["content"][1]
    assert image_part["image_url"]["url"] == "data:image/jpeg;base64,QUJD"


async def test_joins_multipart_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return build_response([{"type": "text", "text": "Первая. "}, {"text": "Вторая."}])

    assert await build_client(handler).extract_text(image_base64="QUJD") == "Первая. Вторая."


async def test_retries_then_succeeds() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(503, json={"error": "overloaded"})
        return build_response("Готово")

    assert await build_client(handler).extract_text(image_base64="QUJD") == "Готово"
    assert attempts["count"] == 2


async def test_raises_provider_error_after_all_attempts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    with pytest.raises(KnowledgeProviderError):
        await build_client(handler).extract_text(image_base64="QUJD")

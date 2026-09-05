"""Общие приспособления characterization-тестов.

Эти тесты фиксируют внешний контракт приложения до архитектурного
рефакторинга. Они намеренно проверяют только то, что видит клиент: статус,
заголовки, тело ответа и имена MCP-инструментов, — и не должны опираться на
внутреннее устройство слоёв, которое рефакторинг как раз меняет.
"""

from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.fixture
def anonymous() -> Generator[None, None, None]:
    """Снимает автоподмену сессии: контракт входа проверяется целиком."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def raw_client() -> AsyncGenerator[AsyncClient, None]:
    """HTTP-клиент без автоматического следования редиректам."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

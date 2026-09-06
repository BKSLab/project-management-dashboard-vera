"""Фабрики клиентов внешних систем.

Фабрика обязана только доставать готовый ресурс. Клиент, созданный на
запрос, обошёл бы общий пул соединений и общий lifecycle, поэтому здесь
проверяется именно это: тот же объект, что положил lifespan, и понятная
ошибка, если lifespan не отработал.
"""

from types import SimpleNamespace

import pytest
from fastapi import Request

from src.core.app_state import RUNTIME_STATE_KEY
from src.dependencies.clients import (
    get_embedding_client,
    get_llm_client,
    get_qdrant_client,
    get_vision_capability,
)
from src.dependencies.http_client import (
    RUNTIME_MISSING,
    get_http_client,
    get_knowledge_runtime,
)


@pytest.fixture
def runtime() -> SimpleNamespace:
    """Контейнер клиентов, какой создаёт lifespan приложения."""
    return SimpleNamespace(
        http_client=object(),
        embedding_client=object(),
        llm_client=object(),
        qdrant_client=object(),
        vision=object(),
    )


def build_request(state: dict) -> Request:
    """Собирает запрос с состоянием, которое приложение отдаёт из lifespan."""
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "query_string": b"",
            "state": state,
        }
    )


def test_runtime_is_taken_from_application_state(runtime: SimpleNamespace) -> None:
    """Runtime приходит из состояния приложения, его отсутствие — явная ошибка."""
    # Контейнер берётся из состояния приложения, а не создаётся заново.
    request = build_request({RUNTIME_STATE_KEY: runtime})

    assert get_knowledge_runtime(request) is runtime
    # Запуск без lifespan — ошибка сборки, а не новый клиент на запрос.
    request = build_request({})

    with pytest.raises(RuntimeError) as error:
        get_knowledge_runtime(request)

    assert str(error.value) == RUNTIME_MISSING


@pytest.mark.parametrize(('factory', 'attribute'), [(get_http_client, 'http_client'), (get_llm_client, 'llm_client'), (get_embedding_client, 'embedding_client'), (get_qdrant_client, 'qdrant_client'), (get_vision_capability, 'vision')])
def test_factories_return_the_same_lifespan_owned_client(runtime: SimpleNamespace, factory, attribute: str) -> None:
    """Фабрика отдаёт клиента, созданного lifespan-ом, и не создаёт нового при повторном вызове."""
    # Каждая фабрика отдаёт ровно тот объект, которым владеет lifespan.
    assert factory(runtime) is getattr(runtime, attribute)
    # Повторный запрос не создаёт второй клиент.
    assert get_llm_client(runtime) is get_llm_client(runtime)
    assert get_qdrant_client(runtime) is get_qdrant_client(runtime)

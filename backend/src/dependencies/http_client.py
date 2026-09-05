"""Доступ к общему HTTP-клиенту внешних API.

Клиент создаётся один раз в lifespan приложения. Фабрика ничего не
создаёт: она только достаёт готовый ресурс. Отсутствие ресурса — ошибка
сборки приложения, а не повод молча открыть новый клиент на запрос,
иначе пул соединений перестанет быть общим и ограниченным.
"""

from typing import Annotated

import httpx
from fastapi import Depends, Request

from src.core.app_state import RUNTIME_STATE_KEY
from src.knowledge.runtime import KnowledgeRuntime

RUNTIME_MISSING = (
    "Клиенты внешних API недоступны: контейнер не создан в lifespan приложения."
)


def get_knowledge_runtime(request: Request) -> KnowledgeRuntime:
    """Возвращает контейнер клиентов, созданный lifespan приложения.

    Args:
        request: HTTP-запрос, через состояние которого доступны ресурсы приложения.

    Returns:
        Контейнер долгоживущих клиентов внешних API.

    Raises:
        RuntimeError: Если приложение запущено без lifespan.
    """
    runtime = getattr(request.state, RUNTIME_STATE_KEY, None)
    if runtime is None:
        raise RuntimeError(RUNTIME_MISSING)
    return runtime


KnowledgeRuntimeDep = Annotated[KnowledgeRuntime, Depends(get_knowledge_runtime)]


def get_http_client(runtime: KnowledgeRuntimeDep) -> httpx.AsyncClient:
    """Возвращает общий HTTP-клиент внешних API."""
    return runtime.http_client


HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]

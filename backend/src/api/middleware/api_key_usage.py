"""Учёт обращений по сервисному API-ключу в REST .

Почему мидлварь, а не запись в каждом эндпоинте: методов много, телеметрия
одинаковая, и забыть её в новом методе не должно быть возможности. Строка
пишется только для запросов, которые ``get_principal`` опознал как запросы
по ключу (он кладёт ключ в ``request.state.api_key``); запросы людей из
интерфейса в журнал не попадают.

Мидлварь написана на голом ASGI, а не на ``BaseHTTPMiddleware``: та
буферизует потоковые ответы (скачивание вложений), а здесь нужно лишь
подсмотреть код ответа. Запись идёт фоновой задачей со своей сессией:
ответ не ждёт журнала, а сбой журнала не становится ошибкой запроса.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from urllib.parse import parse_qsl

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

#: Сколько записей журнала пишется одновременно: телеметрия берёт соединения
#: из того же пула, что и боевые запросы.
MAX_CONCURRENT_WRITERS = 4

Recorder = Callable[..., Awaitable[None]]


class ApiKeyUsageMiddleware:
    """Пишет строку журнала на каждый REST-запрос по сервисному ключу."""

    def __init__(self, app: ASGIApp, *, recorder: Recorder, prefix: str = "/api/") -> None:
        self.app = app
        self.recorder = recorder
        self.prefix = prefix
        self._slots = asyncio.Semaphore(MAX_CONCURRENT_WRITERS)
        # Цикл событий держит задачу слабой ссылкой: без множества запись
        # могла бы пропасть, не дойдя до commit.
        self._pending: set[asyncio.Task] = set()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith(self.prefix):
            await self.app(scope, receive, send)
            return

        started_at = datetime.now(UTC)
        started = time.perf_counter()
        response: dict = {"status": 500, "bytes": 0}

        async def watch(message: Message) -> None:
            if message["type"] == "http.response.start":
                response["status"] = message["status"]
            elif message["type"] == "http.response.body":
                response["bytes"] += len(message.get("body", b""))
            await send(message)

        try:
            await self.app(scope, receive, watch)
        finally:
            # Ключ кладёт get_principal в request.state — это словарь scope["state"].
            state = scope.get("state") or {}
            api_key = state.get("api_key") if isinstance(state, dict) else None
            if api_key is not None:
                self._schedule(scope, api_key, started_at, started, response)

    def _schedule(self, scope: Scope, api_key, started_at, started, response) -> None:
        """Ставит запись журнала в фон."""
        route = scope.get("route")
        path = scope.get("path", "")
        query = _parse_query(scope.get("query_string", b""))
        fields = {
            "api_key_id": api_key.key_id,
            "key_prefix": api_key.key_prefix,
            "at": started_at,
            "channel": "rest",
            "method": scope.get("method", ""),
            "route": getattr(route, "path", None) or path,
            "path": path,
            "query": query,
            "actor_login": (scope.get("state") or {}).get("api_key_actor_login"),
            "status_code": response["status"],
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "response_bytes": response["bytes"] or None,
            "client_ip": _client_ip(scope),
        }

        async def write() -> None:
            async with self._slots:
                await self.recorder(**fields)

        task = asyncio.create_task(write())
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)


def _parse_query(raw: bytes) -> dict[str, str]:
    """Разбирает строку запроса в словарь (последнее значение побеждает)."""
    return dict(parse_qsl(raw.decode("latin-1"), keep_blank_values=True))


def _client_ip(scope: Scope) -> str | None:
    """Адрес клиента: первое значение X-Forwarded-For или адрес соединения."""
    for name, value in scope.get("headers", []):
        if name == b"x-forwarded-for":
            first = value.decode("latin-1").split(",")[0].strip()
            if first:
                return first
    client = scope.get("client")
    return client[0] if client else None

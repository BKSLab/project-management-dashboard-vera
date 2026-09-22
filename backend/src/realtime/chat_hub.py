"""Локальные ограниченные очереди: медленный клиент не тормозит остальных."""

import asyncio
from collections import Counter
from dataclasses import dataclass, field
from time import monotonic
from uuid import uuid4

from src.exceptions.project_chats import ChatUnavailableError


@dataclass(eq=False)
class ChatConnection:
    """Сокет хранит только идентификаторы и очередь, без сессии PostgreSQL."""

    project_id: int
    user_id: int
    queue: asyncio.Queue
    id: str = field(default_factory=lambda: uuid4().hex)
    closed: asyncio.Event = field(default_factory=asyncio.Event)
    close_code: int = 1000

    def close(self, code: int) -> None:
        """Останавливает выдачу, включая ранее накопленную очередь."""
        self.close_code = code
        self.closed.set()


class ChatHub:
    """Fan-out внутри процесса; между процессами сообщения переносит Redis."""

    def __init__(self, *, queue_size: int, max_connections: int):
        self.queue_size = queue_size
        self.max_connections = max_connections
        self.connections: dict[str, ChatConnection] = {}
        self.metrics = Counter()

    def connect(self, project_id: int, user_id: int) -> ChatConnection:
        """Регистрирует соединение с явным пределом памяти."""
        if len(self.connections) >= self.max_connections:
            raise ChatUnavailableError("Достигнут предел подключений.")
        connection = ChatConnection(project_id, user_id, asyncio.Queue(maxsize=self.queue_size))
        self.connections[connection.id] = connection
        self.metrics["connections_total"] += 1
        return connection

    def disconnect(self, connection: ChatConnection) -> None:
        """Освобождает ссылку на очередь независимо от причины отключения."""
        self.connections.pop(connection.id, None)
        connection.close(connection.close_code)
        self.metrics["disconnections_total"] += 1

    def enqueue(self, connection: ChatConnection, event: dict) -> None:
        """Переполнение требует reconnect/resync, а не молчаливой потери события."""
        if connection.closed.is_set():
            return
        try:
            connection.queue.put_nowait(event)
        except asyncio.QueueFull:
            self.metrics["slow_clients_total"] += 1
            connection.close(1013)

    def broadcast(self, event: dict) -> None:
        """Отзыв membership закрывает все вкладки пользователя в этом процессе."""
        started = monotonic()
        for connection in list(self.connections.values()):
            if connection.project_id != event["project_id"]:
                continue
            if event["type"] == "member.removed" and event["data"]["user_id"] == connection.user_id:
                connection.close(4403)
            else:
                self.enqueue(connection, event)
        self.metrics["received_events_total"] += 1
        self.metrics["fanout_ms_sum"] += (monotonic() - started) * 1000

    def close_all(self, code: int = 1013) -> None:
        """При потере Redis-подписки заставляет клиентов восстановить дельту."""
        for connection in self.connections.values():
            connection.close(code)

    def snapshot(self) -> dict:
        """Счётчики процесса для структурированных метрик в логах."""
        return {
            **self.metrics,
            "active_connections": len(self.connections),
            "queued_events": sum(
                connection.queue.qsize() for connection in self.connections.values()
            ),
        }

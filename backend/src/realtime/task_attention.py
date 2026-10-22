"""Один LISTEN на процесс, а не постоянное соединение БД на браузер."""

import asyncio
import logging
from contextlib import suppress
from datetime import UTC, datetime, timedelta

import asyncpg

logger = logging.getLogger(__name__)


class TaskAttentionRuntime:
    def __init__(self, *, connect, authenticate, snapshot, config) -> None:
        self.connect = connect
        self.authenticate = authenticate
        self.snapshot = snapshot
        self.config = config
        self.generation = 0
        self.ready = False
        self.listeners: set[asyncio.Event] = set()
        self.task = None

    def wake(self) -> None:
        """Уведомления содержат только сигнал; персональные данные читаются с проверкой прав."""
        self.generation += 1
        for listener in self.listeners:
            listener.set()

    async def start(self) -> None:
        """LISTEN может восстановиться; HTTP и fallback не зависят от его доступности."""
        self.task = asyncio.create_task(self._listen(), name="task-attention-listen")

    async def close(self) -> None:
        self.ready = False
        self.wake()
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task

    async def _listen(self) -> None:
        while True:
            connection = None
            try:
                connection = await self.connect()
                await connection.add_listener("task_attention", lambda *_args: self.wake())
                self.ready = True
                self.wake()
                while True:
                    await asyncio.sleep(self.config.attention_heartbeat_seconds)
                    await connection.execute("SELECT 1")
            except (asyncpg.PostgresError, OSError, TimeoutError):
                self.ready = False
                self.wake()
                logger.warning(
                    "⚠️ LISTEN счётчиков задач недоступен; переподключаемся.", exc_info=True
                )
                await asyncio.sleep(self.config.attention_reconnect_seconds)
            finally:
                if connection is not None:
                    await connection.close()

    def subscribe(self) -> asyncio.Event:
        """Ограничивает число подписчиков и возвращает объединяемый сигнал пересинхронизации."""
        if len(self.listeners) >= self.config.attention_max_connections:
            raise RuntimeError("Достигнут лимит подписчиков счётчиков.")
        listener = asyncio.Event()
        self.listeners.add(listener)
        return listener

    def unsubscribe(self, listener: asyncio.Event) -> None:
        self.listeners.discard(listener)

    async def wait(self, listener: asyncio.Event, generation: int) -> bool:
        """Полночь сама создаёт новый сигнал просрочки даже без изменений задачи."""
        listener.clear()
        if generation != self.generation:
            return True
        now = datetime.now(UTC)
        midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), UTC)
        timeout = min((midnight - now).total_seconds(), self.config.attention_heartbeat_seconds)
        try:
            await asyncio.wait_for(listener.wait(), timeout=timeout)
            await asyncio.sleep(self.config.attention_debounce_seconds)
            return True
        except TimeoutError:
            return datetime.now(UTC).date() != now.date()

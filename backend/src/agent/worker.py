import asyncio
import logging

from src.services.agent_conversations import AgentConversationsService

logger = logging.getLogger(__name__)


class AgentWorker:
    """Ограниченное число исполнителей постоянной очереди ответов."""

    def __init__(
        self, *, service: AgentConversationsService, poll_seconds: float, concurrency: int
    ) -> None:
        self.service = service
        self.poll_seconds = poll_seconds
        self.concurrency = concurrency

    async def run(self, stop_event: asyncio.Event) -> None:
        """Обрабатывает вопросы до остановки приложения.

        Args:
            stop_event: Сигнал завершения lifespan.
        """
        async with asyncio.TaskGroup() as group:
            for _ in range(self.concurrency):
                group.create_task(self._consume(stop_event))

    async def _consume(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                if await self.service.process_next():
                    continue
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.error("❌ Очередь ответов агента временно недоступна.", exc_info=True)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self.poll_seconds)
            except TimeoutError:
                pass

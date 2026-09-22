"""Публикация outbox без удержания PostgreSQL во время сетевых вызовов."""

from collections import defaultdict

from src.clients.chat_redis import ChatRedisClient
from src.services.project_chats import ProjectChatService


class ChatDeliveryService:
    """At-least-once доставка; клиент устраняет повторы по seq."""

    def __init__(self, chat: ProjectChatService, redis: ChatRedisClient, batch_size: int):
        self.chat = chat
        self.redis = redis
        self.batch_size = batch_size

    async def flush(self) -> int:
        """Читает и гидратирует batch, освобождает БД, затем публикует."""
        async with self.chat.operation() as db:
            pending = await db.events.get_pending(limit=self.batch_size)
            groups = defaultdict(list)
            for row, project_id in pending:
                groups[project_id].append(row)
            outgoing = []
            for project_id, rows in groups.items():
                views = await self.chat.present_events(db, project_id, rows)
                outgoing.extend(
                    (row.id, event.model_dump(mode="json"))
                    for row, event in zip(rows, views, strict=True)
                )
        delivered = []
        for event_id, event in outgoing:
            await self.redis.publish(event["project_id"], event)
            delivered.append(event_id)
        if delivered:
            async with self.chat.operation() as db:
                await db.events.mark_published(delivered)
                await db.unit_of_work.commit()
        return len(delivered)

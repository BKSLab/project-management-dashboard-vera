"""Хранение упорядоченных структурированных ссылок."""

from sqlalchemy import delete, insert, select

from src.db.models.chat_message_entities import ChatMessageEntity
from src.repositories.chat_base import ChatRepository


class ChatMessageEntitiesRepository(ChatRepository):
    """Замена набора ссылок координируется сервисом."""

    async def get_many(self, message_ids: list[int]):
        """Читает ссылки всей страницы одним запросом."""
        return list(
            (
                await self._execute(
                    select(ChatMessageEntity)
                    .where(ChatMessageEntity.message_id.in_(message_ids))
                    .order_by(ChatMessageEntity.position)
                )
            ).scalars()
        )

    async def save_many(self, items: list[dict]) -> None:
        """Сохраняет непустой набор ссылок одной вставкой."""
        await self._execute(insert(ChatMessageEntity).values(items))

    async def delete(self, message_id: int) -> None:
        """Удаляет предыдущие ссылки при правке сообщения."""
        await self._execute(
            delete(ChatMessageEntity).where(ChatMessageEntity.message_id == message_id)
        )

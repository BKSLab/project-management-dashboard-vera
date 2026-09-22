"""Явные упоминания сообщения."""

from sqlalchemy import delete, insert, select

from src.db.models.chat_message_mentions import ChatMessageMention
from src.repositories.chat_base import ChatRepository


class ChatMessageMentionsRepository(ChatRepository):
    """Упоминания не извлекаются из текста регулярными выражениями."""

    async def get_many(self, message_ids: list[int]):
        """Возвращает упоминания страницы."""
        return list(
            (
                await self._execute(
                    select(ChatMessageMention).where(ChatMessageMention.message_id.in_(message_ids))
                )
            ).scalars()
        )

    async def save_many(self, items: list[dict]) -> None:
        """Сохраняет непустой набор упоминаний."""
        await self._execute(insert(ChatMessageMention).values(items))

    async def delete(self, message_id: int) -> None:
        """Убирает упоминания предыдущей версии сообщения."""
        await self._execute(
            delete(ChatMessageMention).where(ChatMessageMention.message_id == message_id)
        )

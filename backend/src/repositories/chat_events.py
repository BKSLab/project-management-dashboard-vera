"""Хранение событий отдельно от их сетевой доставки."""

from sqlalchemy import func, insert, select, update

from src.db.models.chat_events import ChatEvent
from src.db.models.project_chats import ProjectChat
from src.repositories.chat_base import ChatRepository


class ChatEventsRepository(ChatRepository):
    """Дубли публикации допустимы: курсор делает применение идемпотентным."""

    async def save(self, chat_id: int, seq: int, event_type: str, payload: dict):
        """Сохраняет событие в одной транзакции с изменением сообщения."""
        return (
            await self._execute(
                insert(ChatEvent)
                .values(chat_id=chat_id, seq=seq, event_type=event_type, payload=payload)
                .returning(ChatEvent)
            )
        ).scalar_one()

    async def get_page(self, chat_id: int, after: int, *, limit: int = 201):
        """Читает долговечную дельту, включая события старых сообщений."""
        return list(
            (
                await self._execute(
                    select(ChatEvent)
                    .where(ChatEvent.chat_id == chat_id, ChatEvent.seq > after)
                    .order_by(ChatEvent.seq)
                    .limit(limit)
                )
            ).scalars()
        )

    async def get_pending(self, *, limit: int):
        """Получает outbox без удержания транзакции во время Redis publish."""
        return list(
            (
                await self._execute(
                    select(ChatEvent, ProjectChat.project_id)
                    .join(ProjectChat, ProjectChat.id == ChatEvent.chat_id)
                    .where(ChatEvent.published_at.is_(None))
                    .order_by(ChatEvent.id)
                    .limit(limit)
                )
            ).all()
        )

    async def mark_published(self, event_ids: list[int]) -> None:
        """Отметка идёт после успешной публикации; сбой приводит к повтору."""
        await self._execute(
            update(ChatEvent).where(ChatEvent.id.in_(event_ids)).values(published_at=func.now())
        )

"""Чтение чата и сериализация его долговечных событий."""

from sqlalchemy import select, update

from src.db.models.project_chats import ProjectChat
from src.repositories.chat_base import ChatRepository


class ProjectChatsRepository(ChatRepository):
    """Чат создаёт lifecycle-триггер проекта в той же транзакции."""

    async def get(self, project_id: int, *, lock: bool = False):
        """Возвращает чат; блокировка удерживается только на время записи."""
        statement = select(ProjectChat).where(ProjectChat.project_id == project_id)
        if lock:
            statement = statement.with_for_update()
        return (await self._execute(statement)).scalar_one_or_none()

    async def next_seq(self, chat_id: int) -> int:
        """Выделяет курсор под блокировкой строки, поэтому порядок равен commit."""
        return (
            await self._execute(
                update(ProjectChat)
                .where(ProjectChat.id == chat_id)
                .values(last_event_seq=ProjectChat.last_event_seq + 1)
                .returning(ProjectChat.last_event_seq)
            )
        ).scalar_one()

    async def project_id(self, chat_id: int) -> int | None:
        """Находит проект для фоновой очистки загрузок."""
        return (
            await self._execute(select(ProjectChat.project_id).where(ProjectChat.id == chat_id))
        ).scalar_one_or_none()

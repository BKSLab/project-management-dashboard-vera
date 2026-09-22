"""Идемпотентная установка и снятие реакций."""

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from src.db.models.chat_reactions import ChatReaction
from src.repositories.chat_base import ChatRepository


class ChatReactionsRepository(ChatRepository):
    """Уникальность обеспечивает составной первичный ключ."""

    async def get_many(self, message_ids: list[int]):
        """Возвращает реакции сразу для страницы сообщений."""
        return list(
            (
                await self._execute(
                    select(ChatReaction)
                    .where(ChatReaction.message_id.in_(message_ids))
                    .order_by(ChatReaction.reaction, ChatReaction.user_id)
                )
            ).scalars()
        )

    async def add(self, message_id: int, user_id: int, reaction: str) -> bool:
        """Повторная установка не создаёт новую реакцию."""
        return (
            await self._execute(
                insert(ChatReaction)
                .values(message_id=message_id, user_id=user_id, reaction=reaction)
                .on_conflict_do_nothing()
                .returning(ChatReaction.message_id)
            )
        ).scalar_one_or_none() is not None

    async def remove(self, message_id: int, user_id: int, reaction: str) -> bool:
        """Повторное снятие не меняет состояние."""
        return (
            await self._execute(
                delete(ChatReaction)
                .where(
                    ChatReaction.message_id == message_id,
                    ChatReaction.user_id == user_id,
                    ChatReaction.reaction == reaction,
                )
                .returning(ChatReaction.message_id)
            )
        ).scalar_one_or_none() is not None

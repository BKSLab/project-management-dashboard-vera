"""Монотонные отметки прочтения, общие для вкладок пользователя."""

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from src.db.models.chat_read_states import ChatReadState
from src.repositories.chat_base import ChatRepository


class ChatReadStatesRepository(ChatRepository):
    """Граница никогда не откатывается при запоздалом событии другой вкладки."""

    async def get(self, chat_id: int, user_id: int) -> int:
        """Возвращает границу либо начало истории."""
        return (
            await self._execute(
                select(ChatReadState.last_read_seq).where(
                    ChatReadState.chat_id == chat_id, ChatReadState.user_id == user_id
                )
            )
        ).scalar_one_or_none() or 0

    async def advance(self, chat_id: int, user_id: int, seq: int) -> int:
        """Атомарно выбирает максимальную увиденную границу."""
        statement = insert(ChatReadState).values(
            chat_id=chat_id, user_id=user_id, last_read_seq=seq
        )
        return (
            await self._execute(
                statement.on_conflict_do_update(
                    index_elements=["chat_id", "user_id"],
                    set_={
                        "last_read_seq": func.greatest(ChatReadState.last_read_seq, seq),
                        "updated_at": func.now(),
                    },
                ).returning(ChatReadState.last_read_seq)
            )
        ).scalar_one()

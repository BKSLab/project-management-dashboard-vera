"""Общий перевод ошибок драйвера для репозиториев чата."""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions.project_chats import ChatRepositoryError


class ChatRepository:
    """Репозиторий не завершает транзакцию и не вызывает другие репозитории."""

    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def _execute(self, statement):
        try:
            return await self.db_session.execute(statement)
        except SQLAlchemyError as error:
            # SQLAlchemy включает bind parameters в str(error); текст чата не должен попасть в логи.
            raise ChatRepositoryError(type(error).__name__) from None

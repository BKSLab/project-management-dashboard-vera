import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions.unit_of_work import UnitOfWorkRepositoryError

logger = logging.getLogger(__name__)


class UnitOfWork:
    """Фиксирует общую транзакцию доменного изменения и outbox-заданий."""

    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def commit(self) -> None:
        """Фиксирует все изменения текущего бизнес-сценария."""
        try:
            await self.db_session.commit()
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось зафиксировать транзакцию операции.", exc_info=True)
            raise UnitOfWorkRepositoryError(str(error)) from error

    async def rollback(self) -> None:
        """Откатывает все изменения текущего бизнес-сценария."""
        try:
            await self.db_session.rollback()
        except SQLAlchemyError as error:
            logger.error("❌ Не удалось откатить транзакцию операции.", exc_info=True)
            raise UnitOfWorkRepositoryError(str(error)) from error


class AgentToolUnitOfWork(UnitOfWork):
    """Фиксирует действие и журнал вместе поверх commit доменных сервисов.

    Внутренняя сессия подключена к внешней транзакции через create_savepoint:
    commit сервиса завершает SAVEPOINT, а общий commit выполняется здесь.
    """

    def __init__(self, db_session: AsyncSession, inner_session: AsyncSession) -> None:
        super().__init__(db_session)
        self.inner_session = inner_session
        self.committed = False

    async def commit(self) -> None:
        """Фиксирует результат инструмента и его эффект одной транзакцией БД."""
        try:
            await self.inner_session.commit()
            await self.db_session.commit()
            self.committed = True
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            raise UnitOfWorkRepositoryError(str(error)) from error

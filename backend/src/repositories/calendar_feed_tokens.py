import logging

from sqlalchemy import Result, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.calendar_feed_tokens import CalendarFeedToken
from src.exceptions.calendar_feed_tokens import CalendarFeedTokensRepositoryError

logger = logging.getLogger(__name__)


class CalendarFeedTokensRepository:
    """Репозиторий секретов ссылок подписки на календарь."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_by_user(self, user_id: int) -> CalendarFeedToken | None:
        """Возвращает ссылку подписки пользователя.

        Args:
            user_id: Владелец ссылки.

        Returns:
            Запись ссылки или ``None``, если ссылки нет.

        Raises:
            CalendarFeedTokensRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(CalendarFeedToken).where(CalendarFeedToken.user_id == user_id)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось прочитать ссылку подписки.", exc_info=True)
            raise CalendarFeedTokensRepositoryError(str(error)) from error

    async def get_by_hash(self, token_hash: str) -> CalendarFeedToken | None:
        """Возвращает ссылку подписки по хешу секрета.

        Args:
            token_hash: SHA-256 от предъявленного секрета.

        Returns:
            Запись ссылки или ``None``.

        Raises:
            CalendarFeedTokensRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(CalendarFeedToken).where(CalendarFeedToken.token_hash == token_hash)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось проверить ссылку подписки.", exc_info=True)
            raise CalendarFeedTokensRepositoryError(str(error)) from error

    async def replace(
        self, *, user_id: int, token_hash: str, commit: bool = True
    ) -> CalendarFeedToken:
        """Выпускает ссылку пользователя, заменяя прежнюю одним запросом.

        Args:
            user_id: Владелец ссылки.
            token_hash: SHA-256 от нового секрета.
            commit: Зафиксировать ли транзакцию.

        Returns:
            Запись ссылки с моментом выпуска в ``created_at``.

        Raises:
            CalendarFeedTokensRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            stmt = (
                insert(CalendarFeedToken)
                .values(user_id=user_id, token_hash=token_hash)
                .on_conflict_do_update(
                    index_elements=[CalendarFeedToken.user_id],
                    set_={
                        "token_hash": token_hash,
                        "created_at": func.now(),
                        "updated_at": func.now(),
                    },
                )
                .returning(CalendarFeedToken)
            )
            result: Result = await self.db_session.execute(
                stmt, execution_options={"populate_existing": True}
            )
            token = result.scalar_one()
            if commit:
                await self.db_session.commit()
            return token
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось выпустить ссылку подписки.", exc_info=True)
            raise CalendarFeedTokensRepositoryError(str(error)) from error

    async def delete_by_user(self, *, user_id: int, commit: bool = True) -> bool:
        """Отзывает ссылку подписки пользователя.

        Args:
            user_id: Владелец ссылки.
            commit: Зафиксировать ли транзакцию.

        Returns:
            ``True``, если ссылка была и удалена.

        Raises:
            CalendarFeedTokensRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result = await self.db_session.execute(
                delete(CalendarFeedToken)
                .where(CalendarFeedToken.user_id == user_id)
                .returning(CalendarFeedToken.id)
            )
            deleted = result.scalar_one_or_none() is not None
            if commit:
                await self.db_session.commit()
            return deleted
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось отозвать ссылку подписки.", exc_info=True)
            raise CalendarFeedTokensRepositoryError(str(error)) from error

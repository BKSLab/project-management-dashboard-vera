import logging

from sqlalchemy import Result, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models.analytics_reports import AnalyticsReport
from src.exceptions.analytics import AnalyticsReportsRepositoryError

logger = logging.getLogger(__name__)


class AnalyticsReportsRepository:
    """Репозиторий журнала аналитических сводов дашборда."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_latest_for_project(self, project_id: int) -> AnalyticsReport | None:
        """Возвращает последний свод проекта.

        Свод проекта общий для команды: его видит любой участник, а не только
        тот, кто нажал кнопку.

        Args:
            project_id: Идентификатор проекта.

        Returns:
            Последний свод проекта или ``None``, если анализ ещё не запускали.

        Raises:
            AnalyticsReportsRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(AnalyticsReport)
                .options(selectinload(AnalyticsReport.project))
                .where(AnalyticsReport.project_id == project_id)
                .order_by(AnalyticsReport.created_at.desc(), AnalyticsReport.id.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error(
                "❌ Не удалось получить свод проекта id=%s.",
                project_id,
                exc_info=True,
            )
            raise AnalyticsReportsRepositoryError(
                f"Ошибка получения аналитического свода проекта id={project_id}."
            ) from error

    async def get_latest_portfolio(self, user_id: int) -> AnalyticsReport | None:
        """Возвращает последний портфельный свод пользователя.

        Портфель у каждого свой — это набор его проектов, поэтому такой свод
        не может быть общим и отбирается по автору запроса.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Последний портфельный свод или ``None``, если анализ ещё не запускали.

        Raises:
            AnalyticsReportsRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(AnalyticsReport)
                .options(selectinload(AnalyticsReport.project))
                .where(
                    AnalyticsReport.project_id.is_(None),
                    AnalyticsReport.created_by_user_id == user_id,
                )
                .order_by(AnalyticsReport.created_at.desc(), AnalyticsReport.id.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error(
                "❌ Не удалось получить портфельный свод пользователя id=%s.",
                user_id,
                exc_info=True,
            )
            raise AnalyticsReportsRepositoryError(
                f"Ошибка получения портфельного свода пользователя id={user_id}."
            ) from error

    async def save(self, data: dict) -> AnalyticsReport:
        """Сохраняет аналитический свод в текущей транзакции.

        Args:
            data: Поля свода.

        Returns:
            Сохранённый свод.

        Raises:
            AnalyticsReportsRepositoryError: Если сохранить свод не удалось.
        """
        try:
            report = AnalyticsReport(**data)
            self.db_session.add(report)
            await self.db_session.flush()
            await self.db_session.refresh(report)
            return report
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось сохранить аналитический свод.", exc_info=True)
            raise AnalyticsReportsRepositoryError(
                "Ошибка сохранения аналитического свода."
            ) from error

import logging
from datetime import date

from sqlalchemy import Result, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.project_milestones import ProjectMilestone
from src.exceptions.milestones import MilestonesRepositoryError

logger = logging.getLogger(__name__)


class MilestonesRepository:
    """Репозиторий пользовательских вех проекта."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_by_project(self, project_id: int) -> list[ProjectMilestone]:
        """Возвращает все вехи проекта по дате."""
        try:
            result: Result = await self.db_session.execute(
                select(ProjectMilestone)
                .where(ProjectMilestone.project_id == project_id)
                .order_by(ProjectMilestone.due_date, ProjectMilestone.id)
            )
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить вехи проекта id=%s.", project_id, exc_info=True)
            raise MilestonesRepositoryError("Ошибка получения вех проекта.") from error

    async def get_range(
        self,
        *,
        project_id: int,
        date_from: date,
        date_to: date,
    ) -> list[ProjectMilestone]:
        """Возвращает вехи проекта внутри включительного диапазона."""
        try:
            result: Result = await self.db_session.execute(
                select(ProjectMilestone)
                .where(
                    ProjectMilestone.project_id == project_id,
                    ProjectMilestone.due_date >= date_from,
                    ProjectMilestone.due_date <= date_to,
                )
                .order_by(ProjectMilestone.due_date, ProjectMilestone.id)
            )
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error(
                "❌ Не удалось получить диапазон вех проекта id=%s.",
                project_id,
                exc_info=True,
            )
            raise MilestonesRepositoryError("Ошибка получения диапазона вех.") from error

    async def get_by_id(self, milestone_id: int) -> ProjectMilestone | None:
        """Возвращает веху по идентификатору."""
        try:
            result: Result = await self.db_session.execute(
                select(ProjectMilestone).where(ProjectMilestone.id == milestone_id)
            )
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить веху id=%s.", milestone_id, exc_info=True)
            raise MilestonesRepositoryError("Ошибка получения вехи.") from error

    async def save(self, data: dict) -> ProjectMilestone:
        """Создаёт веху в текущей транзакции."""
        try:
            milestone = ProjectMilestone(**data)
            self.db_session.add(milestone)
            await self.db_session.flush()
            await self.db_session.refresh(milestone)
            return milestone
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось сохранить веху.", exc_info=True)
            raise MilestonesRepositoryError("Ошибка сохранения вехи.") from error

    async def update(self, milestone: ProjectMilestone, data: dict) -> ProjectMilestone:
        """Обновляет веху в текущей транзакции."""
        try:
            for field, value in data.items():
                setattr(milestone, field, value)
            await self.db_session.flush()
            await self.db_session.refresh(milestone)
            return milestone
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось обновить веху id=%s.", milestone.id, exc_info=True)
            raise MilestonesRepositoryError("Ошибка обновления вехи.") from error

    async def delete(self, milestone: ProjectMilestone) -> None:
        """Удаляет веху в текущей транзакции."""
        try:
            await self.db_session.delete(milestone)
            await self.db_session.flush()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось удалить веху id=%s.", milestone.id, exc_info=True)
            raise MilestonesRepositoryError("Ошибка удаления вехи.") from error

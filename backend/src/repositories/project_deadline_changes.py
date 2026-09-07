import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.project_deadline_changes import ProjectDeadlineChange
from src.exceptions.projects import ProjectsRepositoryError

logger = logging.getLogger(__name__)


class ProjectDeadlineChangesRepository:
    """Хранит историю в той же транзакции, что и изменение проекта."""

    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def save(self, data: dict) -> ProjectDeadlineChange:
        """Добавляет запись истории; фиксацией владеет сервис проекта."""
        try:
            change = ProjectDeadlineChange(**data)
            self.db_session.add(change)
            await self.db_session.flush()
            return change
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            logger.exception("❌ Не удалось сохранить историю срока проекта.")
            raise ProjectsRepositoryError("Ошибка сохранения истории срока.") from error

    async def get_by_project(self, project_id: int) -> list[ProjectDeadlineChange]:
        """Возвращает историю от последнего изменения к первому."""
        try:
            statement = (
                select(ProjectDeadlineChange)
                .where(ProjectDeadlineChange.project_id == project_id)
                .order_by(ProjectDeadlineChange.id.desc())
            )
            return list((await self.db_session.execute(statement)).scalars().all())
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            logger.exception("❌ Не удалось прочитать историю срока проекта id=%s.", project_id)
            raise ProjectsRepositoryError("Ошибка чтения истории срока.") from error

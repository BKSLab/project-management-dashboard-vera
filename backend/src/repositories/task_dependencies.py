import logging

from sqlalchemy import Result, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.task_dependencies import TaskDependency
from src.exceptions.task_dependencies import (
    TaskDependenciesRepositoryError,
    TaskDependencyAlreadyExistsRepositoryError,
)
from src.utils.db_errors import get_integrity_constraint_name

logger = logging.getLogger(__name__)

DEPENDENCY_PAIR_CONSTRAINT = "uq_task_dependencies_predecessor_successor"


class TaskDependenciesRepository:
    """Репозиторий направленных связей задач."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_by_project(self, project_id: int) -> list[TaskDependency]:
        """Возвращает граф зависимостей проекта."""
        try:
            result: Result = await self.db_session.execute(
                select(TaskDependency)
                .where(TaskDependency.project_id == project_id)
                .order_by(TaskDependency.id)
            )
            return list(result.scalars().all())
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            logger.error(
                "❌ Не удалось получить зависимости проекта id=%s.",
                project_id,
                exc_info=True,
            )
            raise TaskDependenciesRepositoryError(str(error)) from error

    async def get_by_id(self, dependency_id: int) -> TaskDependency | None:
        """Возвращает зависимость по идентификатору."""
        try:
            result: Result = await self.db_session.execute(
                select(TaskDependency).where(TaskDependency.id == dependency_id)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            logger.error(
                "❌ Не удалось получить зависимость id=%s.",
                dependency_id,
                exc_info=True,
            )
            raise TaskDependenciesRepositoryError(str(error)) from error

    async def save(self, data: dict) -> TaskDependency:
        """Создаёт зависимость в текущей транзакции."""
        dependency = TaskDependency(**data)
        try:
            self.db_session.add(dependency)
            await self.db_session.flush()
            await self.db_session.refresh(dependency)
            return dependency
        except IntegrityError as error:
            await self.db_session.rollback()
            if get_integrity_constraint_name(error) == DEPENDENCY_PAIR_CONSTRAINT:
                raise TaskDependencyAlreadyExistsRepositoryError(str(error)) from error
            logger.error("❌ Не удалось сохранить зависимость задач.", exc_info=True)
            raise TaskDependenciesRepositoryError(str(error)) from error
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось сохранить зависимость задач.", exc_info=True)
            raise TaskDependenciesRepositoryError(str(error)) from error

    async def delete(self, dependency: TaskDependency) -> None:
        """Удаляет зависимость в текущей транзакции."""
        try:
            await self.db_session.delete(dependency)
            await self.db_session.flush()
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            logger.error(
                "❌ Не удалось удалить зависимость id=%s.",
                dependency.id,
                exc_info=True,
            )
            raise TaskDependenciesRepositoryError(str(error)) from error

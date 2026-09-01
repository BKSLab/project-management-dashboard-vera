import logging

from sqlalchemy import Result, and_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.project_members import ProjectMember
from src.exceptions.projects import ProjectsRepositoryError

logger = logging.getLogger(__name__)


class ProjectMembersRepository:
    """Репозиторий участия пользователей в проектах."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get(self, project_id: int, user_id: int) -> ProjectMember | None:
        """Возвращает участие пользователя в проекте.

        Args:
            project_id: Идентификатор проекта.
            user_id: Идентификатор пользователя.

        Returns:
            Найденное участие или ``None``, если доступа нет.

        Raises:
            ProjectsRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(ProjectMember).where(
                    and_(
                        ProjectMember.project_id == project_id,
                        ProjectMember.user_id == user_id,
                    )
                )
            )
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error(
                "❌ Не удалось получить участие в проекте id=%s.", project_id, exc_info=True
            )
            raise ProjectsRepositoryError("Ошибка получения участия в проекте.") from error

    async def get_project_ids_for_user(self, user_id: int) -> set[int]:
        """Возвращает идентификаторы проектов, доступных пользователю.

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Набор идентификаторов проектов.

        Raises:
            ProjectsRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(ProjectMember.project_id).where(ProjectMember.user_id == user_id)
            )
            return set(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить проекты пользователя.", exc_info=True)
            raise ProjectsRepositoryError("Ошибка получения проектов пользователя.") from error

    async def get_for_project(self, project_id: int) -> list[ProjectMember]:
        """Возвращает участников проекта.

        Args:
            project_id: Идентификатор проекта.

        Returns:
            Список участий.

        Raises:
            ProjectsRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(ProjectMember)
                .where(ProjectMember.project_id == project_id)
                .order_by(ProjectMember.id)
            )
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error(
                "❌ Не удалось получить участников проекта id=%s.", project_id, exc_info=True
            )
            raise ProjectsRepositoryError("Ошибка получения участников проекта.") from error

    async def save(self, data: dict) -> ProjectMember:
        """Добавляет участника проекта.

        Args:
            data: Поля нового участия.

        Returns:
            Сохранённое участие.

        Raises:
            ProjectsRepositoryError: Если сохранить участие не удалось.
        """
        try:
            member = ProjectMember(**data)
            self.db_session.add(member)
            await self.db_session.commit()
            await self.db_session.refresh(member)
            return member
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось добавить участника проекта.", exc_info=True)
            raise ProjectsRepositoryError("Ошибка добавления участника проекта.") from error

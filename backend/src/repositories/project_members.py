import logging

from sqlalchemy import Result, and_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.db.models.project_members import ProjectMember
from src.exceptions.projects import (
    ProjectMemberAlreadyExistsRepositoryError,
    ProjectsRepositoryError,
)
from src.utils.db_errors import get_integrity_constraint_name

logger = logging.getLogger(__name__)
PROJECT_MEMBER_CONSTRAINTS = frozenset({"uq_project_members_project_user"})


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
                .options(joinedload(ProjectMember.user))
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
            await self.db_session.flush()
            return member
        except IntegrityError as error:
            await self.db_session.rollback()
            if get_integrity_constraint_name(error) in PROJECT_MEMBER_CONSTRAINTS:
                raise ProjectMemberAlreadyExistsRepositoryError(
                    project_id=int(data.get("project_id", 0)),
                    user_id=int(data.get("user_id", 0)),
                ) from error
            logger.error("❌ Ограничение БД не позволило добавить участника.", exc_info=True)
            raise ProjectsRepositoryError("Ошибка ограничения при добавлении участника.") from error
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось добавить участника проекта.", exc_info=True)
            raise ProjectsRepositoryError("Ошибка добавления участника проекта.") from error

    async def delete(self, member: ProjectMember) -> None:
        """Удаляет участие пользователя из проекта."""
        try:
            await self.db_session.delete(member)
            await self.db_session.flush()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error(
                "❌ Не удалось удалить участника id=%s из проекта id=%s.",
                member.user_id,
                member.project_id,
                exc_info=True,
            )
            raise ProjectsRepositoryError("Ошибка удаления участника проекта.") from error

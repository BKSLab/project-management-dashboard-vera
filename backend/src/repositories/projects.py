import logging

from sqlalchemy import Result, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.projects import Project
from src.exceptions.projects import (
    ProjectKeyAlreadyExistsRepositoryError,
    ProjectsRepositoryError,
)
from src.utils.db_errors import get_integrity_constraint_name

logger = logging.getLogger(__name__)

PROJECT_KEY_CONSTRAINTS = frozenset({"projects_key_key", "ix_projects_key"})


class ProjectsRepository:
    """Репозиторий проектов."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_all(self) -> list[Project]:
        """Возвращает проекты в порядке отображения.

        Args:
            Нет дополнительных аргументов.

        Returns:
            Список проектов.

        Raises:
            ProjectsRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(Project).order_by(Project.order_index, Project.id)
            )
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить проекты.", exc_info=True)
            raise ProjectsRepositoryError("Ошибка получения списка проектов.") from error

    async def get_by_id(self, project_id: int) -> Project | None:
        """Возвращает проект по идентификатору.

        Args:
            project_id: Идентификатор проекта.

        Returns:
            Найденный проект или ``None``.

        Raises:
            ProjectsRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(Project).where(Project.id == project_id)
            )
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить проект id=%s.", project_id, exc_info=True)
            raise ProjectsRepositoryError(f"Ошибка получения проекта id={project_id}.") from error

    async def get_by_key(self, key: str) -> Project | None:
        """Возвращает проект по короткому коду.

        Args:
            key: Короткий код проекта.

        Returns:
            Найденный проект или ``None``.

        Raises:
            ProjectsRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(Project).where(Project.key == key)
            )
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить проект по коду %s.", key, exc_info=True)
            raise ProjectsRepositoryError(f"Ошибка получения проекта с кодом {key}.") from error

    async def get_max_order_index(self) -> int:
        """Возвращает наибольший порядковый индекс среди проектов.

        Args:
            Нет дополнительных аргументов.

        Returns:
            Наибольший индекс или ``-1``, если проектов нет.

        Raises:
            ProjectsRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(func.coalesce(func.max(Project.order_index), -1))
            )
            return int(result.scalar_one())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить порядок проектов.", exc_info=True)
            raise ProjectsRepositoryError("Ошибка получения порядка проектов.") from error

    async def save(self, data: dict) -> Project:
        """Создаёт проект и возвращает сохранённую модель.

        Args:
            data: Поля нового проекта.

        Returns:
            Сохранённый проект.

        Raises:
            ProjectKeyAlreadyExistsRepositoryError: Если код проекта уже занят.
            ProjectsRepositoryError: Если сохранить проект не удалось.
        """
        try:
            project = Project(**data)
            self.db_session.add(project)
            await self.db_session.flush()
            await self.db_session.refresh(project)
            return project
        except IntegrityError as error:
            await self.db_session.rollback()
            if get_integrity_constraint_name(error) in PROJECT_KEY_CONSTRAINTS:
                key = str(data.get("key", ""))
                logger.warning("⚠️ Код проекта %s уже занят.", key)
                raise ProjectKeyAlreadyExistsRepositoryError(key=key) from error
            logger.error("❌ Ограничение БД не позволило сохранить проект.", exc_info=True)
            raise ProjectsRepositoryError(
                "Ошибка ограничения БД при сохранении проекта."
            ) from error
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось сохранить проект.", exc_info=True)
            raise ProjectsRepositoryError("Ошибка сохранения проекта.") from error

    async def update(self, project: Project, data: dict) -> Project:
        """Обновляет проект и возвращает сохранённую модель.

        Args:
            project: Изменяемая ORM-модель проекта.
            data: Новые значения полей.

        Returns:
            Обновлённый проект.

        Raises:
            ProjectKeyAlreadyExistsRepositoryError: Если новый код проекта уже занят.
            ProjectsRepositoryError: Если обновить проект не удалось.
        """
        try:
            for field, value in data.items():
                setattr(project, field, value)
            await self.db_session.flush()
            await self.db_session.refresh(project)
            return project
        except IntegrityError as error:
            await self.db_session.rollback()
            if get_integrity_constraint_name(error) in PROJECT_KEY_CONSTRAINTS:
                key = str(data.get("key", ""))
                logger.warning("⚠️ Код проекта %s уже занят.", key)
                raise ProjectKeyAlreadyExistsRepositoryError(key=key) from error
            logger.error("❌ Ограничение БД не позволило обновить проект.", exc_info=True)
            raise ProjectsRepositoryError(
                f"Ошибка ограничения БД при обновлении проекта id={project.id}."
            ) from error
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось обновить проект id=%s.", project.id, exc_info=True)
            raise ProjectsRepositoryError(f"Ошибка обновления проекта id={project.id}.") from error

    async def delete(self, project: Project) -> None:
        """Удаляет проект вместе со всеми зависимыми записями.

        Args:
            project: Удаляемая ORM-модель проекта.

        Returns:
            ``None`` после успешного удаления.

        Raises:
            ProjectsRepositoryError: Если удалить проект не удалось.
        """
        try:
            await self.db_session.delete(project)
            await self.db_session.flush()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось удалить проект id=%s.", project.id, exc_info=True)
            raise ProjectsRepositoryError(f"Ошибка удаления проекта id={project.id}.") from error

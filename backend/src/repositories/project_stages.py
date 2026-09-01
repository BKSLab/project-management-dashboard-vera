import logging

from sqlalchemy import Result, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.project_stages import ProjectStage
from src.exceptions.project_stages import (
    ProjectStageNameAlreadyExistsRepositoryError,
    ProjectStagesRepositoryError,
)
from src.utils.db_errors import get_integrity_constraint_name

logger = logging.getLogger(__name__)

STAGE_NAME_CONSTRAINTS = frozenset({"uq_project_stages_project_name"})


class ProjectStagesRepository:
    """Репозиторий стадий канбан-доски проекта."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_by_project(self, project_id: int) -> list[ProjectStage]:
        """Возвращает стадии проекта в порядке отображения.

        Args:
            project_id: Идентификатор проекта.

        Returns:
            Список стадий проекта.

        Raises:
            ProjectStagesRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(ProjectStage)
                .where(ProjectStage.project_id == project_id)
                .order_by(ProjectStage.order_index, ProjectStage.id)
            )
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить стадии проекта id=%s.", project_id, exc_info=True)
            raise ProjectStagesRepositoryError(
                f"Ошибка получения стадий проекта id={project_id}."
            ) from error

    async def get_all(self) -> list[ProjectStage]:
        """Возвращает стадии всех проектов.

        Args:
            Нет дополнительных аргументов.

        Returns:
            Список стадий всех проектов.

        Raises:
            ProjectStagesRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(ProjectStage).order_by(
                    ProjectStage.project_id,
                    ProjectStage.order_index,
                    ProjectStage.id,
                )
            )
            return list(result.scalars().all())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить стадии проектов.", exc_info=True)
            raise ProjectStagesRepositoryError("Ошибка получения списка стадий.") from error

    async def get_by_id(self, stage_id: int) -> ProjectStage | None:
        """Возвращает стадию по идентификатору.

        Args:
            stage_id: Идентификатор стадии.

        Returns:
            Найденная стадия или ``None``.

        Raises:
            ProjectStagesRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(ProjectStage).where(ProjectStage.id == stage_id)
            )
            return result.scalar_one_or_none()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось получить стадию id=%s.", stage_id, exc_info=True)
            raise ProjectStagesRepositoryError(f"Ошибка получения стадии id={stage_id}.") from error

    async def get_max_order_index(self, project_id: int) -> int:
        """Возвращает наибольший порядковый индекс среди стадий проекта.

        Args:
            project_id: Идентификатор проекта.

        Returns:
            Наибольший индекс или ``-1``, если стадий нет.

        Raises:
            ProjectStagesRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            result: Result = await self.db_session.execute(
                select(func.coalesce(func.max(ProjectStage.order_index), -1)).where(
                    ProjectStage.project_id == project_id
                )
            )
            return int(result.scalar_one())
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error(
                "❌ Не удалось получить порядок стадий проекта id=%s.",
                project_id,
                exc_info=True,
            )
            raise ProjectStagesRepositoryError(
                f"Ошибка получения порядка стадий проекта id={project_id}."
            ) from error

    async def save_many(self, items: list[dict]) -> list[ProjectStage]:
        """Создаёт набор стадий одной транзакцией.

        Args:
            items: Поля создаваемых стадий.

        Returns:
            Сохранённые стадии.

        Raises:
            ProjectStagesRepositoryError: Если сохранить стадии не удалось.
        """
        try:
            stages = [ProjectStage(**item) for item in items]
            self.db_session.add_all(stages)
            await self.db_session.commit()
            for stage in stages:
                await self.db_session.refresh(stage)
            return stages
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось сохранить набор стадий.", exc_info=True)
            raise ProjectStagesRepositoryError("Ошибка сохранения стадий проекта.") from error

    async def save(self, data: dict) -> ProjectStage:
        """Создаёт стадию и возвращает сохранённую модель.

        Args:
            data: Поля новой стадии.

        Returns:
            Сохранённая стадия.

        Raises:
            ProjectStageNameAlreadyExistsRepositoryError: Если название уже занято.
            ProjectStagesRepositoryError: Если сохранить стадию не удалось.
        """
        try:
            stage = ProjectStage(**data)
            self.db_session.add(stage)
            await self.db_session.commit()
            await self.db_session.refresh(stage)
            return stage
        except IntegrityError as error:
            await self.db_session.rollback()
            if get_integrity_constraint_name(error) in STAGE_NAME_CONSTRAINTS:
                name = str(data.get("name", ""))
                logger.warning("⚠️ Стадия %r уже существует в проекте.", name)
                raise ProjectStageNameAlreadyExistsRepositoryError(name=name) from error
            logger.error("❌ Ограничение БД не позволило сохранить стадию.", exc_info=True)
            raise ProjectStagesRepositoryError(
                "Ошибка ограничения БД при сохранении стадии."
            ) from error
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось сохранить стадию.", exc_info=True)
            raise ProjectStagesRepositoryError("Ошибка сохранения стадии.") from error

    async def update(self, stage: ProjectStage, data: dict) -> ProjectStage:
        """Обновляет стадию и возвращает сохранённую модель.

        Args:
            stage: Изменяемая ORM-модель стадии.
            data: Новые значения полей.

        Returns:
            Обновлённая стадия.

        Raises:
            ProjectStageNameAlreadyExistsRepositoryError: Если название уже занято.
            ProjectStagesRepositoryError: Если обновить стадию не удалось.
        """
        try:
            for field, value in data.items():
                setattr(stage, field, value)
            await self.db_session.commit()
            await self.db_session.refresh(stage)
            return stage
        except IntegrityError as error:
            await self.db_session.rollback()
            if get_integrity_constraint_name(error) in STAGE_NAME_CONSTRAINTS:
                name = str(data.get("name", ""))
                logger.warning("⚠️ Стадия %r уже существует в проекте.", name)
                raise ProjectStageNameAlreadyExistsRepositoryError(name=name) from error
            logger.error("❌ Ограничение БД не позволило обновить стадию.", exc_info=True)
            raise ProjectStagesRepositoryError(
                f"Ошибка ограничения БД при обновлении стадии id={stage.id}."
            ) from error
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось обновить стадию id=%s.", stage.id, exc_info=True)
            raise ProjectStagesRepositoryError(
                f"Ошибка обновления стадии id={stage.id}."
            ) from error

    async def delete(self, stage: ProjectStage) -> None:
        """Удаляет стадию.

        Args:
            stage: Удаляемая ORM-модель стадии.

        Returns:
            ``None`` после успешного удаления.

        Raises:
            ProjectStagesRepositoryError: Если удалить стадию не удалось.
        """
        try:
            await self.db_session.delete(stage)
            await self.db_session.commit()
        except (SQLAlchemyError, Exception) as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось удалить стадию id=%s.", stage.id, exc_info=True)
            raise ProjectStagesRepositoryError(f"Ошибка удаления стадии id={stage.id}.") from error

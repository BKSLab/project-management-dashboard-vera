import logging

from src.exceptions.project_stages import (
    ProjectLastStageDeleteError,
    ProjectStageForeignProjectError,
    ProjectStageHasTasksError,
    ProjectStageNameAlreadyExistsRepositoryError,
    ProjectStageNameConflictError,
    ProjectStageNotFoundError,
    ProjectStagesRepositoryError,
    ProjectStagesServiceError,
)
from src.exceptions.projects import ProjectNotFoundError, ProjectsRepositoryError
from src.exceptions.tasks import TasksRepositoryError
from src.repositories.project_stages import ProjectStagesRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.tasks import TasksRepository
from src.schemas.project_stages import StageSchema

logger = logging.getLogger(__name__)

RepositoryErrors = (
    ProjectStagesRepositoryError,
    ProjectsRepositoryError,
    TasksRepositoryError,
)


class ProjectStagesService:
    """Сервис сценариев работы со стадиями канбан-доски проекта."""

    def __init__(
        self,
        stages_repository: ProjectStagesRepository,
        projects_repository: ProjectsRepository,
        tasks_repository: TasksRepository,
    ):
        self.stages_repository = stages_repository
        self.projects_repository = projects_repository
        self.tasks_repository = tasks_repository

    async def get_stage_list(self, project_id: int) -> list[StageSchema]:
        """Возвращает стадии проекта в порядке отображения.

        Args:
            project_id: Идентификатор проекта.

        Returns:
            Стадии канбан-доски проекта.

        Raises:
            ProjectNotFoundError: Если проект не найден.
            ProjectStagesServiceError: Если получить стадии не удалось.
        """
        try:
            await self._ensure_project_exists(project_id=project_id)
            stages = await self.stages_repository.get_by_project(project_id=project_id)
            return [StageSchema.model_validate(stage) for stage in stages]
        except ProjectNotFoundError:
            raise
        except RepositoryErrors as error:
            logger.error("❌ Ошибка получения стадий проекта id=%s.", project_id, exc_info=True)
            raise ProjectStagesServiceError(str(error)) from error

    async def create_stage(self, project_id: int, data: dict) -> StageSchema:
        """Создаёт стадию в конце доски проекта.

        Args:
            project_id: Идентификатор проекта.
            data: Поля новой стадии.

        Returns:
            Созданная стадия.

        Raises:
            ProjectNotFoundError: Если проект не найден.
            ProjectStageNameConflictError: Если название уже занято.
            ProjectStagesServiceError: Если создать стадию не удалось.
        """
        try:
            await self._ensure_project_exists(project_id=project_id)
            order_index = await self.stages_repository.get_max_order_index(project_id=project_id)
            stage = await self.stages_repository.save(
                data={**data, "project_id": project_id, "order_index": order_index + 1}
            )
            return StageSchema.model_validate(stage)
        except ProjectNotFoundError:
            raise
        except ProjectStageNameAlreadyExistsRepositoryError as error:
            logger.warning("⚠️ Конфликт названия стадии %r.", error.name)
            raise ProjectStageNameConflictError(name=error.name) from error
        except RepositoryErrors as error:
            logger.error("❌ Ошибка создания стадии проекта id=%s.", project_id, exc_info=True)
            raise ProjectStagesServiceError(str(error)) from error

    async def update_stage(self, stage_id: int, data: dict) -> StageSchema:
        """Обновляет поля стадии.

        Args:
            stage_id: Идентификатор стадии.
            data: Изменяемые поля стадии.

        Returns:
            Обновлённая стадия.

        Raises:
            ProjectStageNotFoundError: Если стадия не найдена.
            ProjectStageNameConflictError: Если название уже занято.
            ProjectStagesServiceError: Если обновить стадию не удалось.
        """
        try:
            stage = await self.stages_repository.get_by_id(stage_id=stage_id)
            if stage is None:
                raise ProjectStageNotFoundError(stage_id=stage_id)
            updated = await self.stages_repository.update(stage=stage, data=data)
            return StageSchema.model_validate(updated)
        except ProjectStageNotFoundError:
            raise
        except ProjectStageNameAlreadyExistsRepositoryError as error:
            logger.warning("⚠️ Конфликт названия стадии %r.", error.name)
            raise ProjectStageNameConflictError(name=error.name) from error
        except RepositoryErrors as error:
            logger.error("❌ Ошибка обновления стадии id=%s.", stage_id, exc_info=True)
            raise ProjectStagesServiceError(str(error)) from error

    async def delete_stage(self, stage_id: int) -> None:
        """Удаляет пустую стадию проекта.

        Args:
            stage_id: Идентификатор стадии.

        Returns:
            ``None`` после успешного удаления.

        Raises:
            ProjectStageNotFoundError: Если стадия не найдена.
            ProjectStageHasTasksError: Если стадия содержит задачи.
            ProjectLastStageDeleteError: Если это последняя стадия проекта.
            ProjectStagesServiceError: Если удалить стадию не удалось.
        """
        try:
            stage = await self.stages_repository.get_by_id(stage_id=stage_id)
            if stage is None:
                raise ProjectStageNotFoundError(stage_id=stage_id)
            if await self.tasks_repository.get_count_by_stage(stage_id=stage_id) > 0:
                raise ProjectStageHasTasksError(stage_id=stage_id)
            stages = await self.stages_repository.get_by_project(project_id=stage.project_id)
            if len(stages) <= 1:
                raise ProjectLastStageDeleteError(stage_id=stage_id)
            await self.stages_repository.delete(stage=stage)
        except (
            ProjectStageNotFoundError,
            ProjectStageHasTasksError,
            ProjectLastStageDeleteError,
        ):
            raise
        except RepositoryErrors as error:
            logger.error("❌ Ошибка удаления стадии id=%s.", stage_id, exc_info=True)
            raise ProjectStagesServiceError(str(error)) from error

    async def get_stage_in_project(self, project_id: int, stage_id: int):
        """Возвращает стадию, убедившись, что она принадлежит проекту.

        Args:
            project_id: Идентификатор проекта.
            stage_id: Идентификатор стадии.

        Returns:
            ORM-модель стадии.

        Raises:
            ProjectStageNotFoundError: Если стадия не найдена.
            ProjectStageForeignProjectError: Если стадия принадлежит другому проекту.
            ProjectStagesServiceError: Если получить стадию не удалось.
        """
        try:
            stage = await self.stages_repository.get_by_id(stage_id=stage_id)
            if stage is None:
                raise ProjectStageNotFoundError(stage_id=stage_id)
            if stage.project_id != project_id:
                raise ProjectStageForeignProjectError(stage_id=stage_id, project_id=project_id)
            return stage
        except (ProjectStageNotFoundError, ProjectStageForeignProjectError):
            raise
        except RepositoryErrors as error:
            logger.error("❌ Ошибка получения стадии id=%s.", stage_id, exc_info=True)
            raise ProjectStagesServiceError(str(error)) from error

    async def _ensure_project_exists(self, project_id: int) -> None:
        """Проверяет существование проекта перед операцией со стадиями."""
        if await self.projects_repository.get_by_id(project_id=project_id) is None:
            raise ProjectNotFoundError(project_id=project_id)

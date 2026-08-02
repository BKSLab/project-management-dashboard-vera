import logging

from src.exceptions.kanban_stages import (
    KanbanStageHasTasksError,
    KanbanStageNotFoundError,
    KanbanStagesRepositoryError,
    KanbanStagesServiceError,
)
from src.exceptions.kanban_tasks import KanbanTasksRepositoryError
from src.repositories.kanban_stages import KanbanStagesRepository
from src.repositories.kanban_tasks import KanbanTasksRepository
from src.schemas.kanban_stages import StageSchema

logger = logging.getLogger(__name__)


class KanbanStagesService:
    """Сервис управления стадиями канбан-доски."""

    def __init__(
        self,
        stages_repository: KanbanStagesRepository,
        tasks_repository: KanbanTasksRepository,
    ):
        self.stages_repository = stages_repository
        self.tasks_repository = tasks_repository

    async def get_stage_list(self) -> list[StageSchema]:
        """Возвращает стадии канбана в порядке отображения.

        Args:
            Нет дополнительных аргументов.

        Returns:
            Список стадий канбан-доски.

        Raises:
            KanbanStagesServiceError: Если получить стадии не удалось.
        """
        try:
            stages = await self.stages_repository.get_all()
            return [StageSchema.model_validate(stage) for stage in stages]
        except KanbanStagesRepositoryError as error:
            logger.error("❌ Ошибка получения стадий канбана.", exc_info=True)
            raise KanbanStagesServiceError(str(error)) from error

    async def create_stage(self, data: dict) -> StageSchema:
        """Создаёт новую стадию канбана.

        Args:
            data: Поля создаваемой стадии.

        Returns:
            Созданная стадия.

        Raises:
            KanbanStagesServiceError: Если сохранить стадию не удалось.
        """
        try:
            stage = await self.stages_repository.save(data=data)
            return StageSchema.model_validate(stage)
        except KanbanStagesRepositoryError as error:
            logger.error("❌ Ошибка создания стадии канбана.", exc_info=True)
            raise KanbanStagesServiceError(str(error)) from error

    async def update_stage(self, stage_id: int, data: dict) -> StageSchema:
        """Обновляет стадию канбана.

        Args:
            stage_id: Идентификатор стадии.
            data: Изменяемые поля.

        Returns:
            Обновлённая стадия.

        Raises:
            KanbanStageNotFoundError: Если стадия не найдена.
            KanbanStagesServiceError: Если операция с БД завершилась ошибкой.
        """
        try:
            stage = await self.stages_repository.get_by_id(stage_id=stage_id)
            if stage is None:
                raise KanbanStageNotFoundError(stage_id=stage_id)
            updated = await self.stages_repository.update(stage=stage, data=data)
            return StageSchema.model_validate(updated)
        except KanbanStageNotFoundError:
            raise
        except KanbanStagesRepositoryError as error:
            logger.error("❌ Ошибка обновления стадии id=%s.", stage_id, exc_info=True)
            raise KanbanStagesServiceError(str(error)) from error

    async def delete_stage(self, stage_id: int) -> None:
        """Удаляет пустую стадию канбана.

        Args:
            stage_id: Идентификатор стадии.

        Returns:
            ``None`` после успешного удаления.

        Raises:
            KanbanStageNotFoundError: Если стадия не найдена.
            KanbanStageHasTasksError: Если стадия содержит задачи.
            KanbanStagesServiceError: Если операция с БД завершилась ошибкой.
        """
        try:
            stage = await self.stages_repository.get_by_id(stage_id=stage_id)
            if stage is None:
                raise KanbanStageNotFoundError(stage_id=stage_id)
            if await self.tasks_repository.get_count_by_stage(stage_id=stage_id) > 0:
                raise KanbanStageHasTasksError(stage_id=stage_id)
            await self.stages_repository.delete(stage=stage)
        except (KanbanStageNotFoundError, KanbanStageHasTasksError):
            raise
        except (KanbanStagesRepositoryError, KanbanTasksRepositoryError) as error:
            logger.error("❌ Ошибка удаления стадии id=%s.", stage_id, exc_info=True)
            raise KanbanStagesServiceError(str(error)) from error

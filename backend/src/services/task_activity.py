import logging

from src.exceptions.kanban_tasks import KanbanTaskNotFoundError, KanbanTasksRepositoryError
from src.exceptions.task_activity import TaskActivityRepositoryError, TaskActivityServiceError
from src.repositories.kanban_tasks import KanbanTasksRepository
from src.repositories.task_activity import TaskActivityRepository
from src.schemas.task_activity import ActivitySchema

logger = logging.getLogger(__name__)


class TaskActivityService:
    """Сервис чтения истории изменений задач."""

    def __init__(
        self,
        activity_repository: TaskActivityRepository,
        tasks_repository: KanbanTasksRepository,
    ):
        self.activity_repository = activity_repository
        self.tasks_repository = tasks_repository

    async def get_activity(self, task_id: int) -> list[ActivitySchema]:
        """Возвращает историю существующей задачи.

        Args:
            task_id: Идентификатор задачи.

        Returns:
            История изменений задачи.

        Raises:
            KanbanTaskNotFoundError: Если задача не найдена.
            TaskActivityServiceError: Если получить историю не удалось.
        """
        try:
            if await self.tasks_repository.get_by_id(task_id=task_id) is None:
                raise KanbanTaskNotFoundError(task_id=task_id)
            activity = await self.activity_repository.get_for_task(task_id=task_id)
            return [ActivitySchema.model_validate(item) for item in activity]
        except KanbanTaskNotFoundError:
            raise
        except (TaskActivityRepositoryError, KanbanTasksRepositoryError) as error:
            logger.error("❌ Ошибка получения истории задачи id=%s.", task_id, exc_info=True)
            raise TaskActivityServiceError(str(error)) from error

from fastapi import status

from src.exceptions.base import RepositoryError, ServiceError


class KanbanTasksRepositoryError(RepositoryError):
    """Ошибка доступа к задачам канбана."""

    detail = "Ошибка базы данных при обработке задач канбана."


class KanbanTaskWbsLinkAlreadyExistsRepositoryError(KanbanTasksRepositoryError):
    """Узел ИСР уже связан с другой задачей в базе данных."""

    def __init__(self, wbs_item_id: int):
        self.wbs_item_id = wbs_item_id
        super().__init__(error_details=f"Узел ИСР id={wbs_item_id} уже связан с задачей.")


class KanbanTasksServiceError(ServiceError):
    """Ошибка бизнес-операции с задачами канбана."""

    detail = "Не удалось выполнить операцию с задачами канбана."


class KanbanTaskNotFoundError(KanbanTasksServiceError):
    """Задача канбана не найдена."""

    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, task_id: int):
        self.task_id = task_id
        super().__init__(error_details=f"Задача канбана id={task_id} не найдена.")

    @property
    def detail(self) -> str:
        return f"Задача канбана с id={self.task_id} не найдена."


class KanbanTaskFromWbsDeleteError(KanbanTasksServiceError):
    """Связанную с ИСР задачу нельзя удалить напрямую."""

    status_code = status.HTTP_409_CONFLICT

    def __init__(self, task_id: int):
        self.task_id = task_id
        super().__init__(error_details=f"Задача id={task_id} связана с ИСР.")

    @property
    def detail(self) -> str:
        return (
            f"Задача с id={self.task_id} связана с узлом ИСР "
            "и не может быть удалена, только перемещена."
        )

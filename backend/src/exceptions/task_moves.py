from fastapi import status

from src.exceptions.base import RepositoryError, ServiceError


class TaskMovesRepositoryError(RepositoryError):
    """Ошибка чтения или снятия связей задачи при переносе."""

    detail = "Ошибка базы данных при переносе задачи."


class TaskMovesServiceError(ServiceError):
    """Ошибка бизнес-операции переноса задачи."""

    detail = "Не удалось перенести задачу."


class TaskMoveSameTargetError(TaskMovesServiceError):
    """Задача уже находится там, куда её переносят."""

    status_code = status.HTTP_409_CONFLICT
    detail = "Задача уже здесь. Чтобы сменить стадию, передвиньте её на доске проекта."

    def __init__(self, task_id: int) -> None:
        self.task_id = task_id
        super().__init__(error_details=f"Задача id={task_id} уже находится в цели переноса.")


class TaskMoveOwnerRequiredError(TaskMovesServiceError):
    """Задачу вне проекта переносит только её OWNER."""

    status_code = status.HTTP_403_FORBIDDEN
    detail = "Перенести разовую задачу может её постановщик."

    def __init__(self, task_id: int) -> None:
        self.task_id = task_id
        super().__init__(error_details=f"Нет прав перенести задачу id={task_id}.")


class TaskMoveOutsidersError(TaskMovesServiceError):
    """Часть людей задачи не состоит в команде целевого проекта."""

    status_code = status.HTTP_409_CONFLICT

    def __init__(self, names: list[str]) -> None:
        self.names = names
        super().__init__(error_details=f"Не в команде целевого проекта: {', '.join(names)}.")

    @property
    def detail(self) -> str:
        return (
            f"Не в команде проекта: {', '.join(self.names)}. Добавьте их в команду "
            "или подтвердите, что их нужно убрать из задачи."
        )

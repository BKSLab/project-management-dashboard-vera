from fastapi import status

from src.exceptions.base import RepositoryError, ServiceError


class TasksRepositoryError(RepositoryError):
    """Ошибка доступа к задачам."""

    detail = "Ошибка базы данных при обработке задач."


class TaskNumberAlreadyExistsRepositoryError(TasksRepositoryError):
    """Номер задачи уже занят внутри проекта."""

    def __init__(self, project_id: int, number: int):
        self.project_id = project_id
        self.number = number
        super().__init__(
            error_details=f"Номер {number} уже занят в проекте id={project_id}.",
        )


class TasksServiceError(ServiceError):
    """Ошибка бизнес-операции с задачами."""

    detail = "Не удалось выполнить операцию с задачами."


class TaskNotFoundError(TasksServiceError):
    """Задача не найдена."""

    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, task_id: int):
        self.task_id = task_id
        super().__init__(error_details=f"Задача id={task_id} не найдена.")

    @property
    def detail(self) -> str:
        return f"Задача с id={self.task_id} не найдена."


class TaskForeignProjectError(TasksServiceError):
    """Задача принадлежит другому проекту."""

    status_code = status.HTTP_409_CONFLICT

    def __init__(self, task_id: int, project_id: int):
        self.task_id = task_id
        self.project_id = project_id
        super().__init__(
            error_details=f"Задача id={task_id} не принадлежит проекту id={project_id}.",
        )

    @property
    def detail(self) -> str:
        return f"Задача с id={self.task_id} принадлежит другому проекту."


class TaskNumberAllocationError(TasksServiceError):
    """Не удалось выделить свободный номер задачи."""

    status_code = status.HTTP_409_CONFLICT

    def __init__(self, project_id: int):
        self.project_id = project_id
        super().__init__(
            error_details=f"Не удалось выделить номер задачи в проекте id={project_id}.",
        )

    @property
    def detail(self) -> str:
        return "Не удалось выделить номер задачи. Повторите попытку."


class TaskDateRangeError(TasksServiceError):
    """Начало задачи находится после её дедлайна."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    detail = "Дата начала задачи не может быть позже даты завершения."

    def __init__(self):
        super().__init__(error_details=self.detail)

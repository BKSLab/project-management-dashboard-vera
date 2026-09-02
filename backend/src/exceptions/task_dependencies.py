from fastapi import status

from src.exceptions.base import RepositoryError, ServiceError


class TaskDependenciesRepositoryError(RepositoryError):
    """Ошибка доступа к зависимостям задач."""

    detail = "Ошибка базы данных при обработке зависимостей задач."


class TaskDependencyAlreadyExistsRepositoryError(TaskDependenciesRepositoryError):
    """Направленная пара задач уже связана."""


class TaskDependenciesServiceError(ServiceError):
    """Ошибка бизнес-операции с зависимостями задач."""

    detail = "Не удалось выполнить операцию с зависимостями задач."


class TaskDependencyNotFoundError(TaskDependenciesServiceError):
    """Зависимость не найдена в указанном проекте."""

    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, dependency_id: int):
        self.dependency_id = dependency_id
        super().__init__(error_details=f"Зависимость id={dependency_id} не найдена.")

    @property
    def detail(self) -> str:
        return f"Зависимость с id={self.dependency_id} не найдена."


class TaskDependencySelfReferenceError(TaskDependenciesServiceError):
    """Задача не может зависеть сама от себя."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    detail = "Задача не может зависеть сама от себя."

    def __init__(self):
        super().__init__(error_details=self.detail)


class TaskDependencyForeignProjectError(TaskDependenciesServiceError):
    """Одна из задач не принадлежит выбранному проекту."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    detail = "Обе задачи зависимости должны принадлежать выбранному проекту."

    def __init__(self):
        super().__init__(error_details=self.detail)


class TaskDependencyCycleError(TaskDependenciesServiceError):
    """Новая связь создаёт цикл в графе задач."""

    status_code = status.HTTP_409_CONFLICT
    detail = "Зависимость создаёт цикл в графе задач."

    def __init__(self):
        super().__init__(error_details=self.detail)


class TaskDependencyAlreadyExistsError(TaskDependenciesServiceError):
    """Такая направленная связь уже существует."""

    status_code = status.HTTP_409_CONFLICT
    detail = "Такая зависимость задач уже существует."

    def __init__(self):
        super().__init__(error_details=self.detail)

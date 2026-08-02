from src.exceptions.base import RepositoryError, ServiceError


class TaskActivityRepositoryError(RepositoryError):
    """Ошибка доступа к истории задач."""

    detail = "Ошибка базы данных при обработке истории задач."


class TaskActivityServiceError(ServiceError):
    """Ошибка бизнес-операции с историей задач."""

    detail = "Не удалось выполнить операцию с историей задачи."

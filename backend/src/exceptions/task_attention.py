from src.exceptions.base import RepositoryError, ServiceError


class TaskAttentionRepositoryError(RepositoryError):
    """Ошибка хранения персонального просмотра задач."""

    detail = "Не удалось получить счётчики задач."


class TaskAttentionServiceError(ServiceError):
    """Ошибка персональных счётчиков задач."""

    detail = "Не удалось обновить счётчики задач."


class TaskAttentionVersionError(TaskAttentionServiceError):
    """Клиент подтвердил версию, которой ещё нет."""

    status_code = 409
    detail = "Версия просмотра не соответствует задаче. Обновите карточку."

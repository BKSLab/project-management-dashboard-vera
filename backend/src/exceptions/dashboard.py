from src.exceptions.base import ServiceError


class DashboardServiceError(ServiceError):
    """Ошибка сборки сводки по проектам."""

    detail = "Не удалось собрать сводку по проектам."

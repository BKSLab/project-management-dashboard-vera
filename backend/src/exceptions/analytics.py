from fastapi import status

from src.exceptions.base import RepositoryError, ServiceError


class AnalyticsReportsRepositoryError(RepositoryError):
    """Ошибка доступа к сохранённым аналитическим сводам."""

    detail = "Ошибка базы данных при обработке аналитических сводов."


class AnalyticsServiceError(ServiceError):
    """Ошибка бизнес-операции с аналитическим сводом."""

    detail = "Не удалось выполнить операцию с аналитическим сводом."


class AnalyticsEmptyScopeError(AnalyticsServiceError):
    """Анализировать нечего: в выбранной области нет задач."""

    status_code = status.HTTP_409_CONFLICT
    detail = "Пока нечего анализировать: в выбранных проектах нет задач."


class AnalyticsGenerationError(AnalyticsServiceError):
    """Модель не вернула пригодный аналитический свод."""

    status_code = status.HTTP_502_BAD_GATEWAY
    detail = "Аналитика не сформирована: модель вернула непригодный ответ."

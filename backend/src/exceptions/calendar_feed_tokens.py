from fastapi import status

from src.exceptions.base import RepositoryError, ServiceError


class CalendarFeedTokensRepositoryError(RepositoryError):
    """Ошибка доступа к ссылкам подписки на календарь."""

    detail = "Ошибка базы данных при обработке ссылки подписки."


class CalendarFeedServiceError(ServiceError):
    """Ошибка операции со ссылкой подписки или лентой календаря."""

    detail = "Не удалось выполнить операцию с подпиской на календарь."


class CalendarFeedNotFoundError(CalendarFeedServiceError):
    """Ссылка подписки неизвестна, отозвана или её владелец отключён.

    Причина наружу не раскрывается: иначе по ответу можно было бы отличить
    отозванную ссылку от несуществующей.
    """

    status_code = status.HTTP_404_NOT_FOUND
    detail = "Календарь не найден."

    def __init__(self):
        super().__init__(error_details=self.detail)

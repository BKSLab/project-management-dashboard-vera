from fastapi import status


class ApplicationError(Exception):
    """Базовое исключение приложения, которое может быть преобразовано в HTTP-ответ."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail = "Внутренняя ошибка приложения."

    def __init__(self, error_details: str):
        self.error_details = error_details
        super().__init__(error_details)

    def __str__(self) -> str:
        return f"{self.__class__.__name__}: {self.error_details}"


class RepositoryError(ApplicationError):
    """Базовое исключение слоя доступа к данным."""

    detail = "Ошибка базы данных."


class ServiceError(ApplicationError):
    """Базовое исключение сервисного слоя."""

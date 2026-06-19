from fastapi import status


class RepositoryError(Exception):
    """Базовое исключение для ошибок слоя репозиториев."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, error_details: str):
        self.error_details = error_details
        super().__init__(self.error_details)

    def __str__(self) -> str:
        return f"Ошибка в {self.__class__.__name__}. Подробности: {self.error_details}"

    @property
    def detail(self) -> str:
        return f"Ошибка базы данных. Подробности: {self.error_details}"


class DocumentsRepositoryError(RepositoryError):
    """Исключение репозитория документов."""


class WbsRepositoryError(RepositoryError):
    """Исключение репозитория ИСР."""


class KanbanRepositoryError(RepositoryError):
    """Исключение репозитория канбана."""


class DocumentLinksRepositoryError(RepositoryError):
    """Исключение репозитория связей документов."""

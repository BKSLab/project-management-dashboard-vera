from src.exceptions.base import RepositoryError, ServiceError


class SeedStateRepositoryError(RepositoryError):
    """Ошибка доступа к состоянию загрузки начальных данных."""

    detail = "Ошибка базы данных при проверке начальных данных."


class SeedStateAlreadyExistsRepositoryError(SeedStateRepositoryError):
    """Маркер загрузки уже сохранён другим процессом."""

    def __init__(self, key: str):
        self.key = key
        super().__init__(error_details=f"Маркер загрузки {key!r} уже существует.")


class InitialDataServiceError(ServiceError):
    """Ошибка проверки или загрузки начальных данных."""

    detail = "Не удалось подготовить начальные данные приложения."

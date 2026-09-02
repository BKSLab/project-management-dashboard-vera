from src.exceptions.base import RepositoryError


class UnitOfWorkRepositoryError(RepositoryError):
    """Ошибка фиксации общей транзакции сценария."""

    detail = "Ошибка базы данных при фиксации операции."

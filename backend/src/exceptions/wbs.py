from fastapi import status

from src.exceptions.base import RepositoryError, ServiceError


class WbsRepositoryError(RepositoryError):
    """Ошибка доступа к данным ИСР."""

    detail = "Ошибка базы данных при обработке ИСР."


class WbsServiceError(ServiceError):
    """Ошибка бизнес-операции с ИСР."""

    detail = "Не удалось выполнить операцию с ИСР."


class WbsCodeAlreadyExistsRepositoryError(WbsRepositoryError):
    """Код ИСР уже существует в БД."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(error_details=f"Код ИСР {code!r} уже существует.")


class WbsCodeConflictError(WbsServiceError):
    """Код ИСР уже занят другим узлом."""

    status_code = status.HTTP_409_CONFLICT

    def __init__(self, code: str):
        self.code = code
        super().__init__(error_details=f"Код ИСР {code!r} уже существует.")

    @property
    def detail(self) -> str:
        return f"Узел ИСР с кодом '{self.code}' уже существует."


class WbsItemNotFoundError(WbsServiceError):
    """Узел ИСР не найден."""

    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, item_id: int):
        self.item_id = item_id
        super().__init__(error_details=f"Узел ИСР id={item_id} не найден.")

    @property
    def detail(self) -> str:
        return f"Узел ИСР с id={self.item_id} не найден."

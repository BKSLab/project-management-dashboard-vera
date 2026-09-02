from fastapi import status

from src.exceptions.base import RepositoryError, ServiceError


class ApiTokensRepositoryError(RepositoryError):
    """Ошибка доступа к токенам внешних клиентов."""

    detail = "Ошибка базы данных при обработке токенов доступа."


class ApiTokensServiceError(ServiceError):
    """Ошибка бизнес-операции с токенами доступа."""

    detail = "Не удалось выполнить операцию с токеном доступа."


class ApiTokenNotFoundError(ApiTokensServiceError):
    """Токен не найден или принадлежит другому пользователю."""

    status_code = status.HTTP_404_NOT_FOUND
    detail = "Токен доступа не найден."

    def __init__(self, token_id: int):
        self.token_id = token_id
        super().__init__(error_details=f"Токен id={token_id} не найден.")


class ApiTokenLimitExceededError(ApiTokensServiceError):
    """Достигнут предел числа действующих токенов пользователя."""

    status_code = status.HTTP_409_CONFLICT
    detail = "Достигнут предел числа действующих токенов."

    def __init__(self, limit: int):
        self.limit = limit
        super().__init__(error_details=f"Разрешено не более {limit} действующих токенов.")


class InsufficientTokenScopeError(ApiTokensServiceError):
    """Токен выдан только на чтение, а операция изменяет данные."""

    status_code = status.HTTP_403_FORBIDDEN
    detail = "Токен выдан только на чтение."

    def __init__(self) -> None:
        super().__init__(error_details="Операция требует токена с правом записи.")

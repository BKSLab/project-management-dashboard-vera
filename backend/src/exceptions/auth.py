from fastapi import status

from src.exceptions.base import ServiceError


class AuthServiceError(ServiceError):
    """Ошибка сценария аутентификации."""

    detail = "Не удалось выполнить операцию аутентификации."


class InvalidCredentialsError(AuthServiceError):
    """Неверная пара логин и пароль.

    Ответ намеренно одинаков и для несуществующего логина, и для неверного
    пароля: иначе по коду ответа можно перебирать существующие логины.
    """

    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Неверный логин или пароль."

    def __init__(self, username: str):
        self.username = username
        super().__init__(error_details=f"Неудачная попытка входа: {username!r}.")


class InvalidInviteCodeError(AuthServiceError):
    """Код приглашения не подошёл."""

    status_code = status.HTTP_403_FORBIDDEN
    detail = "Неверный код приглашения."

    def __init__(self):
        super().__init__(error_details="Регистрация с неверным кодом приглашения.")


class InactiveUserError(AuthServiceError):
    """Учётная запись отключена."""

    status_code = status.HTTP_403_FORBIDDEN
    detail = "Учётная запись отключена."

    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(error_details=f"Вход отключённого пользователя id={user_id}.")


class NotAuthenticatedError(AuthServiceError):
    """Запрос без действительной сессии."""

    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Требуется вход в систему."

    def __init__(self):
        super().__init__(error_details="Запрос без действительной сессии.")


class WrongCurrentPasswordError(AuthServiceError):
    """Текущий пароль указан неверно при смене пароля."""

    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Текущий пароль указан неверно."

    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(error_details=f"Неверный текущий пароль, id={user_id}.")

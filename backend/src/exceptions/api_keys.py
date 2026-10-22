"""Ошибки сервисных API-ключей ."""

from fastapi import status

from src.exceptions.auth import AuthServiceError
from src.exceptions.base import RepositoryError, ServiceError


class ApiKeysRepositoryError(RepositoryError):
    """Ошибка доступа к таблицам ключей и журнала обращений."""

    detail = "Ошибка базы данных при обработке API-ключей."


class ApiKeysServiceError(ServiceError):
    """Ошибка бизнес-операции с API-ключами."""

    detail = "Не удалось выполнить операцию с API-ключом."




class ApiKeyNotFoundError(ApiKeysServiceError):
    """Ключа с таким идентификатором нет."""

    status_code = status.HTTP_404_NOT_FOUND
    detail = "API-ключ не найден."

    def __init__(self, key_id: object):
        self.key_id = key_id
        super().__init__(error_details=f"API-ключ id={key_id} не найден.")


class ApiKeyOwnerNotFoundError(ApiKeysServiceError):
    """Владелец ключа не найден среди активных пользователей трекера."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    detail = (
        "Владелец ключа должен быть активным пользователем трекера: ключ работает с его правами."
    )

    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(error_details=f"Пользователь id={user_id} не найден или отключён.")


class ApiKeyScopeError(AuthServiceError):
    """Ключу не хватает права на операцию."""

    status_code = status.HTTP_403_FORBIDDEN

    def __init__(self, required: str, granted: list[str]):
        self.required = required
        granted_text = ", ".join(sorted(granted)) if granted else "нет ни одного"
        self.detail = (
            f"Ключу не хватает права {required}. Выданные права: {granted_text}. "
            "Измените права своего ключа в разделе «API-ключи»."
        )
        super().__init__(error_details=self.detail)


class ApiKeyRouteNotAllowedError(AuthServiceError):
    """Операция не открыта сервисным ключам вообще."""

    status_code = status.HTTP_403_FORBIDDEN
    detail = (
        "Эта операция недоступна по сервисному API-ключу: она выполняется "
        "только из интерфейса трекера."
    )

    def __init__(self, operation: str):
        self.operation = operation
        super().__init__(error_details=f"Операция {operation} закрыта для API-ключей.")








class ApiKeyInvalidError(AuthServiceError):
    """Ключ не найден, отозван или не того формата (401).

    Отозванный и выдуманный ключ неотличимы: иначе перебором выяснялось бы,
    какие префиксы существуют.
    """

    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Недействительный API-ключ."

    def __init__(self) -> None:
        super().__init__(error_details="Предъявлен недействительный или отозванный API-ключ.")


class ApiKeyExpiredError(ApiKeyInvalidError):
    """Срок действия ключа истёк (401)."""

    def __init__(self, expires_on: str):
        self.detail = (
            f"Срок действия API-ключа истёк {expires_on}. "
            "Выпустите новый ключ в разделе «API-ключи»."
        )
        AuthServiceError.__init__(self, error_details=self.detail)

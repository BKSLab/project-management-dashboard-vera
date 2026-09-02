import logging
from dataclasses import dataclass
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException

from src.core.settings import get_settings
from src.db.models.api_tokens import ApiTokenScope
from src.db.models.users import User
from src.dependencies.repositories import ApiTokensRepositoryDep, UsersRepositoryDep
from src.exceptions.api_tokens import (
    ApiTokensRepositoryError,
    InsufficientTokenScopeError,
)
from src.exceptions.auth import InactiveUserError, NotAuthenticatedError
from src.exceptions.users import UsersRepositoryError
from src.utils.api_tokens import hash_token_secret
from src.utils.tokens import decode_access_token

logger = logging.getLogger(__name__)

SessionCookieDep = Annotated[str | None, Cookie(alias=get_settings().auth.session_cookie_name)]
AuthorizationHeaderDep = Annotated[str | None, Header(alias="Authorization")]

BEARER_SCHEME = "bearer"


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    """Кто выполняет запрос и с какими правами.

    Сессия из cookie всегда имеет полные права: ограничение скоупа введено
    для внешних клиентов, а не для владельца, работающего в интерфейсе.
    """

    user: User
    scope: ApiTokenScope
    via_api_token: bool


async def get_principal(
    session_cookie: SessionCookieDep = None,
    authorization: AuthorizationHeaderDep = None,
    users_repository: UsersRepositoryDep = None,
    tokens_repository: ApiTokensRepositoryDep = None,
) -> AuthenticatedPrincipal:
    """Определяет пользователя запроса по API-токену либо по cookie сессии.

    Это единственная точка аутентификации приложения: и HTTP-эндпоинты, и
    MCP-инструменты проходят через неё, поэтому проверки прав не дублируются.

    Args:
        session_cookie: Значение cookie сессии.
        authorization: Заголовок ``Authorization`` внешнего клиента.
        users_repository: Репозиторий пользователей.
        tokens_repository: Репозиторий токенов доступа.

    Returns:
        Пользователь запроса вместе с его правами.

    Raises:
        HTTPException: Если аутентификация не пройдена или пользователь отключён.
    """
    bearer_secret = _extract_bearer(authorization)
    if bearer_secret is not None:
        return await _principal_from_token(
            secret=bearer_secret,
            tokens_repository=tokens_repository,
            users_repository=users_repository,
        )

    if not session_cookie:
        raise _unauthorized(NotAuthenticatedError())
    user_id = decode_access_token(session_cookie)
    if user_id is None:
        raise _unauthorized(NotAuthenticatedError())
    user = await _load_active_user(users_repository, user_id)
    return AuthenticatedPrincipal(user=user, scope=ApiTokenScope.WRITE, via_api_token=False)


PrincipalDep = Annotated[AuthenticatedPrincipal, Depends(get_principal)]


async def get_current_user(principal: PrincipalDep) -> User:
    """Возвращает пользователя текущего запроса.

    Это охранник всех закрытых эндпоинтов: без действительной сессии или
    токена запрос дальше не проходит.

    Args:
        principal: Результат аутентификации.

    Returns:
        ORM-модель пользователя.
    """
    return principal.user


async def require_write_scope(principal: PrincipalDep) -> AuthenticatedPrincipal:
    """Пропускает только запросы, которым разрешено изменять данные.

    Args:
        principal: Результат аутентификации.

    Returns:
        Тот же принципал, если запись разрешена.

    Raises:
        HTTPException: Если токен выдан только на чтение.
    """
    if principal.scope is not ApiTokenScope.WRITE:
        error = InsufficientTokenScopeError()
        raise HTTPException(status_code=error.status_code, detail=error.detail)
    return principal


async def require_session(principal: PrincipalDep) -> User:
    """Пропускает только запросы из интерфейса, но не из внешнего клиента.

    Управление токенами закрыто для самих токенов: иначе скомпрометированный
    токен смог бы выпустить себе замену и отозвать чужие.

    Args:
        principal: Результат аутентификации.

    Returns:
        Пользователь сессии интерфейса.

    Raises:
        HTTPException: Если запрос выполнен по API-токену.
    """
    if principal.via_api_token:
        raise HTTPException(
            status_code=403,
            detail="Управление токенами доступно только из интерфейса.",
        )
    return principal.user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
WriteScopeDep = Annotated[AuthenticatedPrincipal, Depends(require_write_scope)]
SessionUserDep = Annotated[User, Depends(require_session)]


def _extract_bearer(authorization: str | None) -> str | None:
    """Достаёт секрет из заголовка ``Authorization: Bearer <token>``."""
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.strip().lower() != BEARER_SCHEME:
        return None
    secret = value.strip()
    return secret or None


async def _principal_from_token(
    *,
    secret: str,
    tokens_repository: ApiTokensRepositoryDep,
    users_repository: UsersRepositoryDep,
) -> AuthenticatedPrincipal:
    """Проверяет предъявленный секрет и собирает принципала."""
    try:
        token = await tokens_repository.get_active_by_hash(hash_token_secret(secret))
    except ApiTokensRepositoryError as error:
        logger.error("❌ Ошибка проверки токена доступа.", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка проверки доступа.") from error

    if token is None:
        # Отозванный, истёкший и выдуманный токен неотличимы для клиента.
        raise _unauthorized(NotAuthenticatedError())

    user = await _load_active_user(users_repository, token.user_id)
    try:
        await tokens_repository.touch_last_used(token)
    except ApiTokensRepositoryError:
        # Отметка использования — диагностика, а не условие доступа.
        logger.warning("⚠️ Не удалось отметить использование токена id=%s.", token.id)
    return AuthenticatedPrincipal(user=user, scope=token.scope, via_api_token=True)


async def _load_active_user(users_repository: UsersRepositoryDep, user_id: int) -> User:
    """Загружает пользователя и проверяет, что он не отключён."""
    try:
        user = await users_repository.get_by_id(user_id=user_id)
    except UsersRepositoryError as error:
        logger.error("❌ Ошибка загрузки пользователя сессии.", exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка проверки сессии.") from error

    if user is None:
        # Токен ещё валиден, но пользователя уже удалили.
        raise _unauthorized(NotAuthenticatedError())
    if not user.is_active:
        raise _unauthorized(InactiveUserError(user_id=user.id))
    return user


def _unauthorized(error: NotAuthenticatedError | InactiveUserError) -> HTTPException:
    """Преобразует доменную ошибку доступа в HTTP-ответ."""
    return HTTPException(status_code=error.status_code, detail=error.detail)

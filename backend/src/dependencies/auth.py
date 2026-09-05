"""HTTP-адаптер аутентификации.

Здесь нет ни одного правила доступа и ни одного обращения к данным: слой
достаёт cookie и заголовок, вызывает сервис и переводит его доменную ошибку
в HTTP-ответ. Это единственное исключение, разрешённое Depends-слою: над ним
нет эндпоинта, который сделал бы преобразование за него.
"""

import logging
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException

from src.core.settings import get_settings
from src.dependencies.services import AuthServiceDep
from src.exceptions.api_tokens import InsufficientTokenScopeError
from src.exceptions.auth import AuthServiceError
from src.services.auth import Principal
from src.utils.api_tokens import extract_bearer_secret

logger = logging.getLogger(__name__)

SessionCookieDep = Annotated[str | None, Cookie(alias=get_settings().auth.session_cookie_name)]
AuthorizationHeaderDep = Annotated[str | None, Header(alias="Authorization")]

TOKENS_ARE_SESSION_ONLY = "Управление токенами доступно только из интерфейса."


async def get_principal(
    service: AuthServiceDep,
    session_cookie: SessionCookieDep = None,
    authorization: AuthorizationHeaderDep = None,
) -> Principal:
    """Определяет принципала запроса и переводит отказ в HTTP-ответ.

    Args:
        service: Сервис аутентификации.
        session_cookie: Значение cookie сессии.
        authorization: Заголовок ``Authorization`` внешнего клиента.

    Returns:
        Принципал запроса вместе с его правами.

    Raises:
        HTTPException: Если аутентификация не пройдена или пользователь отключён.
    """
    try:
        return await service.resolve_principal(
            session_token=session_cookie,
            bearer_secret=extract_bearer_secret(authorization),
        )
    except AuthServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


PrincipalDep = Annotated[Principal, Depends(get_principal)]


async def require_write_scope(principal: PrincipalDep) -> Principal:
    """Пропускает только запросы, которым разрешено изменять данные.

    Args:
        principal: Результат аутентификации.

    Returns:
        Тот же принципал, если запись разрешена.

    Raises:
        HTTPException: Если токен выдан только на чтение.
    """
    if not principal.can_write:
        error = InsufficientTokenScopeError()
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    return principal


WriteScopeDep = Annotated[Principal, Depends(require_write_scope)]


async def require_session(principal: PrincipalDep) -> Principal:
    """Пропускает только запросы из интерфейса, но не из внешнего клиента.

    Управление токенами закрыто для самих токенов: иначе скомпрометированный
    токен смог бы выпустить себе замену и отозвать чужие.

    Args:
        principal: Результат аутентификации.

    Returns:
        Принципал сессии интерфейса.

    Raises:
        HTTPException: Если запрос выполнен по API-токену.
    """
    if principal.via_api_token:
        raise HTTPException(status_code=403, detail=TOKENS_ARE_SESSION_ONLY)
    return principal


SessionPrincipalDep = Annotated[Principal, Depends(require_session)]

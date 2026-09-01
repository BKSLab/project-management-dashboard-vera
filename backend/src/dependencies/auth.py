import logging
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException

from src.core.settings import get_settings
from src.db.models.users import User
from src.dependencies.repositories import UsersRepositoryDep
from src.exceptions.auth import InactiveUserError, NotAuthenticatedError
from src.exceptions.users import UsersRepositoryError
from src.utils.tokens import decode_access_token

logger = logging.getLogger(__name__)

SessionCookieDep = Annotated[str | None, Cookie(alias=get_settings().auth.session_cookie_name)]


async def get_current_user(
    session_cookie: SessionCookieDep = None,
    users_repository: UsersRepositoryDep = None,
) -> User:
    """Возвращает пользователя текущей сессии.

    Это охранник всех закрытых эндпоинтов: без действительного токена запрос
    дальше не проходит.

    Args:
        session_cookie: Значение cookie сессии.
        users_repository: Репозиторий пользователей.

    Returns:
        ORM-модель пользователя.

    Raises:
        HTTPException: Если сессии нет, она недействительна или пользователь отключён.
    """
    if not session_cookie:
        raise _unauthorized(NotAuthenticatedError())

    user_id = decode_access_token(session_cookie)
    if user_id is None:
        raise _unauthorized(NotAuthenticatedError())

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


CurrentUserDep = Annotated[User, Depends(get_current_user)]

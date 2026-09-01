import logging

from fastapi import APIRouter, HTTPException, Response, status

from src.api.v1.responses import (
    CONFLICT_RESPONSE,
    SERVER_ERROR_RESPONSE,
    VALIDATION_RESPONSE,
)
from src.core.settings import get_settings
from src.dependencies.auth import CurrentUserDep
from src.dependencies.services import AuthServiceDep
from src.exceptions.auth import AuthServiceError
from src.exceptions.users import UsersServiceError
from src.schemas.users import UserLoginSchema, UserRegisterSchema, UserSchema
from src.services.auth import to_user_schema

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

UNAUTHORIZED_RESPONSE = {
    "description": "Требуется вход в систему.",
    "content": {"application/json": {"example": {"detail": "Требуется вход в систему."}}},
}
FORBIDDEN_RESPONSE = {
    "description": "Действие запрещено.",
    "content": {"application/json": {"example": {"detail": "Неверный код приглашения."}}},
}


def _set_session_cookie(response: Response, token: str) -> None:
    """Кладёт токен в httpOnly cookie.

    `SameSite=Lax` закрывает CSRF: браузер не отправит такую cookie при
    кросс-сайтовых POST, PATCH и DELETE, а именно ими идут все мутации.
    """
    settings = get_settings().auth
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        max_age=settings.access_token_ttl_hours * 3600,
        path="/",
    )


@router.post(
    path="/register",
    status_code=status.HTTP_201_CREATED,
    summary="Зарегистрировать пользователя",
    description="Создаёт учётную запись по коду приглашения и сразу выполняет вход.",
    operation_id="registerUser",
    response_description="Созданный пользователь.",
    responses={
        403: FORBIDDEN_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
    response_model=UserSchema,
)
async def register(
    data: UserRegisterSchema,
    response: Response,
    service: AuthServiceDep,
) -> UserSchema:
    """Регистрирует пользователя и открывает сессию.

    Args:
        data: Поля регистрации, включая код приглашения.
        response: HTTP-ответ для установки cookie сессии.
        service: Сервис аутентификации.

    Returns:
        Карточка созданного пользователя.

    Raises:
        HTTPException: Если код неверен, логин занят или создать запись не удалось.
    """
    logger.info("🚀 Запрос POST /auth/register. Логин: %s.", data.username)
    try:
        user = await service.register(data=data.model_dump())
        _, token = await service.login(username=data.username, password=data.password)
        _set_session_cookie(response=response, token=token)
        logger.info("✅ Пользователь %s зарегистрирован.", user.username)
        return user
    except (AuthServiceError, UsersServiceError) as error:
        logger.exception("❌ Ошибка POST /auth/register. Детали: %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post(
    path="/login",
    status_code=status.HTTP_200_OK,
    summary="Войти в систему",
    description="Проверяет логин и пароль и открывает сессию в httpOnly cookie.",
    operation_id="loginUser",
    response_description="Вошедший пользователь.",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        403: FORBIDDEN_RESPONSE,
        422: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
    response_model=UserSchema,
)
async def login(
    data: UserLoginSchema,
    response: Response,
    service: AuthServiceDep,
) -> UserSchema:
    """Выполняет вход пользователя.

    Args:
        data: Логин и пароль.
        response: HTTP-ответ для установки cookie сессии.
        service: Сервис аутентификации.

    Returns:
        Карточка вошедшего пользователя.

    Raises:
        HTTPException: Если пара неверна или учётная запись отключена.
    """
    logger.info("🚀 Запрос POST /auth/login. Логин: %s.", data.username)
    try:
        user, token = await service.login(username=data.username, password=data.password)
        _set_session_cookie(response=response, token=token)
        logger.info("✅ Пользователь %s вошёл в систему.", user.username)
        return user
    except AuthServiceError as error:
        logger.warning("⚠️ Неудачный вход. Детали: %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post(
    path="/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Выйти из системы",
    description="Сбрасывает cookie сессии.",
    operation_id="logoutUser",
    response_description="Сессия завершена.",
)
async def logout(response: Response) -> None:
    """Завершает сессию пользователя.

    Args:
        response: HTTP-ответ для сброса cookie.

    Returns:
        ``None`` после сброса cookie.
    """
    logger.info("🚀 Запрос POST /auth/logout.")
    response.delete_cookie(key=get_settings().auth.session_cookie_name, path="/")
    logger.info("✅ Сессия завершена.")


@router.get(
    path="/me",
    status_code=status.HTTP_200_OK,
    summary="Текущий пользователь",
    description="Возвращает карточку пользователя текущей сессии.",
    operation_id="getCurrentUser",
    response_description="Текущий пользователь.",
    responses={401: UNAUTHORIZED_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=UserSchema,
)
async def get_me(user: CurrentUserDep) -> UserSchema:
    """Возвращает пользователя текущей сессии.

    Args:
        user: Пользователь, разрешённый зависимостью сессии.

    Returns:
        Карточка пользователя.
    """
    logger.info("🚀 Запрос GET /auth/me. Пользователь: %s.", user.username)
    return to_user_schema(user)

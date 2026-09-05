import logging

from fastapi import APIRouter, HTTPException, Response, status

from src.api.v1.responses import (
    CONFLICT_RESPONSE,
    SERVER_ERROR_RESPONSE,
    VALIDATION_RESPONSE,
)
from src.dependencies.auth import PrincipalDep
from src.dependencies.cookies import SessionCookiePolicyDep
from src.dependencies.services import AuthServiceDep, UsersServiceDep
from src.exceptions.auth import AuthServiceError
from src.exceptions.users import UsersServiceError
from src.schemas.users import UserLoginSchema, UserRegisterSchema, UserSchema

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
    cookie_policy: SessionCookiePolicyDep,
) -> UserSchema:
    """Регистрирует пользователя и открывает сессию.

    Регистрация со входом — один сценарий сервиса: эндпоинт только
    ставит cookie по его результату.

    Args:
        data: Поля регистрации, включая код приглашения.
        response: HTTP-ответ для установки cookie сессии.
        service: Сервис аутентификации.
        cookie_policy: Политика cookie сессии.

    Returns:
        Карточка созданного пользователя.

    Raises:
        HTTPException: Если код неверен, логин занят или создать запись не удалось.
    """
    logger.info("🚀 Запрос POST /auth/register. Логин: %s.", data.username)
    try:
        user, token = await service.register_and_login(data=data.model_dump())
        cookie_policy.set(response=response, token=token)
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
    cookie_policy: SessionCookiePolicyDep,
) -> UserSchema:
    """Выполняет вход пользователя.

    Args:
        data: Логин и пароль.
        response: HTTP-ответ для установки cookie сессии.
        service: Сервис аутентификации.
        cookie_policy: Политика cookie сессии.

    Returns:
        Карточка вошедшего пользователя.

    Raises:
        HTTPException: Если пара неверна или учётная запись отключена.
    """
    logger.info("🚀 Запрос POST /auth/login. Логин: %s.", data.username)
    try:
        user, token = await service.login(username=data.username, password=data.password)
        cookie_policy.set(response=response, token=token)
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
async def logout(response: Response, cookie_policy: SessionCookiePolicyDep) -> None:
    """Завершает сессию пользователя.

    Args:
        response: HTTP-ответ для сброса cookie.
        cookie_policy: Политика cookie сессии.

    Returns:
        ``None`` после сброса cookie.
    """
    logger.info("🚀 Запрос POST /auth/logout.")
    cookie_policy.clear(response=response)
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
async def get_me(principal: PrincipalDep, service: UsersServiceDep) -> UserSchema:
    """Возвращает пользователя текущей сессии.

    Карточка собирается сервисом пользователей: транспорт знает принципала,
    но не персистентную модель и не её преобразование в схему.

    Args:
        principal: Принципал, разрешённый зависимостью сессии.
        service: Сервис профиля пользователя.

    Returns:
        Карточка пользователя.

    Raises:
        HTTPException: Если получить карточку не удалось.
    """
    logger.info("🚀 Запрос GET /auth/me. Пользователь: %s.", principal.username)
    try:
        return await service.get_user(user_id=principal.user_id)
    except UsersServiceError as error:
        logger.exception("❌ Ошибка GET /auth/me. Детали: %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

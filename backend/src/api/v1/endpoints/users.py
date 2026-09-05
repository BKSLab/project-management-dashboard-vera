import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status

from src.api.v1.responses import (
    NOT_FOUND_RESPONSE,
    SERVER_ERROR_RESPONSE,
    VALIDATION_RESPONSE,
)
from src.dependencies.auth import PrincipalDep, require_write_scope
from src.dependencies.services import UsersServiceDep
from src.exceptions.auth import AuthServiceError
from src.exceptions.users import UsersServiceError
from src.schemas.users import PasswordChangeSchema, UserSchema, UserUpdateSchema

router = APIRouter(prefix="/users", tags=["users"])
logger = logging.getLogger(__name__)

UNAUTHORIZED_RESPONSE = {
    "description": "Требуется вход в систему.",
    "content": {"application/json": {"example": {"detail": "Требуется вход в систему."}}},
}


@router.patch(
    path="/me",
    dependencies=[Depends(require_write_scope)],
    status_code=status.HTTP_200_OK,
    summary="Изменить профиль",
    description="Обновляет ФИО и контакты текущего пользователя.",
    operation_id="updateCurrentUser",
    response_description="Обновлённый профиль.",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        422: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
    response_model=UserSchema,
)
async def update_me(
    data: UserUpdateSchema,
    principal: PrincipalDep,
    service: UsersServiceDep,
) -> UserSchema:
    """Обновляет профиль текущего пользователя.

    Args:
        data: Изменяемые поля профиля.
        principal: Принципал текущего запроса.
        service: Сервис профиля.

    Returns:
        Обновлённая карточка пользователя.

    Raises:
        HTTPException: Если обновить профиль не удалось.
    """
    logger.info("🚀 Запрос PATCH /users/me. Пользователь: %s.", principal.username)
    try:
        result = await service.update_profile(
            user_id=principal.user_id,
            data=data.model_dump(exclude_unset=True),
        )
        logger.info("✅ Профиль пользователя %s обновлён.", principal.username)
        return result
    except UsersServiceError as error:
        logger.exception("❌ Ошибка PATCH /users/me. Детали: %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post(
    path="/me/password",
    dependencies=[Depends(require_write_scope)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Сменить пароль",
    description="Меняет пароль после проверки текущего. Новый пароль вводится дважды.",
    operation_id="changeCurrentUserPassword",
    response_description="Пароль изменён.",
    responses={
        400: VALIDATION_RESPONSE,
        401: UNAUTHORIZED_RESPONSE,
        422: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
)
async def change_password(
    data: PasswordChangeSchema,
    principal: PrincipalDep,
    service: UsersServiceDep,
) -> None:
    """Меняет пароль текущего пользователя.

    Args:
        data: Текущий и новый пароль.
        principal: Принципал текущего запроса.
        service: Сервис профиля.

    Returns:
        ``None`` после успешной смены.

    Raises:
        HTTPException: Если текущий пароль неверен или сменить не удалось.
    """
    logger.info("🚀 Запрос POST /users/me/password. Пользователь: %s.", principal.username)
    try:
        await service.change_password(
            user_id=principal.user_id,
            current_password=data.current_password,
            new_password=data.password,
        )
        logger.info("✅ Пароль пользователя %s изменён.", principal.username)
    except (UsersServiceError, AuthServiceError) as error:
        logger.warning("⚠️ Ошибка POST /users/me/password. Детали: %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post(
    path="/me/avatar",
    dependencies=[Depends(require_write_scope)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Загрузить фотографию",
    description="Сохраняет фотографию профиля: JPEG, PNG или WebP до 5 МБ.",
    operation_id="uploadCurrentUserAvatar",
    response_description="Фотография сохранена.",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        413: VALIDATION_RESPONSE,
        415: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
)
async def upload_avatar(
    principal: PrincipalDep,
    service: UsersServiceDep,
    file: Annotated[UploadFile, File(description="Файл изображения до 5 МБ.")],
) -> None:
    """Загружает фотографию профиля.

    Args:
        principal: Принципал текущего запроса.
        service: Сервис профиля.
        file: Загружаемый файл изображения.

    Returns:
        ``None`` после успешной загрузки.

    Raises:
        HTTPException: Если тип или размер не подходят, либо сохранить не удалось.
    """
    logger.info("🚀 Запрос POST /users/me/avatar. Файл: %r.", file.filename)
    try:
        await service.set_avatar(
            user_id=principal.user_id,
            content_type=file.content_type or "",
            content=await file.read(),
        )
        logger.info("✅ Фотография пользователя %s загружена.", principal.username)
    except UsersServiceError as error:
        logger.warning("⚠️ Ошибка POST /users/me/avatar. Детали: %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get(
    path="/me/avatar",
    status_code=status.HTTP_200_OK,
    summary="Получить фотографию",
    description="Отдаёт фотографию профиля текущего пользователя.",
    operation_id="getCurrentUserAvatar",
    response_description="Содержимое файла фотографии.",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
    response_class=Response,
)
async def get_avatar(principal: PrincipalDep, service: UsersServiceDep) -> Response:
    """Отдаёт фотографию профиля.

    Args:
        principal: Принципал текущего запроса.
        service: Сервис профиля.

    Returns:
        Ответ с бинарным содержимым изображения.

    Raises:
        HTTPException: Если фотографии нет или прочитать её не удалось.
    """
    logger.info("🚀 Запрос GET /users/me/avatar. Пользователь: %s.", principal.username)
    try:
        content, content_type = await service.get_avatar(user_id=principal.user_id)
        # Фотография меняется редко, но приватна: кэшируем только в браузере.
        return Response(
            content=content,
            media_type=content_type,
            headers={"Cache-Control": "private, max-age=60"},
        )
    except UsersServiceError as error:
        logger.info("ℹ️ Ошибка GET /users/me/avatar. Детали: %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.delete(
    path="/me/avatar",
    dependencies=[Depends(require_write_scope)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить фотографию",
    description="Удаляет фотографию профиля текущего пользователя.",
    operation_id="deleteCurrentUserAvatar",
    response_description="Фотография удалена.",
    responses={
        401: UNAUTHORIZED_RESPONSE,
        404: NOT_FOUND_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
)
async def delete_avatar(principal: PrincipalDep, service: UsersServiceDep) -> None:
    """Удаляет фотографию профиля.

    Args:
        principal: Принципал текущего запроса.
        service: Сервис профиля.

    Returns:
        ``None`` после успешного удаления.

    Raises:
        HTTPException: Если фотографии нет или удалить её не удалось.
    """
    logger.info("🚀 Запрос DELETE /users/me/avatar. Пользователь: %s.", principal.username)
    try:
        await service.delete_avatar(user_id=principal.user_id)
        logger.info("✅ Фотография пользователя %s удалена.", principal.username)
    except UsersServiceError as error:
        logger.warning("⚠️ Ошибка DELETE /users/me/avatar. Детали: %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from src.api.v1.responses import (
    CONFLICT_RESPONSE,
    NOT_FOUND_RESPONSE,
    SERVER_ERROR_RESPONSE,
    VALIDATION_RESPONSE,
)
from src.dependencies.access import ProjectIdPath, require_project_access
from src.dependencies.auth import PrincipalDep, require_write_scope
from src.dependencies.services import ProjectStickersServiceDep
from src.exceptions.project_stickers import ProjectStickersServiceError
from src.schemas.project_stickers import (
    ProjectStickerCreateSchema,
    ProjectStickerPositionUpdateSchema,
    ProjectStickerSchema,
    ProjectStickerUpdateSchema,
)

router = APIRouter(tags=["project-board"])
logger = logging.getLogger(__name__)
StickerIdPath = Annotated[int, Path(gt=0, description="Идентификатор стикера.")]


@router.get(
    "/projects/{project_id}/board/stickers",
    dependencies=[Depends(require_project_access)],
    response_model=list[ProjectStickerSchema],
    responses={404: NOT_FOUND_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    summary="Получить стикеры Project Board",
    operation_id="listProjectBoardStickers",
)
async def list_project_stickers(
    project_id: ProjectIdPath,
    service: ProjectStickersServiceDep,
) -> list[ProjectStickerSchema]:
    """Возвращает стикеры только доступного пользователю проекта."""
    logger.info("🚀 Запрос GET /projects/%s/board/stickers.", project_id)
    try:
        result = await service.list_stickers(project_id)
        logger.info("✅ Получено стикеров проекта id=%s: %s.", project_id, len(result))
        return result
    except ProjectStickersServiceError as error:
        logger.exception("❌ Ошибка GET стикеров проекта id=%s.", project_id)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post(
    "/projects/{project_id}/board/stickers",
    dependencies=[Depends(require_project_access), Depends(require_write_scope)],
    response_model=ProjectStickerSchema,
    status_code=status.HTTP_201_CREATED,
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    summary="Создать стикер Project Board",
    operation_id="createProjectBoardSticker",
)
async def create_project_sticker(
    project_id: ProjectIdPath,
    data: ProjectStickerCreateSchema,
    service: ProjectStickersServiceDep,
    principal: PrincipalDep,
) -> ProjectStickerSchema:
    """Создаёт общий стикер от имени текущего участника проекта."""
    logger.info("🚀 Запрос POST стикера проекта id=%s.", project_id)
    try:
        result = await service.create_sticker(
            project_id=project_id,
            data=data,
            author_id=principal.user_id,
            author_username=principal.username,
            author_display_name=principal.full_name,
        )
        logger.info("✅ Создан стикер id=%s проекта id=%s.", result.id, project_id)
        return result
    except ProjectStickersServiceError as error:
        if error.status_code >= 500:
            logger.exception("❌ Ошибка POST стикера проекта id=%s.", project_id)
        else:
            logger.info("ℹ️ POST стикера проекта id=%s отклонён: %s", project_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.patch(
    "/projects/{project_id}/board/stickers/{sticker_id}",
    dependencies=[Depends(require_project_access), Depends(require_write_scope)],
    response_model=ProjectStickerSchema,
    responses={
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
    summary="Изменить стикер Project Board",
    operation_id="updateProjectBoardSticker",
)
async def update_project_sticker(
    project_id: ProjectIdPath,
    sticker_id: StickerIdPath,
    data: ProjectStickerUpdateSchema,
    service: ProjectStickersServiceDep,
) -> ProjectStickerSchema:
    """Изменяет стикер доступного проекта по optimistic revision."""
    logger.info("🚀 Запрос PATCH стикера id=%s проекта id=%s.", sticker_id, project_id)
    try:
        result = await service.update_sticker(
            project_id=project_id,
            sticker_id=sticker_id,
            data=data,
        )
        logger.info("✅ Изменён стикер id=%s, revision=%s.", result.id, result.revision)
        return result
    except ProjectStickersServiceError as error:
        if error.status_code >= 500:
            logger.exception("❌ Ошибка PATCH стикера id=%s.", sticker_id)
        else:
            logger.info("ℹ️ PATCH стикера id=%s отклонён: %s", sticker_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.patch(
    "/projects/{project_id}/board/stickers/{sticker_id}/position",
    dependencies=[Depends(require_project_access), Depends(require_write_scope)],
    response_model=ProjectStickerSchema,
    responses={
        404: NOT_FOUND_RESPONSE,
        422: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
    summary="Переместить стикер на Project Board",
    operation_id="moveProjectBoardSticker",
)
async def move_project_sticker(
    project_id: ProjectIdPath,
    sticker_id: StickerIdPath,
    data: ProjectStickerPositionUpdateSchema,
    service: ProjectStickersServiceDep,
) -> ProjectStickerSchema:
    """Сохраняет координаты стикера доступного пользователю проекта."""
    logger.info("🚀 Запрос PATCH позиции стикера id=%s проекта id=%s.", sticker_id, project_id)
    try:
        result = await service.move_sticker(
            project_id=project_id,
            sticker_id=sticker_id,
            data=data,
        )
        logger.info("✅ Перемещён стикер id=%s: (%s, %s).", result.id, result.canvas_x, result.canvas_y)
        return result
    except ProjectStickersServiceError as error:
        if error.status_code >= 500:
            logger.exception("❌ Ошибка PATCH позиции стикера id=%s.", sticker_id)
        else:
            logger.info("ℹ️ PATCH позиции стикера id=%s отклонён: %s", sticker_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.delete(
    "/projects/{project_id}/board/stickers/{sticker_id}",
    dependencies=[Depends(require_project_access), Depends(require_write_scope)],
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
    summary="Удалить стикер Project Board",
    operation_id="deleteProjectBoardSticker",
)
async def delete_project_sticker(
    project_id: ProjectIdPath,
    sticker_id: StickerIdPath,
    service: ProjectStickersServiceDep,
    revision: Annotated[int, Query(ge=1, description="Ожидаемая ревизия стикера.")],
) -> None:
    """Удаляет стикер доступного проекта по optimistic revision."""
    logger.info("🚀 Запрос DELETE стикера id=%s проекта id=%s.", sticker_id, project_id)
    try:
        await service.delete_sticker(
            project_id=project_id,
            sticker_id=sticker_id,
            revision=revision,
        )
        logger.info("✅ Удалён стикер id=%s проекта id=%s.", sticker_id, project_id)
    except ProjectStickersServiceError as error:
        if error.status_code >= 500:
            logger.exception("❌ Ошибка DELETE стикера id=%s.", sticker_id)
        else:
            logger.info("ℹ️ DELETE стикера id=%s отклонён: %s", sticker_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

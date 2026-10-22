import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response

from src.api.v1.responses import (
    NOT_FOUND_RESPONSE,
    SERVER_ERROR_RESPONSE,
    VALIDATION_RESPONSE,
)
from src.api.v1.uploads import read_upload
from src.dependencies.access import ProjectAccessDep, ProjectIdPath, require_project_access
from src.dependencies.auth import require_write_scope
from src.dependencies.services import ProjectIconsServiceDep
from src.exceptions.projects import ProjectsServiceError
from src.schemas.projects import ProjectSchema
from src.services.project_icons import MAX_ICON_IMAGE_SIZE

router = APIRouter(prefix="/projects", tags=["projects"])
logger = logging.getLogger(__name__)

TOO_LARGE = {"description": "Картинка больше 2 МБ."}
STORAGE_DOWN = {"description": "Файловое хранилище недоступно."}
# Картинка адресуется версией (?v=…): новая загрузка меняет адрес, поэтому
# ответ можно кешировать надолго, но только в браузере пользователя.
ICON_CACHE = "private, max-age=31536000, immutable"


@router.post(
    path="/{project_id}/icon-image",
    dependencies=[Depends(require_write_scope)],
    status_code=status.HTTP_200_OK,
    summary="Загрузить свою картинку проекта",
    description=(
        "Принимает PNG, JPG или WebP до 2 МБ (тип проверяется по содержимому, SVG не "
        "принимается) и показывает её вместо иконки проекта. Менять может тот, кто может "
        "менять проект. Прежняя картинка заменяется."
    ),
    operation_id="uploadProjectIconImage",
    response_description="Проект с новой версией картинки в icon_image_version.",
    responses={
        404: NOT_FOUND_RESPONSE,
        413: TOO_LARGE,
        422: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
        502: STORAGE_DOWN,
    },
    response_model=ProjectSchema,
)
async def upload_project_icon_image(
    project_id: ProjectIdPath,
    file: Annotated[UploadFile, File(description="PNG, JPG или WebP до 2 МБ.")],
    grant: ProjectAccessDep,
    service: ProjectIconsServiceDep,
) -> ProjectSchema:
    """Сохраняет свою картинку проекта.

    Args:
        project_id: Идентификатор проекта.
        file: Загружаемая картинка.
        grant: Подтверждённый доступ с правом записи.
        service: Сервис картинки проекта.

    Returns:
        Обновлённый проект.

    Raises:
        HTTPException: Файл велик или не картинка, проект недоступен, хранилище лежит.
    """
    logger.info("🚀 Запрос POST /projects/%s/icon-image.", project_id)
    try:
        upload = await read_upload(file, max_size=MAX_ICON_IMAGE_SIZE)
        return await service.upload(
            project_id=project_id,
            content=upload.content,
        )
    except ProjectsServiceError as error:
        logger.warning("⚠️ Картинка проекта id=%s отклонена: %s.", project_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    finally:
        await file.close()


@router.delete(
    path="/{project_id}/icon-image",
    dependencies=[Depends(require_write_scope)],
    status_code=status.HTTP_200_OK,
    summary="Убрать свою картинку проекта",
    description="Проект снова показывает иконку из набора, эмодзи или цветную точку.",
    operation_id="deleteProjectIconImage",
    response_description="Проект без картинки.",
    responses={404: NOT_FOUND_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=ProjectSchema,
)
async def delete_project_icon_image(
    project_id: ProjectIdPath,
    grant: ProjectAccessDep,
    service: ProjectIconsServiceDep,
) -> ProjectSchema:
    """Убирает картинку проекта.

    Args:
        project_id: Идентификатор проекта.
        grant: Подтверждённый доступ с правом записи.
        service: Сервис картинки проекта.

    Returns:
        Обновлённый проект.

    Raises:
        HTTPException: Проект недоступен или сохранить не удалось.
    """
    logger.info("🚀 Запрос DELETE /projects/%s/icon-image.", project_id)
    try:
        return await service.remove(
            project_id=project_id
        )
    except ProjectsServiceError as error:
        logger.exception("❌ Ошибка DELETE /projects/%s/icon-image: %s", project_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get(
    path="/{project_id}/icon-image",
    dependencies=[Depends(require_project_access)],
    summary="Получить свою картинку проекта",
    description=(
        "Отдаёт картинку проекта тем, кто видит проект. Адрес с ?v=<icon_image_version> "
        "кешируется браузером надолго: новая загрузка меняет версию."
    ),
    operation_id="getProjectIconImage",
    response_description="Картинка PNG, JPEG или WebP.",
    responses={404: NOT_FOUND_RESPONSE, 500: SERVER_ERROR_RESPONSE, 502: STORAGE_DOWN},
)
async def get_project_icon_image(
    project_id: ProjectIdPath,
    service: ProjectIconsServiceDep,
) -> Response:
    """Отдаёт картинку проекта через трекер, не раскрывая ссылку хранилища.

    Args:
        project_id: Идентификатор доступного проекта.
        service: Сервис картинки проекта.

    Returns:
        Содержимое картинки.

    Raises:
        HTTPException: Картинки нет или хранилище недоступно.
    """
    try:
        image = await service.get(project_id)
    except ProjectsServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    return Response(
        content=image.content,
        media_type=image.content_type,
        headers={"Cache-Control": ICON_CACHE, "X-Content-Type-Options": "nosniff"},
    )

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status

from src.api.v1.responses import (
    CONFLICT_RESPONSE,
    NOT_FOUND_RESPONSE,
    SERVER_ERROR_RESPONSE,
    VALIDATION_RESPONSE,
)
from src.dependencies.services import ProjectsServiceDep
from src.exceptions.projects import ProjectsServiceError
from src.schemas.projects import (
    ProjectCreateSchema,
    ProjectSchema,
    ProjectStatsSchema,
    ProjectUpdateSchema,
)

router = APIRouter(prefix="/projects", tags=["projects"])
logger = logging.getLogger(__name__)


@router.get(
    path="",
    status_code=status.HTTP_200_OK,
    summary="Получить проекты",
    description="Возвращает все проекты трекера в порядке отображения.",
    operation_id="getProjects",
    response_description="Список проектов.",
    responses={500: SERVER_ERROR_RESPONSE},
    response_model=list[ProjectSchema],
)
async def get_projects(service: ProjectsServiceDep) -> list[ProjectSchema]:
    """Получает список проектов.

    Args:
        service: Сервис проектов.

    Returns:
        Список проектов.

    Raises:
        HTTPException: Если получить проекты не удалось.
    """
    logger.info("🚀 Запрос GET /projects.")
    try:
        result = await service.get_project_list()
        logger.info("✅ Проекты получены. Найдено: %s.", len(result))
        return result
    except ProjectsServiceError as error:
        logger.exception("❌ Ошибка GET /projects. Детали: %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post(
    path="",
    status_code=status.HTTP_201_CREATED,
    summary="Создать проект",
    description="Создаёт проект и наполняет его стадиями канбана по умолчанию.",
    operation_id="createProject",
    response_description="Созданный проект.",
    responses={
        409: CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
    response_model=ProjectSchema,
)
async def create_project(
    data: ProjectCreateSchema,
    service: ProjectsServiceDep,
) -> ProjectSchema:
    """Создаёт проект.

    Args:
        data: Поля нового проекта.
        service: Сервис проектов.

    Returns:
        Созданный проект.

    Raises:
        HTTPException: Если код проекта занят или создать проект не удалось.
    """
    logger.info("🚀 Запрос POST /projects. Код: %s.", data.key)
    try:
        result = await service.create_project(data=data.model_dump())
        logger.info("✅ Проект создан. id=%s.", result.id)
        return result
    except ProjectsServiceError as error:
        logger.exception("❌ Ошибка POST /projects. Детали: %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get(
    path="/{project_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить проект",
    description="Возвращает карточку проекта по идентификатору.",
    operation_id="getProject",
    response_description="Карточка проекта.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=ProjectSchema,
)
async def get_project(
    project_id: Annotated[int, Path(gt=0, description="Идентификатор проекта.")],
    service: ProjectsServiceDep,
) -> ProjectSchema:
    """Получает проект по идентификатору.

    Args:
        project_id: Идентификатор проекта.
        service: Сервис проектов.

    Returns:
        Карточка проекта.

    Raises:
        HTTPException: Если проект не найден или получить его не удалось.
    """
    logger.info("🚀 Запрос GET /projects/%s.", project_id)
    try:
        result = await service.get_project(project_id=project_id)
        logger.info("✅ Проект id=%s получен.", project_id)
        return result
    except ProjectsServiceError as error:
        logger.exception("❌ Ошибка GET /projects/%s. Детали: %s", project_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get(
    path="/{project_id}/stats",
    status_code=status.HTTP_200_OK,
    summary="Получить показатели проекта",
    description="Возвращает прогресс, сроки и распределение задач по стадиям проекта.",
    operation_id="getProjectStats",
    response_description="Показатели проекта.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=ProjectStatsSchema,
)
async def get_project_stats(
    project_id: Annotated[int, Path(gt=0, description="Идентификатор проекта.")],
    service: ProjectsServiceDep,
) -> ProjectStatsSchema:
    """Получает показатели проекта.

    Args:
        project_id: Идентификатор проекта.
        service: Сервис проектов.

    Returns:
        Показатели проекта.

    Raises:
        HTTPException: Если проект не найден или собрать показатели не удалось.
    """
    logger.info("🚀 Запрос GET /projects/%s/stats.", project_id)
    try:
        result = await service.get_project_stats(project_id=project_id)
        logger.info("✅ Показатели проекта id=%s собраны.", project_id)
        return result
    except ProjectsServiceError as error:
        logger.exception("❌ Ошибка GET /projects/%s/stats. Детали: %s", project_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.patch(
    path="/{project_id}",
    status_code=status.HTTP_200_OK,
    summary="Изменить проект",
    description="Частично обновляет поля проекта.",
    operation_id="updateProject",
    response_description="Обновлённый проект.",
    responses={
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
    response_model=ProjectSchema,
)
async def update_project(
    project_id: Annotated[int, Path(gt=0, description="Идентификатор проекта.")],
    data: ProjectUpdateSchema,
    service: ProjectsServiceDep,
) -> ProjectSchema:
    """Обновляет проект.

    Args:
        project_id: Идентификатор проекта.
        data: Изменяемые поля проекта.
        service: Сервис проектов.

    Returns:
        Обновлённый проект.

    Raises:
        HTTPException: Если проект не найден или обновить его не удалось.
    """
    logger.info("🚀 Запрос PATCH /projects/%s.", project_id)
    try:
        result = await service.update_project(
            project_id=project_id,
            data=data.model_dump(exclude_unset=True),
        )
        logger.info("✅ Проект id=%s обновлён.", project_id)
        return result
    except ProjectsServiceError as error:
        logger.exception("❌ Ошибка PATCH /projects/%s. Детали: %s", project_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.delete(
    path="/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить проект",
    description="Удаляет проект вместе с задачами, стадиями, структурой и документами.",
    operation_id="deleteProject",
    response_description="Проект удалён.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
)
async def delete_project(
    project_id: Annotated[int, Path(gt=0, description="Идентификатор проекта.")],
    service: ProjectsServiceDep,
) -> None:
    """Удаляет проект.

    Args:
        project_id: Идентификатор проекта.
        service: Сервис проектов.

    Returns:
        ``None`` после успешного удаления.

    Raises:
        HTTPException: Если проект не найден или удалить его не удалось.
    """
    logger.info("🚀 Запрос DELETE /projects/%s.", project_id)
    try:
        await service.delete_project(project_id=project_id)
        logger.info("✅ Проект id=%s удалён.", project_id)
    except ProjectsServiceError as error:
        logger.exception("❌ Ошибка DELETE /projects/%s. Детали: %s", project_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

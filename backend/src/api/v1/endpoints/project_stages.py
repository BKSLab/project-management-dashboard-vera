import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status

from src.api.v1.responses import (
    CONFLICT_RESPONSE,
    NOT_FOUND_RESPONSE,
    SERVER_ERROR_RESPONSE,
    VALIDATION_RESPONSE,
)
from src.dependencies.services import ProjectStagesServiceDep
from src.exceptions.project_stages import ProjectStagesServiceError
from src.exceptions.projects import ProjectsServiceError
from src.schemas.project_stages import StageCreateSchema, StageSchema, StageUpdateSchema

router = APIRouter(tags=["project-stages"])
logger = logging.getLogger(__name__)


@router.get(
    path="/projects/{project_id}/stages",
    status_code=status.HTTP_200_OK,
    summary="Получить стадии проекта",
    description="Возвращает колонки канбан-доски проекта в порядке отображения.",
    operation_id="getProjectStages",
    response_description="Список стадий проекта.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=list[StageSchema],
)
async def get_stages(
    project_id: Annotated[int, Path(gt=0, description="Идентификатор проекта.")],
    service: ProjectStagesServiceDep,
) -> list[StageSchema]:
    """Получает стадии проекта.

    Args:
        project_id: Идентификатор проекта.
        service: Сервис стадий проекта.

    Returns:
        Список стадий.

    Raises:
        HTTPException: Если проект не найден или получить стадии не удалось.
    """
    logger.info("🚀 Запрос GET /projects/%s/stages.", project_id)
    try:
        result = await service.get_stage_list(project_id=project_id)
        logger.info("✅ Стадии проекта id=%s получены. Найдено: %s.", project_id, len(result))
        return result
    except (ProjectStagesServiceError, ProjectsServiceError) as error:
        logger.exception("❌ Ошибка GET /projects/%s/stages. Детали: %s", project_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post(
    path="/projects/{project_id}/stages",
    status_code=status.HTTP_201_CREATED,
    summary="Создать стадию проекта",
    description="Добавляет новую колонку в конец канбан-доски проекта.",
    operation_id="createProjectStage",
    response_description="Созданная стадия.",
    responses={
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
    response_model=StageSchema,
)
async def create_stage(
    project_id: Annotated[int, Path(gt=0, description="Идентификатор проекта.")],
    data: StageCreateSchema,
    service: ProjectStagesServiceDep,
) -> StageSchema:
    """Создаёт стадию проекта.

    Args:
        project_id: Идентификатор проекта.
        data: Поля новой стадии.
        service: Сервис стадий проекта.

    Returns:
        Созданная стадия.

    Raises:
        HTTPException: Если проект не найден или создать стадию не удалось.
    """
    logger.info("🚀 Запрос POST /projects/%s/stages. Название: %s.", project_id, data.name)
    try:
        result = await service.create_stage(project_id=project_id, data=data.model_dump())
        logger.info("✅ Стадия проекта создана. id=%s.", result.id)
        return result
    except (ProjectStagesServiceError, ProjectsServiceError) as error:
        logger.exception("❌ Ошибка POST /projects/%s/stages. Детали: %s", project_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.patch(
    path="/stages/{stage_id}",
    status_code=status.HTTP_200_OK,
    summary="Изменить стадию",
    description="Частично обновляет название, цвет, порядок или признак завершения стадии.",
    operation_id="updateProjectStage",
    response_description="Обновлённая стадия.",
    responses={
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
    response_model=StageSchema,
)
async def update_stage(
    stage_id: Annotated[int, Path(gt=0, description="Идентификатор стадии.")],
    data: StageUpdateSchema,
    service: ProjectStagesServiceDep,
) -> StageSchema:
    """Обновляет стадию.

    Args:
        stage_id: Идентификатор стадии.
        data: Изменяемые поля стадии.
        service: Сервис стадий проекта.

    Returns:
        Обновлённая стадия.

    Raises:
        HTTPException: Если стадия не найдена или обновить её не удалось.
    """
    logger.info("🚀 Запрос PATCH /stages/%s.", stage_id)
    try:
        result = await service.update_stage(
            stage_id=stage_id,
            data=data.model_dump(exclude_unset=True),
        )
        logger.info("✅ Стадия id=%s обновлена.", stage_id)
        return result
    except ProjectStagesServiceError as error:
        logger.exception("❌ Ошибка PATCH /stages/%s. Детали: %s", stage_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.delete(
    path="/stages/{stage_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить стадию",
    description="Удаляет пустую стадию проекта. Последнюю стадию удалить нельзя.",
    operation_id="deleteProjectStage",
    response_description="Стадия удалена.",
    responses={
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
)
async def delete_stage(
    stage_id: Annotated[int, Path(gt=0, description="Идентификатор стадии.")],
    service: ProjectStagesServiceDep,
) -> None:
    """Удаляет стадию.

    Args:
        stage_id: Идентификатор стадии.
        service: Сервис стадий проекта.

    Returns:
        ``None`` после успешного удаления.

    Raises:
        HTTPException: Если стадия не найдена, не пуста или удалить её не удалось.
    """
    logger.info("🚀 Запрос DELETE /stages/%s.", stage_id)
    try:
        await service.delete_stage(stage_id=stage_id)
        logger.info("✅ Стадия id=%s удалена.", stage_id)
    except ProjectStagesServiceError as error:
        logger.exception("❌ Ошибка DELETE /stages/%s. Детали: %s", stage_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

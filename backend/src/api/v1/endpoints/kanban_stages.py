import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status

from src.api.v1.responses import (
    CONFLICT_RESPONSE,
    NOT_FOUND_RESPONSE,
    SERVER_ERROR_RESPONSE,
    VALIDATION_RESPONSE,
)
from src.dependencies.services import KanbanStagesServiceDep
from src.exceptions.kanban_stages import KanbanStagesServiceError
from src.schemas.kanban_stages import StageCreateSchema, StageSchema, StageUpdateSchema

router = APIRouter(prefix="/kanban/stages", tags=["kanban-stages"])
logger = logging.getLogger(__name__)


@router.get(
    path="",
    status_code=status.HTTP_200_OK,
    summary="Получить стадии канбана",
    description="Возвращает стадии в настроенном порядке отображения.",
    operation_id="getKanbanStages",
    response_description="Упорядоченный список стадий.",
    responses={500: SERVER_ERROR_RESPONSE},
    response_model=list[StageSchema],
)
async def get_stages(service: KanbanStagesServiceDep) -> list[StageSchema]:
    """Получает стадии канбан-доски.

    Args:
        service: Сервис стадий канбана.

    Returns:
        Список стадий.

    Raises:
        HTTPException: Если получить стадии не удалось.
    """
    logger.info("🚀 Запрос GET /kanban/stages.")
    try:
        result = await service.get_stage_list()
        logger.info("✅ Стадии канбана получены. Найдено: %s.", len(result))
        return result
    except KanbanStagesServiceError as error:
        logger.exception("❌ Ошибка GET /kanban/stages. Детали: %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post(
    path="",
    status_code=status.HTTP_201_CREATED,
    summary="Создать стадию канбана",
    description="Добавляет новую колонку канбан-доски.",
    operation_id="createKanbanStage",
    response_description="Созданная стадия канбана.",
    responses={422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=StageSchema,
)
async def create_stage(
    data: StageCreateSchema,
    service: KanbanStagesServiceDep,
) -> StageSchema:
    """Создаёт стадию канбана.

    Args:
        data: Поля новой стадии.
        service: Сервис стадий канбана.

    Returns:
        Созданная стадия.

    Raises:
        HTTPException: Если создать стадию не удалось.
    """
    logger.info("🚀 Запрос POST /kanban/stages. Название: %s.", data.name)
    try:
        result = await service.create_stage(data=data.model_dump())
        logger.info("✅ Стадия канбана создана. id=%s.", result.id)
        return result
    except KanbanStagesServiceError as error:
        logger.exception("❌ Ошибка POST /kanban/stages. Детали: %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.patch(
    path="/{stage_id}",
    status_code=status.HTTP_200_OK,
    summary="Обновить стадию канбана",
    description="Частично обновляет название, порядок, цвет или завершающий признак стадии.",
    operation_id="updateKanbanStage",
    response_description="Обновлённая стадия канбана.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=StageSchema,
)
async def update_stage(
    stage_id: Annotated[int, Path(gt=0, description="Идентификатор стадии канбана.")],
    data: StageUpdateSchema,
    service: KanbanStagesServiceDep,
) -> StageSchema:
    """Обновляет стадию канбана.

    Args:
        stage_id: Идентификатор стадии.
        data: Изменяемые поля.
        service: Сервис стадий канбана.

    Returns:
        Обновлённая стадия.

    Raises:
        HTTPException: Если стадия не найдена или обновление не удалось.
    """
    logger.info("🚀 Запрос PATCH /kanban/stages/%s.", stage_id)
    try:
        result = await service.update_stage(
            stage_id=stage_id,
            data=data.model_dump(exclude_unset=True),
        )
        logger.info("✅ Стадия id=%s обновлена.", stage_id)
        return result
    except KanbanStagesServiceError as error:
        logger.exception("❌ Ошибка PATCH /kanban/stages/%s. Детали: %s", stage_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.delete(
    path="/{stage_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить стадию канбана",
    description="Удаляет только пустую стадию канбан-доски.",
    operation_id="deleteKanbanStage",
    response_description="Стадия удалена.",
    responses={
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
)
async def delete_stage(
    stage_id: Annotated[int, Path(gt=0, description="Идентификатор стадии канбана.")],
    service: KanbanStagesServiceDep,
) -> None:
    """Удаляет пустую стадию канбана.

    Args:
        stage_id: Идентификатор стадии.
        service: Сервис стадий канбана.

    Returns:
        ``None`` после успешного удаления.

    Raises:
        HTTPException: Если стадия не найдена, содержит задачи или удаление не удалось.
    """
    logger.info("🚀 Запрос DELETE /kanban/stages/%s.", stage_id)
    try:
        await service.delete_stage(stage_id=stage_id)
        logger.info("✅ Стадия id=%s удалена.", stage_id)
    except KanbanStagesServiceError as error:
        logger.exception("❌ Ошибка DELETE /kanban/stages/%s. Детали: %s", stage_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

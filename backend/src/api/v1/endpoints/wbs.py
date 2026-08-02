import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status

from src.api.v1.responses import (
    CONFLICT_RESPONSE,
    NOT_FOUND_RESPONSE,
    SERVER_ERROR_RESPONSE,
    VALIDATION_RESPONSE,
)
from src.dependencies.services import WbsServiceDep
from src.exceptions.wbs import WbsServiceError
from src.schemas.wbs import WbsItemCreateSchema, WbsItemSchema, WbsItemUpdateSchema, WbsNodeSchema

router = APIRouter(prefix="/wbs", tags=["wbs"])
logger = logging.getLogger(__name__)


@router.get(
    path="/tree",
    status_code=status.HTTP_200_OK,
    summary="Получить дерево ИСР",
    description="Возвращает иерархию работ с rollup-прогрессом листовых задач.",
    operation_id="getWbsTree",
    response_description="Корневые узлы дерева ИСР.",
    responses={500: SERVER_ERROR_RESPONSE},
    response_model=list[WbsNodeSchema],
)
async def get_tree(service: WbsServiceDep) -> list[WbsNodeSchema]:
    """Получает дерево ИСР.

    Args:
        service: Сервис ИСР.

    Returns:
        Корневые узлы дерева.

    Raises:
        HTTPException: Если построить дерево не удалось.
    """
    logger.info("🚀 Запрос GET /wbs/tree.")
    try:
        result = await service.get_tree()
        logger.info("✅ Дерево ИСР получено. Корневых узлов: %s.", len(result))
        return result
    except WbsServiceError as error:
        logger.exception("❌ Ошибка GET /wbs/tree. Детали: %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post(
    path="/items",
    status_code=status.HTTP_201_CREATED,
    summary="Создать узел ИСР",
    description="Добавляет узел ИСР и создаёт для нового листа связанную задачу канбана.",
    operation_id="createWbsItem",
    response_description="Созданный узел ИСР.",
    responses={
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
    response_model=WbsItemSchema,
)
async def create_item(
    data: WbsItemCreateSchema,
    service: WbsServiceDep,
) -> WbsItemSchema:
    """Создаёт узел ИСР.

    Args:
        data: Родитель и поля нового узла.
        service: Сервис ИСР.

    Returns:
        Созданный узел.

    Raises:
        HTTPException: Если родитель не найден или создать узел не удалось.
    """
    logger.info("🚀 Запрос POST /wbs/items. parent_id=%s, title=%s.", data.parent_id, data.title)
    try:
        result = await service.create_item(
            parent_id=data.parent_id,
            title=data.title,
            role=data.role,
            phase_name=data.phase_name,
        )
        logger.info("✅ Узел ИСР создан. id=%s, code=%s.", result.id, result.code)
        return result
    except WbsServiceError as error:
        logger.exception("❌ Ошибка POST /wbs/items. Детали: %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.patch(
    path="/items/{item_id}",
    status_code=status.HTTP_200_OK,
    summary="Обновить узел ИСР",
    description="Частично обновляет узел и синхронизирует название связанной задачи.",
    operation_id="updateWbsItem",
    response_description="Обновлённый узел ИСР.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=WbsItemSchema,
)
async def update_item(
    item_id: Annotated[int, Path(gt=0, description="Идентификатор узла ИСР.")],
    data: WbsItemUpdateSchema,
    service: WbsServiceDep,
) -> WbsItemSchema:
    """Обновляет узел ИСР.

    Args:
        item_id: Идентификатор узла.
        data: Изменяемые поля.
        service: Сервис ИСР.

    Returns:
        Обновлённый узел.

    Raises:
        HTTPException: Если узел не найден или обновление не удалось.
    """
    logger.info("🚀 Запрос PATCH /wbs/items/%s.", item_id)
    try:
        result = await service.update_item(
            item_id=item_id,
            data=data.model_dump(exclude_unset=True),
        )
        logger.info("✅ Узел ИСР id=%s обновлён.", item_id)
        return result
    except WbsServiceError as error:
        logger.exception("❌ Ошибка PATCH /wbs/items/%s. Детали: %s", item_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.delete(
    path="/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить узел ИСР",
    description="Удаляет узел, его потомков и связанные с листьями задачи канбана.",
    operation_id="deleteWbsItem",
    response_description="Узел ИСР удалён.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
)
async def delete_item(
    item_id: Annotated[int, Path(gt=0, description="Идентификатор узла ИСР.")],
    service: WbsServiceDep,
) -> None:
    """Удаляет узел ИСР.

    Args:
        item_id: Идентификатор узла.
        service: Сервис ИСР.

    Returns:
        ``None`` после успешного удаления.

    Raises:
        HTTPException: Если узел не найден или удаление не удалось.
    """
    logger.info("🚀 Запрос DELETE /wbs/items/%s.", item_id)
    try:
        await service.delete_item(item_id=item_id)
        logger.info("✅ Узел ИСР id=%s удалён.", item_id)
    except WbsServiceError as error:
        logger.exception("❌ Ошибка DELETE /wbs/items/%s. Детали: %s", item_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, status

from src.api.v1.responses import (
    CONFLICT_RESPONSE,
    NOT_FOUND_RESPONSE,
    SERVER_ERROR_RESPONSE,
    VALIDATION_RESPONSE,
)
from src.dependencies.services import DocumentLinksServiceDep, KanbanTasksServiceDep
from src.exceptions.document_links import DocumentLinksServiceError
from src.exceptions.kanban_stages import KanbanStagesServiceError
from src.exceptions.kanban_tasks import KanbanTasksServiceError
from src.schemas.document_links import LinkedDocumentSchema
from src.schemas.kanban_tasks import TaskCreateSchema, TaskMoveSchema, TaskSchema, TaskUpdateSchema

router = APIRouter(prefix="/kanban/tasks", tags=["kanban-tasks"])
logger = logging.getLogger(__name__)


@router.get(
    path="",
    status_code=status.HTTP_200_OK,
    summary="Получить задачи канбана",
    description="Возвращает задачи с фильтром по стадии и полнотекстовым поиском.",
    operation_id="getKanbanTasks",
    response_description="Список задач с контекстом ИСР, комментариев и поиска.",
    responses={422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=list[TaskSchema],
)
async def get_tasks(
    service: KanbanTasksServiceDep,
    stage_id: Annotated[
        int | None,
        Query(gt=0, description="Идентификатор стадии для фильтрации."),
    ] = None,
    search: Annotated[
        str | None,
        Query(max_length=200, description="Поиск по задаче, комментарию или коду ИСР."),
    ] = None,
) -> list[TaskSchema]:
    """Получает задачи канбан-доски.

    Args:
        service: Сервис задач канбана.
        stage_id: Опциональный фильтр стадии.
        search: Опциональная поисковая строка.

    Returns:
        Список задач.

    Raises:
        HTTPException: Если получить задачи не удалось.
    """
    logger.info("🚀 Запрос GET /kanban/tasks. stage_id=%s, search=%s.", stage_id, search)
    try:
        result = await service.get_task_list(stage_id=stage_id, search=search)
        logger.info("✅ Задачи канбана получены. Найдено: %s.", len(result))
        return result
    except KanbanTasksServiceError as error:
        logger.exception("❌ Ошибка GET /kanban/tasks. Детали: %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get(
    path="/{task_id}",
    status_code=status.HTTP_200_OK,
    summary="Получить задачу канбана",
    description="Возвращает карточку задачи по идентификатору.",
    operation_id="getKanbanTask",
    response_description="Карточка задачи канбана.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=TaskSchema,
)
async def get_task(
    task_id: Annotated[int, Path(gt=0, description="Идентификатор задачи канбана.")],
    service: KanbanTasksServiceDep,
) -> TaskSchema:
    """Получает задачу по идентификатору.

    Args:
        task_id: Идентификатор задачи.
        service: Сервис задач канбана.

    Returns:
        Карточка задачи.

    Raises:
        HTTPException: Если задача не найдена или получить её не удалось.
    """
    logger.info("🚀 Запрос GET /kanban/tasks/%s.", task_id)
    try:
        result = await service.get_task(task_id=task_id)
        logger.info("✅ Задача id=%s получена.", task_id)
        return result
    except KanbanTasksServiceError as error:
        logger.exception("❌ Ошибка GET /kanban/tasks/%s. Детали: %s", task_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post(
    path="",
    status_code=status.HTTP_201_CREATED,
    summary="Создать задачу канбана",
    description="Создаёт ручную задачу без связи с узлом ИСР.",
    operation_id="createKanbanTask",
    response_description="Созданная задача канбана.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=TaskSchema,
)
async def create_task(
    data: TaskCreateSchema,
    service: KanbanTasksServiceDep,
) -> TaskSchema:
    """Создаёт ручную задачу канбана.

    Args:
        data: Поля новой задачи.
        service: Сервис задач канбана.

    Returns:
        Созданная задача.

    Raises:
        HTTPException: Если стадия не найдена или создать задачу не удалось.
    """
    logger.info("🚀 Запрос POST /kanban/tasks. Заголовок: %s.", data.title)
    try:
        result = await service.create_task(data=data.model_dump())
        logger.info("✅ Задача канбана создана. id=%s.", result.id)
        return result
    except (KanbanTasksServiceError, KanbanStagesServiceError) as error:
        logger.exception("❌ Ошибка POST /kanban/tasks. Детали: %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.patch(
    path="/{task_id}",
    status_code=status.HTTP_200_OK,
    summary="Обновить задачу канбана",
    description="Частично обновляет заголовок, описание или срок задачи.",
    operation_id="updateKanbanTask",
    response_description="Обновлённая задача канбана.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=TaskSchema,
)
async def update_task(
    task_id: Annotated[int, Path(gt=0, description="Идентификатор задачи канбана.")],
    data: TaskUpdateSchema,
    service: KanbanTasksServiceDep,
) -> TaskSchema:
    """Обновляет задачу канбана.

    Args:
        task_id: Идентификатор задачи.
        data: Изменяемые поля.
        service: Сервис задач канбана.

    Returns:
        Обновлённая задача.

    Raises:
        HTTPException: Если задача не найдена или обновление не удалось.
    """
    logger.info("🚀 Запрос PATCH /kanban/tasks/%s.", task_id)
    try:
        result = await service.update_task(
            task_id=task_id,
            data=data.model_dump(exclude_unset=True),
        )
        logger.info("✅ Задача id=%s обновлена.", task_id)
        return result
    except KanbanTasksServiceError as error:
        logger.exception("❌ Ошибка PATCH /kanban/tasks/%s. Детали: %s", task_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.patch(
    path="/{task_id}/move",
    status_code=status.HTTP_200_OK,
    summary="Переместить задачу канбана",
    description="Изменяет стадию и позицию задачи с записью истории перехода.",
    operation_id="moveKanbanTask",
    response_description="Перемещённая задача канбана.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=TaskSchema,
)
async def move_task(
    task_id: Annotated[int, Path(gt=0, description="Идентификатор задачи канбана.")],
    data: TaskMoveSchema,
    service: KanbanTasksServiceDep,
) -> TaskSchema:
    """Перемещает задачу внутри канбан-доски.

    Args:
        task_id: Идентификатор задачи.
        data: Новая стадия и позиция.
        service: Сервис задач канбана.

    Returns:
        Перемещённая задача.

    Raises:
        HTTPException: Если задача или стадия не найдена либо перемещение не удалось.
    """
    logger.info(
        "🚀 Запрос PATCH /kanban/tasks/%s/move. stage_id=%s, position=%s.",
        task_id,
        data.stage_id,
        data.position,
    )
    try:
        result = await service.move_task(
            task_id=task_id,
            stage_id=data.stage_id,
            position=data.position,
        )
        logger.info("✅ Задача id=%s перемещена в стадию id=%s.", task_id, data.stage_id)
        return result
    except (KanbanTasksServiceError, KanbanStagesServiceError) as error:
        logger.exception("❌ Ошибка перемещения задачи id=%s. Детали: %s", task_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.delete(
    path="/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить задачу канбана",
    description="Удаляет только ручную задачу; задачи ИСР удаляются через дерево ИСР.",
    operation_id="deleteKanbanTask",
    response_description="Задача удалена.",
    responses={
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
)
async def delete_task(
    task_id: Annotated[int, Path(gt=0, description="Идентификатор задачи канбана.")],
    service: KanbanTasksServiceDep,
) -> None:
    """Удаляет ручную задачу канбана.

    Args:
        task_id: Идентификатор задачи.
        service: Сервис задач канбана.

    Returns:
        ``None`` после успешного удаления.

    Raises:
        HTTPException: Если задача не найдена, связана с ИСР или удаление не удалось.
    """
    logger.info("🚀 Запрос DELETE /kanban/tasks/%s.", task_id)
    try:
        await service.delete_task(task_id=task_id)
        logger.info("✅ Задача id=%s удалена.", task_id)
    except KanbanTasksServiceError as error:
        logger.exception("❌ Ошибка DELETE /kanban/tasks/%s. Детали: %s", task_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get(
    path="/{task_id}/links",
    status_code=status.HTTP_200_OK,
    summary="Получить документы задачи",
    description="Возвращает документы, связанные с задачей канбана.",
    operation_id="getKanbanTaskLinks",
    response_description="Список связанных документов.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=list[LinkedDocumentSchema],
)
async def get_task_links(
    task_id: Annotated[int, Path(gt=0, description="Идентификатор задачи канбана.")],
    service: DocumentLinksServiceDep,
) -> list[LinkedDocumentSchema]:
    """Получает документы задачи.

    Args:
        task_id: Идентификатор задачи.
        service: Сервис связей документов.

    Returns:
        Связанные документы.

    Raises:
        HTTPException: Если задача не найдена или получить связи не удалось.
    """
    logger.info("🚀 Запрос GET /kanban/tasks/%s/links.", task_id)
    try:
        result = await service.get_links_for_task(kanban_task_id=task_id)
        logger.info("✅ Связи задачи id=%s получены. Найдено: %s.", task_id, len(result))
        return result
    except (KanbanTasksServiceError, DocumentLinksServiceError) as error:
        logger.exception("❌ Ошибка GET /kanban/tasks/%s/links. Детали: %s", task_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from src.api.v1.responses import (
    CONFLICT_RESPONSE,
    NOT_FOUND_RESPONSE,
    SERVER_ERROR_RESPONSE,
    VALIDATION_RESPONSE,
)
from src.dependencies.access import get_accessible_project, get_accessible_task
from src.dependencies.services import DocumentLinksServiceDep, TasksServiceDep
from src.exceptions.document_links import DocumentLinksServiceError
from src.exceptions.project_stages import ProjectStagesServiceError
from src.exceptions.projects import ProjectsServiceError
from src.exceptions.tasks import TasksServiceError
from src.exceptions.wbs_nodes import WbsNodesServiceError
from src.schemas.document_links import LinkedDocumentSchema
from src.schemas.tasks import TaskCreateSchema, TaskMoveSchema, TaskSchema, TaskUpdateSchema

router = APIRouter(tags=["tasks"])
logger = logging.getLogger(__name__)

TaskErrors = (
    TasksServiceError,
    ProjectsServiceError,
    ProjectStagesServiceError,
    WbsNodesServiceError,
)


@router.get(
    path="/projects/{project_id}/tasks",
    dependencies=[Depends(get_accessible_project)],
    status_code=status.HTTP_200_OK,
    summary="Получить задачи проекта",
    description="Возвращает задачи проекта с фильтром по стадии и поиском по тексту и номеру.",
    operation_id="getProjectTasks",
    response_description="Список задач с контекстом комментариев и поиска.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=list[TaskSchema],
)
async def get_tasks(
    project_id: Annotated[int, Path(gt=0, description="Идентификатор проекта.")],
    service: TasksServiceDep,
    stage_id: Annotated[
        int | None,
        Query(gt=0, description="Идентификатор стадии для фильтрации."),
    ] = None,
    search: Annotated[
        str | None,
        Query(max_length=200, description="Поиск по задаче, комментарию или номеру."),
    ] = None,
) -> list[TaskSchema]:
    """Получает задачи проекта.

    Args:
        project_id: Идентификатор проекта.
        service: Сервис задач.
        stage_id: Опциональный фильтр стадии.
        search: Опциональная поисковая строка.

    Returns:
        Список задач.

    Raises:
        HTTPException: Если проект не найден или получить задачи не удалось.
    """
    logger.info(
        "🚀 Запрос GET /projects/%s/tasks. stage_id=%s, search=%s.",
        project_id,
        stage_id,
        search,
    )
    try:
        result = await service.get_task_list(
            project_id=project_id,
            stage_id=stage_id,
            search=search,
        )
        logger.info("✅ Задачи проекта id=%s получены. Найдено: %s.", project_id, len(result))
        return result
    except TaskErrors as error:
        logger.exception("❌ Ошибка GET /projects/%s/tasks. Детали: %s", project_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post(
    path="/projects/{project_id}/tasks",
    dependencies=[Depends(get_accessible_project)],
    status_code=status.HTTP_201_CREATED,
    summary="Создать задачу",
    description="Создаёт задачу в проекте и выдаёт ей сквозной номер вида KEY-42.",
    operation_id="createProjectTask",
    response_description="Созданная задача.",
    responses={
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
    response_model=TaskSchema,
)
async def create_task(
    project_id: Annotated[int, Path(gt=0, description="Идентификатор проекта.")],
    data: TaskCreateSchema,
    service: TasksServiceDep,
) -> TaskSchema:
    """Создаёт задачу проекта.

    Args:
        project_id: Идентификатор проекта.
        data: Поля новой задачи.
        service: Сервис задач.

    Returns:
        Созданная задача.

    Raises:
        HTTPException: Если проект или стадия не найдены, либо создать задачу не удалось.
    """
    logger.info("🚀 Запрос POST /projects/%s/tasks. Заголовок: %s.", project_id, data.title)
    try:
        result = await service.create_task(project_id=project_id, data=data.model_dump())
        logger.info("✅ Задача создана. id=%s, ключ=%s.", result.id, result.key)
        return result
    except TaskErrors as error:
        logger.exception("❌ Ошибка POST /projects/%s/tasks. Детали: %s", project_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get(
    path="/tasks/{task_id}",
    dependencies=[Depends(get_accessible_task)],
    status_code=status.HTTP_200_OK,
    summary="Получить задачу",
    description="Возвращает карточку задачи по идентификатору.",
    operation_id="getTask",
    response_description="Карточка задачи.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=TaskSchema,
)
async def get_task(
    task_id: Annotated[int, Path(gt=0, description="Идентификатор задачи.")],
    service: TasksServiceDep,
) -> TaskSchema:
    """Получает задачу по идентификатору.

    Args:
        task_id: Идентификатор задачи.
        service: Сервис задач.

    Returns:
        Карточка задачи.

    Raises:
        HTTPException: Если задача не найдена или получить её не удалось.
    """
    logger.info("🚀 Запрос GET /tasks/%s.", task_id)
    try:
        result = await service.get_task(task_id=task_id)
        logger.info("✅ Задача id=%s получена.", task_id)
        return result
    except TaskErrors as error:
        logger.exception("❌ Ошибка GET /tasks/%s. Детали: %s", task_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.patch(
    path="/tasks/{task_id}",
    dependencies=[Depends(get_accessible_task)],
    status_code=status.HTTP_200_OK,
    summary="Изменить задачу",
    description="Частично обновляет поля задачи и фиксирует значимые изменения в истории.",
    operation_id="updateTask",
    response_description="Обновлённая задача.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=TaskSchema,
)
async def update_task(
    task_id: Annotated[int, Path(gt=0, description="Идентификатор задачи.")],
    data: TaskUpdateSchema,
    service: TasksServiceDep,
) -> TaskSchema:
    """Обновляет задачу.

    Args:
        task_id: Идентификатор задачи.
        data: Изменяемые поля задачи.
        service: Сервис задач.

    Returns:
        Обновлённая задача.

    Raises:
        HTTPException: Если задача не найдена или обновить её не удалось.
    """
    logger.info("🚀 Запрос PATCH /tasks/%s.", task_id)
    try:
        result = await service.update_task(
            task_id=task_id,
            data=data.model_dump(exclude_unset=True),
        )
        logger.info("✅ Задача id=%s обновлена.", task_id)
        return result
    except TaskErrors as error:
        logger.exception("❌ Ошибка PATCH /tasks/%s. Детали: %s", task_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.patch(
    path="/tasks/{task_id}/move",
    dependencies=[Depends(get_accessible_task)],
    status_code=status.HTTP_200_OK,
    summary="Переместить задачу",
    description="Переносит задачу в другую стадию доски с сохранением позиции.",
    operation_id="moveTask",
    response_description="Перемещённая задача.",
    responses={
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
    response_model=TaskSchema,
)
async def move_task(
    task_id: Annotated[int, Path(gt=0, description="Идентификатор задачи.")],
    data: TaskMoveSchema,
    service: TasksServiceDep,
) -> TaskSchema:
    """Перемещает задачу по доске.

    Args:
        task_id: Идентификатор задачи.
        data: Целевая стадия и позиция.
        service: Сервис задач.

    Returns:
        Перемещённая задача.

    Raises:
        HTTPException: Если задача или стадия не найдены, либо переместить не удалось.
    """
    logger.info("🚀 Запрос PATCH /tasks/%s/move. Стадия: %s.", task_id, data.stage_id)
    try:
        result = await service.move_task(
            task_id=task_id,
            stage_id=data.stage_id,
            position=data.position,
        )
        logger.info("✅ Задача id=%s перемещена в стадию %s.", task_id, data.stage_id)
        return result
    except TaskErrors as error:
        logger.exception("❌ Ошибка PATCH /tasks/%s/move. Детали: %s", task_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.delete(
    path="/tasks/{task_id}",
    dependencies=[Depends(get_accessible_task)],
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить задачу",
    description="Удаляет задачу вместе с комментариями, историей и файлами.",
    operation_id="deleteTask",
    response_description="Задача удалена.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
)
async def delete_task(
    task_id: Annotated[int, Path(gt=0, description="Идентификатор задачи.")],
    service: TasksServiceDep,
) -> None:
    """Удаляет задачу.

    Args:
        task_id: Идентификатор задачи.
        service: Сервис задач.

    Returns:
        ``None`` после успешного удаления.

    Raises:
        HTTPException: Если задача не найдена или удалить её не удалось.
    """
    logger.info("🚀 Запрос DELETE /tasks/%s.", task_id)
    try:
        await service.delete_task(task_id=task_id)
        logger.info("✅ Задача id=%s удалена.", task_id)
    except TaskErrors as error:
        logger.exception("❌ Ошибка DELETE /tasks/%s. Детали: %s", task_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get(
    path="/tasks/{task_id}/links",
    dependencies=[Depends(get_accessible_task)],
    status_code=status.HTTP_200_OK,
    summary="Получить документы задачи",
    description="Возвращает документы, связанные с задачей.",
    operation_id="getTaskLinks",
    response_description="Связанные документы.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=list[LinkedDocumentSchema],
)
async def get_task_links(
    task_id: Annotated[int, Path(gt=0, description="Идентификатор задачи.")],
    service: DocumentLinksServiceDep,
) -> list[LinkedDocumentSchema]:
    """Получает связанные с задачей документы.

    Args:
        task_id: Идентификатор задачи.
        service: Сервис связей документов.

    Returns:
        Список связанных документов.

    Raises:
        HTTPException: Если задача не найдена или получить связи не удалось.
    """
    logger.info("🚀 Запрос GET /tasks/%s/links.", task_id)
    try:
        result = await service.get_links_for_task(task_id=task_id)
        logger.info("✅ Связи задачи id=%s получены. Найдено: %s.", task_id, len(result))
        return result
    except (DocumentLinksServiceError, TasksServiceError) as error:
        logger.exception("❌ Ошибка GET /tasks/%s/links. Детали: %s", task_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

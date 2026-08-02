import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status

from src.api.v1.responses import NOT_FOUND_RESPONSE, SERVER_ERROR_RESPONSE, VALIDATION_RESPONSE
from src.dependencies.services import TaskCommentsServiceDep
from src.exceptions.kanban_tasks import KanbanTasksServiceError
from src.exceptions.task_comments import TaskCommentsServiceError
from src.schemas.task_comments import CommentCreateSchema, CommentSchema

router = APIRouter(prefix="/kanban", tags=["task-comments"])
logger = logging.getLogger(__name__)


@router.get(
    path="/tasks/{task_id}/comments",
    status_code=status.HTTP_200_OK,
    summary="Получить комментарии задачи",
    description="Возвращает комментарии задачи в хронологическом порядке.",
    operation_id="getTaskComments",
    response_description="Список комментариев задачи.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=list[CommentSchema],
)
async def get_comments(
    task_id: Annotated[int, Path(gt=0, description="Идентификатор задачи канбана.")],
    service: TaskCommentsServiceDep,
) -> list[CommentSchema]:
    """Получает комментарии задачи.

    Args:
        task_id: Идентификатор задачи.
        service: Сервис комментариев задач.

    Returns:
        Комментарии задачи.

    Raises:
        HTTPException: Если задача не найдена или получить комментарии не удалось.
    """
    logger.info("🚀 Запрос GET /kanban/tasks/%s/comments.", task_id)
    try:
        result = await service.get_comments(task_id=task_id)
        logger.info("✅ Комментарии задачи id=%s получены. Найдено: %s.", task_id, len(result))
        return result
    except (TaskCommentsServiceError, KanbanTasksServiceError) as error:
        logger.exception(
            "❌ Ошибка получения комментариев задачи id=%s. Детали: %s", task_id, error
        )
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post(
    path="/tasks/{task_id}/comments",
    status_code=status.HTTP_201_CREATED,
    summary="Добавить комментарий к задаче",
    description="Добавляет комментарий и фиксирует событие в истории задачи.",
    operation_id="createTaskComment",
    response_description="Созданный комментарий.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=CommentSchema,
)
async def add_comment(
    task_id: Annotated[int, Path(gt=0, description="Идентификатор задачи канбана.")],
    data: CommentCreateSchema,
    service: TaskCommentsServiceDep,
) -> CommentSchema:
    """Добавляет комментарий к задаче.

    Args:
        task_id: Идентификатор задачи.
        data: Автор и текст комментария.
        service: Сервис комментариев задач.

    Returns:
        Созданный комментарий.

    Raises:
        HTTPException: Если задача не найдена или комментарий сохранить не удалось.
    """
    logger.info("🚀 Запрос POST /kanban/tasks/%s/comments. Автор: %s.", task_id, data.author_name)
    try:
        result = await service.add_comment(
            task_id=task_id,
            author_name=data.author_name,
            body_md=data.body_md,
        )
        logger.info("✅ Комментарий id=%s добавлен к задаче id=%s.", result.id, task_id)
        return result
    except (TaskCommentsServiceError, KanbanTasksServiceError) as error:
        logger.exception(
            "❌ Ошибка добавления комментария задачи id=%s. Детали: %s", task_id, error
        )
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.delete(
    path="/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить комментарий задачи",
    description="Удаляет комментарий по его идентификатору.",
    operation_id="deleteTaskComment",
    response_description="Комментарий удалён.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
)
async def delete_comment(
    comment_id: Annotated[int, Path(gt=0, description="Идентификатор комментария.")],
    service: TaskCommentsServiceDep,
) -> None:
    """Удаляет комментарий задачи.

    Args:
        comment_id: Идентификатор комментария.
        service: Сервис комментариев задач.

    Returns:
        ``None`` после успешного удаления.

    Raises:
        HTTPException: Если комментарий не найден или удаление не удалось.
    """
    logger.info("🚀 Запрос DELETE /kanban/comments/%s.", comment_id)
    try:
        await service.delete_comment(comment_id=comment_id)
        logger.info("✅ Комментарий id=%s удалён.", comment_id)
    except TaskCommentsServiceError as error:
        logger.exception("❌ Ошибка удаления комментария id=%s. Детали: %s", comment_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from src.api.v1.responses import NOT_FOUND_RESPONSE, SERVER_ERROR_RESPONSE, VALIDATION_RESPONSE
from src.dependencies.access import get_accessible_task
from src.dependencies.services import TaskActivityServiceDep
from src.exceptions.task_activity import TaskActivityServiceError
from src.exceptions.tasks import TasksServiceError
from src.schemas.task_activity import ActivitySchema

router = APIRouter(prefix="/tasks", tags=["task-activity"])
logger = logging.getLogger(__name__)


@router.get(
    path="/{task_id}/activity",
    dependencies=[Depends(get_accessible_task)],
    status_code=status.HTTP_200_OK,
    summary="Получить историю задачи",
    description="Возвращает неизменяемую историю значимых изменений задачи.",
    operation_id="getTaskActivity",
    response_description="Хронологический список событий задачи.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=list[ActivitySchema],
)
async def get_activity(
    task_id: Annotated[int, Path(gt=0, description="Идентификатор задачи канбана.")],
    service: TaskActivityServiceDep,
) -> list[ActivitySchema]:
    """Получает историю задачи.

    Args:
        task_id: Идентификатор задачи.
        service: Сервис истории задач.

    Returns:
        Список событий задачи.

    Raises:
        HTTPException: Если задача не найдена или получить историю не удалось.
    """
    logger.info("🚀 Запрос GET /tasks/%s/activity.", task_id)
    try:
        result = await service.get_activity(task_id=task_id)
        logger.info("✅ История задачи id=%s получена. Событий: %s.", task_id, len(result))
        return result
    except (TaskActivityServiceError, TasksServiceError) as error:
        logger.exception("❌ Ошибка получения истории задачи id=%s. Детали: %s", task_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from src.api.v1.responses import NOT_FOUND_RESPONSE, SERVER_ERROR_RESPONSE, VALIDATION_RESPONSE
from src.db.models.tasks import TaskPriority
from src.dependencies.access import get_accessible_project
from src.dependencies.services import CalendarServiceDep
from src.exceptions.calendar import CalendarServiceError
from src.exceptions.projects import ProjectNotFoundError
from src.schemas.calendar import CalendarResponseSchema, UnscheduledTasksPageSchema

router = APIRouter(tags=["calendar"])
logger = logging.getLogger(__name__)

CalendarErrors = (CalendarServiceError, ProjectNotFoundError)


@router.get(
    path="/projects/{project_id}/calendar",
    dependencies=[Depends(get_accessible_project)],
    status_code=status.HTTP_200_OK,
    summary="Получить временной диапазон проекта",
    description="Возвращает компактные задачи с дедлайнами и справочники календаря.",
    operation_id="getProjectCalendar",
    response_description="Read model календаря проекта.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=CalendarResponseSchema,
)
async def get_project_calendar(
    project_id: Annotated[int, Path(gt=0, description="Идентификатор проекта.")],
    date_from: Annotated[date, Query(description="Первый день диапазона включительно.")],
    date_to: Annotated[date, Query(description="Последний день диапазона включительно.")],
    today: Annotated[date, Query(description="Текущая дата в часовом поясе клиента.")],
    service: CalendarServiceDep,
    stage_id: Annotated[int | None, Query(gt=0, description="Фильтр по стадии.")] = None,
    priority: Annotated[TaskPriority | None, Query(description="Фильтр по приоритету.")] = None,
    assignee: Annotated[
        str | None,
        Query(min_length=1, max_length=255, description="Точная подпись исполнителя."),
    ] = None,
    wbs_node_id: Annotated[int | None, Query(gt=0, description="Фильтр по узлу ИСР.")] = None,
) -> CalendarResponseSchema:
    """Получает календарные задачи проекта в ограниченном диапазоне."""
    logger.info(
        "🚀 Запрос GET /projects/%s/calendar. date_from=%s, date_to=%s.",
        project_id,
        date_from,
        date_to,
    )
    try:
        return await service.get_range(
            project_id=project_id,
            date_from=date_from,
            date_to=date_to,
            today=today,
            stage_id=stage_id,
            priority=priority,
            assignee=assignee,
            wbs_node_id=wbs_node_id,
        )
    except CalendarErrors as error:
        logger.exception("❌ Ошибка GET /projects/%s/calendar. Детали: %s", project_id, error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get(
    path="/projects/{project_id}/calendar/unscheduled",
    dependencies=[Depends(get_accessible_project)],
    status_code=status.HTTP_200_OK,
    summary="Получить задачи проекта без срока",
    description="Возвращает курсорную страницу задач, у которых не задан due_date.",
    operation_id="getProjectUnscheduledTasks",
    response_description="Страница задач без срока.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=UnscheduledTasksPageSchema,
)
async def get_unscheduled_tasks(
    project_id: Annotated[int, Path(gt=0, description="Идентификатор проекта.")],
    today: Annotated[date, Query(description="Текущая дата в часовом поясе клиента.")],
    service: CalendarServiceDep,
    cursor: Annotated[int | None, Query(gt=0, description="Последний id прошлой страницы.")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Размер страницы.")] = 50,
    stage_id: Annotated[int | None, Query(gt=0, description="Фильтр по стадии.")] = None,
    priority: Annotated[TaskPriority | None, Query(description="Фильтр по приоритету.")] = None,
    assignee: Annotated[
        str | None,
        Query(min_length=1, max_length=255, description="Точная подпись исполнителя."),
    ] = None,
    wbs_node_id: Annotated[int | None, Query(gt=0, description="Фильтр по узлу ИСР.")] = None,
) -> UnscheduledTasksPageSchema:
    """Получает ограниченную страницу задач проекта без срока."""
    logger.info("🚀 Запрос GET /projects/%s/calendar/unscheduled.", project_id)
    try:
        return await service.get_unscheduled(
            project_id=project_id,
            today=today,
            cursor=cursor,
            limit=limit,
            stage_id=stage_id,
            priority=priority,
            assignee=assignee,
            wbs_node_id=wbs_node_id,
        )
    except CalendarErrors as error:
        logger.exception(
            "❌ Ошибка GET /projects/%s/calendar/unscheduled. Детали: %s",
            project_id,
            error,
        )
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from src.api.v1.responses import (
    CONFLICT_RESPONSE,
    NOT_FOUND_RESPONSE,
    SERVER_ERROR_RESPONSE,
    VALIDATION_RESPONSE,
)
from src.dependencies.access import get_accessible_project
from src.dependencies.services import CalendarScenarioServiceDep
from src.exceptions.calendar import CalendarServiceError
from src.exceptions.projects import ProjectNotFoundError
from src.exceptions.tasks import TasksServiceError
from src.schemas.calendar_scenarios import (
    ScenarioApplyRequestSchema,
    ScenarioApplyResponseSchema,
    ScenarioPreviewRequestSchema,
    ScenarioPreviewResponseSchema,
)

router = APIRouter(tags=["calendar-scenarios"])
logger = logging.getLogger(__name__)

ScenarioErrors = (CalendarServiceError, ProjectNotFoundError, TasksServiceError)


@router.post(
    "/projects/{project_id}/calendar/scenarios/preview",
    dependencies=[Depends(get_accessible_project)],
    response_model=ScenarioPreviewResponseSchema,
    responses={
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
    summary="Рассчитать календарный сценарий",
)
async def preview_calendar_scenario(
    project_id: Annotated[int, Path(gt=0)],
    data: ScenarioPreviewRequestSchema,
    service: CalendarScenarioServiceDep,
) -> ScenarioPreviewResponseSchema:
    """Возвращает proposed state без записи в PostgreSQL."""
    try:
        return await service.preview(
            project_id,
            [item.model_dump() for item in data.changes],
        )
    except ScenarioErrors as error:
        logger.info("⚠️ Preview сценария проекта id=%s отклонён: %s.", project_id, error.detail)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post(
    "/projects/{project_id}/calendar/scenarios/apply",
    dependencies=[Depends(get_accessible_project)],
    response_model=ScenarioApplyResponseSchema,
    responses={
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
    summary="Применить календарный сценарий",
)
async def apply_calendar_scenario(
    project_id: Annotated[int, Path(gt=0)],
    data: ScenarioApplyRequestSchema,
    service: CalendarScenarioServiceDep,
) -> ScenarioApplyResponseSchema:
    """Атомарно применяет подтверждённый результат preview."""
    try:
        return await service.apply(
            project_id,
            [item.model_dump() for item in data.changes],
        )
    except ScenarioErrors as error:
        logger.info("⚠️ Apply сценария проекта id=%s отклонён: %s.", project_id, error.detail)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

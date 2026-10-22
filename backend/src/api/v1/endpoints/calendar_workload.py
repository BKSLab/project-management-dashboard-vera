import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from src.api.v1.responses import NOT_FOUND_RESPONSE, SERVER_ERROR_RESPONSE, VALIDATION_RESPONSE
from src.dependencies.access import require_project_access
from src.dependencies.auth import PrincipalDep
from src.dependencies.services import CalendarWorkloadServiceDep
from src.exceptions.calendar import CalendarServiceError
from src.exceptions.projects import ProjectNotFoundError
from src.schemas.calendar_workload import CalendarWorkloadResponseSchema

router = APIRouter(tags=["calendar"])
logger = logging.getLogger(__name__)


@router.get(
    path="/projects/{project_id}/calendar/workload",
    dependencies=[Depends(require_project_access)],
    status_code=status.HTTP_200_OK,
    summary="Получить загрузку команды проекта по дням",
    description=(
        "По каждому участнику команды — нагрузка по рабочим дням периода в этом проекте и "
        "суммарно вне его (другие проекты и разовые задачи). Чужие задачи раскрываются "
        "ключом и названием, только если смотрящему виден их источник; иначе — только счётчик."
    ),
    operation_id="getProjectCalendarWorkload",
    response_description="Загрузка команды проекта.",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=CalendarWorkloadResponseSchema,
)
async def get_project_calendar_workload(
    project_id: Annotated[int, Path(gt=0, description="Идентификатор проекта.")],
    date_from: Annotated[date, Query(description="Первый день периода включительно.")],
    date_to: Annotated[date, Query(description="Последний день периода включительно.")],
    principal: PrincipalDep,
    service: CalendarWorkloadServiceDep,
) -> CalendarWorkloadResponseSchema:
    """Получает загрузку участников проекта в ограниченном периоде."""
    logger.info(
        "🚀 Запрос GET /projects/%s/calendar/workload. date_from=%s, date_to=%s.",
        project_id,
        date_from,
        date_to,
    )
    try:
        return await service.get_workload(
            project_id=project_id,
            viewer_id=principal.user_id,
            date_from=date_from,
            date_to=date_to,
        )
    except (CalendarServiceError, ProjectNotFoundError) as error:
        logger.exception(
            "❌ Ошибка GET /projects/%s/calendar/workload. Детали: %s", project_id, error
        )
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

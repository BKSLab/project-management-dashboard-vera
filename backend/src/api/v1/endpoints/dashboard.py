import logging

from fastapi import APIRouter, HTTPException, status

from src.api.v1.responses import SERVER_ERROR_RESPONSE
from src.dependencies.auth import PrincipalDep
from src.dependencies.services import DashboardServiceDep
from src.exceptions.dashboard import DashboardServiceError
from src.schemas.dashboard import DashboardSchema

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
logger = logging.getLogger(__name__)


@router.get(
    path="",
    status_code=status.HTTP_200_OK,
    summary="Получить сводку по проектам",
    description="Возвращает показатели портфеля, карточки проектов и задачи, требующие внимания.",
    operation_id="getDashboard",
    response_description="Сводка состояния всех проектов.",
    responses={500: SERVER_ERROR_RESPONSE},
    response_model=DashboardSchema,
)
async def get_dashboard(principal: PrincipalDep, service: DashboardServiceDep) -> DashboardSchema:
    """Получает сводку по всем проектам.

    Args:
        principal: Принципал текущего запроса.
        service: Сервис сводки по проектам.

    Returns:
        Сводка состояния проектов.

    Raises:
        HTTPException: Если собрать сводку не удалось.
    """
    logger.info("🚀 Запрос GET /dashboard.")
    try:
        result = await service.get_overview(user_id=principal.user_id)
        logger.info(
            "✅ Сводка собрана. Проектов: %s, задач: %s.",
            result.totals.total_projects,
            result.totals.total_tasks,
        )
        return result
    except DashboardServiceError as error:
        logger.exception("❌ Ошибка GET /dashboard. Детали: %s", error)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

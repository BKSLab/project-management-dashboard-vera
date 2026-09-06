"""HTTP-контракт проектного реестра рисков."""

import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from src.api.v1.responses import NOT_FOUND_RESPONSE, SERVER_ERROR_RESPONSE, VALIDATION_RESPONSE
from src.dependencies.access import require_project_access
from src.dependencies.auth import PrincipalDep, require_write_scope
from src.dependencies.services import ProjectRiskServiceDep
from src.exceptions.access import AccessServiceError
from src.exceptions.project_risks import ProjectRiskServiceError
from src.schemas.enums import RiskRating, RiskStatus
from src.schemas.project_risks import (
    ProjectRiskCreateSchema,
    ProjectRiskFilters,
    ProjectRiskPageSchema,
    ProjectRiskSchema,
    ProjectRiskSummarySchema,
    ProjectRiskUpdateSchema,
)

router = APIRouter(tags=["project-risks"], dependencies=[Depends(require_project_access)])
logger = logging.getLogger(__name__)
RiskErrors = (ProjectRiskServiceError, AccessServiceError)
ProjectId = Annotated[int, Path(gt=0, description="Идентификатор текущего проекта.", examples=[1])]
RiskId = Annotated[
    int, Path(gt=0, description="Идентификатор риска в текущем проекте.", examples=[12])
]
ERROR_RESPONSES = {
    401: {
        "description": "Требуется вход.",
        "content": {"application/json": {"example": {"detail": "Требуется авторизация."}}},
    },
    404: NOT_FOUND_RESPONSE,
    422: VALIDATION_RESPONSE,
    500: SERVER_ERROR_RESPONSE,
}
WRITE_RESPONSES = {
    **ERROR_RESPONSES,
    403: {
        "description": "Токен имеет только право чтения.",
        "content": {"application/json": {"example": {"detail": "Требуется право записи."}}},
    },
}


def get_risk_filters(
    status: Annotated[RiskStatus | None, Query(description="Состояние риска.")] = None,
    probability: Annotated[RiskRating | None, Query(description="Вероятность.")] = None,
    impact: Annotated[RiskRating | None, Query(description="Влияние.")] = None,
    risk_level: Annotated[RiskRating | None, Query(description="Вычисленный уровень.")] = None,
    owner_user_id: Annotated[
        int | None, Query(gt=0, description="Ответственный участник проекта.")
    ] = None,
    task_id: Annotated[int | None, Query(gt=0, description="Связанная задача.")] = None,
    search: Annotated[
        str | None, Query(max_length=255, description="Поиск по RISK-id, названию и описанию.")
    ] = None,
    active_only: Annotated[bool, Query(description="Исключить закрытые риски.")] = False,
) -> ProjectRiskFilters:
    """Собирает описанные query-параметры в единый контракт фильтров."""
    return ProjectRiskFilters(
        status=status,
        probability=probability,
        impact=impact,
        risk_level=risk_level,
        owner_user_id=owner_user_id,
        task_id=task_id,
        search=search,
        active_only=active_only,
    )


RiskFiltersDep = Annotated[ProjectRiskFilters, Depends(get_risk_filters)]


@router.get(
    "/projects/{project_id}/risks",
    response_model=ProjectRiskPageSchema,
    summary="Получить реестр рисков",
    description="Страница рисков проекта с фильтрами и общим числом совпадений.",
    operation_id="listProjectRisks",
    response_description="Страница реестра.",
    responses=ERROR_RESPONSES,
)
async def list_project_risks(
    project_id: ProjectId,
    principal: PrincipalDep,
    service: ProjectRiskServiceDep,
    filters: RiskFiltersDep,
    page: Annotated[int, Query(ge=1, description="Номер страницы от единицы.")] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, description="Число рисков на странице.")] = 25,
) -> ProjectRiskPageSchema:
    """Получает реестр доступного проекта.

    Args:
        project_id: Проект запроса.
        principal: Авторизованный пользователь.
        service: Сервис реестра.
        filters: Фильтры реестра.
        page: Номер страницы.
        page_size: Размер страницы.

    Returns:
        Страница и общее число совпадений.

    Raises:
        HTTPException: Ошибка доступа, валидации или чтения.
    """
    logger.info("🚀 Получение рисков проекта id=%s, страница=%s.", project_id, page)
    try:
        result = await service.list_risks(
            project_id=project_id,
            user_id=principal.user_id,
            filters=filters,
            page=page,
            page_size=page_size,
        )
        logger.info("✅ Получены риски проекта id=%s.", project_id)
        return result
    except RiskErrors as error:
        logger.exception("❌ Ошибка чтения реестра проекта id=%s.", project_id)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get(
    "/projects/{project_id}/risks/summary",
    response_model=ProjectRiskSummarySchema,
    summary="Получить аналитику рисков",
    description="Счётчики, причины внимания и все девять ячеек матрицы по всему отфильтрованному набору.",
    operation_id="getProjectRiskSummary",
    response_description="Сводка и матрица рисков.",
    responses=ERROR_RESPONSES,
)
async def get_project_risk_summary(
    project_id: ProjectId,
    principal: PrincipalDep,
    service: ProjectRiskServiceDep,
    filters: RiskFiltersDep,
    today: Annotated[
        date | None, Query(description="Локальная дата для контроля; по умолчанию дата сервера.")
    ] = None,
) -> ProjectRiskSummarySchema:
    """Получает сводку рисков независимо от пагинации.

    Args:
        project_id: Проект запроса.
        principal: Пользователь запроса.
        service: Сервис реестра.
        filters: Условия сводки.
        today: Локальная дата контроля.

    Returns:
        Матрица, счётчики и сигналы внимания.

    Raises:
        HTTPException: Ошибка доступа или агрегации.
    """
    logger.info("🚀 Аналитика рисков проекта id=%s.", project_id)
    try:
        result = await service.get_summary(
            project_id=project_id, user_id=principal.user_id, filters=filters, today=today
        )
        logger.info("✅ Получена аналитика рисков проекта id=%s.", project_id)
        return result
    except RiskErrors as error:
        logger.exception("❌ Ошибка аналитики рисков проекта id=%s.", project_id)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get(
    "/projects/{project_id}/risks/task-counts",
    response_model=dict[int, int],
    summary="Получить индикаторы рисков задач",
    description="Количество активных рисков сразу для всех связанных задач проекта.",
    operation_id="getProjectRiskTaskCounts",
    response_description="Отображение ID задачи в количество рисков.",
    responses=ERROR_RESPONSES,
)
async def get_project_risk_task_counts(
    project_id: ProjectId,
    principal: PrincipalDep,
    service: ProjectRiskServiceDep,
) -> dict[int, int]:
    """Получает индикаторы Kanban без запроса на каждую карточку.

    Args:
        project_id: Проект запроса.
        principal: Пользователь запроса.
        service: Сервис реестра.

    Returns:
        Счётчики по ID задач.

    Raises:
        HTTPException: Ошибка доступа или чтения.
    """
    logger.info("🚀 Индикаторы рисков задач проекта id=%s.", project_id)
    try:
        result = await service.get_task_counts(project_id=project_id, user_id=principal.user_id)
        logger.info("✅ Получены индикаторы рисков проекта id=%s.", project_id)
        return result
    except RiskErrors as error:
        logger.exception("❌ Ошибка индикаторов рисков проекта id=%s.", project_id)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get(
    "/projects/{project_id}/risks/{risk_id}",
    response_model=ProjectRiskSchema,
    summary="Получить риск",
    description="Возвращает риск только в текущем доступном проекте.",
    operation_id="getProjectRisk",
    response_description="Сохранённый риск.",
    responses=ERROR_RESPONSES,
)
async def get_project_risk(
    project_id: ProjectId,
    risk_id: RiskId,
    principal: PrincipalDep,
    service: ProjectRiskServiceDep,
) -> ProjectRiskSchema:
    """Получить риск в доступном проекте.

    Args:
        project_id: Проект запроса.
        risk_id: Идентификатор риска.
        principal: Пользователь запроса.
        service: Сервис реестра.

    Returns:
        Сохранённый риск с серверной оценкой.

    Raises:
        HTTPException: Ошибка доступа, данных или операции.
    """
    logger.info("🚀 Получить риск, проект id=%s.", project_id)
    try:
        result = await service.get_risk(
            project_id=project_id, user_id=principal.user_id, risk_id=risk_id
        )
        logger.info("✅ Получить риск: выполнено, проект id=%s.", project_id)
        return result
    except RiskErrors as error:
        logger.exception("❌ Получить риск: ошибка, проект id=%s.", project_id)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post(
    "/projects/{project_id}/risks",
    response_model=ProjectRiskSchema,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_write_scope)],
    summary="Создать риск",
    description="Регистрирует подтверждённый пользователем риск. Итоговый уровень рассчитывает backend.",
    operation_id="createProjectRisk",
    response_description="Сохранённый риск.",
    responses=WRITE_RESPONSES,
)
async def create_project_risk(
    project_id: ProjectId,
    principal: PrincipalDep,
    service: ProjectRiskServiceDep,
    data: ProjectRiskCreateSchema,
) -> ProjectRiskSchema:
    """Создать риск в доступном проекте.

    Args:
        project_id: Проект запроса.
        principal: Пользователь запроса.
        service: Сервис реестра.
        data: Валидированные поля запроса.

    Returns:
        Сохранённый риск с серверной оценкой.

    Raises:
        HTTPException: Ошибка доступа, данных или операции.
    """
    logger.info("🚀 Создать риск, проект id=%s.", project_id)
    try:
        result = await service.create_risk(
            project_id=project_id, user_id=principal.user_id, data=data
        )
        logger.info("✅ Создать риск: выполнено, проект id=%s.", project_id)
        return result
    except RiskErrors as error:
        logger.exception("❌ Создать риск: ошибка, проект id=%s.", project_id)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.patch(
    "/projects/{project_id}/risks/{risk_id}",
    response_model=ProjectRiskSchema,
    dependencies=[Depends(require_write_scope)],
    summary="Изменить риск",
    description="Изменяет поля риска и пересчитывает уровень по актуальным вероятности и влиянию.",
    operation_id="updateProjectRisk",
    response_description="Сохранённый риск.",
    responses=WRITE_RESPONSES,
)
async def update_project_risk(
    project_id: ProjectId,
    risk_id: RiskId,
    principal: PrincipalDep,
    service: ProjectRiskServiceDep,
    data: ProjectRiskUpdateSchema,
) -> ProjectRiskSchema:
    """Изменить риск в доступном проекте.

    Args:
        project_id: Проект запроса.
        risk_id: Идентификатор риска.
        principal: Пользователь запроса.
        service: Сервис реестра.
        data: Валидированные поля запроса.

    Returns:
        Сохранённый риск с серверной оценкой.

    Raises:
        HTTPException: Ошибка доступа, данных или операции.
    """
    logger.info("🚀 Изменить риск, проект id=%s.", project_id)
    try:
        result = await service.update_risk(
            project_id=project_id, user_id=principal.user_id, risk_id=risk_id, data=data
        )
        logger.info("✅ Изменить риск: выполнено, проект id=%s.", project_id)
        return result
    except RiskErrors as error:
        logger.exception("❌ Изменить риск: ошибка, проект id=%s.", project_id)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.delete(
    "/projects/{project_id}/risks/{risk_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_write_scope)],
    summary="Удалить риск",
    description="Удаляет риск и ставит удаление его semantic-представления в очередь.",
    operation_id="deleteProjectRisk",
    response_description="Риск удалён.",
    responses=WRITE_RESPONSES,
)
async def delete_project_risk(
    project_id: ProjectId,
    risk_id: RiskId,
    principal: PrincipalDep,
    service: ProjectRiskServiceDep,
) -> None:
    """Удалить риск в доступном проекте.

    Args:
        project_id: Проект запроса.
        risk_id: Идентификатор риска.
        principal: Пользователь запроса.
        service: Сервис реестра.

    Raises:
        HTTPException: Ошибка доступа, данных или операции.
    """
    logger.info("🚀 Удалить риск, проект id=%s.", project_id)
    try:
        await service.delete_risk(project_id=project_id, user_id=principal.user_id, risk_id=risk_id)
        logger.info("✅ Удалить риск: выполнено, проект id=%s.", project_id)
    except RiskErrors as error:
        logger.exception("❌ Удалить риск: ошибка, проект id=%s.", project_id)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

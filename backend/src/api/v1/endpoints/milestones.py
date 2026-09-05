import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from src.api.v1.responses import NOT_FOUND_RESPONSE, SERVER_ERROR_RESPONSE, VALIDATION_RESPONSE
from src.dependencies.access import require_project_access
from src.dependencies.auth import require_write_scope
from src.dependencies.services import MilestonesServiceDep
from src.exceptions.milestones import MilestonesServiceError
from src.exceptions.projects import ProjectsServiceError
from src.exceptions.wbs_nodes import WbsNodesServiceError
from src.schemas.milestones import MilestoneCreateSchema, MilestoneSchema, MilestoneUpdateSchema

router = APIRouter(tags=["milestones"])
logger = logging.getLogger(__name__)

MilestoneErrors = (MilestonesServiceError, ProjectsServiceError, WbsNodesServiceError)


@router.get(
    "/projects/{project_id}/milestones",
    dependencies=[Depends(require_project_access)],
    response_model=list[MilestoneSchema],
    responses={404: NOT_FOUND_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    summary="Получить вехи проекта",
)
async def list_milestones(
    project_id: Annotated[int, Path(gt=0)],
    service: MilestonesServiceDep,
) -> list[MilestoneSchema]:
    """Возвращает пользовательские вехи проекта."""
    try:
        return await service.list_milestones(project_id)
    except MilestoneErrors as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post(
    "/projects/{project_id}/milestones",
    dependencies=[Depends(require_write_scope), Depends(require_project_access)],
    response_model=MilestoneSchema,
    status_code=status.HTTP_201_CREATED,
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    summary="Создать веху проекта",
)
async def create_milestone(
    project_id: Annotated[int, Path(gt=0)],
    data: MilestoneCreateSchema,
    service: MilestonesServiceDep,
) -> MilestoneSchema:
    """Создаёт пользовательскую веху проекта."""
    try:
        return await service.create_milestone(project_id, data.model_dump())
    except MilestoneErrors as error:
        logger.exception("❌ Ошибка создания вехи проекта id=%s.", project_id)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.patch(
    "/projects/{project_id}/milestones/{milestone_id}",
    dependencies=[Depends(require_write_scope), Depends(require_project_access)],
    response_model=MilestoneSchema,
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    summary="Изменить веху проекта",
)
async def update_milestone(
    project_id: Annotated[int, Path(gt=0)],
    milestone_id: Annotated[int, Path(gt=0)],
    data: MilestoneUpdateSchema,
    service: MilestonesServiceDep,
) -> MilestoneSchema:
    """Изменяет пользовательскую веху проекта."""
    try:
        return await service.update_milestone(
            project_id,
            milestone_id,
            data.model_dump(exclude_unset=True),
        )
    except MilestoneErrors as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.delete(
    "/projects/{project_id}/milestones/{milestone_id}",
    dependencies=[Depends(require_write_scope), Depends(require_project_access)],
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: NOT_FOUND_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    summary="Удалить веху проекта",
)
async def delete_milestone(
    project_id: Annotated[int, Path(gt=0)],
    milestone_id: Annotated[int, Path(gt=0)],
    service: MilestonesServiceDep,
) -> None:
    """Удаляет пользовательскую веху проекта."""
    try:
        await service.delete_milestone(project_id, milestone_id)
    except MilestoneErrors as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

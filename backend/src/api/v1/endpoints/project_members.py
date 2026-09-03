import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status

from src.api.v1.responses import (
    CONFLICT_RESPONSE,
    NOT_FOUND_RESPONSE,
    SERVER_ERROR_RESPONSE,
    VALIDATION_RESPONSE,
)
from src.dependencies.access import AccessibleProjectDep, OwnedProjectDep
from src.dependencies.services import ProjectMembersServiceDep
from src.exceptions.projects import ProjectsServiceError
from src.schemas.project_members import ProjectMemberCreateSchema, ProjectMemberSchema

router = APIRouter(tags=["project-members"])
logger = logging.getLogger(__name__)


@router.get(
    path="/projects/{project_id}/members",
    status_code=status.HTTP_200_OK,
    summary="Получить команду проекта",
    description="Возвращает только пользователей, уже входящих в команду проекта.",
    operation_id="getProjectMembers",
    responses={404: NOT_FOUND_RESPONSE, 422: VALIDATION_RESPONSE, 500: SERVER_ERROR_RESPONSE},
    response_model=list[ProjectMemberSchema],
)
async def get_project_members(
    project: AccessibleProjectDep,
    service: ProjectMembersServiceDep,
) -> list[ProjectMemberSchema]:
    """Возвращает команду доступного пользователю проекта."""
    logger.info("🚀 Запрос GET /projects/%s/members.", project.id)
    try:
        return await service.get_member_list(project_id=project.id)
    except ProjectsServiceError as error:
        logger.exception("❌ Ошибка GET /projects/%s/members.", project.id)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post(
    path="/projects/{project_id}/members",
    status_code=status.HTTP_201_CREATED,
    summary="Добавить участника проекта",
    description="Сразу добавляет пользователя по точному логину без поиска и приглашения.",
    operation_id="addProjectMember",
    responses={
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
    response_model=ProjectMemberSchema,
)
async def add_project_member(
    project: OwnedProjectDep,
    data: ProjectMemberCreateSchema,
    service: ProjectMembersServiceDep,
) -> ProjectMemberSchema:
    """Добавляет пользователя в команду; операция доступна только владельцу."""
    logger.info("🚀 Запрос POST /projects/%s/members.", project.id)
    try:
        return await service.add_member(project_id=project.id, username=data.username)
    except ProjectsServiceError as error:
        logger.exception("❌ Ошибка POST /projects/%s/members.", project.id)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.delete(
    path="/projects/{project_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить участника проекта",
    description="Удаляет участника и его ролевые назначения. Владельца удалить нельзя.",
    operation_id="removeProjectMember",
    responses={
        404: NOT_FOUND_RESPONSE,
        409: CONFLICT_RESPONSE,
        422: VALIDATION_RESPONSE,
        500: SERVER_ERROR_RESPONSE,
    },
)
async def remove_project_member(
    project: OwnedProjectDep,
    user_id: Annotated[int, Path(gt=0, description="Идентификатор пользователя.")],
    service: ProjectMembersServiceDep,
) -> None:
    """Удаляет участника из команды; операция доступна только владельцу."""
    logger.info("🚀 Запрос DELETE /projects/%s/members/%s.", project.id, user_id)
    try:
        await service.remove_member(project_id=project.id, user_id=user_id)
    except ProjectsServiceError as error:
        logger.exception("❌ Ошибка DELETE /projects/%s/members/%s.", project.id, user_id)
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

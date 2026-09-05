"""HTTP-адаптер проверки доступа к объектам проекта.

Слой достаёт идентификатор из пути, вызывает `AccessService` и переводит его
доменную ошибку в HTTP-ответ. Ни правил доступа, ни обращений к репозиториям
здесь нет: они принадлежат сервису и одинаковы для HTTP и MCP.

Чужой объект отдаёт 404, а не 403: пользователь не должен узнавать, что
объект с таким идентификатором вообще существует.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Path

from src.dependencies.auth import PrincipalDep
from src.dependencies.services import AccessServiceDep
from src.exceptions.access import AccessServiceError
from src.services.access import AccessGrant

ProjectIdPath = Annotated[int, Path(gt=0, description="Идентификатор проекта.")]
TaskIdPath = Annotated[int, Path(gt=0, description="Идентификатор задачи.")]
StageIdPath = Annotated[int, Path(gt=0, description="Идентификатор стадии.")]
DocumentIdPath = Annotated[int, Path(gt=0, description="Идентификатор документа.")]
CommentIdPath = Annotated[int, Path(gt=0, description="Идентификатор комментария.")]
LinkIdPath = Annotated[int, Path(gt=0, description="Идентификатор связи.")]


def _as_http_error(error: AccessServiceError) -> HTTPException:
    """Переводит доменную ошибку доступа в транспортный ответ."""
    return HTTPException(status_code=error.status_code, detail=error.detail)


async def require_project_access(
    project_id: ProjectIdPath,
    principal: PrincipalDep,
    service: AccessServiceDep,
) -> AccessGrant:
    """Разрешает работу с проектом, в котором состоит пользователь."""
    try:
        return await service.ensure_project_access(
            project_id=project_id,
            user_id=principal.user_id,
        )
    except AccessServiceError as error:
        raise _as_http_error(error) from error


async def require_project_ownership(
    project_id: ProjectIdPath,
    principal: PrincipalDep,
    service: AccessServiceDep,
) -> AccessGrant:
    """Разрешает действие, доступное только владельцу проекта."""
    try:
        return await service.ensure_project_ownership(
            project_id=project_id,
            user_id=principal.user_id,
        )
    except AccessServiceError as error:
        raise _as_http_error(error) from error


async def require_task_access(
    task_id: TaskIdPath,
    principal: PrincipalDep,
    service: AccessServiceDep,
) -> AccessGrant:
    """Разрешает работу с задачей из доступного пользователю проекта."""
    try:
        return await service.ensure_task_access(task_id=task_id, user_id=principal.user_id)
    except AccessServiceError as error:
        raise _as_http_error(error) from error


async def require_stage_access(
    stage_id: StageIdPath,
    principal: PrincipalDep,
    service: AccessServiceDep,
) -> AccessGrant:
    """Разрешает работу со стадией из доступного пользователю проекта."""
    try:
        return await service.ensure_stage_access(stage_id=stage_id, user_id=principal.user_id)
    except AccessServiceError as error:
        raise _as_http_error(error) from error


async def require_document_access(
    document_id: DocumentIdPath,
    principal: PrincipalDep,
    service: AccessServiceDep,
) -> AccessGrant:
    """Разрешает работу с документом из доступного пользователю проекта."""
    try:
        return await service.ensure_document_access(
            document_id=document_id,
            user_id=principal.user_id,
        )
    except AccessServiceError as error:
        raise _as_http_error(error) from error


async def require_comment_access(
    comment_id: CommentIdPath,
    principal: PrincipalDep,
    service: AccessServiceDep,
) -> AccessGrant:
    """Разрешает работу с комментарием из доступного пользователю проекта."""
    try:
        return await service.ensure_comment_access(
            comment_id=comment_id,
            user_id=principal.user_id,
        )
    except AccessServiceError as error:
        raise _as_http_error(error) from error


async def require_link_access(
    link_id: LinkIdPath,
    principal: PrincipalDep,
    service: AccessServiceDep,
) -> AccessGrant:
    """Разрешает работу со связью документа из доступного проекта."""
    try:
        return await service.ensure_link_access(link_id=link_id, user_id=principal.user_id)
    except AccessServiceError as error:
        raise _as_http_error(error) from error


ProjectAccessDep = Annotated[AccessGrant, Depends(require_project_access)]
ProjectOwnershipDep = Annotated[AccessGrant, Depends(require_project_ownership)]
TaskAccessDep = Annotated[AccessGrant, Depends(require_task_access)]
StageAccessDep = Annotated[AccessGrant, Depends(require_stage_access)]
DocumentAccessDep = Annotated[AccessGrant, Depends(require_document_access)]
CommentAccessDep = Annotated[AccessGrant, Depends(require_comment_access)]
LinkAccessDep = Annotated[AccessGrant, Depends(require_link_access)]

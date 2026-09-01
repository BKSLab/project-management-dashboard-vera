"""Разрешение доступа к объектам проекта.

Проверка вынесена в Depends-слой по правилу из `FASTAPI_PATTERNS.md`: это
единственное место, где зависимость сама поднимает `HTTPException`, потому
что над ней нет эндпоинта, который сделал бы это за неё.

Задачи, стадии, документы и разделы ИСР принадлежат проекту, поэтому любой
доступ сводится к вопросу «состоит ли пользователь в проекте объекта».
Чужой объект отдаёт 404, а не 403: пользователь не должен узнавать, что
объект с таким идентификатором вообще существует.
"""

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, Path, status

from src.db.models.document_links import DocumentLink
from src.db.models.documents import Document
from src.db.models.project_members import ProjectRole
from src.db.models.project_stages import ProjectStage
from src.db.models.projects import Project
from src.db.models.task_comments import TaskComment
from src.db.models.tasks import Task
from src.dependencies.auth import CurrentUserDep
from src.dependencies.repositories import (
    DocumentLinksRepositoryDep,
    DocumentsRepositoryDep,
    ProjectMembersRepositoryDep,
    ProjectsRepositoryDep,
    ProjectStagesRepositoryDep,
    TaskCommentsRepositoryDep,
    TasksRepositoryDep,
)
from src.exceptions.base import ApplicationError

logger = logging.getLogger(__name__)

NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Объект не найден.",
)
OWNER_REQUIRED = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Действие доступно только владельцу проекта.",
)


async def _authorize(
    members_repository: ProjectMembersRepositoryDep,
    project_id: int,
    user_id: int,
    require_owner: bool = False,
) -> None:
    """Проверяет участие пользователя в проекте."""
    try:
        membership = await members_repository.get(project_id=project_id, user_id=user_id)
    except ApplicationError as error:
        logger.error("❌ Ошибка проверки доступа к проекту id=%s.", project_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Ошибка проверки доступа.") from error

    if membership is None:
        logger.info(
            "ℹ️ Пользователь id=%s обратился к недоступному проекту id=%s.",
            user_id,
            project_id,
        )
        raise NOT_FOUND
    if require_owner and membership.role is not ProjectRole.OWNER:
        raise OWNER_REQUIRED


async def get_accessible_project(
    project_id: Annotated[int, Path(gt=0, description="Идентификатор проекта.")],
    user: CurrentUserDep,
    members_repository: ProjectMembersRepositoryDep,
    projects_repository: ProjectsRepositoryDep,
) -> Project:
    """Возвращает проект, к которому у пользователя есть доступ."""
    await _authorize(members_repository, project_id, user.id)
    project = await projects_repository.get_by_id(project_id=project_id)
    if project is None:
        raise NOT_FOUND
    return project


async def get_owned_project(
    project_id: Annotated[int, Path(gt=0, description="Идентификатор проекта.")],
    user: CurrentUserDep,
    members_repository: ProjectMembersRepositoryDep,
    projects_repository: ProjectsRepositoryDep,
) -> Project:
    """Возвращает проект, которым пользователь владеет."""
    await _authorize(members_repository, project_id, user.id, require_owner=True)
    project = await projects_repository.get_by_id(project_id=project_id)
    if project is None:
        raise NOT_FOUND
    return project


async def get_accessible_task(
    task_id: Annotated[int, Path(gt=0, description="Идентификатор задачи.")],
    user: CurrentUserDep,
    members_repository: ProjectMembersRepositoryDep,
    tasks_repository: TasksRepositoryDep,
) -> Task:
    """Возвращает задачу из доступного пользователю проекта."""
    task = await tasks_repository.get_by_id(task_id=task_id)
    if task is None:
        raise NOT_FOUND
    await _authorize(members_repository, task.project_id, user.id)
    return task


async def get_accessible_stage(
    stage_id: Annotated[int, Path(gt=0, description="Идентификатор стадии.")],
    user: CurrentUserDep,
    members_repository: ProjectMembersRepositoryDep,
    stages_repository: ProjectStagesRepositoryDep,
) -> ProjectStage:
    """Возвращает стадию из доступного пользователю проекта."""
    stage = await stages_repository.get_by_id(stage_id=stage_id)
    if stage is None:
        raise NOT_FOUND
    await _authorize(members_repository, stage.project_id, user.id)
    return stage


async def get_accessible_document(
    document_id: Annotated[int, Path(gt=0, description="Идентификатор документа.")],
    user: CurrentUserDep,
    members_repository: ProjectMembersRepositoryDep,
    documents_repository: DocumentsRepositoryDep,
) -> Document:
    """Возвращает документ из доступного пользователю проекта."""
    document = await documents_repository.get_by_id(document_id=document_id)
    if document is None:
        raise NOT_FOUND
    await _authorize(members_repository, document.project_id, user.id)
    return document


async def get_accessible_comment(
    comment_id: Annotated[int, Path(gt=0, description="Идентификатор комментария.")],
    user: CurrentUserDep,
    members_repository: ProjectMembersRepositoryDep,
    comments_repository: TaskCommentsRepositoryDep,
    tasks_repository: TasksRepositoryDep,
) -> TaskComment:
    """Возвращает комментарий из доступного пользователю проекта."""
    comment = await comments_repository.get_by_id(comment_id=comment_id)
    if comment is None:
        raise NOT_FOUND
    task = await tasks_repository.get_by_id(task_id=comment.task_id)
    if task is None:
        raise NOT_FOUND
    await _authorize(members_repository, task.project_id, user.id)
    return comment


async def get_accessible_link(
    link_id: Annotated[int, Path(gt=0, description="Идентификатор связи.")],
    user: CurrentUserDep,
    members_repository: ProjectMembersRepositoryDep,
    links_repository: DocumentLinksRepositoryDep,
    documents_repository: DocumentsRepositoryDep,
) -> DocumentLink:
    """Возвращает связь документа из доступного пользователю проекта."""
    link = await links_repository.get_by_id(link_id=link_id)
    if link is None:
        raise NOT_FOUND
    document = await documents_repository.get_by_id(document_id=link.document_id)
    if document is None:
        raise NOT_FOUND
    await _authorize(members_repository, document.project_id, user.id)
    return link


AccessibleProjectDep = Annotated[Project, Depends(get_accessible_project)]
OwnedProjectDep = Annotated[Project, Depends(get_owned_project)]
AccessibleTaskDep = Annotated[Task, Depends(get_accessible_task)]
AccessibleStageDep = Annotated[ProjectStage, Depends(get_accessible_stage)]
AccessibleDocumentDep = Annotated[Document, Depends(get_accessible_document)]

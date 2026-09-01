from typing import Annotated

from fastapi import Depends

from src.dependencies.repositories import (
    DocumentLinksRepositoryDep,
    DocumentsRepositoryDep,
    ProjectMembersRepositoryDep,
    ProjectsRepositoryDep,
    ProjectStagesRepositoryDep,
    TaskActivityRepositoryDep,
    TaskAttachmentsRepositoryDep,
    TaskCommentsRepositoryDep,
    TasksRepositoryDep,
    UsersRepositoryDep,
    WbsNodesRepositoryDep,
)
from src.dependencies.storage import AvatarStorageDep, TaskAttachmentStorageDep
from src.services.auth import AuthService
from src.services.dashboard import DashboardService
from src.services.document_links import DocumentLinksService
from src.services.documents import DocumentsService
from src.services.project_stages import ProjectStagesService
from src.services.projects import ProjectsService
from src.services.task_activity import TaskActivityService
from src.services.task_attachments import TaskAttachmentsService
from src.services.task_comments import TaskCommentsService
from src.services.tasks import TasksService
from src.services.users import UsersService
from src.services.wbs_nodes import WbsNodesService


def get_auth_service(users_repository: UsersRepositoryDep) -> AuthService:
    """Создаёт сервис регистрации и входа."""
    return AuthService(users_repository=users_repository)


def get_users_service(
    users_repository: UsersRepositoryDep,
    avatar_storage: AvatarStorageDep,
) -> UsersService:
    """Создаёт сервис профиля пользователя."""
    return UsersService(users_repository=users_repository, avatar_storage=avatar_storage)


def get_projects_service(
    projects_repository: ProjectsRepositoryDep,
    members_repository: ProjectMembersRepositoryDep,
    stages_repository: ProjectStagesRepositoryDep,
    tasks_repository: TasksRepositoryDep,
    storage: TaskAttachmentStorageDep,
) -> ProjectsService:
    """Создаёт сервис проектов."""
    return ProjectsService(
        projects_repository=projects_repository,
        members_repository=members_repository,
        stages_repository=stages_repository,
        tasks_repository=tasks_repository,
        attachment_storage=storage,
    )


def get_project_stages_service(
    stages_repository: ProjectStagesRepositoryDep,
    projects_repository: ProjectsRepositoryDep,
    tasks_repository: TasksRepositoryDep,
) -> ProjectStagesService:
    """Создаёт сервис стадий проекта."""
    return ProjectStagesService(
        stages_repository=stages_repository,
        projects_repository=projects_repository,
        tasks_repository=tasks_repository,
    )


def get_tasks_service(
    tasks_repository: TasksRepositoryDep,
    projects_repository: ProjectsRepositoryDep,
    stages_repository: ProjectStagesRepositoryDep,
    comments_repository: TaskCommentsRepositoryDep,
    activity_repository: TaskActivityRepositoryDep,
    wbs_nodes_repository: WbsNodesRepositoryDep,
    storage: TaskAttachmentStorageDep,
) -> TasksService:
    """Создаёт сервис задач со всеми доменными зависимостями."""
    return TasksService(
        tasks_repository=tasks_repository,
        projects_repository=projects_repository,
        stages_repository=stages_repository,
        comments_repository=comments_repository,
        activity_repository=activity_repository,
        wbs_nodes_repository=wbs_nodes_repository,
        attachment_storage=storage,
    )


def get_wbs_nodes_service(
    wbs_nodes_repository: WbsNodesRepositoryDep,
    projects_repository: ProjectsRepositoryDep,
    stages_repository: ProjectStagesRepositoryDep,
    tasks_repository: TasksRepositoryDep,
    activity_repository: TaskActivityRepositoryDep,
) -> WbsNodesService:
    """Создаёт сервис структуры ИСР."""
    return WbsNodesService(
        wbs_nodes_repository=wbs_nodes_repository,
        projects_repository=projects_repository,
        stages_repository=stages_repository,
        tasks_repository=tasks_repository,
        activity_repository=activity_repository,
    )


def get_dashboard_service(
    projects_repository: ProjectsRepositoryDep,
    members_repository: ProjectMembersRepositoryDep,
    stages_repository: ProjectStagesRepositoryDep,
    tasks_repository: TasksRepositoryDep,
) -> DashboardService:
    """Создаёт сервис общей сводки по проектам."""
    return DashboardService(
        projects_repository=projects_repository,
        members_repository=members_repository,
        stages_repository=stages_repository,
        tasks_repository=tasks_repository,
    )


def get_documents_service(
    documents_repository: DocumentsRepositoryDep,
    projects_repository: ProjectsRepositoryDep,
) -> DocumentsService:
    """Создаёт сервис документов проекта."""
    return DocumentsService(
        documents_repository=documents_repository,
        projects_repository=projects_repository,
    )


def get_document_links_service(
    document_links_repository: DocumentLinksRepositoryDep,
    documents_repository: DocumentsRepositoryDep,
    tasks_repository: TasksRepositoryDep,
    projects_repository: ProjectsRepositoryDep,
    members_repository: ProjectMembersRepositoryDep,
) -> DocumentLinksService:
    """Создаёт сервис связей документов."""
    return DocumentLinksService(
        document_links_repository=document_links_repository,
        documents_repository=documents_repository,
        tasks_repository=tasks_repository,
        projects_repository=projects_repository,
        members_repository=members_repository,
    )


def get_task_comments_service(
    comments_repository: TaskCommentsRepositoryDep,
    tasks_repository: TasksRepositoryDep,
    activity_repository: TaskActivityRepositoryDep,
) -> TaskCommentsService:
    """Создаёт сервис комментариев задач."""
    return TaskCommentsService(
        comments_repository=comments_repository,
        tasks_repository=tasks_repository,
        activity_repository=activity_repository,
    )


def get_task_activity_service(
    activity_repository: TaskActivityRepositoryDep,
    tasks_repository: TasksRepositoryDep,
) -> TaskActivityService:
    """Создаёт сервис истории задач."""
    return TaskActivityService(
        activity_repository=activity_repository,
        tasks_repository=tasks_repository,
    )


def get_task_attachments_service(
    attachments_repository: TaskAttachmentsRepositoryDep,
    tasks_repository: TasksRepositoryDep,
    storage: TaskAttachmentStorageDep,
) -> TaskAttachmentsService:
    """Создаёт сервис файлов задач."""
    return TaskAttachmentsService(
        attachments_repository=attachments_repository,
        tasks_repository=tasks_repository,
        storage=storage,
    )


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
UsersServiceDep = Annotated[UsersService, Depends(get_users_service)]
ProjectsServiceDep = Annotated[ProjectsService, Depends(get_projects_service)]
ProjectStagesServiceDep = Annotated[
    ProjectStagesService,
    Depends(get_project_stages_service),
]
TasksServiceDep = Annotated[TasksService, Depends(get_tasks_service)]
WbsNodesServiceDep = Annotated[WbsNodesService, Depends(get_wbs_nodes_service)]
DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]
DocumentsServiceDep = Annotated[DocumentsService, Depends(get_documents_service)]
DocumentLinksServiceDep = Annotated[
    DocumentLinksService,
    Depends(get_document_links_service),
]
TaskCommentsServiceDep = Annotated[
    TaskCommentsService,
    Depends(get_task_comments_service),
]
TaskActivityServiceDep = Annotated[
    TaskActivityService,
    Depends(get_task_activity_service),
]
TaskAttachmentsServiceDep = Annotated[
    TaskAttachmentsService,
    Depends(get_task_attachments_service),
]

from typing import Annotated

from fastapi import Depends

from src.core.settings import get_settings
from src.dependencies.repositories import (
    ApiTokensRepositoryDep,
    DocumentLinksRepositoryDep,
    DocumentsRepositoryDep,
    KnowledgeIndexJobsRepositoryDep,
    MilestonesRepositoryDep,
    ProjectMembersRepositoryDep,
    ProjectsRepositoryDep,
    ProjectStagesRepositoryDep,
    TaskActivityRepositoryDep,
    TaskAttachmentsRepositoryDep,
    TaskCommentsRepositoryDep,
    TaskDependenciesRepositoryDep,
    TasksRepositoryDep,
    UnitOfWorkDep,
    UsersRepositoryDep,
    WbsNodesRepositoryDep,
)
from src.dependencies.storage import AvatarStorageDep, TaskAttachmentStorageDep
from src.services.api_tokens import ApiTokensService
from src.services.auth import AuthService
from src.services.calendar import CalendarService
from src.services.calendar_scenarios import CalendarScenarioService
from src.services.dashboard import DashboardService
from src.services.document_links import DocumentLinksService
from src.services.documents import DocumentsService
from src.services.knowledge_events import KnowledgeEvents
from src.services.milestones import MilestonesService
from src.services.project_agent import ProjectAgentService
from src.services.project_stages import ProjectStagesService
from src.services.projects import ProjectsService
from src.services.task_activity import TaskActivityService
from src.services.task_attachments import TaskAttachmentsService
from src.services.task_comments import TaskCommentsService
from src.services.task_dependencies import TaskDependenciesService
from src.services.tasks import TasksService
from src.services.users import UsersService
from src.services.wbs_nodes import WbsNodesService


def get_knowledge_events(
    jobs_repository: KnowledgeIndexJobsRepositoryDep,
) -> KnowledgeEvents:
    """Создаёт безопасный publisher изменений для фонового индексатора."""
    return KnowledgeEvents(
        repository=jobs_repository,
        enabled=get_settings().knowledge.knowledge_enabled,
    )


KnowledgeEventsDep = Annotated[KnowledgeEvents, Depends(get_knowledge_events)]


def get_auth_service(users_repository: UsersRepositoryDep) -> AuthService:
    """Создаёт сервис регистрации и входа."""
    return AuthService(users_repository=users_repository)


def get_api_tokens_service(tokens_repository: ApiTokensRepositoryDep) -> ApiTokensService:
    """Создаёт сервис токенов доступа в рамках сессии запроса."""
    return ApiTokensService(tokens_repository=tokens_repository)


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
    knowledge_events: KnowledgeEventsDep,
    unit_of_work: UnitOfWorkDep,
) -> ProjectsService:
    """Создаёт сервис проектов."""
    return ProjectsService(
        projects_repository=projects_repository,
        members_repository=members_repository,
        stages_repository=stages_repository,
        tasks_repository=tasks_repository,
        attachment_storage=storage,
        knowledge_events=knowledge_events,
        unit_of_work=unit_of_work,
    )


def get_project_stages_service(
    stages_repository: ProjectStagesRepositoryDep,
    projects_repository: ProjectsRepositoryDep,
    tasks_repository: TasksRepositoryDep,
    unit_of_work: UnitOfWorkDep,
) -> ProjectStagesService:
    """Создаёт сервис стадий проекта."""
    return ProjectStagesService(
        stages_repository=stages_repository,
        projects_repository=projects_repository,
        tasks_repository=tasks_repository,
        unit_of_work=unit_of_work,
    )


def get_tasks_service(
    tasks_repository: TasksRepositoryDep,
    projects_repository: ProjectsRepositoryDep,
    stages_repository: ProjectStagesRepositoryDep,
    comments_repository: TaskCommentsRepositoryDep,
    activity_repository: TaskActivityRepositoryDep,
    wbs_nodes_repository: WbsNodesRepositoryDep,
    storage: TaskAttachmentStorageDep,
    knowledge_events: KnowledgeEventsDep,
    unit_of_work: UnitOfWorkDep,
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
        knowledge_events=knowledge_events,
        unit_of_work=unit_of_work,
    )


def get_wbs_nodes_service(
    wbs_nodes_repository: WbsNodesRepositoryDep,
    projects_repository: ProjectsRepositoryDep,
    stages_repository: ProjectStagesRepositoryDep,
    tasks_repository: TasksRepositoryDep,
    activity_repository: TaskActivityRepositoryDep,
    knowledge_events: KnowledgeEventsDep,
    unit_of_work: UnitOfWorkDep,
) -> WbsNodesService:
    """Создаёт сервис структуры ИСР."""
    return WbsNodesService(
        wbs_nodes_repository=wbs_nodes_repository,
        projects_repository=projects_repository,
        stages_repository=stages_repository,
        tasks_repository=tasks_repository,
        activity_repository=activity_repository,
        knowledge_events=knowledge_events,
        unit_of_work=unit_of_work,
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


def get_calendar_service(
    projects_repository: ProjectsRepositoryDep,
    tasks_repository: TasksRepositoryDep,
    stages_repository: ProjectStagesRepositoryDep,
    wbs_nodes_repository: WbsNodesRepositoryDep,
    activity_repository: TaskActivityRepositoryDep,
    milestones_repository: MilestonesRepositoryDep,
    dependencies_repository: TaskDependenciesRepositoryDep,
) -> CalendarService:
    """Создаёт сервис календаря проекта."""
    return CalendarService(
        projects_repository=projects_repository,
        tasks_repository=tasks_repository,
        stages_repository=stages_repository,
        wbs_nodes_repository=wbs_nodes_repository,
        activity_repository=activity_repository,
        milestones_repository=milestones_repository,
        dependencies_repository=dependencies_repository,
    )


def get_calendar_scenario_service(
    projects_repository: ProjectsRepositoryDep,
    tasks_repository: TasksRepositoryDep,
    dependencies_repository: TaskDependenciesRepositoryDep,
    milestones_repository: MilestonesRepositoryDep,
    activity_repository: TaskActivityRepositoryDep,
    unit_of_work: UnitOfWorkDep,
) -> CalendarScenarioService:
    """Создаёт сервис preview и применения календарных сценариев."""
    return CalendarScenarioService(
        projects_repository=projects_repository,
        tasks_repository=tasks_repository,
        dependencies_repository=dependencies_repository,
        milestones_repository=milestones_repository,
        activity_repository=activity_repository,
        unit_of_work=unit_of_work,
    )


def get_milestones_service(
    milestones_repository: MilestonesRepositoryDep,
    projects_repository: ProjectsRepositoryDep,
    wbs_nodes_repository: WbsNodesRepositoryDep,
    unit_of_work: UnitOfWorkDep,
    knowledge_events: KnowledgeEventsDep,
) -> MilestonesService:
    """Создаёт сервис проектных вех."""
    return MilestonesService(
        milestones_repository=milestones_repository,
        projects_repository=projects_repository,
        wbs_nodes_repository=wbs_nodes_repository,
        unit_of_work=unit_of_work,
        knowledge_events=knowledge_events,
    )


def get_task_dependencies_service(
    dependencies_repository: TaskDependenciesRepositoryDep,
    projects_repository: ProjectsRepositoryDep,
    tasks_repository: TasksRepositoryDep,
    unit_of_work: UnitOfWorkDep,
) -> TaskDependenciesService:
    """Создаёт сервис графа зависимостей проекта."""
    return TaskDependenciesService(
        dependencies_repository=dependencies_repository,
        projects_repository=projects_repository,
        tasks_repository=tasks_repository,
        unit_of_work=unit_of_work,
    )


def get_documents_service(
    documents_repository: DocumentsRepositoryDep,
    projects_repository: ProjectsRepositoryDep,
    knowledge_events: KnowledgeEventsDep,
    unit_of_work: UnitOfWorkDep,
) -> DocumentsService:
    """Создаёт сервис документов проекта."""
    return DocumentsService(
        documents_repository=documents_repository,
        projects_repository=projects_repository,
        knowledge_events=knowledge_events,
        unit_of_work=unit_of_work,
    )


def get_project_agent_service(
    stages_repository: ProjectStagesRepositoryDep,
    tasks_repository: TasksRepositoryDep,
    wbs_nodes_repository: WbsNodesRepositoryDep,
    documents_repository: DocumentsRepositoryDep,
    activity_repository: TaskActivityRepositoryDep,
    jobs_repository: KnowledgeIndexJobsRepositoryDep,
    unit_of_work: UnitOfWorkDep,
    milestones_repository: MilestonesRepositoryDep,
    calendar_service: Annotated[CalendarService, Depends(get_calendar_service)],
    scenario_service: Annotated[
        CalendarScenarioService,
        Depends(get_calendar_scenario_service),
    ],
) -> ProjectAgentService:
    """Создаёт Project Agent в рамках сессии доступного проекта."""
    return ProjectAgentService(
        stages_repository=stages_repository,
        tasks_repository=tasks_repository,
        wbs_nodes_repository=wbs_nodes_repository,
        documents_repository=documents_repository,
        activity_repository=activity_repository,
        jobs_repository=jobs_repository,
        unit_of_work=unit_of_work,
        milestones_repository=milestones_repository,
        calendar_service=calendar_service,
        scenario_service=scenario_service,
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
    knowledge_events: KnowledgeEventsDep,
    unit_of_work: UnitOfWorkDep,
) -> TaskCommentsService:
    """Создаёт сервис комментариев задач."""
    return TaskCommentsService(
        comments_repository=comments_repository,
        tasks_repository=tasks_repository,
        activity_repository=activity_repository,
        knowledge_events=knowledge_events,
        unit_of_work=unit_of_work,
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
    knowledge_events: KnowledgeEventsDep,
    unit_of_work: UnitOfWorkDep,
) -> TaskAttachmentsService:
    """Создаёт сервис файлов задач."""
    return TaskAttachmentsService(
        attachments_repository=attachments_repository,
        tasks_repository=tasks_repository,
        storage=storage,
        knowledge_events=knowledge_events,
        unit_of_work=unit_of_work,
    )


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
UsersServiceDep = Annotated[UsersService, Depends(get_users_service)]
ApiTokensServiceDep = Annotated[ApiTokensService, Depends(get_api_tokens_service)]
ProjectsServiceDep = Annotated[ProjectsService, Depends(get_projects_service)]
ProjectStagesServiceDep = Annotated[
    ProjectStagesService,
    Depends(get_project_stages_service),
]
TasksServiceDep = Annotated[TasksService, Depends(get_tasks_service)]
WbsNodesServiceDep = Annotated[WbsNodesService, Depends(get_wbs_nodes_service)]
DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]
CalendarServiceDep = Annotated[CalendarService, Depends(get_calendar_service)]
CalendarScenarioServiceDep = Annotated[
    CalendarScenarioService,
    Depends(get_calendar_scenario_service),
]
MilestonesServiceDep = Annotated[MilestonesService, Depends(get_milestones_service)]
TaskDependenciesServiceDep = Annotated[
    TaskDependenciesService,
    Depends(get_task_dependencies_service),
]
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
ProjectAgentServiceDep = Annotated[ProjectAgentService, Depends(get_project_agent_service)]

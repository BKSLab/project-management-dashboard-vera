"""Сборка сервисов приложения для графа зависимостей запроса.

Каждая фабрика объявлена вместе со своим `...Dep` alias, а вышестоящие
фабрики используют именно alias, а не повторяют `Annotated[..., Depends(...)]`:
иначе один и тот же сервис пришлось бы описывать в нескольких местах и
подменять в тестах тоже в нескольких местах.

Настройки читаются здесь, на уровне сборки графа. Сервис получает готовые
значения и клиентов через конструктор и о конфигурации приложения не знает.
"""

from typing import Annotated

from fastapi import Depends

from src.core.settings import Settings
from src.dependencies.clients import (
    EmbeddingClientDep,
    LlmClientDep,
    QdrantClientDep,
    VisionCapabilityDep,
)
from src.dependencies.repositories import (
    AnalyticsReportsRepositoryDep,
    ApiTokensRepositoryDep,
    DocumentLinksRepositoryDep,
    DocumentsRepositoryDep,
    KnowledgeIndexJobsRepositoryDep,
    MilestonesRepositoryDep,
    ProjectMembersRepositoryDep,
    ProjectsRepositoryDep,
    ProjectStagesRepositoryDep,
    ProjectStickersRepositoryDep,
    TaskActivityRepositoryDep,
    TaskAttachmentsRepositoryDep,
    TaskCommentsRepositoryDep,
    TaskDependenciesRepositoryDep,
    TaskParticipantsRepositoryDep,
    TasksRepositoryDep,
    UnitOfWorkDep,
    UsersRepositoryDep,
    WbsNodesRepositoryDep,
)
from src.dependencies.settings import SettingsDep
from src.dependencies.storage import AvatarStorageDep, TaskAttachmentStorageDep
from src.services.access import AccessService
from src.services.analytics import AnalyticsService
from src.services.api_tokens import ApiTokensService
from src.services.auth import AuthService
from src.services.calendar import CalendarService
from src.services.calendar_scenarios import CalendarScenarioService
from src.services.dashboard import DashboardService
from src.services.document_links import DocumentLinksService
from src.services.documents import DocumentsService
from src.services.knowledge_events import KnowledgeEvents
from src.services.milestones import MilestonesService
from src.services.project_agent import ProjectAgentConfig, ProjectAgentService
from src.services.project_members import ProjectMembersService
from src.services.project_stages import ProjectStagesService
from src.services.project_stickers import ProjectStickersService
from src.services.projects import ProjectsService
from src.services.task_activity import TaskActivityService
from src.services.task_attachments import TaskAttachmentsService
from src.services.task_comments import TaskCommentsService
from src.services.task_dependencies import TaskDependenciesService
from src.services.task_descriptions import TaskDescriptionService
from src.services.task_documents import TaskDocumentImportService
from src.services.tasks import TasksService
from src.services.users import UsersService
from src.services.wbs_nodes import WbsNodesService
from src.services.wbs_suggestion import WbsSuggestionService


def get_knowledge_events(
    jobs_repository: KnowledgeIndexJobsRepositoryDep,
    settings: SettingsDep,
) -> KnowledgeEvents:
    """Создаёт безопасный publisher изменений для фонового индексатора."""
    return KnowledgeEvents(
        repository=jobs_repository,
        enabled=settings.knowledge.knowledge_enabled,
    )


KnowledgeEventsDep = Annotated[KnowledgeEvents, Depends(get_knowledge_events)]


def get_auth_service(
    users_repository: UsersRepositoryDep,
    tokens_repository: ApiTokensRepositoryDep,
    settings: SettingsDep,
) -> AuthService:
    """Создаёт сервис регистрации, входа и разрешения принципала."""
    return AuthService(
        users_repository=users_repository,
        tokens_repository=tokens_repository,
        invite_code=settings.auth.registration_invite_code.get_secret_value(),
    )


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def get_access_service(
    members_repository: ProjectMembersRepositoryDep,
    tasks_repository: TasksRepositoryDep,
    stages_repository: ProjectStagesRepositoryDep,
    documents_repository: DocumentsRepositoryDep,
    comments_repository: TaskCommentsRepositoryDep,
    links_repository: DocumentLinksRepositoryDep,
) -> AccessService:
    """Создаёт сервис разрешения доступа к объектам проекта."""
    return AccessService(
        members_repository=members_repository,
        tasks_repository=tasks_repository,
        stages_repository=stages_repository,
        documents_repository=documents_repository,
        comments_repository=comments_repository,
        links_repository=links_repository,
    )


AccessServiceDep = Annotated[AccessService, Depends(get_access_service)]


def get_api_tokens_service(
    tokens_repository: ApiTokensRepositoryDep,
    settings: SettingsDep,
) -> ApiTokensService:
    """Создаёт сервис токенов доступа в рамках сессии запроса."""
    return ApiTokensService(
        tokens_repository=tokens_repository,
        max_active_tokens=settings.auth.api_token_max_active,
    )


ApiTokensServiceDep = Annotated[ApiTokensService, Depends(get_api_tokens_service)]


def get_users_service(
    users_repository: UsersRepositoryDep,
    avatar_storage: AvatarStorageDep,
) -> UsersService:
    """Создаёт сервис профиля пользователя."""
    return UsersService(users_repository=users_repository, avatar_storage=avatar_storage)


UsersServiceDep = Annotated[UsersService, Depends(get_users_service)]


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


ProjectsServiceDep = Annotated[ProjectsService, Depends(get_projects_service)]


def get_project_members_service(
    members_repository: ProjectMembersRepositoryDep,
    users_repository: UsersRepositoryDep,
    participants_repository: TaskParticipantsRepositoryDep,
    tasks_repository: TasksRepositoryDep,
    unit_of_work: UnitOfWorkDep,
    users_service: UsersServiceDep,
) -> ProjectMembersService:
    """Создаёт сервис управления проектной командой."""
    return ProjectMembersService(
        members_repository=members_repository,
        users_repository=users_repository,
        participants_repository=participants_repository,
        tasks_repository=tasks_repository,
        unit_of_work=unit_of_work,
        users_service=users_service,
    )


ProjectMembersServiceDep = Annotated[
    ProjectMembersService,
    Depends(get_project_members_service),
]


def get_project_stickers_service(
    stickers_repository: ProjectStickersRepositoryDep,
    tasks_repository: TasksRepositoryDep,
    unit_of_work: UnitOfWorkDep,
) -> ProjectStickersService:
    """Создаёт сервис стикеров Project Board."""
    return ProjectStickersService(
        stickers_repository=stickers_repository,
        tasks_repository=tasks_repository,
        unit_of_work=unit_of_work,
    )


ProjectStickersServiceDep = Annotated[
    ProjectStickersService,
    Depends(get_project_stickers_service),
]


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


ProjectStagesServiceDep = Annotated[
    ProjectStagesService,
    Depends(get_project_stages_service),
]


def get_tasks_service(
    tasks_repository: TasksRepositoryDep,
    members_repository: ProjectMembersRepositoryDep,
    participants_repository: TaskParticipantsRepositoryDep,
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
        members_repository=members_repository,
        participants_repository=participants_repository,
        projects_repository=projects_repository,
        stages_repository=stages_repository,
        comments_repository=comments_repository,
        activity_repository=activity_repository,
        wbs_nodes_repository=wbs_nodes_repository,
        attachment_storage=storage,
        knowledge_events=knowledge_events,
        unit_of_work=unit_of_work,
    )


TasksServiceDep = Annotated[TasksService, Depends(get_tasks_service)]


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


WbsNodesServiceDep = Annotated[WbsNodesService, Depends(get_wbs_nodes_service)]


def get_wbs_suggestion_service(
    wbs_nodes_repository: WbsNodesRepositoryDep,
    projects_repository: ProjectsRepositoryDep,
    stages_repository: ProjectStagesRepositoryDep,
    tasks_repository: TasksRepositoryDep,
    activity_repository: TaskActivityRepositoryDep,
    knowledge_events: KnowledgeEventsDep,
    unit_of_work: UnitOfWorkDep,
    llm_client: LlmClientDep,
) -> WbsSuggestionService:
    """Создаёт сервис предложения структуры ИСР."""
    return WbsSuggestionService(
        wbs_nodes_repository=wbs_nodes_repository,
        projects_repository=projects_repository,
        stages_repository=stages_repository,
        tasks_repository=tasks_repository,
        activity_repository=activity_repository,
        knowledge_events=knowledge_events,
        unit_of_work=unit_of_work,
        llm_client=llm_client,
    )


WbsSuggestionServiceDep = Annotated[WbsSuggestionService, Depends(get_wbs_suggestion_service)]


def get_analytics_service(
    reports_repository: AnalyticsReportsRepositoryDep,
    projects_repository: ProjectsRepositoryDep,
    members_repository: ProjectMembersRepositoryDep,
    stages_repository: ProjectStagesRepositoryDep,
    tasks_repository: TasksRepositoryDep,
    comments_repository: TaskCommentsRepositoryDep,
    activity_repository: TaskActivityRepositoryDep,
    dependencies_repository: TaskDependenciesRepositoryDep,
    wbs_nodes_repository: WbsNodesRepositoryDep,
    milestones_repository: MilestonesRepositoryDep,
    stickers_repository: ProjectStickersRepositoryDep,
    documents_repository: DocumentsRepositoryDep,
    document_links_repository: DocumentLinksRepositoryDep,
    unit_of_work: UnitOfWorkDep,
    llm_client: LlmClientDep,
) -> AnalyticsService:
    """Создаёт сервис аналитического свода дашборда."""
    return AnalyticsService(
        reports_repository=reports_repository,
        projects_repository=projects_repository,
        members_repository=members_repository,
        stages_repository=stages_repository,
        tasks_repository=tasks_repository,
        comments_repository=comments_repository,
        activity_repository=activity_repository,
        dependencies_repository=dependencies_repository,
        wbs_nodes_repository=wbs_nodes_repository,
        milestones_repository=milestones_repository,
        stickers_repository=stickers_repository,
        documents_repository=documents_repository,
        document_links_repository=document_links_repository,
        unit_of_work=unit_of_work,
        llm_client=llm_client,
    )


AnalyticsServiceDep = Annotated[AnalyticsService, Depends(get_analytics_service)]


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


DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]


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


CalendarServiceDep = Annotated[CalendarService, Depends(get_calendar_service)]


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


CalendarScenarioServiceDep = Annotated[
    CalendarScenarioService,
    Depends(get_calendar_scenario_service),
]


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


MilestonesServiceDep = Annotated[MilestonesService, Depends(get_milestones_service)]


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


TaskDependenciesServiceDep = Annotated[
    TaskDependenciesService,
    Depends(get_task_dependencies_service),
]


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


DocumentsServiceDep = Annotated[DocumentsService, Depends(get_documents_service)]


def build_project_agent_config(settings: Settings) -> ProjectAgentConfig:
    """Собирает неизменяемую конфигурацию Project Agent из настроек."""
    return ProjectAgentConfig(
        knowledge_enabled=settings.knowledge.knowledge_enabled,
        semantic_limit=settings.knowledge.knowledge_agent_semantic_limit,
        score_threshold=settings.knowledge.qdrant_score_threshold,
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
    calendar_service: CalendarServiceDep,
    scenario_service: CalendarScenarioServiceDep,
    llm_client: LlmClientDep,
    embedding_client: EmbeddingClientDep,
    qdrant_client: QdrantClientDep,
    settings: SettingsDep,
    knowledge_events: KnowledgeEventsDep,
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
        llm_client=llm_client,
        embedding_client=embedding_client,
        qdrant_client=qdrant_client,
        config=build_project_agent_config(settings),
        knowledge_events=knowledge_events,
    )


ProjectAgentServiceDep = Annotated[ProjectAgentService, Depends(get_project_agent_service)]


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


DocumentLinksServiceDep = Annotated[
    DocumentLinksService,
    Depends(get_document_links_service),
]


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


TaskCommentsServiceDep = Annotated[
    TaskCommentsService,
    Depends(get_task_comments_service),
]


def get_task_activity_service(
    activity_repository: TaskActivityRepositoryDep,
    tasks_repository: TasksRepositoryDep,
) -> TaskActivityService:
    """Создаёт сервис истории задач."""
    return TaskActivityService(
        activity_repository=activity_repository,
        tasks_repository=tasks_repository,
    )


TaskActivityServiceDep = Annotated[
    TaskActivityService,
    Depends(get_task_activity_service),
]


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


TaskAttachmentsServiceDep = Annotated[
    TaskAttachmentsService,
    Depends(get_task_attachments_service),
]


def get_task_description_service(
    projects_repository: ProjectsRepositoryDep,
    tasks_repository: TasksRepositoryDep,
    documents_repository: DocumentsRepositoryDep,
    llm_client: LlmClientDep,
    vision: VisionCapabilityDep,
    settings: SettingsDep,
) -> TaskDescriptionService:
    """Создаёт stateless-сервис переформулирования черновика задачи."""
    return TaskDescriptionService(
        projects_repository=projects_repository,
        tasks_repository=tasks_repository,
        documents_repository=documents_repository,
        llm_client=llm_client,
        vision=vision,
        file_context_limit=settings.llm.task_rephrase_file_max_chars,
    )


TaskDescriptionServiceDep = Annotated[
    TaskDescriptionService,
    Depends(get_task_description_service),
]


def get_task_document_import_service(
    tasks_repository: TasksRepositoryDep,
    attachments_service: TaskAttachmentsServiceDep,
    documents_service: DocumentsServiceDep,
    links_service: DocumentLinksServiceDep,
    unit_of_work: UnitOfWorkDep,
    storage: TaskAttachmentStorageDep,
    vision: VisionCapabilityDep,
    settings: SettingsDep,
) -> TaskDocumentImportService:
    """Создаёт составной импорт документа из формы задачи."""
    return TaskDocumentImportService(
        tasks_repository=tasks_repository,
        attachments_service=attachments_service,
        documents_service=documents_service,
        links_service=links_service,
        unit_of_work=unit_of_work,
        attachment_storage=storage,
        vision=vision,
        extract_max_chars=settings.knowledge.knowledge_extract_max_chars,
    )


TaskDocumentImportServiceDep = Annotated[
    TaskDocumentImportService,
    Depends(get_task_document_import_service),
]

"""Короткие области работы с базой для долгоживущих сценариев.

Обычный запрос получает сессию через yield-зависимость FastAPI, и она
живёт до конца ответа. Для streaming-выдачи и для сценариев с медленным
внешним вызовом это неприемлемо: соединение с PostgreSQL оставалось бы
занятым всё время передачи файла или ожидания модели.

Здесь собирается SQLAlchemy-реализация коротких областей. Сервисы
получают только фабрику области и о SQLAlchemy не знают.
"""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.settings import Settings
from src.db.session import async_session_factory
from src.dependencies.settings import SettingsDep
from src.dependencies.storage import TaskAttachmentStorageDep
from src.repositories.analytics_reports import AnalyticsReportsRepository
from src.repositories.api_tokens import ApiTokensRepository
from src.repositories.document_links import DocumentLinksRepository
from src.repositories.documents import DocumentsRepository
from src.repositories.knowledge_index_jobs import KnowledgeIndexJobsRepository
from src.repositories.milestones import MilestonesRepository
from src.repositories.project_members import ProjectMembersRepository
from src.repositories.project_stages import ProjectStagesRepository
from src.repositories.project_stickers import ProjectStickersRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.task_activity import TaskActivityRepository
from src.repositories.task_attachments import TaskAttachmentsRepository
from src.repositories.task_comments import TaskCommentsRepository
from src.repositories.task_dependencies import TaskDependenciesRepository
from src.repositories.tasks import TasksRepository
from src.repositories.unit_of_work import UnitOfWork
from src.repositories.users import UsersRepository
from src.repositories.wbs_nodes import WbsNodesRepository
from src.services.access import AccessService
from src.services.attachment_download import (
    AttachmentDownloadScope,
    AttachmentDownloadService,
)
from src.services.auth import AuthService
from src.services.calendar import CalendarService
from src.services.calendar_scenarios import CalendarScenarioService
from src.services.db_scope import (
    AnalyticsDbScope,
    ProjectAgentScope,
    TaskDescriptionScope,
    TaskDocumentImportScope,
    WbsSuggestionScope,
)
from src.services.document_links import DocumentLinksService
from src.services.documents import DocumentsService
from src.services.knowledge_events import KnowledgeEvents
from src.services.task_attachments import TaskAttachmentsService
from src.storage.task_attachments import TaskAttachmentStorage

SessionFactory = async_sessionmaker[AsyncSession]


def build_attachment_download_scope(
    *,
    session_factory: SessionFactory,
    settings: Settings,
    storage: TaskAttachmentStorage,
) -> Callable[[], AbstractAsyncContextManager[AttachmentDownloadScope]]:
    """Собирает фабрику короткой области подготовки выдачи файла.

    Область открывается на время проверки доступа и чтения метаданных и
    закрывается до начала передачи файла.

    Args:
        session_factory: Фабрика сессий PostgreSQL.
        settings: Настройки приложения.
        storage: Локальное хранилище файлов задач.

    Returns:
        Фабрику асинхронного контекста с узким набором операций.
    """

    @asynccontextmanager
    async def scope() -> AsyncIterator[AttachmentDownloadScope]:
        async with session_factory() as session:
            yield AttachmentDownloadScope(
                auth_service=AuthService(
                    users_repository=UsersRepository(session),
                    tokens_repository=ApiTokensRepository(session),
                    invite_code=settings.auth.registration_invite_code.get_secret_value(),
                ),
                access_service=AccessService(
                    members_repository=ProjectMembersRepository(session),
                    tasks_repository=TasksRepository(session),
                    stages_repository=ProjectStagesRepository(session),
                    documents_repository=DocumentsRepository(session),
                    comments_repository=TaskCommentsRepository(session),
                    links_repository=DocumentLinksRepository(session),
                ),
                attachments_service=TaskAttachmentsService(
                    attachments_repository=TaskAttachmentsRepository(session),
                    tasks_repository=TasksRepository(session),
                    storage=storage,
                    knowledge_events=KnowledgeEvents(
                        repository=KnowledgeIndexJobsRepository(session),
                        enabled=settings.knowledge.knowledge_enabled,
                    ),
                    unit_of_work=UnitOfWork(session),
                ),
            )

    return scope


def get_attachment_download_service(
    settings: SettingsDep,
    storage: TaskAttachmentStorageDep,
) -> AttachmentDownloadService:
    """Создаёт сервис подготовки выдачи файла задачи.

    Зависимость намеренно не является yield-зависимостью и не получает
    `DbSessionDep`: сессия не должна пережить подготовку ответа.
    """
    return AttachmentDownloadService(
        scope=build_attachment_download_scope(
            session_factory=async_session_factory,
            settings=settings,
            storage=storage,
        )
    )


AttachmentDownloadServiceDep = Annotated[
    AttachmentDownloadService,
    Depends(get_attachment_download_service),
]


def build_wbs_suggestion_scope(
    *,
    session_factory: SessionFactory,
    settings: Settings,
) -> Callable[[], AbstractAsyncContextManager[WbsSuggestionScope]]:
    """Собирает фабрику короткой области сценария предложения ИСР.

    Args:
        session_factory: Фабрика сессий PostgreSQL.
        settings: Настройки приложения.

    Returns:
        Фабрику асинхронного контекста с репозиториями сценария.
    """

    @asynccontextmanager
    async def scope() -> AsyncIterator[WbsSuggestionScope]:
        async with session_factory() as session:
            yield WbsSuggestionScope(
                projects=ProjectsRepository(session),
                wbs_nodes=WbsNodesRepository(session),
                tasks=TasksRepository(session),
                stages=ProjectStagesRepository(session),
                activity=TaskActivityRepository(session),
                knowledge_events=KnowledgeEvents(
                    repository=KnowledgeIndexJobsRepository(session),
                    enabled=settings.knowledge.knowledge_enabled,
                ),
                unit_of_work=UnitOfWork(session),
            )

    return scope


def get_wbs_suggestion_scope(
    settings: SettingsDep,
) -> Callable[[], AbstractAsyncContextManager[WbsSuggestionScope]]:
    """Возвращает фабрику области для сценария предложения ИСР."""
    return build_wbs_suggestion_scope(
        session_factory=async_session_factory,
        settings=settings,
    )


WbsSuggestionScopeDep = Annotated[
    Callable[[], AbstractAsyncContextManager[WbsSuggestionScope]],
    Depends(get_wbs_suggestion_scope),
]


def build_task_description_scope(
    *,
    session_factory: SessionFactory,
) -> Callable[[], AbstractAsyncContextManager[TaskDescriptionScope]]:
    """Собирает фабрику короткой области переформулирования черновика."""

    @asynccontextmanager
    async def scope() -> AsyncIterator[TaskDescriptionScope]:
        async with session_factory() as session:
            yield TaskDescriptionScope(
                projects=ProjectsRepository(session),
                tasks=TasksRepository(session),
                documents=DocumentsRepository(session),
            )

    return scope


def get_task_description_scope() -> (
    Callable[[], AbstractAsyncContextManager[TaskDescriptionScope]]
):
    """Возвращает фабрику области для переформулирования черновика."""
    return build_task_description_scope(session_factory=async_session_factory)


TaskDescriptionScopeDep = Annotated[
    Callable[[], AbstractAsyncContextManager[TaskDescriptionScope]],
    Depends(get_task_description_scope),
]


def build_analytics_scope(
    *,
    session_factory: SessionFactory,
) -> Callable[[], AbstractAsyncContextManager[AnalyticsDbScope]]:
    """Собирает фабрику короткой области сценария аналитического свода."""

    @asynccontextmanager
    async def scope() -> AsyncIterator[AnalyticsDbScope]:
        async with session_factory() as session:
            yield AnalyticsDbScope(
                reports=AnalyticsReportsRepository(session),
                projects=ProjectsRepository(session),
                members=ProjectMembersRepository(session),
                stages=ProjectStagesRepository(session),
                tasks=TasksRepository(session),
                comments=TaskCommentsRepository(session),
                activity=TaskActivityRepository(session),
                dependencies=TaskDependenciesRepository(session),
                wbs_nodes=WbsNodesRepository(session),
                milestones=MilestonesRepository(session),
                stickers=ProjectStickersRepository(session),
                documents=DocumentsRepository(session),
                document_links=DocumentLinksRepository(session),
                unit_of_work=UnitOfWork(session),
            )

    return scope


def get_analytics_scope() -> Callable[[], AbstractAsyncContextManager[AnalyticsDbScope]]:
    """Возвращает фабрику области для аналитического свода."""
    return build_analytics_scope(session_factory=async_session_factory)


AnalyticsScopeDep = Annotated[
    Callable[[], AbstractAsyncContextManager[AnalyticsDbScope]],
    Depends(get_analytics_scope),
]


def build_project_agent_scope(
    *,
    session_factory: SessionFactory,
    settings: Settings,
) -> Callable[[], AbstractAsyncContextManager[ProjectAgentScope]]:
    """Собирает фабрику короткой области сценариев Project Agent."""

    @asynccontextmanager
    async def scope() -> AsyncIterator[ProjectAgentScope]:
        async with session_factory() as session:
            yield ProjectAgentScope(
                projects=ProjectsRepository(session),
                stages=ProjectStagesRepository(session),
                tasks=TasksRepository(session),
                wbs_nodes=WbsNodesRepository(session),
                documents=DocumentsRepository(session),
                activity=TaskActivityRepository(session),
                milestones=MilestonesRepository(session),
                dependencies=TaskDependenciesRepository(session),
                jobs=KnowledgeIndexJobsRepository(session),
                knowledge_events=KnowledgeEvents(
                    repository=KnowledgeIndexJobsRepository(session),
                    enabled=settings.knowledge.knowledge_enabled,
                ),
                unit_of_work=UnitOfWork(session),
                calendar=CalendarService(
                    projects_repository=ProjectsRepository(session),
                    tasks_repository=TasksRepository(session),
                    stages_repository=ProjectStagesRepository(session),
                    wbs_nodes_repository=WbsNodesRepository(session),
                    activity_repository=TaskActivityRepository(session),
                    milestones_repository=MilestonesRepository(session),
                    dependencies_repository=TaskDependenciesRepository(session),
                ),
                scenario=CalendarScenarioService(
                    projects_repository=ProjectsRepository(session),
                    tasks_repository=TasksRepository(session),
                    dependencies_repository=TaskDependenciesRepository(session),
                    milestones_repository=MilestonesRepository(session),
                    activity_repository=TaskActivityRepository(session),
                    unit_of_work=UnitOfWork(session),
                ),
            )

    return scope


def get_project_agent_scope(
    settings: SettingsDep,
) -> Callable[[], AbstractAsyncContextManager[ProjectAgentScope]]:
    """Возвращает фабрику области для сценариев Project Agent."""
    return build_project_agent_scope(
        session_factory=async_session_factory,
        settings=settings,
    )


ProjectAgentScopeDep = Annotated[
    Callable[[], AbstractAsyncContextManager[ProjectAgentScope]],
    Depends(get_project_agent_scope),
]


def build_task_document_import_scope(
    *,
    session_factory: SessionFactory,
    settings: Settings,
    storage: TaskAttachmentStorage,
) -> Callable[[], AbstractAsyncContextManager[TaskDocumentImportScope]]:
    """Собирает фабрику короткой области импорта документа в задачу.

    Все вложенные сервисы получают одну сессию: три записи импорта — это
    один бизнес-факт и одна транзакция.
    """

    @asynccontextmanager
    async def scope() -> AsyncIterator[TaskDocumentImportScope]:
        async with session_factory() as session:
            unit_of_work = UnitOfWork(session)
            events = KnowledgeEvents(
                repository=KnowledgeIndexJobsRepository(session),
                enabled=settings.knowledge.knowledge_enabled,
            )
            yield TaskDocumentImportScope(
                tasks=TasksRepository(session),
                attachments=TaskAttachmentsService(
                    attachments_repository=TaskAttachmentsRepository(session),
                    tasks_repository=TasksRepository(session),
                    storage=storage,
                    knowledge_events=events,
                    unit_of_work=unit_of_work,
                ),
                documents=DocumentsService(
                    documents_repository=DocumentsRepository(session),
                    projects_repository=ProjectsRepository(session),
                    knowledge_events=events,
                    unit_of_work=unit_of_work,
                ),
                links=DocumentLinksService(
                    document_links_repository=DocumentLinksRepository(session),
                    documents_repository=DocumentsRepository(session),
                    tasks_repository=TasksRepository(session),
                    projects_repository=ProjectsRepository(session),
                    members_repository=ProjectMembersRepository(session),
                ),
                unit_of_work=unit_of_work,
            )

    return scope


def get_task_document_import_scope(
    settings: SettingsDep,
    storage: TaskAttachmentStorageDep,
) -> Callable[[], AbstractAsyncContextManager[TaskDocumentImportScope]]:
    """Возвращает фабрику области для импорта документа в задачу."""
    return build_task_document_import_scope(
        session_factory=async_session_factory,
        settings=settings,
        storage=storage,
    )


TaskDocumentImportScopeDep = Annotated[
    Callable[[], AbstractAsyncContextManager[TaskDocumentImportScope]],
    Depends(get_task_document_import_scope),
]

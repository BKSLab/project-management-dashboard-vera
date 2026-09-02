"""Сборка доменных сервисов для MCP-инструментов.

Инструменты записи не работают с репозиториями напрямую: они вызывают те же
сервисы, что и HTTP-эндпоинты, поэтому история задачи, нумерация и постановка
в очередь индексации знаний происходят одинаково независимо от канала.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.settings import get_settings
from src.repositories.knowledge_index_jobs import KnowledgeIndexJobsRepository
from src.repositories.milestones import MilestonesRepository
from src.repositories.project_stages import ProjectStagesRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.task_activity import TaskActivityRepository
from src.repositories.task_comments import TaskCommentsRepository
from src.repositories.task_dependencies import TaskDependenciesRepository
from src.repositories.tasks import TasksRepository
from src.repositories.unit_of_work import UnitOfWork
from src.repositories.wbs_nodes import WbsNodesRepository
from src.services.calendar import CalendarService
from src.services.knowledge_events import KnowledgeEvents
from src.services.milestones import MilestonesService
from src.services.task_comments import TaskCommentsService
from src.services.tasks import TasksService
from src.storage.task_attachments import TaskAttachmentStorage


def build_knowledge_events(session: AsyncSession) -> KnowledgeEvents:
    """Создаёт публикатор событий индексации знаний."""
    settings = get_settings()
    return KnowledgeEvents(
        repository=KnowledgeIndexJobsRepository(session),
        enabled=settings.knowledge.knowledge_enabled,
    )


def build_tasks_service(session: AsyncSession) -> TasksService:
    """Создаёт сервис задач со всеми доменными зависимостями."""
    settings = get_settings()
    return TasksService(
        tasks_repository=TasksRepository(session),
        projects_repository=ProjectsRepository(session),
        stages_repository=ProjectStagesRepository(session),
        comments_repository=TaskCommentsRepository(session),
        activity_repository=TaskActivityRepository(session),
        wbs_nodes_repository=WbsNodesRepository(session),
        unit_of_work=UnitOfWork(session),
        attachment_storage=TaskAttachmentStorage(settings.app.uploads_path),
        knowledge_events=build_knowledge_events(session),
    )


def build_comments_service(session: AsyncSession) -> TaskCommentsService:
    """Создаёт сервис комментариев задач."""
    return TaskCommentsService(
        comments_repository=TaskCommentsRepository(session),
        tasks_repository=TasksRepository(session),
        activity_repository=TaskActivityRepository(session),
        unit_of_work=UnitOfWork(session),
        knowledge_events=build_knowledge_events(session),
    )


def build_calendar_service(session: AsyncSession) -> CalendarService:
    """Создаёт read-only сервис временной карты для MCP."""
    return CalendarService(
        projects_repository=ProjectsRepository(session),
        tasks_repository=TasksRepository(session),
        stages_repository=ProjectStagesRepository(session),
        wbs_nodes_repository=WbsNodesRepository(session),
        activity_repository=TaskActivityRepository(session),
        milestones_repository=MilestonesRepository(session),
        dependencies_repository=TaskDependenciesRepository(session),
    )


def build_milestones_service(session: AsyncSession) -> MilestonesService:
    """Создаёт сервис проектных вех с transactional outbox."""
    return MilestonesService(
        milestones_repository=MilestonesRepository(session),
        projects_repository=ProjectsRepository(session),
        wbs_nodes_repository=WbsNodesRepository(session),
        unit_of_work=UnitOfWork(session),
        knowledge_events=build_knowledge_events(session),
    )

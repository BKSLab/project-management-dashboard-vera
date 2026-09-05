"""Короткие области работы с базой для сценариев с внешним вызовом.

Обычный запрос держит сессию до конца ответа, и это нормально, пока
сценарий короткий. Но у AI-сценариев между чтением и записью стоит вызов
LLM, эмбеддингов или Qdrant, который в худшем случае длится сотни секунд.
Всё это время request-scoped сессия остаётся занятой: после первого
`SELECT` открыта транзакция, соединение выведено из пула, и пул исчерпаем
десятком таких запросов.

Поэтому сценарий делится на фазы: короткая DB-фаза собирает неизменяемый
снимок, область закрывается, выполняется внешний вызов, и при
необходимости открывается новая короткая область для записи результата.

Область описана конкретным набором именованных репозиториев, а не
контейнером с поиском по имени: сервис не должен уметь запросить
произвольную зависимость — иначе глобальный service locator был бы просто
заменён локальным.
"""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass

from src.repositories.analytics_reports import AnalyticsReportsRepository
from src.repositories.document_links import DocumentLinksRepository
from src.repositories.documents import DocumentsRepository
from src.repositories.knowledge_index_jobs import KnowledgeIndexJobsRepository
from src.repositories.milestones import MilestonesRepository
from src.repositories.project_members import ProjectMembersRepository
from src.repositories.project_stages import ProjectStagesRepository
from src.repositories.project_stickers import ProjectStickersRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.task_activity import TaskActivityRepository
from src.repositories.task_comments import TaskCommentsRepository
from src.repositories.task_dependencies import TaskDependenciesRepository
from src.repositories.tasks import TasksRepository
from src.repositories.unit_of_work import UnitOfWork
from src.repositories.wbs_nodes import WbsNodesRepository
from src.services.calendar import CalendarService
from src.services.calendar_scenarios import CalendarScenarioService
from src.services.document_links import DocumentLinksService
from src.services.documents import DocumentsService
from src.services.knowledge_events import KnowledgeEvents
from src.services.task_attachments import TaskAttachmentsService


@dataclass(frozen=True, slots=True)
class WbsSuggestionScope:
    """Одна короткая область сценария предложения структуры ИСР."""

    projects: ProjectsRepository
    wbs_nodes: WbsNodesRepository
    tasks: TasksRepository
    stages: ProjectStagesRepository
    activity: TaskActivityRepository
    knowledge_events: KnowledgeEvents
    unit_of_work: UnitOfWork


@dataclass(frozen=True, slots=True)
class TaskDescriptionScope:
    """Одна короткая область сценария переформулирования черновика."""

    projects: ProjectsRepository
    tasks: TasksRepository
    documents: DocumentsRepository


@dataclass(frozen=True, slots=True)
class AnalyticsDbScope:
    """Одна короткая область сценария аналитического свода.

    Названа `DbScope`, чтобы не смешиваться с `AnalyticsScope` —
    перечислением области анализа: проект или весь портфель.
    """

    reports: AnalyticsReportsRepository
    projects: ProjectsRepository
    members: ProjectMembersRepository
    stages: ProjectStagesRepository
    tasks: TasksRepository
    comments: TaskCommentsRepository
    activity: TaskActivityRepository
    dependencies: TaskDependenciesRepository
    wbs_nodes: WbsNodesRepository
    milestones: MilestonesRepository
    stickers: ProjectStickersRepository
    documents: DocumentsRepository
    document_links: DocumentLinksRepository
    unit_of_work: UnitOfWork


@dataclass(frozen=True, slots=True)
class ProjectAgentScope:
    """Одна короткая область сценария Project Agent."""

    projects: ProjectsRepository
    stages: ProjectStagesRepository
    tasks: TasksRepository
    wbs_nodes: WbsNodesRepository
    documents: DocumentsRepository
    activity: TaskActivityRepository
    milestones: MilestonesRepository
    dependencies: TaskDependenciesRepository
    jobs: KnowledgeIndexJobsRepository
    knowledge_events: KnowledgeEvents
    unit_of_work: UnitOfWork
    calendar: CalendarService
    scenario: CalendarScenarioService


ScopeFactory = Callable[[], AbstractAsyncContextManager]


WbsSuggestionScopeFactory = Callable[[], AbstractAsyncContextManager[WbsSuggestionScope]]
TaskDescriptionScopeFactory = Callable[[], AbstractAsyncContextManager[TaskDescriptionScope]]
AnalyticsDbScopeFactory = Callable[[], AbstractAsyncContextManager[AnalyticsDbScope]]
ProjectAgentScopeFactory = Callable[[], AbstractAsyncContextManager[ProjectAgentScope]]


@dataclass(frozen=True, slots=True)
class TaskDocumentImportScope:
    """Одна короткая область сценария импорта документа в задачу.

    Здесь перечислены сервисы, а не репозитории: импорт собран из трёх
    вложенных сценариев, и каждому из них нужна та же сессия, что и
    владельцу транзакции.
    """

    tasks: TasksRepository
    attachments: TaskAttachmentsService
    documents: DocumentsService
    links: DocumentLinksService
    unit_of_work: UnitOfWork


TaskDocumentImportScopeFactory = Callable[
    [], AbstractAsyncContextManager[TaskDocumentImportScope]
]

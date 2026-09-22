"""Явные зависимости одного короткого сценария инструмента проекта."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass

from src.repositories.agent_conversations import AgentConversationsRepository
from src.repositories.agent_files import AgentFilesRepository
from src.repositories.agent_messages import AgentMessagesRepository
from src.repositories.agent_tool_runs import AgentToolRunsRepository
from src.repositories.unit_of_work import AgentToolUnitOfWork
from src.repositories.users import UsersRepository
from src.services.access import AccessService
from src.services.calendar import CalendarService
from src.services.calendar_scenarios import CalendarScenarioService
from src.services.document_links import DocumentLinksService
from src.services.documents import DocumentsService
from src.services.milestones import MilestonesService
from src.services.project_members import ProjectMembersService
from src.services.project_risks import ProjectRiskService
from src.services.project_stages import ProjectStagesService
from src.services.project_stickers import ProjectStickersService
from src.services.projects import ProjectsService
from src.services.task_attachments import TaskAttachmentsService
from src.services.task_comments import TaskCommentsService
from src.services.task_dependencies import TaskDependenciesService
from src.services.tasks import TasksService
from src.services.wbs_nodes import WbsNodesService
from src.storage.agent_tool_files import AgentToolFileStorage


@dataclass(frozen=True, slots=True)
class AgentProjectToolScope:
    """Доменные сервисы и журнал одной атомарной операции."""

    projects: ProjectsService
    tasks: TasksService
    comments: TaskCommentsService
    members: ProjectMembersService
    stickers: ProjectStickersService
    stages: ProjectStagesService
    documents: DocumentsService
    links: DocumentLinksService
    attachments: TaskAttachmentsService
    wbs: WbsNodesService
    milestones: MilestonesService
    dependencies: TaskDependenciesService
    calendar: CalendarService
    scenarios: CalendarScenarioService
    risks: ProjectRiskService
    access: AccessService
    users: UsersRepository
    conversations: AgentConversationsRepository
    messages: AgentMessagesRepository
    runs: AgentToolRunsRepository
    uploads: AgentFilesRepository
    upload_storage: AgentToolFileStorage
    unit_of_work: AgentToolUnitOfWork


AgentProjectToolScopeFactory = Callable[[], AbstractAsyncContextManager[AgentProjectToolScope]]

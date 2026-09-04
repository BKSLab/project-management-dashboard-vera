from typing import Annotated

from fastapi import Depends

from src.dependencies.db_session import DbSessionDep
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
from src.repositories.task_participants import TaskParticipantsRepository
from src.repositories.tasks import TasksRepository
from src.repositories.unit_of_work import UnitOfWork
from src.repositories.users import UsersRepository
from src.repositories.wbs_nodes import WbsNodesRepository


def get_analytics_reports_repository(session: DbSessionDep) -> AnalyticsReportsRepository:
    """Создаёт репозиторий аналитических сводов в рамках сессии запроса."""
    return AnalyticsReportsRepository(session)


def get_api_tokens_repository(session: DbSessionDep) -> ApiTokensRepository:
    """Создаёт репозиторий токенов доступа в рамках сессии запроса."""
    return ApiTokensRepository(session)


def get_users_repository(session: DbSessionDep) -> UsersRepository:
    """Создаёт репозиторий пользователей в рамках сессии запроса."""
    return UsersRepository(session)


def get_project_members_repository(session: DbSessionDep) -> ProjectMembersRepository:
    """Создаёт репозиторий участников проекта в рамках сессии запроса."""
    return ProjectMembersRepository(session)


def get_project_stickers_repository(session: DbSessionDep) -> ProjectStickersRepository:
    """Создаёт репозиторий стикеров Project Board в рамках сессии запроса."""
    return ProjectStickersRepository(session)


def get_projects_repository(session: DbSessionDep) -> ProjectsRepository:
    """Создаёт репозиторий проектов в рамках сессии запроса."""
    return ProjectsRepository(session)


def get_project_stages_repository(session: DbSessionDep) -> ProjectStagesRepository:
    """Создаёт репозиторий стадий проекта в рамках сессии запроса."""
    return ProjectStagesRepository(session)


def get_tasks_repository(session: DbSessionDep) -> TasksRepository:
    """Создаёт репозиторий задач в рамках сессии запроса."""
    return TasksRepository(session)


def get_task_participants_repository(session: DbSessionDep) -> TaskParticipantsRepository:
    """Создаёт репозиторий ролевых назначений задач в рамках сессии запроса."""
    return TaskParticipantsRepository(session)


def get_wbs_nodes_repository(session: DbSessionDep) -> WbsNodesRepository:
    """Создаёт репозиторий узлов ИСР в рамках сессии запроса."""
    return WbsNodesRepository(session)


def get_documents_repository(session: DbSessionDep) -> DocumentsRepository:
    """Создаёт репозиторий документов в рамках сессии запроса."""
    return DocumentsRepository(session)


def get_knowledge_index_jobs_repository(session: DbSessionDep) -> KnowledgeIndexJobsRepository:
    """Создаёт репозиторий постоянной очереди базы знаний."""
    return KnowledgeIndexJobsRepository(session)


def get_milestones_repository(session: DbSessionDep) -> MilestonesRepository:
    """Создаёт репозиторий проектных вех в рамках сессии запроса."""
    return MilestonesRepository(session)


def get_document_links_repository(session: DbSessionDep) -> DocumentLinksRepository:
    """Создаёт репозиторий связей документов в рамках сессии запроса."""
    return DocumentLinksRepository(session)


def get_task_comments_repository(session: DbSessionDep) -> TaskCommentsRepository:
    """Создаёт репозиторий комментариев в рамках сессии запроса."""
    return TaskCommentsRepository(session)


def get_task_dependencies_repository(session: DbSessionDep) -> TaskDependenciesRepository:
    """Создаёт репозиторий зависимостей задач в рамках сессии запроса."""
    return TaskDependenciesRepository(session)


def get_task_activity_repository(session: DbSessionDep) -> TaskActivityRepository:
    """Создаёт репозиторий истории задач в рамках сессии запроса."""
    return TaskActivityRepository(session)


def get_task_attachments_repository(session: DbSessionDep) -> TaskAttachmentsRepository:
    """Создаёт репозиторий файлов задач в рамках сессии запроса."""
    return TaskAttachmentsRepository(session)


def get_unit_of_work(session: DbSessionDep) -> UnitOfWork:
    """Создаёт координатор общей транзакции в рамках сессии запроса."""
    return UnitOfWork(session)


UsersRepositoryDep = Annotated[UsersRepository, Depends(get_users_repository)]
ApiTokensRepositoryDep = Annotated[ApiTokensRepository, Depends(get_api_tokens_repository)]
ProjectMembersRepositoryDep = Annotated[
    ProjectMembersRepository,
    Depends(get_project_members_repository),
]
ProjectsRepositoryDep = Annotated[ProjectsRepository, Depends(get_projects_repository)]
ProjectStagesRepositoryDep = Annotated[
    ProjectStagesRepository,
    Depends(get_project_stages_repository),
]
TasksRepositoryDep = Annotated[TasksRepository, Depends(get_tasks_repository)]
TaskParticipantsRepositoryDep = Annotated[
    TaskParticipantsRepository,
    Depends(get_task_participants_repository),
]
ProjectStickersRepositoryDep = Annotated[
    ProjectStickersRepository,
    Depends(get_project_stickers_repository),
]
WbsNodesRepositoryDep = Annotated[WbsNodesRepository, Depends(get_wbs_nodes_repository)]
DocumentsRepositoryDep = Annotated[DocumentsRepository, Depends(get_documents_repository)]
KnowledgeIndexJobsRepositoryDep = Annotated[
    KnowledgeIndexJobsRepository,
    Depends(get_knowledge_index_jobs_repository),
]
MilestonesRepositoryDep = Annotated[MilestonesRepository, Depends(get_milestones_repository)]
DocumentLinksRepositoryDep = Annotated[
    DocumentLinksRepository,
    Depends(get_document_links_repository),
]
TaskCommentsRepositoryDep = Annotated[
    TaskCommentsRepository,
    Depends(get_task_comments_repository),
]
TaskDependenciesRepositoryDep = Annotated[
    TaskDependenciesRepository,
    Depends(get_task_dependencies_repository),
]
TaskActivityRepositoryDep = Annotated[
    TaskActivityRepository,
    Depends(get_task_activity_repository),
]
TaskAttachmentsRepositoryDep = Annotated[
    TaskAttachmentsRepository,
    Depends(get_task_attachments_repository),
]
AnalyticsReportsRepositoryDep = Annotated[
    AnalyticsReportsRepository,
    Depends(get_analytics_reports_repository),
]
UnitOfWorkDep = Annotated[UnitOfWork, Depends(get_unit_of_work)]

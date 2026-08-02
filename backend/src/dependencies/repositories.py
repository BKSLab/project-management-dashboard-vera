from typing import Annotated

from fastapi import Depends

from src.dependencies.db_session import DbSessionDep
from src.repositories.document_links import DocumentLinksRepository
from src.repositories.documents import DocumentsRepository
from src.repositories.kanban_stages import KanbanStagesRepository
from src.repositories.kanban_tasks import KanbanTasksRepository
from src.repositories.task_activity import TaskActivityRepository
from src.repositories.task_attachments import TaskAttachmentsRepository
from src.repositories.task_comments import TaskCommentsRepository
from src.repositories.wbs import WbsRepository


def get_documents_repository(session: DbSessionDep) -> DocumentsRepository:
    """Создаёт репозиторий документов в рамках сессии запроса."""
    return DocumentsRepository(session)


def get_document_links_repository(session: DbSessionDep) -> DocumentLinksRepository:
    """Создаёт репозиторий связей документов в рамках сессии запроса."""
    return DocumentLinksRepository(session)


def get_kanban_stages_repository(session: DbSessionDep) -> KanbanStagesRepository:
    """Создаёт репозиторий стадий канбана в рамках сессии запроса."""
    return KanbanStagesRepository(session)


def get_kanban_tasks_repository(session: DbSessionDep) -> KanbanTasksRepository:
    """Создаёт репозиторий задач канбана в рамках сессии запроса."""
    return KanbanTasksRepository(session)


def get_task_comments_repository(session: DbSessionDep) -> TaskCommentsRepository:
    """Создаёт репозиторий комментариев в рамках сессии запроса."""
    return TaskCommentsRepository(session)


def get_task_activity_repository(session: DbSessionDep) -> TaskActivityRepository:
    """Создаёт репозиторий истории задач в рамках сессии запроса."""
    return TaskActivityRepository(session)


def get_task_attachments_repository(session: DbSessionDep) -> TaskAttachmentsRepository:
    """Создаёт репозиторий файлов задач в рамках сессии запроса."""
    return TaskAttachmentsRepository(session)


def get_wbs_repository(session: DbSessionDep) -> WbsRepository:
    """Создаёт репозиторий ИСР в рамках сессии запроса."""
    return WbsRepository(session)


DocumentsRepositoryDep = Annotated[DocumentsRepository, Depends(get_documents_repository)]
DocumentLinksRepositoryDep = Annotated[
    DocumentLinksRepository,
    Depends(get_document_links_repository),
]
KanbanStagesRepositoryDep = Annotated[
    KanbanStagesRepository,
    Depends(get_kanban_stages_repository),
]
KanbanTasksRepositoryDep = Annotated[
    KanbanTasksRepository,
    Depends(get_kanban_tasks_repository),
]
TaskCommentsRepositoryDep = Annotated[
    TaskCommentsRepository,
    Depends(get_task_comments_repository),
]
TaskActivityRepositoryDep = Annotated[
    TaskActivityRepository,
    Depends(get_task_activity_repository),
]
TaskAttachmentsRepositoryDep = Annotated[
    TaskAttachmentsRepository,
    Depends(get_task_attachments_repository),
]
WbsRepositoryDep = Annotated[WbsRepository, Depends(get_wbs_repository)]

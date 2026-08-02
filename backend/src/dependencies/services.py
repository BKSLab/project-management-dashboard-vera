from typing import Annotated

from fastapi import Depends

from src.dependencies.repositories import (
    DocumentLinksRepositoryDep,
    DocumentsRepositoryDep,
    KanbanStagesRepositoryDep,
    KanbanTasksRepositoryDep,
    TaskActivityRepositoryDep,
    TaskAttachmentsRepositoryDep,
    TaskCommentsRepositoryDep,
    WbsRepositoryDep,
)
from src.dependencies.storage import TaskAttachmentStorageDep
from src.services.document_links import DocumentLinksService
from src.services.documents import DocumentsService
from src.services.kanban_stages import KanbanStagesService
from src.services.kanban_tasks import KanbanTasksService
from src.services.task_activity import TaskActivityService
from src.services.task_attachments import TaskAttachmentsService
from src.services.task_comments import TaskCommentsService
from src.services.wbs import WbsService


def get_documents_service(documents_repository: DocumentsRepositoryDep) -> DocumentsService:
    """Создаёт сервис документов."""
    return DocumentsService(documents_repository=documents_repository)


def get_document_links_service(
    document_links_repository: DocumentLinksRepositoryDep,
    documents_repository: DocumentsRepositoryDep,
    tasks_repository: KanbanTasksRepositoryDep,
    wbs_repository: WbsRepositoryDep,
) -> DocumentLinksService:
    """Создаёт сервис связей документов."""
    return DocumentLinksService(
        document_links_repository=document_links_repository,
        documents_repository=documents_repository,
        tasks_repository=tasks_repository,
        wbs_repository=wbs_repository,
    )


def get_kanban_stages_service(
    stages_repository: KanbanStagesRepositoryDep,
    tasks_repository: KanbanTasksRepositoryDep,
) -> KanbanStagesService:
    """Создаёт сервис стадий канбана."""
    return KanbanStagesService(
        stages_repository=stages_repository,
        tasks_repository=tasks_repository,
    )


def get_kanban_tasks_service(
    tasks_repository: KanbanTasksRepositoryDep,
    stages_repository: KanbanStagesRepositoryDep,
    comments_repository: TaskCommentsRepositoryDep,
    activity_repository: TaskActivityRepositoryDep,
    wbs_repository: WbsRepositoryDep,
    storage: TaskAttachmentStorageDep,
) -> KanbanTasksService:
    """Создаёт сервис задач канбана со всеми доменными зависимостями."""
    return KanbanTasksService(
        tasks_repository=tasks_repository,
        stages_repository=stages_repository,
        comments_repository=comments_repository,
        activity_repository=activity_repository,
        wbs_repository=wbs_repository,
        attachment_storage=storage,
    )


def get_task_comments_service(
    comments_repository: TaskCommentsRepositoryDep,
    tasks_repository: KanbanTasksRepositoryDep,
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
    tasks_repository: KanbanTasksRepositoryDep,
) -> TaskActivityService:
    """Создаёт сервис истории задач."""
    return TaskActivityService(
        activity_repository=activity_repository,
        tasks_repository=tasks_repository,
    )


def get_task_attachments_service(
    attachments_repository: TaskAttachmentsRepositoryDep,
    tasks_repository: KanbanTasksRepositoryDep,
    storage: TaskAttachmentStorageDep,
) -> TaskAttachmentsService:
    """Создаёт сервис файлов задач."""
    return TaskAttachmentsService(
        attachments_repository=attachments_repository,
        tasks_repository=tasks_repository,
        storage=storage,
    )


def get_wbs_service(
    wbs_repository: WbsRepositoryDep,
    tasks_repository: KanbanTasksRepositoryDep,
    stages_repository: KanbanStagesRepositoryDep,
    storage: TaskAttachmentStorageDep,
) -> WbsService:
    """Создаёт сервис ИСР."""
    return WbsService(
        wbs_repository=wbs_repository,
        tasks_repository=tasks_repository,
        stages_repository=stages_repository,
        attachment_storage=storage,
    )


DocumentsServiceDep = Annotated[DocumentsService, Depends(get_documents_service)]
DocumentLinksServiceDep = Annotated[
    DocumentLinksService,
    Depends(get_document_links_service),
]
KanbanStagesServiceDep = Annotated[
    KanbanStagesService,
    Depends(get_kanban_stages_service),
]
KanbanTasksServiceDep = Annotated[
    KanbanTasksService,
    Depends(get_kanban_tasks_service),
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
WbsServiceDep = Annotated[WbsService, Depends(get_wbs_service)]

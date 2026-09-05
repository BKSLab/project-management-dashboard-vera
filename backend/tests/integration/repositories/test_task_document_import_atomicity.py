"""Атомарность импорта документа в задачу.

Раньше сценарий состоял из трёх независимых commit, и сбой на последнем
шаге оставлял в базе уже зафиксированные оригинал и документ — их
приходилось удалять компенсирующими запросами. Теперь это один DB-факт:
либо появляются все три записи, либо ни одной.

Проверка идёт на реальном PostgreSQL: видимость и откат — это поведение
СУБД, а не сервиса.
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.vision import DisabledVisionCapability
from src.db.models.document_links import DocumentLink
from src.db.models.documents import Document
from src.db.models.project_members import ProjectRole
from src.db.models.project_stages import ProjectStage
from src.db.models.projects import Project
from src.db.models.task_attachments import TaskAttachment
from src.exceptions.document_links import DocumentLinksServiceError
from src.exceptions.task_documents import TaskDocumentStepFailedError
from src.repositories.document_links import DocumentLinksRepository
from src.repositories.documents import DocumentsRepository
from src.repositories.knowledge_index_jobs import KnowledgeIndexJobsRepository
from src.repositories.project_members import ProjectMembersRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.task_attachments import TaskAttachmentsRepository
from src.repositories.tasks import TasksRepository
from src.repositories.unit_of_work import UnitOfWork
from src.services.db_scope import TaskDocumentImportScope
from src.services.document_links import DocumentLinksService
from src.services.documents import DocumentsService
from src.services.knowledge_events import KnowledgeEvents
from src.services.task_attachments import TaskAttachmentsService
from src.services.task_documents import TaskDocumentImportService
from src.storage.task_attachments import TaskAttachmentStorage

FILE_NAME = "brief.txt"
FILE_CONTENT = "Содержимое импортируемого документа.".encode()


def build_import_service(
    session: AsyncSession,
    storage: TaskAttachmentStorage,
    *,
    links_service: DocumentLinksService | None = None,
) -> TaskDocumentImportService:
    """Собирает импорт на реальных репозиториях и локальном хранилище."""
    unit_of_work = UnitOfWork(session)
    events = KnowledgeEvents(
        repository=KnowledgeIndexJobsRepository(session),
        enabled=False,
    )
    attachments = TaskAttachmentsService(
        attachments_repository=TaskAttachmentsRepository(session),
        tasks_repository=TasksRepository(session),
        storage=storage,
        knowledge_events=events,
        unit_of_work=unit_of_work,
    )
    documents = DocumentsService(
        documents_repository=DocumentsRepository(session),
        projects_repository=ProjectsRepository(session),
        knowledge_events=events,
        unit_of_work=unit_of_work,
    )
    links = links_service or DocumentLinksService(
        document_links_repository=DocumentLinksRepository(session),
        documents_repository=DocumentsRepository(session),
        tasks_repository=TasksRepository(session),
        projects_repository=ProjectsRepository(session),
        members_repository=ProjectMembersRepository(session),
    )
    db = TaskDocumentImportScope(
        tasks=TasksRepository(session),
        attachments=attachments,
        documents=documents,
        links=links,
        unit_of_work=unit_of_work,
    )

    @asynccontextmanager
    async def scope():
        """Одна и та же сессия теста: тест проверяет атомарность, не пул."""
        yield db

    return TaskDocumentImportService(
        scope=scope,
        attachment_storage=storage,
        vision=DisabledVisionCapability(),
        extract_max_chars=350_000,
        max_file_size=10 * 1024 * 1024,
    )


async def make_membership(session: AsyncSession, project: Project) -> None:
    """Делает владельца участником: связь документа проверяет членство."""
    await ProjectMembersRepository(session).save(
        data={
            "project_id": project.id,
            "user_id": project.owner_id,
            "role": ProjectRole.OWNER,
        }
    )


async def make_task(session: AsyncSession, project: Project, stage: ProjectStage):
    """Создаёт задачу, в которую идёт импорт."""
    return await TasksRepository(session).save(
        data={
            "project_id": project.id,
            "stage_id": stage.id,
            "number": 900,
            "title": "Задача импорта",
            "position": 9000.0,
        }
    )


async def count_rows(session: AsyncSession, model) -> int:
    """Считает строки таблицы в текущей транзакции."""
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)


@pytest.mark.asyncio
async def test_successful_import_writes_all_three_rows(
    db_session: AsyncSession,
    project: Project,
    stage: ProjectStage,
    tmp_path,
) -> None:
    """Успешный импорт создаёт оригинал, документ и связь."""
    await make_membership(db_session, project)
    task = await make_task(db_session, project, stage)
    service = build_import_service(db_session, TaskAttachmentStorage(tmp_path))

    result = await service.import_file(
        task_id=task.id,
        user_id=project.owner_id,
        file_name=FILE_NAME,
        content_type="text/plain",
        content=FILE_CONTENT,
    )

    assert result.attachment.original_name == FILE_NAME
    assert await count_rows(db_session, TaskAttachment) == 1
    assert await count_rows(db_session, Document) == 1
    assert await count_rows(db_session, DocumentLink) == 1


@pytest.mark.asyncio
async def test_failure_on_last_step_leaves_no_rows_at_all(
    db_session: AsyncSession,
    project: Project,
    stage: ProjectStage,
    tmp_path,
) -> None:
    """Сбой на последнем шаге не оставляет ни одной частичной записи.

    Именно этого не давали три независимых commit: оригинал и документ
    успевали зафиксироваться и жили дальше сами по себе.
    """
    task = await make_task(db_session, project, stage)
    failing_links = AsyncMock(spec=DocumentLinksService)
    failing_links.create_link.side_effect = DocumentLinksServiceError("связь не создана")
    service = build_import_service(
        db_session,
        TaskAttachmentStorage(tmp_path),
        links_service=failing_links,
    )

    with pytest.raises(TaskDocumentStepFailedError):
        await service.import_file(
            task_id=task.id,
            user_id=project.owner_id,
            file_name=FILE_NAME,
            content_type="text/plain",
            content=FILE_CONTENT,
        )

    assert await count_rows(db_session, TaskAttachment) == 0
    assert await count_rows(db_session, Document) == 0
    assert await count_rows(db_session, DocumentLink) == 0


@pytest.mark.asyncio
async def test_failed_import_removes_the_physical_file(
    db_session: AsyncSession,
    project: Project,
    stage: ProjectStage,
    tmp_path,
) -> None:
    """Файл на диске удаляется: его откат транзакции не затрагивает."""
    task = await make_task(db_session, project, stage)
    storage = TaskAttachmentStorage(tmp_path)
    failing_links = AsyncMock(spec=DocumentLinksService)
    failing_links.create_link.side_effect = DocumentLinksServiceError("связь не создана")
    service = build_import_service(db_session, storage, links_service=failing_links)

    with pytest.raises(TaskDocumentStepFailedError):
        await service.import_file(
            task_id=task.id,
            user_id=project.owner_id,
            file_name=FILE_NAME,
            content_type="text/plain",
            content=FILE_CONTENT,
        )

    stored_files = [path for path in tmp_path.rglob("*") if path.is_file()]
    assert not stored_files, f"После отката остался файл-сирота: {stored_files}"


@pytest.mark.asyncio
async def test_rejected_format_writes_nothing_and_stores_no_file(
    db_session: AsyncSession,
    project: Project,
    stage: ProjectStage,
    tmp_path,
) -> None:
    """Неподдерживаемый формат отсекается до любой записи."""
    task = await make_task(db_session, project, stage)
    service = build_import_service(db_session, TaskAttachmentStorage(tmp_path))

    with pytest.raises(Exception):  # noqa: B017 - проверяется отсутствие записей
        await service.import_file(
            task_id=task.id,
            user_id=project.owner_id,
            file_name="archive.zip",
            content_type="application/zip",
            content=b"PK\x03\x04",
        )

    assert await count_rows(db_session, TaskAttachment) == 0
    assert await count_rows(db_session, Document) == 0
    assert not [path for path in tmp_path.rglob("*") if path.is_file()]

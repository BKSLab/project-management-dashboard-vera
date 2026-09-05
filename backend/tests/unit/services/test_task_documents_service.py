from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.clients.vision import DisabledVisionCapability
from src.exceptions.documents import DocumentsServiceError
from src.exceptions.task_documents import TaskDocumentStepFailedError
from src.repositories.tasks import TasksRepository
from src.repositories.unit_of_work import UnitOfWork
from src.schemas.document_links import DocumentLinkSchema
from src.schemas.documents import DocumentDetailSchema
from src.schemas.task_attachments import TaskAttachmentSchema
from src.services.db_scope import TaskDocumentImportScope
from src.services.document_links import DocumentLinksService
from src.services.documents import DocumentsService
from src.services.task_attachments import StoredAttachment, TaskAttachmentsService
from src.services.task_documents import TaskDocumentImportService
from src.storage.task_attachments import TaskAttachmentStorage


def build_service():
    tasks = AsyncMock(spec=TasksRepository)
    tasks.get_by_id.return_value = SimpleNamespace(id=8, project_id=2)
    attachments = AsyncMock(spec=TaskAttachmentsService)
    attachments.max_file_size = 10 * 1024 * 1024
    attachments.save_in_transaction.return_value = StoredAttachment(
        attachment=TaskAttachmentSchema(
            id=10,
            task_id=8,
            original_name="brief.txt",
            content_type="text/plain",
            size=5,
            created_at=datetime.now(UTC),
            content_url="/content",
            previewable=False,
        ),
        storage_key="tasks/8/stored.txt",
    )
    documents = AsyncMock(spec=DocumentsService)
    documents.create_document.return_value = DocumentDetailSchema(
        id=11,
        project_id=2,
        slug="brief-txt",
        title="brief.txt",
        content_md="# brief.txt\n\nhello",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        search_match_source=None,
        search_title=None,
        search_excerpt=None,
    )
    links = AsyncMock(spec=DocumentLinksService)
    links.create_link.return_value = DocumentLinkSchema(id=12, document_id=11, task_id=8)
    unit_of_work = AsyncMock(spec=UnitOfWork)
    storage = AsyncMock(spec=TaskAttachmentStorage)
    db = TaskDocumentImportScope(
        tasks=tasks,
        attachments=attachments,
        documents=documents,
        links=links,
        unit_of_work=unit_of_work,
    )

    @asynccontextmanager
    async def scope():
        yield db

    service = TaskDocumentImportService(
        scope=scope,
        attachment_storage=storage,
        vision=DisabledVisionCapability(),
        extract_max_chars=350_000,
        max_file_size=10 * 1024 * 1024,
    )
    return service, attachments, documents, links, unit_of_work, storage


@pytest.mark.asyncio
async def test_import_file_creates_attachment_document_and_link() -> None:
    service, attachments, documents, links, unit_of_work, storage = build_service()

    result = await service.import_file(
        task_id=8,
        user_id=4,
        file_name="brief.txt",
        content_type="text/plain",
        content=b"hello",
    )

    assert result.document.id == 11
    saved = attachments.save_in_transaction.await_args.kwargs
    assert saved["index_for_knowledge"] is False
    # Все три записи фиксируются одним commit владельца сценария.
    unit_of_work.commit.assert_awaited_once_with()
    assert documents.create_document.await_args.kwargs["content_md"] == "# brief.txt\n\nhello"
    links.create_link.assert_awaited_once_with(
        document_id=11,
        task_id=8,
        user_id=4,
        commit=False,
    )


@pytest.mark.asyncio
async def test_import_file_removes_attachment_when_document_creation_fails() -> None:
    service, attachments, documents, links, unit_of_work, storage = build_service()
    documents.create_document.side_effect = DocumentsServiceError("БД недоступна")

    # Наружу уходит ошибка верхнего сервиса: эндпоинт знает одну иерархию.
    with pytest.raises(TaskDocumentStepFailedError) as error:
        await service.import_file(
            task_id=8,
            user_id=4,
            file_name="brief.txt",
            content_type="text/plain",
            content=b"hello",
        )

    assert error.value.status_code == DocumentsServiceError("x").status_code
    links.create_link.assert_not_awaited()
    # Промежуточные строки снимает откат, а не компенсирующее удаление.
    unit_of_work.rollback.assert_awaited_once_with()
    unit_of_work.commit.assert_not_awaited()
    attachments.delete_attachment.assert_not_awaited()
    documents.delete_document.assert_not_awaited()
    # Физический файл транзакция откатить не может — его удаляем явно.
    storage.delete.assert_awaited_once_with("tasks/8/stored.txt")

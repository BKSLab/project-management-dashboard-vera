from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.exceptions.documents import DocumentsServiceError
from src.repositories.tasks import TasksRepository
from src.schemas.document_links import DocumentLinkSchema
from src.schemas.documents import DocumentDetailSchema
from src.schemas.task_attachments import TaskAttachmentSchema
from src.services.document_links import DocumentLinksService
from src.services.documents import DocumentsService
from src.services.task_attachments import TaskAttachmentsService
from src.services.task_documents import TaskDocumentImportService


def build_service():
    tasks = AsyncMock(spec=TasksRepository)
    tasks.get_by_id.return_value = SimpleNamespace(id=8, project_id=2)
    attachments = AsyncMock(spec=TaskAttachmentsService)
    attachments.max_file_size = 10 * 1024 * 1024
    attachments.upload_attachment.return_value = TaskAttachmentSchema(
        id=10,
        task_id=8,
        original_name="brief.txt",
        content_type="text/plain",
        size=5,
        created_at=datetime.now(UTC),
        content_url="/content",
        previewable=False,
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
    runtime = SimpleNamespace(vision_client=None)
    service = TaskDocumentImportService(
        tasks_repository=tasks,
        attachments_service=attachments,
        documents_service=documents,
        links_service=links,
        runtime=runtime,
    )
    return service, attachments, documents, links


@pytest.mark.asyncio
async def test_import_file_creates_attachment_document_and_link() -> None:
    service, attachments, documents, links = build_service()

    result = await service.import_file(
        task_id=8,
        user_id=4,
        file_name="brief.txt",
        content_type="text/plain",
        content=b"hello",
    )

    assert result.document.id == 11
    assert attachments.upload_attachment.await_args.kwargs["index_for_knowledge"] is False
    assert documents.create_document.await_args.kwargs["content_md"] == "# brief.txt\n\nhello"
    links.create_link.assert_awaited_once_with(document_id=11, task_id=8, user_id=4)


@pytest.mark.asyncio
async def test_import_file_removes_attachment_when_document_creation_fails() -> None:
    service, attachments, documents, links = build_service()
    documents.create_document.side_effect = DocumentsServiceError("БД недоступна")

    with pytest.raises(DocumentsServiceError):
        await service.import_file(
            task_id=8,
            user_id=4,
            file_name="brief.txt",
            content_type="text/plain",
            content=b"hello",
        )

    links.create_link.assert_not_awaited()
    attachments.delete_attachment.assert_awaited_once_with(task_id=8, attachment_id=10)

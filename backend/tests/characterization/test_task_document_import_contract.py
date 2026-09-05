"""Контракт импорта документа в задачу: успех, отказ и отсутствие остатков.

Этап 5 делает импорт одной транзакцией вместо трёх независимых commit с
best-effort компенсацией. Механизм меняется, наблюдаемый инвариант — нет:
клиент получает тот же ответ, а после неуспешного импорта в системе не
остаётся ни одной частично созданной сущности.
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from main import app
from src.dependencies.services import get_task_document_import_service
from src.exceptions.documents import DocumentsServiceError
from src.exceptions.task_attachments import (
    TaskAttachmentTooLargeError,
    TaskDocumentImportError,
)
from src.repositories.tasks import TasksRepository
from src.schemas.document_links import DocumentLinkSchema
from src.schemas.documents import DocumentDetailSchema
from src.schemas.task_attachments import TaskAttachmentSchema
from src.schemas.task_documents import TaskDocumentImportSchema
from src.services.document_links import DocumentLinksService
from src.services.documents import DocumentsService
from src.services.task_attachments import TaskAttachmentsService
from src.services.task_documents import TaskDocumentImportService

IMPORT_PATH = "/api/v1/tasks/8/documents/import"


def _attachment() -> TaskAttachmentSchema:
    """Метаданные сохранённого оригинала."""
    return TaskAttachmentSchema(
        id=10,
        task_id=8,
        original_name="brief.txt",
        content_type="text/plain",
        size=5,
        created_at=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
        content_url="/api/v1/tasks/8/attachments/10/content",
        previewable=False,
    )


def _document() -> DocumentDetailSchema:
    """Документ проекта, полученный из файла."""
    return DocumentDetailSchema(
        id=11,
        project_id=2,
        slug="brief-txt",
        title="brief.txt",
        content_md="# brief.txt\n\nhello",
        created_at=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
        updated_at=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
        search_match_source=None,
        search_title=None,
        search_excerpt=None,
    )


def _link() -> DocumentLinkSchema:
    """Связь документа с задачей."""
    return DocumentLinkSchema(id=12, document_id=11, task_id=8)


class FakeImportService:
    """Верхний сервис импорта с заданным результатом."""

    def __init__(self, *, result=None, error=None) -> None:
        self.result = result
        self.error = error
        self.max_file_size = 10 * 1024 * 1024

    async def import_file(self, **kwargs) -> TaskDocumentImportSchema:
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


def _install(service: FakeImportService) -> None:
    """Ставит двойник сервиса импорта в граф зависимостей."""
    app.dependency_overrides[get_task_document_import_service] = lambda: service


async def test_successful_import_returns_all_three_entities(
    api_client: AsyncClient,
) -> None:
    """Успешный импорт отвечает 201 и отдаёт оригинал, документ и связь."""
    _install(
        FakeImportService(
            result=TaskDocumentImportSchema(
                attachment=_attachment(),
                document=_document(),
                link=_link(),
            )
        )
    )

    response = await api_client.post(
        IMPORT_PATH,
        files={"file": ("brief.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"attachment", "document", "link"}
    assert body["attachment"]["id"] == 10
    assert body["document"]["id"] == 11
    assert body["link"] == {"id": 12, "document_id": 11, "task_id": 8}


@pytest.mark.parametrize(
    "error",
    [
        TaskDocumentImportError("Этот формат нельзя преобразовать в документ проекта."),
        TaskAttachmentTooLargeError(max_size_mb=10),
        DocumentsServiceError("сбой создания документа"),
    ],
    ids=["неподдерживаемый формат", "слишком большой файл", "сбой вложенного сервиса"],
)
async def test_failed_import_keeps_status_and_detail(
    api_client: AsyncClient,
    error: Exception,
) -> None:
    """Отказ импорта отвечает статусом и формулировкой доменной ошибки."""
    _install(FakeImportService(error=error))

    response = await api_client.post(
        IMPORT_PATH,
        files={"file": ("brief.txt", b"hello", "text/plain")},
    )

    assert response.status_code == error.status_code
    assert response.json() == {"detail": error.detail}


def _build_service(*, link_error: Exception | None = None):
    """Собирает сервис импорта на двойниках вложенных сервисов."""
    tasks = AsyncMock(spec=TasksRepository)
    tasks.get_by_id.return_value = SimpleNamespace(id=8, project_id=2)

    attachments = AsyncMock(spec=TaskAttachmentsService)
    attachments.max_file_size = 10 * 1024 * 1024
    attachments.upload_attachment.return_value = _attachment()

    documents = AsyncMock(spec=DocumentsService)
    documents.create_document.return_value = _document()

    links = AsyncMock(spec=DocumentLinksService)
    if link_error is not None:
        links.create_link.side_effect = link_error
    else:
        links.create_link.return_value = _link()

    service = TaskDocumentImportService(
        tasks_repository=tasks,
        attachments_service=attachments,
        documents_service=documents,
        links_service=links,
        runtime=SimpleNamespace(vision_client=None),
    )
    return service, attachments, documents, links


async def test_import_leaves_nothing_behind_when_last_step_fails() -> None:
    """Инвариант: после неуспешного импорта не остаётся частичных сущностей.

    Сейчас это достигается компенсацией уже сохранённых записей, после
    этапа 5 — единой транзакцией. Проверяется результат, а не механизм.
    """
    service, attachments, documents, _ = _build_service(
        link_error=DocumentsServiceError("связь не создана")
    )

    with pytest.raises(DocumentsServiceError):
        await service.import_file(
            task_id=8,
            user_id=1,
            file_name="brief.txt",
            content_type="text/plain",
            content=b"hello",
        )

    documents.delete_document.assert_awaited_once_with(document_id=11)
    attachments.delete_attachment.assert_awaited_once_with(task_id=8, attachment_id=10)


async def test_import_creates_attachment_document_and_link_in_order() -> None:
    """Успешный сценарий создаёт все три сущности и ничего не удаляет."""
    service, attachments, documents, links = _build_service()

    result = await service.import_file(
        task_id=8,
        user_id=1,
        file_name="brief.txt",
        content_type="text/plain",
        content=b"hello",
    )

    assert result.attachment.id == 10
    assert result.document.id == 11
    assert result.link.id == 12
    attachments.upload_attachment.assert_awaited_once()
    documents.create_document.assert_awaited_once()
    links.create_link.assert_awaited_once()
    documents.delete_document.assert_not_awaited()
    attachments.delete_attachment.assert_not_awaited()


async def test_unsupported_extension_is_rejected_before_any_write() -> None:
    """Неподдерживаемый формат отсекается до создания чего-либо."""
    service, attachments, documents, links = _build_service()

    with pytest.raises(TaskDocumentImportError):
        await service.import_file(
            task_id=8,
            user_id=1,
            file_name="archive.zip",
            content_type="application/zip",
            content=b"PK\x03\x04",
        )

    attachments.upload_attachment.assert_not_awaited()
    documents.create_document.assert_not_awaited()
    links.create_link.assert_not_awaited()

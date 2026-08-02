from unittest.mock import AsyncMock

import pytest

from src.exceptions.document_links import (
    DocumentLinkAlreadyExistsError,
    DocumentLinkAlreadyExistsRepositoryError,
    DocumentLinkInvalidError,
    DocumentLinkNotFoundError,
    DocumentLinksRepositoryError,
    DocumentLinksServiceError,
)
from src.repositories.document_links import DocumentLinksRepository
from src.repositories.documents import DocumentsRepository
from src.repositories.kanban_tasks import KanbanTasksRepository
from src.repositories.wbs import WbsRepository
from src.services.document_links import DocumentLinksService


def make_service() -> DocumentLinksService:
    """Создаёт сервис связей с репозиториями-дублёрами."""
    return DocumentLinksService(
        document_links_repository=AsyncMock(spec=DocumentLinksRepository),
        documents_repository=AsyncMock(spec=DocumentsRepository),
        tasks_repository=AsyncMock(spec=KanbanTasksRepository),
        wbs_repository=AsyncMock(spec=WbsRepository),
    )


@pytest.mark.asyncio
async def test_create_link_with_two_targets_raises_invalid_error() -> None:
    service = make_service()

    with pytest.raises(DocumentLinkInvalidError) as exc_info:
        await service.create_link(document_id=1, kanban_task_id=2, wbs_item_id=3)

    assert exc_info.value.status_code == 422
    service.document_links_repository.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_link_when_missing_raises_not_found() -> None:
    service = make_service()
    service.document_links_repository.get_by_id.return_value = None

    with pytest.raises(DocumentLinkNotFoundError) as exc_info:
        await service.delete_link(link_id=999)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_create_link_when_duplicate_raises_conflict() -> None:
    service = make_service()
    service.documents_repository.get_by_slug_or_id.return_value = object()
    service.tasks_repository.get_by_id.return_value = object()
    service.document_links_repository.create.side_effect = DocumentLinkAlreadyExistsRepositoryError(
        document_id=1
    )

    with pytest.raises(DocumentLinkAlreadyExistsError) as exc_info:
        await service.create_link(document_id=1, kanban_task_id=2, wbs_item_id=None)

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_get_links_wraps_repository_error() -> None:
    service = make_service()
    service.document_links_repository.get_for_document.side_effect = DocumentLinksRepositoryError(
        "БД недоступна"
    )

    with pytest.raises(DocumentLinksServiceError) as exc_info:
        await service.get_links_for_document(document_id=1)

    assert exc_info.value.status_code == 500

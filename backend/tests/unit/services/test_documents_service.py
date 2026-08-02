from unittest.mock import AsyncMock

import pytest

from src.exceptions.documents import (
    DocumentNotFoundError,
    DocumentSlugAlreadyExistsRepositoryError,
    DocumentSlugConflictError,
    DocumentsRepositoryError,
    DocumentsServiceError,
)
from src.repositories.documents import DocumentsRepository
from src.services.documents import DocumentsService


@pytest.mark.asyncio
async def test_get_document_by_slug_when_missing_raises_not_found() -> None:
    repository = AsyncMock(spec=DocumentsRepository)
    repository.get_by_slug.return_value = None
    service = DocumentsService(documents_repository=repository)

    with pytest.raises(DocumentNotFoundError) as exc_info:
        await service.get_document_by_slug(slug="missing")

    assert exc_info.value.status_code == 404
    assert "missing" in exc_info.value.detail


@pytest.mark.asyncio
async def test_create_document_when_unique_constraint_races_raises_conflict() -> None:
    repository = AsyncMock(spec=DocumentsRepository)
    repository.get_by_slug.return_value = None
    repository.create.side_effect = DocumentSlugAlreadyExistsRepositoryError(slug="roadmap")
    service = DocumentsService(documents_repository=repository)

    with pytest.raises(DocumentSlugConflictError) as exc_info:
        await service.create_document(title="Roadmap", slug="roadmap", content_md="Текст")

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_get_documents_wraps_repository_error() -> None:
    repository = AsyncMock(spec=DocumentsRepository)
    repository.get_all.side_effect = DocumentsRepositoryError("БД недоступна")
    service = DocumentsService(documents_repository=repository)

    with pytest.raises(DocumentsServiceError) as exc_info:
        await service.get_document_list()

    assert exc_info.value.status_code == 500

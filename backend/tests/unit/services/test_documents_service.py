from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.exceptions.documents import (
    DocumentNotFoundError,
    DocumentSlugAlreadyExistsRepositoryError,
    DocumentSlugConflictError,
    DocumentsRepositoryError,
    DocumentsServiceError,
)
from src.exceptions.projects import ProjectNotFoundError
from src.repositories.documents import DocumentsRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.unit_of_work import UnitOfWork
from src.services.documents import DocumentsService


def make_document(slug: str = "roadmap") -> SimpleNamespace:
    """Возвращает дублёр документа со всеми полями схемы ответа."""
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=3,
        project_id=1,
        slug=slug,
        title="Roadmap",
        content_md="Текст",
        created_at=now,
        updated_at=now,
        search_match_source=None,
        search_title=None,
        search_excerpt=None,
    )


def build_service(
    documents_repository: AsyncMock,
    projects_repository: AsyncMock | None = None,
) -> DocumentsService:
    """Собирает сервис документов с подменёнными репозиториями."""
    projects = projects_repository or AsyncMock(spec=ProjectsRepository)
    if projects_repository is None:
        projects.get_by_id.return_value = SimpleNamespace(id=1, key="PROJ")
    return DocumentsService(
        documents_repository=documents_repository,
        projects_repository=projects,
        unit_of_work=AsyncMock(spec=UnitOfWork),
    )


@pytest.mark.asyncio
async def test_get_document_when_missing_raises_not_found() -> None:
    repository = AsyncMock(spec=DocumentsRepository)
    repository.get_by_id.return_value = None

    with pytest.raises(DocumentNotFoundError) as exc_info:
        await build_service(repository).get_document(document_id=999)

    assert exc_info.value.status_code == 404
    assert "999" in exc_info.value.detail


@pytest.mark.asyncio
async def test_create_document_in_missing_project_raises_not_found() -> None:
    repository = AsyncMock(spec=DocumentsRepository)
    projects_repository = AsyncMock(spec=ProjectsRepository)
    projects_repository.get_by_id.return_value = None
    service = build_service(repository, projects_repository)

    with pytest.raises(ProjectNotFoundError) as exc_info:
        await service.create_document(
            project_id=42,
            title="Roadmap",
            slug=None,
            content_md="Текст",
        )

    assert exc_info.value.status_code == 404
    repository.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_document_appends_suffix_to_busy_slug() -> None:
    repository = AsyncMock(spec=DocumentsRepository)
    repository.get_by_project_slug.side_effect = [SimpleNamespace(id=1), None]
    repository.create.return_value = make_document(slug="roadmap-2")

    await build_service(repository).create_document(
        project_id=1,
        title="Roadmap",
        slug="roadmap",
        content_md="Текст",
    )

    assert repository.create.await_args.kwargs["data"]["slug"] == "roadmap-2"


@pytest.mark.asyncio
async def test_create_document_when_unique_constraint_races_raises_conflict() -> None:
    repository = AsyncMock(spec=DocumentsRepository)
    repository.get_by_project_slug.return_value = None
    repository.create.side_effect = DocumentSlugAlreadyExistsRepositoryError(slug="roadmap")

    with pytest.raises(DocumentSlugConflictError) as exc_info:
        await build_service(repository).create_document(
            project_id=1,
            title="Roadmap",
            slug="roadmap",
            content_md="Текст",
        )

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_get_documents_wraps_repository_error() -> None:
    repository = AsyncMock(spec=DocumentsRepository)
    repository.get_by_project.side_effect = DocumentsRepositoryError("БД недоступна")

    with pytest.raises(DocumentsServiceError) as exc_info:
        await build_service(repository).get_document_list(project_id=1)

    assert exc_info.value.status_code == 500

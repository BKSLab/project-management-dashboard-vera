from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.exceptions.document_links import (
    DocumentLinkAlreadyExistsError,
    DocumentLinkAlreadyExistsRepositoryError,
    DocumentLinkNotFoundError,
    DocumentLinkProjectMismatchError,
    DocumentLinksRepositoryError,
    DocumentLinksServiceError,
)
from src.exceptions.documents import DocumentNotFoundError
from src.exceptions.tasks import TaskNotFoundError
from src.repositories.document_links import DocumentLinksRepository
from src.repositories.documents import DocumentsRepository
from src.repositories.project_members import ProjectMembersRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.tasks import TasksRepository
from src.services.document_links import DocumentLinksService

USER_ID = 1


def build_service(
    links_repository: AsyncMock | None = None,
    documents_repository: AsyncMock | None = None,
    tasks_repository: AsyncMock | None = None,
) -> DocumentLinksService:
    """Собирает сервис связей документов с подменёнными репозиториями."""
    projects_repository = AsyncMock(spec=ProjectsRepository)
    projects_repository.get_by_id.return_value = SimpleNamespace(id=1, key="PROJ")
    members_repository = AsyncMock(spec=ProjectMembersRepository)
    members_repository.get.return_value = SimpleNamespace(project_id=1, user_id=USER_ID)
    return DocumentLinksService(
        document_links_repository=links_repository or AsyncMock(spec=DocumentLinksRepository),
        documents_repository=documents_repository or AsyncMock(spec=DocumentsRepository),
        tasks_repository=tasks_repository or AsyncMock(spec=TasksRepository),
        projects_repository=projects_repository,
        members_repository=members_repository,
    )


@pytest.mark.asyncio
async def test_create_link_rejects_objects_from_different_projects() -> None:
    documents_repository = AsyncMock(spec=DocumentsRepository)
    documents_repository.get_by_id.return_value = SimpleNamespace(id=1, project_id=1)
    tasks_repository = AsyncMock(spec=TasksRepository)
    tasks_repository.get_by_id.return_value = SimpleNamespace(id=2, project_id=5)
    links_repository = AsyncMock(spec=DocumentLinksRepository)
    service = build_service(links_repository, documents_repository, tasks_repository)

    with pytest.raises(DocumentLinkProjectMismatchError) as exc_info:
        await service.create_link(document_id=1, task_id=2, user_id=USER_ID)

    assert exc_info.value.status_code == 409
    links_repository.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_link_with_missing_document_raises_not_found() -> None:
    documents_repository = AsyncMock(spec=DocumentsRepository)
    documents_repository.get_by_id.return_value = None

    with pytest.raises(DocumentNotFoundError):
        await build_service(documents_repository=documents_repository).create_link(
            document_id=1,
            task_id=2,
            user_id=USER_ID,
        )


@pytest.mark.asyncio
async def test_create_link_with_missing_task_raises_not_found() -> None:
    documents_repository = AsyncMock(spec=DocumentsRepository)
    documents_repository.get_by_id.return_value = SimpleNamespace(id=1, project_id=1)
    tasks_repository = AsyncMock(spec=TasksRepository)
    tasks_repository.get_by_id.return_value = None
    service = build_service(
        documents_repository=documents_repository, tasks_repository=tasks_repository
    )

    with pytest.raises(TaskNotFoundError):
        await service.create_link(document_id=1, task_id=999, user_id=USER_ID)


@pytest.mark.asyncio
async def test_create_link_when_duplicate_races_raises_conflict() -> None:
    documents_repository = AsyncMock(spec=DocumentsRepository)
    documents_repository.get_by_id.return_value = SimpleNamespace(id=1, project_id=1)
    tasks_repository = AsyncMock(spec=TasksRepository)
    tasks_repository.get_by_id.return_value = SimpleNamespace(id=2, project_id=1)
    links_repository = AsyncMock(spec=DocumentLinksRepository)
    links_repository.create.side_effect = DocumentLinkAlreadyExistsRepositoryError(document_id=1)
    service = build_service(links_repository, documents_repository, tasks_repository)

    with pytest.raises(DocumentLinkAlreadyExistsError) as exc_info:
        await service.create_link(document_id=1, task_id=2, user_id=USER_ID)

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_get_links_for_document_builds_task_keys() -> None:
    documents_repository = AsyncMock(spec=DocumentsRepository)
    documents_repository.get_by_id.return_value = SimpleNamespace(id=1, project_id=1)
    links_repository = AsyncMock(spec=DocumentLinksRepository)
    links_repository.get_for_document.return_value = [SimpleNamespace(id=9, task_id=2)]
    tasks_repository = AsyncMock(spec=TasksRepository)
    tasks_repository.get_by_ids.return_value = [
        SimpleNamespace(id=2, number=142, title="Фильтрация"),
    ]
    service = build_service(links_repository, documents_repository, tasks_repository)

    result = await service.get_links_for_document(document_id=1)

    assert result[0].key == "PROJ-142"
    assert result[0].link_id == 9


@pytest.mark.asyncio
async def test_delete_link_when_missing_raises_not_found() -> None:
    links_repository = AsyncMock(spec=DocumentLinksRepository)
    links_repository.get_by_id.return_value = None

    with pytest.raises(DocumentLinkNotFoundError) as exc_info:
        await build_service(links_repository).delete_link(link_id=999)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_links_for_task_wraps_repository_error() -> None:
    tasks_repository = AsyncMock(spec=TasksRepository)
    tasks_repository.get_by_id.return_value = SimpleNamespace(id=2, project_id=1)
    links_repository = AsyncMock(spec=DocumentLinksRepository)
    links_repository.get_for_task.side_effect = DocumentLinksRepositoryError("БД недоступна")
    service = build_service(links_repository, tasks_repository=tasks_repository)

    with pytest.raises(DocumentLinksServiceError) as exc_info:
        await service.get_links_for_task(task_id=2)

    assert exc_info.value.status_code == 500

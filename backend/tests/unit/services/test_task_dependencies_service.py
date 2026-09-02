from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.db.models.task_dependencies import TaskDependencyType
from src.exceptions.task_dependencies import (
    TaskDependencyCycleError,
    TaskDependencyForeignProjectError,
    TaskDependencySelfReferenceError,
)
from src.repositories.projects import ProjectsRepository
from src.repositories.task_dependencies import TaskDependenciesRepository
from src.repositories.tasks import TasksRepository
from src.repositories.unit_of_work import UnitOfWork
from src.services.task_dependencies import TaskDependenciesService


def dependency(
    dependency_id: int = 1,
    predecessor_id: int = 1,
    successor_id: int = 2,
):
    return SimpleNamespace(
        id=dependency_id,
        project_id=1,
        predecessor_task_id=predecessor_id,
        successor_task_id=successor_id,
        dependency_type=TaskDependencyType.FINISH_TO_START,
        lag_days=0,
        created_at=datetime.now(UTC),
    )


def build_service():
    dependencies = AsyncMock(spec=TaskDependenciesRepository)
    dependencies.get_by_project.return_value = []
    projects = AsyncMock(spec=ProjectsRepository)
    projects.get_by_id.return_value = SimpleNamespace(id=1)
    tasks = AsyncMock(spec=TasksRepository)
    tasks.get_by_ids.return_value = [
        SimpleNamespace(id=1, project_id=1),
        SimpleNamespace(id=2, project_id=1),
        SimpleNamespace(id=3, project_id=1),
    ]
    uow = AsyncMock(spec=UnitOfWork)
    return (
        TaskDependenciesService(dependencies, projects, tasks, uow),
        dependencies,
        tasks,
        uow,
    )


@pytest.mark.asyncio
async def test_create_finish_to_start_dependency_commits_through_uow() -> None:
    service, repository, _, uow = build_service()
    repository.save.return_value = dependency()

    result = await service.create_dependency(
        1,
        {
            "predecessor_task_id": 1,
            "successor_task_id": 2,
            "dependency_type": TaskDependencyType.FINISH_TO_START,
            "lag_days": 0,
        },
    )

    assert result.dependency_type is TaskDependencyType.FINISH_TO_START
    repository.save.assert_awaited_once()
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_dependency_rejects_self_reference_without_db_write() -> None:
    service, repository, _, uow = build_service()

    with pytest.raises(TaskDependencySelfReferenceError):
        await service.create_dependency(
            1,
            {"predecessor_task_id": 1, "successor_task_id": 1},
        )

    repository.save.assert_not_awaited()
    uow.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_dependency_rejects_task_from_another_project() -> None:
    service, repository, tasks, uow = build_service()
    tasks.get_by_ids.return_value = [
        SimpleNamespace(id=1, project_id=1),
        SimpleNamespace(id=2, project_id=9),
    ]

    with pytest.raises(TaskDependencyForeignProjectError):
        await service.create_dependency(
            1,
            {"predecessor_task_id": 1, "successor_task_id": 2},
        )

    repository.save.assert_not_awaited()
    uow.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_dependency_rejects_indirect_cycle() -> None:
    service, repository, _, uow = build_service()
    repository.get_by_project.return_value = [
        dependency(predecessor_id=1, successor_id=2),
        dependency(dependency_id=2, predecessor_id=2, successor_id=3),
    ]

    with pytest.raises(TaskDependencyCycleError):
        await service.create_dependency(
            1,
            {"predecessor_task_id": 3, "successor_task_id": 1},
        )

    repository.save.assert_not_awaited()
    uow.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_dependency_uses_same_transaction_boundary() -> None:
    service, repository, _, uow = build_service()
    item = dependency()
    repository.get_by_id.return_value = item

    await service.delete_dependency(1, item.id)

    repository.delete.assert_awaited_once_with(item)
    uow.commit.assert_awaited_once()

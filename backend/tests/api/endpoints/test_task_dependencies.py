from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from main import app
from src.db.models.task_dependencies import TaskDependencyType
from src.dependencies.services import get_task_dependencies_service
from src.exceptions.task_dependencies import TaskDependencyCycleError
from src.schemas.task_dependencies import TaskDependencySchema
from src.services.task_dependencies import TaskDependenciesService


def dependency_schema() -> TaskDependencySchema:
    return TaskDependencySchema(
        id=7,
        project_id=1,
        predecessor_task_id=10,
        successor_task_id=11,
        dependency_type=TaskDependencyType.FINISH_TO_START,
        lag_days=1,
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_create_dependency_endpoint_forwards_typed_payload(
    api_client: AsyncClient,
) -> None:
    service = AsyncMock(spec=TaskDependenciesService)
    service.create_dependency.return_value = dependency_schema()
    app.dependency_overrides[get_task_dependencies_service] = lambda: service

    response = await api_client.post(
        "/api/v1/projects/1/task-dependencies",
        json={
            "predecessor_task_id": 10,
            "successor_task_id": 11,
            "lag_days": 1,
        },
    )

    assert response.status_code == 201
    assert response.json()["dependency_type"] == "FINISH_TO_START"
    assert (
        service.create_dependency.await_args.args[1]["dependency_type"]
        is TaskDependencyType.FINISH_TO_START
    )


@pytest.mark.asyncio
async def test_dependency_endpoint_rejects_unsupported_type(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=TaskDependenciesService)
    app.dependency_overrides[get_task_dependencies_service] = lambda: service

    response = await api_client.post(
        "/api/v1/projects/1/task-dependencies",
        json={
            "predecessor_task_id": 10,
            "successor_task_id": 11,
            "dependency_type": "START_TO_START",
        },
    )

    assert response.status_code == 422
    service.create_dependency.assert_not_awaited()


@pytest.mark.asyncio
async def test_dependency_cycle_is_returned_as_conflict(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=TaskDependenciesService)
    service.create_dependency.side_effect = TaskDependencyCycleError()
    app.dependency_overrides[get_task_dependencies_service] = lambda: service

    response = await api_client.post(
        "/api/v1/projects/1/task-dependencies",
        json={"predecessor_task_id": 10, "successor_task_id": 11},
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_delete_dependency_endpoint_returns_no_content(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=TaskDependenciesService)
    app.dependency_overrides[get_task_dependencies_service] = lambda: service

    response = await api_client.delete("/api/v1/projects/1/task-dependencies/7")

    assert response.status_code == 204
    service.delete_dependency.assert_awaited_once_with(1, 7)

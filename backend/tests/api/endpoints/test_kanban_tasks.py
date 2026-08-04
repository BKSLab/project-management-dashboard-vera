from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from main import app
from src.dependencies.services import get_kanban_tasks_service
from src.exceptions.kanban_tasks import (
    KanbanTaskFromWbsDeleteError,
    KanbanTaskNotFoundError,
)
from src.services.kanban_tasks import KanbanTasksService

TASK_RESPONSE = {
    "id": 7,
    "wbs_item_id": None,
    "stage_id": 2,
    "title": "Тестовая задача",
    "description_md": None,
    "due_date": None,
    "position": 3000.0,
    "created_at": "2026-08-04T10:00:00Z",
    "updated_at": "2026-08-04T10:00:00Z",
}


@pytest.mark.asyncio
async def test_get_task_maps_not_found_to_404(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=KanbanTasksService)
    service.get_task.side_effect = KanbanTaskNotFoundError(task_id=999)
    app.dependency_overrides[get_kanban_tasks_service] = lambda: service

    response = await api_client.get("/api/v1/kanban/tasks/999")

    assert response.status_code == 404
    assert "999" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_task_rejects_non_positive_id(api_client: AsyncClient) -> None:
    response = await api_client.get("/api/v1/kanban/tasks/0")

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_delete_task_maps_wbs_conflict_to_409(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=KanbanTasksService)
    service.delete_task.side_effect = KanbanTaskFromWbsDeleteError(task_id=7)
    app.dependency_overrides[get_kanban_tasks_service] = lambda: service

    response = await api_client.delete("/api/v1/kanban/tasks/7")

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_move_task_accepts_stage_without_position(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=KanbanTasksService)
    service.move_task.return_value = TASK_RESPONSE
    app.dependency_overrides[get_kanban_tasks_service] = lambda: service

    response = await api_client.patch(
        "/api/v1/kanban/tasks/7/move",
        json={"stage_id": 2},
    )

    assert response.status_code == 200
    assert response.json()["stage_id"] == 2
    service.move_task.assert_awaited_once_with(task_id=7, stage_id=2, position=None)


@pytest.mark.asyncio
async def test_move_task_keeps_explicit_position_for_drag_and_drop(
    api_client: AsyncClient,
) -> None:
    service = AsyncMock(spec=KanbanTasksService)
    service.move_task.return_value = TASK_RESPONSE
    app.dependency_overrides[get_kanban_tasks_service] = lambda: service

    response = await api_client.patch(
        "/api/v1/kanban/tasks/7/move",
        json={"stage_id": 2, "position": 1500.0},
    )

    assert response.status_code == 200
    service.move_task.assert_awaited_once_with(task_id=7, stage_id=2, position=1500.0)

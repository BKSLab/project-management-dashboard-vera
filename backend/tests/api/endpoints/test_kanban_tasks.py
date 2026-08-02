from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from main import app
from src.dependencies.services import get_kanban_tasks_service
from src.exceptions.kanban_tasks import KanbanTaskFromWbsDeleteError, KanbanTaskNotFoundError
from src.services.kanban_tasks import KanbanTasksService


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

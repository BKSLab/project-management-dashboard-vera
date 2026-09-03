from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from main import app
from src.db.models.tasks import TaskPriority
from src.dependencies.services import get_wbs_nodes_service, get_wbs_suggestion_service
from src.exceptions.wbs_nodes import WbsSuggestionEmptyError, WbsSuggestionInvalidError
from src.schemas.tasks import TaskCompactSchema
from src.schemas.wbs_suggestion import (
    WbsSuggestedAssignmentSchema,
    WbsSuggestedNodeSchema,
    WbsSuggestionApplyResultSchema,
    WbsSuggestionSchema,
)
from src.services.wbs_nodes import WbsNodesService
from src.services.wbs_suggestion import WbsSuggestionService


def compact_task(
    wbs_node_id: int | None = None,
    canvas_x: float | None = None,
    canvas_y: float | None = None,
) -> TaskCompactSchema:
    """Возвращает компактную задачу в ответе размещения."""
    return TaskCompactSchema(
        id=2,
        key="PROJ-2",
        title="Задача",
        stage_id=1,
        wbs_node_id=wbs_node_id,
        wbs_position=1000.0 if wbs_node_id is not None else None,
        canvas_x=canvas_x,
        canvas_y=canvas_y,
        priority=TaskPriority.MEDIUM,
        assignee=None,
        start_date=None,
        due_date=None,
        is_done=False,
    )


@pytest.mark.asyncio
async def test_placement_endpoint_forwards_section_and_neighbour(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=WbsNodesService)
    service.place_task.return_value = compact_task(wbs_node_id=5)
    app.dependency_overrides[get_wbs_nodes_service] = lambda: service

    response = await api_client.post(
        "/api/v1/projects/1/wbs/tasks/2/placement",
        json={"wbs_node_id": 5, "before_task_id": 88},
    )

    assert response.status_code == 200
    assert response.json()["wbs_node_id"] == 5
    assert service.place_task.await_args.kwargs["before_task_id"] == 88


@pytest.mark.asyncio
async def test_placement_endpoint_puts_task_on_canvas(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=WbsNodesService)
    service.place_task.return_value = compact_task(canvas_x=420.0, canvas_y=180.0)
    app.dependency_overrides[get_wbs_nodes_service] = lambda: service

    response = await api_client.post(
        "/api/v1/projects/1/wbs/tasks/2/placement",
        json={"wbs_node_id": None, "canvas_x": 420.0, "canvas_y": 180.0},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["wbs_node_id"] is None
    assert (body["canvas_x"], body["canvas_y"]) == (420.0, 180.0)


@pytest.mark.asyncio
async def test_suggestion_endpoint_returns_draft(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=WbsSuggestionService)
    service.suggest.return_value = WbsSuggestionSchema(
        nodes=[
            WbsSuggestedNodeSchema(temp_id="n1", parent_temp_id=None, title="Аналитика"),
        ],
        assignments=[WbsSuggestedAssignmentSchema(task_id=2, node_temp_id="n1")],
        summary="Разбито по этапам.",
    )
    app.dependency_overrides[get_wbs_suggestion_service] = lambda: service

    response = await api_client.post("/api/v1/projects/1/wbs/suggestion")

    assert response.status_code == 200
    body = response.json()
    assert [item["temp_id"] for item in body["nodes"]] == ["n1"]
    assert body["assignments"][0]["task_id"] == 2


@pytest.mark.asyncio
async def test_suggestion_without_tasks_maps_to_409(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=WbsSuggestionService)
    service.suggest.side_effect = WbsSuggestionEmptyError(error_details="нет задач")
    app.dependency_overrides[get_wbs_suggestion_service] = lambda: service

    response = await api_client.post("/api/v1/projects/1/wbs/suggestion")

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_apply_suggestion_endpoint_forwards_edited_draft(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=WbsSuggestionService)
    service.apply.return_value = WbsSuggestionApplyResultSchema(
        created_nodes=1,
        assigned_tasks=1,
    )
    app.dependency_overrides[get_wbs_suggestion_service] = lambda: service

    response = await api_client.post(
        "/api/v1/projects/1/wbs/suggestion/apply",
        json={
            "nodes": [{"temp_id": "n1", "parent_temp_id": None, "title": "Аналитика"}],
            "assignments": [{"task_id": 2, "node_temp_id": "n1"}],
        },
    )

    assert response.status_code == 200
    assert response.json() == {"created_nodes": 1, "assigned_tasks": 1}
    assert [node.temp_id for node in service.apply.await_args.kwargs["nodes"]] == ["n1"]


@pytest.mark.asyncio
async def test_apply_invalid_suggestion_maps_to_422(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=WbsSuggestionService)
    service.apply.side_effect = WbsSuggestionInvalidError(reason="раздел n1 повторяется.")
    app.dependency_overrides[get_wbs_suggestion_service] = lambda: service

    response = await api_client.post(
        "/api/v1/projects/1/wbs/suggestion/apply",
        json={
            "nodes": [{"temp_id": "n1", "parent_temp_id": None, "title": "Аналитика"}],
            "assignments": [],
        },
    )

    assert response.status_code == 422
    assert "повторяется" in response.json()["detail"]

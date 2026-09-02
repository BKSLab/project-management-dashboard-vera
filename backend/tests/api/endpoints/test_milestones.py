from datetime import UTC, date, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from main import app
from src.db.models.project_milestones import ProjectMilestoneStatus
from src.dependencies.services import get_milestones_service
from src.exceptions.milestones import MilestoneNotFoundError
from src.schemas.milestones import MilestoneSchema
from src.services.milestones import MilestonesService


def milestone_schema() -> MilestoneSchema:
    now = datetime.now(UTC)
    return MilestoneSchema(
        id=3,
        project_id=1,
        title="MVP",
        due_date=date(2026, 9, 30),
        status=ProjectMilestoneStatus.PLANNED,
        wbs_node_id=None,
        description_md=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_create_milestone_endpoint_forwards_typed_payload(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=MilestonesService)
    service.create_milestone.return_value = milestone_schema()
    app.dependency_overrides[get_milestones_service] = lambda: service

    response = await api_client.post(
        "/api/v1/projects/1/milestones",
        json={"title": "MVP", "due_date": "2026-09-30"},
    )

    assert response.status_code == 201
    assert response.json()["title"] == "MVP"
    payload = service.create_milestone.await_args.args[1]
    assert payload["due_date"] == date(2026, 9, 30)


@pytest.mark.asyncio
async def test_list_milestones_endpoint(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=MilestonesService)
    service.list_milestones.return_value = [milestone_schema()]
    app.dependency_overrides[get_milestones_service] = lambda: service

    response = await api_client.get("/api/v1/projects/1/milestones")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [3]


@pytest.mark.asyncio
async def test_foreign_milestone_is_returned_as_not_found(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=MilestonesService)
    service.update_milestone.side_effect = MilestoneNotFoundError(44)
    app.dependency_overrides[get_milestones_service] = lambda: service

    response = await api_client.patch(
        "/api/v1/projects/1/milestones/44",
        json={"title": "Недоступная"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_milestone_endpoint_returns_no_content(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=MilestonesService)
    app.dependency_overrides[get_milestones_service] = lambda: service

    response = await api_client.delete("/api/v1/projects/1/milestones/3")

    assert response.status_code == 204
    service.delete_milestone.assert_awaited_once_with(1, 3)

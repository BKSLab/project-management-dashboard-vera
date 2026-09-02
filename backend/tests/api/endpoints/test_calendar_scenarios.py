from datetime import UTC, date, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from main import app
from src.dependencies.services import get_calendar_scenario_service
from src.exceptions.calendar import CalendarScenarioVersionConflictError
from src.schemas.calendar_scenarios import (
    ScenarioApplyResponseSchema,
    ScenarioPreviewResponseSchema,
)
from src.services.calendar_scenarios import CalendarScenarioService

TODAY = date(2026, 9, 2)
NOW = datetime(2026, 9, 2, 10, tzinfo=UTC)


@pytest.mark.asyncio
async def test_preview_endpoint_passes_date_only_values(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=CalendarScenarioService)
    service.preview.return_value = ScenarioPreviewResponseSchema(
        changes=[],
        conflicts=[],
        consequences_count=0,
        can_apply=False,
    )
    app.dependency_overrides[get_calendar_scenario_service] = lambda: service

    response = await api_client.post(
        "/api/v1/projects/1/calendar/scenarios/preview",
        json={
            "changes": [
                {
                    "task_id": 1,
                    "start_date": "2026-09-02",
                    "due_date": "2026-09-08",
                }
            ]
        },
    )

    assert response.status_code == 200
    change = service.preview.await_args.args[1][0]
    assert change["start_date"] == TODAY


@pytest.mark.asyncio
async def test_apply_endpoint_maps_version_conflict_to_409(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=CalendarScenarioService)
    service.apply.side_effect = CalendarScenarioVersionConflictError()
    app.dependency_overrides[get_calendar_scenario_service] = lambda: service

    response = await api_client.post(
        "/api/v1/projects/1/calendar/scenarios/apply",
        json={
            "changes": [
                {
                    "task_id": 1,
                    "start_date": "2026-09-02",
                    "due_date": "2026-09-08",
                    "expected_updated_at": NOW.isoformat(),
                }
            ]
        },
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_apply_endpoint_returns_transaction_result(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=CalendarScenarioService)
    service.apply.return_value = ScenarioApplyResponseSchema(applied_count=2, task_ids=[1, 2])
    app.dependency_overrides[get_calendar_scenario_service] = lambda: service

    response = await api_client.post(
        "/api/v1/projects/1/calendar/scenarios/apply",
        json={
            "changes": [
                {
                    "task_id": 1,
                    "start_date": "2026-09-02",
                    "due_date": "2026-09-08",
                    "expected_updated_at": NOW.isoformat(),
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json() == {"applied_count": 2, "task_ids": [1, 2]}


@pytest.mark.asyncio
async def test_preview_rejects_duplicate_tasks_at_contract_boundary(
    api_client: AsyncClient,
) -> None:
    service = AsyncMock(spec=CalendarScenarioService)
    app.dependency_overrides[get_calendar_scenario_service] = lambda: service
    change = {"task_id": 1, "start_date": "2026-09-02", "due_date": "2026-09-08"}

    response = await api_client.post(
        "/api/v1/projects/1/calendar/scenarios/preview",
        json={"changes": [change, change]},
    )

    assert response.status_code == 422
    service.preview.assert_not_awaited()

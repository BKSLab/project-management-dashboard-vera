from datetime import date
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from main import app
from src.dependencies.services import get_calendar_service
from src.exceptions.calendar import CalendarRangeError
from src.schemas.calendar import (
    CalendarProjectSchema,
    CalendarRangeSchema,
    CalendarResponseSchema,
    CalendarSummarySchema,
    UnscheduledTasksPageSchema,
)
from src.services.calendar import CalendarService

TODAY = date(2026, 9, 2)


@pytest.mark.asyncio
async def test_calendar_endpoint_forwards_range_and_filters(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=CalendarService)
    service.get_range.return_value = CalendarResponseSchema(
        range=CalendarRangeSchema(date_from=TODAY, date_to=TODAY, today=TODAY),
        project=CalendarProjectSchema(start_date=None, due_date=None),
        tasks=[],
        stages=[],
        wbs_nodes=[],
        assignees=[],
        summary=CalendarSummarySchema(overdue=0, due_soon=0, unscheduled=0, drifted=0),
        recent_changes=[],
        milestones=[],
        dependencies=[],
    )
    app.dependency_overrides[get_calendar_service] = lambda: service

    response = await api_client.get(
        "/api/v1/projects/1/calendar",
        params={
            "date_from": TODAY.isoformat(),
            "date_to": TODAY.isoformat(),
            "today": TODAY.isoformat(),
            "priority": "HIGH",
            "stage_id": 2,
        },
    )

    assert response.status_code == 200
    assert response.json()["range"]["today"] == TODAY.isoformat()
    assert service.get_range.await_args.kwargs["stage_id"] == 2
    assert service.get_range.await_args.kwargs["priority"].value == "HIGH"


@pytest.mark.asyncio
async def test_calendar_endpoint_requires_client_today(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=CalendarService)
    app.dependency_overrides[get_calendar_service] = lambda: service

    response = await api_client.get(
        "/api/v1/projects/1/calendar",
        params={"date_from": TODAY.isoformat(), "date_to": TODAY.isoformat()},
    )

    assert response.status_code == 422
    service.get_range.assert_not_awaited()


@pytest.mark.asyncio
async def test_calendar_domain_error_is_mapped_to_422(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=CalendarService)
    service.get_range.side_effect = CalendarRangeError("Некорректный диапазон.")
    app.dependency_overrides[get_calendar_service] = lambda: service

    response = await api_client.get(
        "/api/v1/projects/1/calendar",
        params={
            "date_from": TODAY.isoformat(),
            "date_to": TODAY.isoformat(),
            "today": TODAY.isoformat(),
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "Некорректный диапазон."


@pytest.mark.asyncio
async def test_unscheduled_endpoint_returns_cursor_page(api_client: AsyncClient) -> None:
    service = AsyncMock(spec=CalendarService)
    service.get_unscheduled.return_value = UnscheduledTasksPageSchema(items=[], next_cursor=42)
    app.dependency_overrides[get_calendar_service] = lambda: service

    response = await api_client.get(
        "/api/v1/projects/1/calendar/unscheduled",
        params={"today": TODAY.isoformat(), "limit": 10},
    )

    assert response.status_code == 200
    assert response.json() == {"items": [], "next_cursor": 42}
    assert service.get_unscheduled.await_args.kwargs["limit"] == 10

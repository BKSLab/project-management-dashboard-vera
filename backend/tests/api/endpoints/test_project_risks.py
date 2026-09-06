from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from main import app
from src.dependencies.services import get_project_risk_service
from src.exceptions.access import ResourceNotAvailableError
from src.exceptions.project_risks import (
    ProjectRiskNotFoundError,
    ProjectRiskOwnerMismatchError,
    ProjectRiskServiceError,
    ProjectRiskTaskMismatchError,
)
from src.schemas.project_risks import (
    ProjectRiskPageSchema,
    ProjectRiskSchema,
    ProjectRiskSummarySchema,
)
from src.services.project_risks import ProjectRiskService

BODY = {
    "title": "Задержка CRM",
    "description": "Поставщик может задержать API.",
    "probability": "HIGH",
    "impact": "HIGH",
    "response_strategy": "MITIGATE",
}


@pytest.fixture
def service():
    service = AsyncMock(spec=ProjectRiskService)
    saved = ProjectRiskSchema(
        **BODY,
        id=12,
        key="RISK-12",
        project_id=1,
        risk_level="HIGH",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service.create_risk.return_value = saved
    service.get_risk.return_value = saved
    service.update_risk.return_value = saved
    service.list_risks.return_value = ProjectRiskPageSchema(
        items=[saved], total=41, page=2, page_size=10
    )
    service.get_summary.return_value = ProjectRiskSummarySchema(total_risks=41)
    service.get_task_counts.return_value = {142: 2}
    app.dependency_overrides[get_project_risk_service] = lambda: service
    return service


async def test_create_get_patch_delete_contract_and_authenticated_actor(api_client, service):
    response = await api_client.post("/api/v1/projects/1/risks", json=BODY)
    assert response.status_code == 201
    assert response.json()["key"] == "RISK-12"
    assert response.json()["risk_level"] == "HIGH"
    assert service.create_risk.await_args.kwargs["user_id"] == 1
    assert (await api_client.get("/api/v1/projects/1/risks/12")).status_code == 200
    assert (
        await api_client.patch("/api/v1/projects/1/risks/12", json={"task_id": None})
    ).status_code == 200
    data = service.update_risk.await_args.kwargs["data"]
    assert data.model_dump(exclude_unset=True) == {"task_id": None}
    deleted = await api_client.delete("/api/v1/projects/1/risks/12")
    assert deleted.status_code == 204 and deleted.content == b""


async def test_filters_pagination_and_static_paths_are_routed_before_risk_id(api_client, service):
    response = await api_client.get(
        "/api/v1/projects/1/risks",
        params={
            "page": 2,
            "page_size": 10,
            "status": "MITIGATING",
            "probability": "HIGH",
            "impact": "MEDIUM",
            "risk_level": "HIGH",
            "owner_user_id": 15,
            "task_id": 142,
            "search": "CRM",
            "active_only": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["total"] == 41
    call = service.list_risks.await_args.kwargs
    assert call["page"] == 2 and call["page_size"] == 10
    assert call["filters"].task_id == 142 and call["filters"].active_only
    assert (await api_client.get("/api/v1/projects/1/risks/summary")).status_code == 200
    assert (await api_client.get("/api/v1/projects/1/risks/task-counts")).json() == {"142": 2}


@pytest.mark.parametrize(
    "changes",
    [
        {"risk_level": "LOW"},
        {"project_id": 2},
        {"owner_user_id": -1},
        {"probability": "73%"},
        {"description": "  "},
        {"title": "  "},
        {"description": "a\u0000b"},
    ],
)
async def test_create_rejects_derived_fields_and_invalid_values(api_client, service, changes):
    response = await api_client.post("/api/v1/projects/1/risks", json={**BODY, **changes})
    assert response.status_code == 422
    service.create_risk.assert_not_awaited()


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"status": None},
        {"probability": None},
        {"risk_level": "HIGH"},
        {"source": "AI_SUGGESTED"},
        {"title": ""},
    ],
)
async def test_patch_rejects_empty_or_invalid_changes(api_client, service, body):
    response = await api_client.patch("/api/v1/projects/1/risks/12", json=body)
    assert response.status_code == 422
    service.update_risk.assert_not_awaited()


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ProjectRiskNotFoundError(12), 404),
        (ResourceNotAvailableError(resource="Проект", resource_id=1), 404),
        (ProjectRiskTaskMismatchError(99), 422),
        (ProjectRiskOwnerMismatchError(99), 422),
        (ProjectRiskServiceError("Внутренний SQL и секрет."), 500),
    ],
)
async def test_domain_errors_map_without_leaking_internal_details(api_client, service, error, code):
    service.update_risk.side_effect = error
    response = await api_client.patch("/api/v1/projects/1/risks/12", json={"status": "CLOSED"})
    assert response.status_code == code
    assert response.json()["detail"] == error.detail
    assert "Внутренний SQL" not in response.text

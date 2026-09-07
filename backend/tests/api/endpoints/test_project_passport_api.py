"""HTTP-контракт паспорта сохраняет идентичность автора и PATCH-семантику."""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock

import pytest

from main import app
from src.dependencies.services import get_projects_service
from src.schemas.projects import ProjectSchema
from src.services.projects import ProjectsService


async def test_project_patch_passes_authenticated_author_and_explicit_empty_date(api_client):
    service = AsyncMock(spec=ProjectsService)
    service.update_project.return_value = ProjectSchema(
        id=1,
        owner_id=1,
        key="PROJ",
        name="Проект",
        status="ACTIVE",
        color="#334455",
        order_index=0,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    app.dependency_overrides[get_projects_service] = lambda: service
    response = await api_client.patch(
        "/api/v1/projects/1",
        json={
            "due_date": None,
            "expected_due_date": "2026-10-01",
            "due_date_comment": "Пересмотр",
            "updated_by_user_id": 999,
        },
    )
    assert response.status_code == 200
    service.update_project.assert_awaited_once_with(
        project_id=1,
        updated_by_user_id=1,
        data={
            "due_date": None,
            "expected_due_date": date(2026, 10, 1),
            "due_date_comment": "Пересмотр",
        },
    )


@pytest.mark.parametrize(
    "stages", [[], [{"name": " "}], [{"name": "Готово"}, {"name": " готово "}]]
)
async def test_project_creation_rejects_invalid_stage_sets(api_client, stages):
    service = AsyncMock(spec=ProjectsService)
    app.dependency_overrides[get_projects_service] = lambda: service
    response = await api_client.post(
        "/api/v1/projects", json={"key": "NEW", "name": "Проект", "stages": stages}
    )
    assert response.status_code == 422
    service.create_project.assert_not_awaited()

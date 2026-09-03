import pytest
from httpx import AsyncClient

from main import app

# Единственные адреса, доступные без входа: всё остальное закрыто.
PUBLIC_PATHS = {"/api/v1/auth/register", "/api/v1/auth/login", "/api/v1/auth/logout"}

PROTECTED_REQUESTS = [
    ("get", "/api/v1/auth/me"),
    ("get", "/api/v1/dashboard"),
    ("get", "/api/v1/projects"),
    ("post", "/api/v1/projects"),
    ("get", "/api/v1/projects/1"),
    ("get", "/api/v1/projects/1/stats"),
    ("get", "/api/v1/projects/1/members"),
    ("post", "/api/v1/projects/1/members"),
    ("delete", "/api/v1/projects/1/members/2"),
    ("get", "/api/v1/projects/1/stages"),
    ("get", "/api/v1/projects/1/tasks"),
    ("get", "/api/v1/projects/1/wbs"),
    ("post", "/api/v1/projects/1/wbs/tasks/1/placement"),
    ("post", "/api/v1/projects/1/wbs/suggestion"),
    ("post", "/api/v1/projects/1/wbs/suggestion/apply"),
    ("get", "/api/v1/projects/1/documents"),
    ("get", "/api/v1/projects/1/knowledge/status"),
    ("post", "/api/v1/projects/1/knowledge/ask"),
    ("post", "/api/v1/projects/1/knowledge/reindex"),
    ("get", "/api/v1/tasks/1"),
    ("get", "/api/v1/tasks/1/comments"),
    ("get", "/api/v1/tasks/1/activity"),
    ("get", "/api/v1/tasks/1/attachments"),
    ("get", "/api/v1/documents/1"),
    ("patch", "/api/v1/stages/1"),
    ("post", "/api/v1/document-links"),
    ("patch", "/api/v1/users/me"),
    ("get", "/api/v1/users/me/avatar"),
]


@pytest.fixture
def anonymous() -> None:
    """Снимает подмену сессии: тесты этого модуля проверяют саму стену входа."""
    app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "path"), PROTECTED_REQUESTS)
async def test_protected_endpoint_requires_login(
    api_client: AsyncClient,
    anonymous: None,
    method: str,
    path: str,
) -> None:
    request_kwargs = {"json": {}} if method in {"post", "put", "patch"} else {}
    response = await api_client.request(method.upper(), path, **request_kwargs)

    assert response.status_code == 401, f"{method.upper()} {path} доступен без входа"


@pytest.mark.asyncio
async def test_invalid_session_cookie_is_rejected(
    api_client: AsyncClient,
    anonymous: None,
) -> None:
    response = await api_client.get(
        "/api/v1/auth/me",
        cookies={"tracker_session": "not.a.valid.token"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_public_paths_are_declared_explicitly() -> None:
    """Страхует от случайного открытия эндпоинта: список публичных путей фиксирован."""
    documented = {
        route.path for route in app.routes if getattr(route, "path", "").startswith("/api/v1/auth/")
    }

    assert documented - {"/api/v1/auth/me"} == PUBLIC_PATHS

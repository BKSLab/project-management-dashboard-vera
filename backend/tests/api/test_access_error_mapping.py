"""Перевод доменных ошибок auth и access в HTTP-ответы.

Depends-слой не принимает решений: он только переводит ошибку сервиса в код
и формулировку. Здесь проверяется именно перевод, по одной ошибке за раз.
"""

import pytest
from httpx import AsyncClient

from main import app
from src.db.models.api_tokens import ApiTokenScope
from src.dependencies.services import get_access_service, get_auth_service
from src.exceptions.access import (
    AccessServiceError,
    ProjectOwnerRequiredError,
    ResourceNotAvailableError,
)
from src.exceptions.auth import (
    AuthServiceError,
    InactiveUserError,
    NotAuthenticatedError,
)
from tests.api.bearer_doubles import auth_header, install_bearer_auth


class FailingAuthService:
    """Сервис аутентификации, поднимающий заданную доменную ошибку."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    async def resolve_principal(self, *, session_token, bearer_secret):
        raise self.error


class FailingAccessService:
    """Сервис доступа, поднимающий заданную доменную ошибку."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    async def ensure_project_access(self, *, project_id: int, user_id: int):
        raise self.error

    async def ensure_project_ownership(self, *, project_id: int, user_id: int):
        raise self.error

    async def ensure_task_access(self, *, task_id: int, user_id: int):
        raise self.error


@pytest.fixture
def anonymous_app():
    """Снимает автоподмену: проверяется настоящая цепочка зависимостей."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def failing_access(anonymous_app: None):
    """Пропускает аутентификацию и ломает проверку доступа заданной ошибкой."""

    def install(error: Exception) -> None:
        install_bearer_auth(ApiTokenScope.WRITE)
        app.dependency_overrides[get_access_service] = lambda: FailingAccessService(error)

    return install


@pytest.mark.parametrize(
    "error",
    [
        NotAuthenticatedError(),
        InactiveUserError(user_id=1),
        AuthServiceError("сбой базы"),
    ],
    ids=["не аутентифицирован", "учётная запись отключена", "сбой инфраструктуры"],
)
async def test_auth_service_error_maps_to_its_status(
    api_client: AsyncClient,
    anonymous_app: None,
    error: Exception,
) -> None:
    """Каждая ошибка аутентификации отдаёт свой код и свою формулировку."""
    app.dependency_overrides[get_auth_service] = lambda: FailingAuthService(error)

    response = await api_client.get("/api/v1/projects")

    assert response.status_code == error.status_code
    assert response.json() == {"detail": error.detail}


@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (ResourceNotAvailableError(resource="Проект", resource_id=1), 404),
        (ProjectOwnerRequiredError(project_id=1), 403),
        (AccessServiceError("сбой базы"), 500),
    ],
    ids=["объект недоступен", "нужен владелец", "сбой инфраструктуры"],
)
async def test_access_service_error_maps_to_its_status(
    api_client: AsyncClient,
    failing_access,
    error: Exception,
    expected_status: int,
) -> None:
    """Каждая ошибка доступа отдаёт свой код и свою формулировку."""
    failing_access(error)

    response = await api_client.get("/api/v1/projects/1", headers=auth_header())

    assert response.status_code == expected_status
    assert response.json() == {"detail": error.detail}


async def test_infrastructure_failure_is_not_reported_as_missing_object(
    api_client: AsyncClient,
    failing_access,
) -> None:
    """Сбой базы не превращается в 404.

    Иначе временная недоступность PostgreSQL выглядела бы как отсутствие
    проекта, и причину искали бы в правах доступа.
    """
    failing_access(AccessServiceError("сбой базы"))

    response = await api_client.get("/api/v1/projects/1", headers=auth_header())

    assert response.status_code == 500
    assert "сбой базы" not in response.text


async def test_access_error_details_do_not_leak_internals(
    api_client: AsyncClient,
    failing_access,
) -> None:
    """Внутренняя формулировка ошибки не попадает клиенту."""
    failing_access(ResourceNotAvailableError(resource="Проект", resource_id=777))

    response = await api_client.get("/api/v1/projects/777", headers=auth_header())

    assert response.status_code == 404
    assert response.json() == {"detail": "Объект не найден."}
    assert "777" not in response.text


async def test_owner_only_action_is_forbidden_for_plain_member(
    api_client: AsyncClient,
    failing_access,
) -> None:
    """Действие владельца отвечает 403, а не скрывает проект под 404.

    Проект пользователю виден, поэтому скрывать его существование смысла
    нет: отказ должен объяснять причину.
    """
    failing_access(ProjectOwnerRequiredError(project_id=1))

    response = await api_client.delete("/api/v1/projects/1", headers=auth_header())

    assert response.status_code == 403
    assert response.json() == {"detail": "Действие доступно только владельцу проекта."}

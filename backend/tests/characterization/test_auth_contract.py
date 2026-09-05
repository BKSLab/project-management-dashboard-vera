"""Контракт входа: cookie-сессия, регистрация и выход.

Рефакторинг переносит аутентификацию из Depends-слоя в сервисный, поэтому
внешнее поведение входа зафиксировано здесь до переноса: имя и флаги cookie,
коды ответов и форма карточки пользователя меняться не должны.
"""

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from main import app
from src.core.settings import get_settings
from src.db.models.api_tokens import ApiTokenScope
from src.dependencies.auth import get_principal
from src.dependencies.services import get_auth_service, get_users_service
from src.exceptions.auth import InvalidCredentialsError, InvalidInviteCodeError
from src.exceptions.users import UsernameConflictError
from src.schemas.users import UserSchema
from src.services.auth import Principal

COOKIE_NAME = get_settings().auth.session_cookie_name

REGISTER_PAYLOAD = {
    "username": "characterization",
    "password": "надёжный-пароль",
    "password_confirm": "надёжный-пароль",
    "last_name": "Тестов",
    "first_name": "Тест",
    "invite_code": "код-приглашения",
}
LOGIN_PAYLOAD = {"username": "characterization", "password": "надёжный-пароль"}


def _user_schema() -> UserSchema:
    """Карточка пользователя, которую сервис отдаёт наружу."""
    return UserSchema(
        id=7,
        username="characterization",
        last_name="Тестов",
        first_name="Тест",
        middle_name=None,
        email=None,
        phone=None,
        telegram=None,
        has_avatar=False,
        created_at=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
    )


class FakeUsersService:
    """Сервис профиля, отдающий карточку без обращения к базе."""

    async def get_user(self, user_id: int) -> UserSchema:
        return _user_schema()


class FakeAuthService:
    """Сервис аутентификации, отвечающий заранее заданным результатом."""

    def __init__(self, *, register_error=None, login_error=None) -> None:
        self.register_error = register_error
        self.login_error = login_error
        self.registered: list[dict] = []
        self.logged_in: list[tuple[str, str]] = []

    async def register(self, data: dict) -> UserSchema:
        if self.register_error is not None:
            raise self.register_error
        self.registered.append(data)
        return _user_schema()

    async def register_and_login(self, data: dict) -> tuple[UserSchema, str]:
        """Регистрация и вход — один сценарий сервиса."""
        user = await self.register(data=data)
        self.logged_in.append((data["username"], data["password"]))
        return user, "signed.session.token"

    async def login(self, username: str, password: str) -> tuple[UserSchema, str]:
        if self.login_error is not None:
            raise self.login_error
        self.logged_in.append((username, password))
        return _user_schema(), "signed.session.token"


@pytest.fixture
def auth_service() -> FakeAuthService:
    """Подменяет сервис аутентификации на управляемый двойник."""
    return FakeAuthService()


@pytest.fixture
def use_auth_service(anonymous: None, auth_service: FakeAuthService) -> FakeAuthService:
    """Ставит двойник сервиса в граф зависимостей приложения."""
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    return auth_service


async def test_login_sets_httponly_session_cookie(
    raw_client: AsyncClient,
    use_auth_service: FakeAuthService,
) -> None:
    """Успешный вход отдаёт 200, карточку пользователя и cookie сессии."""
    response = await raw_client.post("/api/v1/auth/login", json=LOGIN_PAYLOAD)

    assert response.status_code == 200
    assert response.json()["username"] == "characterization"
    assert "password" not in response.text
    cookie = response.cookies.get(COOKIE_NAME)
    assert cookie == "signed.session.token"
    header = response.headers["set-cookie"]
    assert "HttpOnly" in header
    assert "samesite=lax" in header.lower()
    assert "Path=/" in header


async def test_login_with_wrong_credentials_keeps_status_and_detail(
    raw_client: AsyncClient,
    anonymous: None,
) -> None:
    """Неверная пара логин/пароль отвечает доменным статусом сервиса."""
    error = InvalidCredentialsError(username="characterization")
    app.dependency_overrides[get_auth_service] = lambda: FakeAuthService(login_error=error)

    response = await raw_client.post("/api/v1/auth/login", json=LOGIN_PAYLOAD)

    assert response.status_code == error.status_code
    assert response.json() == {"detail": error.detail}
    assert COOKIE_NAME not in response.cookies


async def test_register_creates_user_and_opens_session(
    raw_client: AsyncClient,
    use_auth_service: FakeAuthService,
) -> None:
    """Регистрация отвечает 201 и сразу открывает сессию."""
    response = await raw_client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    assert response.status_code == 201
    assert response.json()["id"] == 7
    assert response.cookies.get(COOKIE_NAME) == "signed.session.token"
    assert use_auth_service.registered, "Сервис регистрации не был вызван."
    assert use_auth_service.logged_in == [("characterization", "надёжный-пароль")]


async def test_register_with_wrong_invite_code_is_rejected(
    raw_client: AsyncClient,
    anonymous: None,
) -> None:
    """Неверный код приглашения не создаёт пользователя и не даёт cookie."""
    error = InvalidInviteCodeError()
    app.dependency_overrides[get_auth_service] = lambda: FakeAuthService(register_error=error)

    response = await raw_client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    assert response.status_code == error.status_code
    assert response.json() == {"detail": error.detail}
    assert COOKIE_NAME not in response.cookies


async def test_register_with_taken_username_returns_conflict(
    raw_client: AsyncClient,
    anonymous: None,
) -> None:
    """Занятый логин остаётся конфликтом, а не общей ошибкой сервера."""
    error = UsernameConflictError(username="characterization")
    app.dependency_overrides[get_auth_service] = lambda: FakeAuthService(register_error=error)

    response = await raw_client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)

    assert response.status_code == error.status_code
    assert response.json() == {"detail": error.detail}


async def test_register_rejects_mismatched_password_confirmation(
    raw_client: AsyncClient,
    anonymous: None,
) -> None:
    """Расхождение пароля и подтверждения остаётся ошибкой валидации 422."""
    payload = {**REGISTER_PAYLOAD, "password_confirm": "другой-пароль"}

    response = await raw_client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422
    assert "detail" in response.json()


async def test_logout_clears_session_cookie(
    raw_client: AsyncClient,
    anonymous: None,
) -> None:
    """Выход отвечает 204 и сбрасывает cookie сессии."""
    response = await raw_client.post("/api/v1/auth/logout")

    assert response.status_code == 204
    header = response.headers["set-cookie"]
    assert header.startswith(f'{COOKIE_NAME}=""') or header.startswith(f"{COOKIE_NAME}=;")
    assert "Path=/" in header


async def test_logout_needs_no_session(
    raw_client: AsyncClient,
    anonymous: None,
) -> None:
    """Выход доступен без входа: повторный клик не должен давать 401."""
    response = await raw_client.post("/api/v1/auth/logout")

    assert response.status_code == 204


async def test_me_requires_session(raw_client: AsyncClient, anonymous: None) -> None:
    """Без cookie и токена карточка пользователя недоступна."""
    response = await raw_client.get("/api/v1/auth/me")

    assert response.status_code == 401


async def test_me_returns_safe_user_fields(
    raw_client: AsyncClient,
    anonymous: None,
) -> None:
    """Карточка текущего пользователя не содержит секретов."""
    app.dependency_overrides[get_principal] = lambda: Principal(
        user_id=7,
        username="characterization",
        last_name="Тестов",
        first_name="Тест",
        middle_name=None,
        scope=ApiTokenScope.WRITE,
        via_api_token=False,
    )
    app.dependency_overrides[get_users_service] = lambda: FakeUsersService()

    response = await raw_client.get("/api/v1/auth/me")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "id",
        "username",
        "last_name",
        "first_name",
        "middle_name",
        "email",
        "phone",
        "telegram",
        "has_avatar",
        "created_at",
    }
    assert "password_hash" not in body

"""Проверки единой точки аутентификации: cookie и Bearer-токен."""

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from src.db.models.api_tokens import ApiToken, ApiTokenScope
from src.db.models.users import User
from src.dependencies.auth import (
    _extract_bearer,
    get_principal,
    require_session,
    require_write_scope,
)
from src.exceptions.api_tokens import ApiTokensRepositoryError
from src.utils.api_tokens import hash_token_secret
from src.utils.tokens import create_access_token


class FakeUsersRepository:
    """Репозиторий пользователей в памяти."""

    def __init__(self, user: User | None):
        self.user = user

    async def get_by_id(self, user_id: int) -> User | None:
        return self.user if self.user is not None and self.user.id == user_id else None


class FakeTokensRepository:
    """Репозиторий токенов в памяти, отдающий только действующие токены."""

    def __init__(self, token: ApiToken | None = None, *, broken: bool = False):
        self.token = token
        self.broken = broken
        self.touched: list[ApiToken] = []

    async def get_active_by_hash(self, token_hash: str) -> ApiToken | None:
        if self.broken:
            raise ApiTokensRepositoryError("сбой БД")
        if self.token is not None and self.token.token_hash == token_hash:
            return self.token
        return None

    async def touch_last_used(self, token: ApiToken) -> None:
        self.touched.append(token)


def _user(**overrides) -> User:
    values = {
        "id": 1,
        "username": "tester",
        "password_hash": "hash",
        "last_name": "Тестов",
        "first_name": "Тест",
        "is_active": True,
    }
    values.update(overrides)
    return User(**values)


def _token(secret: str, **overrides) -> ApiToken:
    values = {
        "id": 1,
        "user_id": 1,
        "name": "Ноутбук",
        "token_hash": hash_token_secret(secret),
        "prefix": secret[:8],
        "scope": ApiTokenScope.READ,
        "expires_at": None,
        "revoked_at": None,
        "last_used_at": None,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    values.update(overrides)
    return ApiToken(**values)


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("Bearer vera_secret", "vera_secret"),
        ("bearer vera_secret", "vera_secret"),
        ("BEARER vera_secret", "vera_secret"),
        ("Bearer   vera_secret  ", "vera_secret"),
        ("Basic vera_secret", None),
        ("vera_secret", None),
        ("Bearer", None),
        ("Bearer   ", None),
        ("", None),
        (None, None),
    ],
)
def test_extract_bearer(header: str | None, expected: str | None) -> None:
    """Разбор заголовка не принимает чужую схему и пустое значение."""
    assert _extract_bearer(header) == expected


async def test_valid_token_authenticates_and_keeps_scope() -> None:
    """Действующий токен пускает пользователя и сохраняет свои права."""
    secret = "vera_valid"
    user = _user()
    tokens = FakeTokensRepository(_token(secret, scope=ApiTokenScope.READ))

    principal = await get_principal(
        session_cookie=None,
        authorization=f"Bearer {secret}",
        users_repository=FakeUsersRepository(user),
        tokens_repository=tokens,
    )

    assert principal.user is user
    assert principal.scope is ApiTokenScope.READ
    assert principal.via_api_token is True
    assert tokens.touched == [tokens.token]


async def test_unknown_token_is_rejected() -> None:
    """Выдуманный токен не пускает."""
    with pytest.raises(HTTPException) as error:
        await get_principal(
            session_cookie=None,
            authorization="Bearer vera_unknown",
            users_repository=FakeUsersRepository(_user()),
            tokens_repository=FakeTokensRepository(_token("vera_other")),
        )

    assert error.value.status_code == 401


async def test_token_of_disabled_user_is_rejected() -> None:
    """Отключённый пользователь не проходит даже с действующим токеном."""
    secret = "vera_valid"

    with pytest.raises(HTTPException) as error:
        await get_principal(
            session_cookie=None,
            authorization=f"Bearer {secret}",
            users_repository=FakeUsersRepository(_user(is_active=False)),
            tokens_repository=FakeTokensRepository(_token(secret)),
        )

    assert error.value.status_code in (401, 403)


async def test_token_of_deleted_user_is_rejected() -> None:
    """Токен пережившего удаление пользователя не пускает."""
    secret = "vera_valid"

    with pytest.raises(HTTPException) as error:
        await get_principal(
            session_cookie=None,
            authorization=f"Bearer {secret}",
            users_repository=FakeUsersRepository(None),
            tokens_repository=FakeTokensRepository(_token(secret)),
        )

    assert error.value.status_code == 401


async def test_repository_failure_does_not_leak_as_unauthorized() -> None:
    """Сбой базы отличается от отказа в доступе."""
    with pytest.raises(HTTPException) as error:
        await get_principal(
            session_cookie=None,
            authorization="Bearer vera_any",
            users_repository=FakeUsersRepository(_user()),
            tokens_repository=FakeTokensRepository(broken=True),
        )

    assert error.value.status_code == 500


async def test_cookie_session_still_works_and_has_write_scope() -> None:
    """Прежний вход по cookie не сломан и имеет полные права."""
    user = _user()

    principal = await get_principal(
        session_cookie=create_access_token(user.id),
        authorization=None,
        users_repository=FakeUsersRepository(user),
        tokens_repository=FakeTokensRepository(),
    )

    assert principal.user is user
    assert principal.scope is ApiTokenScope.WRITE
    assert principal.via_api_token is False


async def test_bearer_takes_precedence_over_cookie() -> None:
    """При обоих способах побеждает токен: иначе скоуп можно было бы обойти."""
    secret = "vera_valid"
    user = _user()

    principal = await get_principal(
        session_cookie=create_access_token(user.id),
        authorization=f"Bearer {secret}",
        users_repository=FakeUsersRepository(user),
        tokens_repository=FakeTokensRepository(_token(secret, scope=ApiTokenScope.READ)),
    )

    assert principal.scope is ApiTokenScope.READ
    assert principal.via_api_token is True


async def test_no_credentials_at_all_is_rejected() -> None:
    """Без cookie и без заголовка доступа нет."""
    with pytest.raises(HTTPException) as error:
        await get_principal(
            session_cookie=None,
            authorization=None,
            users_repository=FakeUsersRepository(_user()),
            tokens_repository=FakeTokensRepository(),
        )

    assert error.value.status_code == 401


async def test_read_scope_cannot_write() -> None:
    """Токен на чтение не допускается к изменяющей операции."""
    secret = "vera_valid"
    principal = await get_principal(
        session_cookie=None,
        authorization=f"Bearer {secret}",
        users_repository=FakeUsersRepository(_user()),
        tokens_repository=FakeTokensRepository(_token(secret, scope=ApiTokenScope.READ)),
    )

    with pytest.raises(HTTPException) as error:
        await require_write_scope(principal)

    assert error.value.status_code == 403


async def test_write_scope_passes() -> None:
    """Токен на запись допускается к изменяющей операции."""
    secret = "vera_valid"
    principal = await get_principal(
        session_cookie=None,
        authorization=f"Bearer {secret}",
        users_repository=FakeUsersRepository(_user()),
        tokens_repository=FakeTokensRepository(_token(secret, scope=ApiTokenScope.WRITE)),
    )

    assert await require_write_scope(principal) is principal


async def test_token_cannot_manage_tokens() -> None:
    """Управление токенами закрыто для самих токенов."""
    secret = "vera_valid"
    principal = await get_principal(
        session_cookie=None,
        authorization=f"Bearer {secret}",
        users_repository=FakeUsersRepository(_user()),
        tokens_repository=FakeTokensRepository(_token(secret, scope=ApiTokenScope.WRITE)),
    )

    with pytest.raises(HTTPException) as error:
        await require_session(principal)

    assert error.value.status_code == 403


async def test_session_can_manage_tokens() -> None:
    """Из интерфейса управление токенами доступно."""
    user = _user()
    principal = await get_principal(
        session_cookie=create_access_token(user.id),
        authorization=None,
        users_repository=FakeUsersRepository(user),
        tokens_repository=FakeTokensRepository(),
    )

    assert await require_session(principal) is user

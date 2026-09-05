from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.settings import get_settings
from src.exceptions.auth import (
    InactiveUserError,
    InvalidCredentialsError,
    InvalidInviteCodeError,
)
from src.exceptions.users import (
    UsernameAlreadyExistsRepositoryError,
    UsernameConflictError,
)
from src.repositories.api_tokens import ApiTokensRepository
from src.repositories.users import UsersRepository
from src.services.auth import AuthService
from src.utils.security import hash_password
from src.utils.tokens import decode_access_token

VALID_INVITE = get_settings().auth.registration_invite_code.get_secret_value()

# Регистрация собирает минимум: контакты заполняются позже в профиле.
REGISTRATION = {
    "username": "boris",
    "password": "pa$$word123",
    "password_confirm": "pa$$word123",
    "last_name": "Кузнецов",
    "first_name": "Борис",
    "invite_code": VALID_INVITE,
}


def make_user(user_id: int = 1, password: str = "pa$$word123", is_active: bool = True):
    """Возвращает дублёр пользователя с настоящим хешем пароля."""
    return SimpleNamespace(
        id=user_id,
        username="boris",
        password_hash=hash_password(password),
        last_name="Кузнецов",
        first_name="Борис",
        middle_name=None,
        email=None,
        phone=None,
        telegram=None,
        avatar_key=None,
        is_active=is_active,
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_register_rejects_wrong_invite_code() -> None:
    repository = AsyncMock(spec=UsersRepository)
    service = AuthService(
        users_repository=repository,
        tokens_repository=AsyncMock(spec=ApiTokensRepository),
        invite_code=VALID_INVITE,
    )

    with pytest.raises(InvalidInviteCodeError) as exc_info:
        await service.register(data={**REGISTRATION, "invite_code": "не тот код"})

    assert exc_info.value.status_code == 403
    repository.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_register_hashes_password_and_drops_confirmation() -> None:
    repository = AsyncMock(spec=UsersRepository)
    repository.save.return_value = make_user()
    service = AuthService(
        users_repository=repository,
        tokens_repository=AsyncMock(spec=ApiTokensRepository),
        invite_code=VALID_INVITE,
    )

    await service.register(data=dict(REGISTRATION))

    saved = repository.save.await_args.kwargs["data"]
    assert "password" not in saved
    assert "password_confirm" not in saved
    assert "invite_code" not in saved
    # Контакты в регистрации не участвуют и в запись не попадают.
    assert set(saved) == {"username", "last_name", "first_name", "password_hash"}
    # Пароль должен уходить в БД только хешем.
    assert saved["password_hash"] != REGISTRATION["password"]
    assert saved["password_hash"].startswith("$2b$")


@pytest.mark.asyncio
async def test_register_maps_busy_username_to_conflict() -> None:
    repository = AsyncMock(spec=UsersRepository)
    repository.save.side_effect = UsernameAlreadyExistsRepositoryError(username="boris")
    service = AuthService(
        users_repository=repository,
        tokens_repository=AsyncMock(spec=ApiTokensRepository),
        invite_code=VALID_INVITE,
    )

    with pytest.raises(UsernameConflictError) as exc_info:
        await service.register(data=dict(REGISTRATION))

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_login_returns_token_with_user_id() -> None:
    repository = AsyncMock(spec=UsersRepository)
    repository.get_by_username.return_value = make_user(user_id=42)
    service = AuthService(
        users_repository=repository,
        tokens_repository=AsyncMock(spec=ApiTokensRepository),
        invite_code=VALID_INVITE,
    )

    user, token = await service.login(username="boris", password="pa$$word123")

    assert user.id == 42
    assert decode_access_token(token) == 42


@pytest.mark.asyncio
async def test_login_with_unknown_username_and_wrong_password_look_identical() -> None:
    missing_repository = AsyncMock(spec=UsersRepository)
    missing_repository.get_by_username.return_value = None
    wrong_repository = AsyncMock(spec=UsersRepository)
    wrong_repository.get_by_username.return_value = make_user()

    with pytest.raises(InvalidCredentialsError) as missing:
        await AuthService(
            users_repository=missing_repository,
            tokens_repository=AsyncMock(spec=ApiTokensRepository),
            invite_code=VALID_INVITE,
        ).login(
            username="нет-такого",
            password="pa$$word123",
        )
    with pytest.raises(InvalidCredentialsError) as wrong:
        await AuthService(
            users_repository=wrong_repository,
            tokens_repository=AsyncMock(spec=ApiTokensRepository),
            invite_code=VALID_INVITE,
        ).login(
            username="boris",
            password="неверный",
        )

    # Ответы обязаны совпадать, иначе логины можно перебрать по коду и тексту.
    assert missing.value.status_code == wrong.value.status_code == 401
    assert missing.value.detail == wrong.value.detail


@pytest.mark.asyncio
async def test_login_rejects_inactive_user() -> None:
    repository = AsyncMock(spec=UsersRepository)
    repository.get_by_username.return_value = make_user(is_active=False)
    service = AuthService(
        users_repository=repository,
        tokens_repository=AsyncMock(spec=ApiTokensRepository),
        invite_code=VALID_INVITE,
    )

    with pytest.raises(InactiveUserError) as exc_info:
        await service.login(username="boris", password="pa$$word123")

    assert exc_info.value.status_code == 403

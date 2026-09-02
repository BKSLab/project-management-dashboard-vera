"""Интеграционные проверки репозитория токенов на настоящем PostgreSQL."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.api_tokens import ApiTokenScope
from src.db.models.users import User
from src.repositories.api_tokens import ApiTokensRepository
from src.utils.api_tokens import generate_token_secret, hash_token_secret


async def _create(
    repository: ApiTokensRepository,
    user: User,
    *,
    name: str = "Ноутбук",
    scope: ApiTokenScope = ApiTokenScope.READ,
    expires_at: datetime | None = None,
) -> tuple[str, int]:
    """Выпускает токен и возвращает секрет с идентификатором."""
    secret = generate_token_secret()
    token = await repository.create(
        user_id=user.id,
        name=name,
        token_hash=hash_token_secret(secret),
        prefix=secret[:8],
        scope=scope,
        expires_at=expires_at,
    )
    return secret, token.id


@pytest.mark.asyncio
async def test_active_token_is_found_by_hash(db_session: AsyncSession, user: User) -> None:
    repository = ApiTokensRepository(db_session)
    secret, token_id = await _create(repository, user)

    found = await repository.get_active_by_hash(hash_token_secret(secret))

    assert found is not None
    assert found.id == token_id
    assert found.user_id == user.id


@pytest.mark.asyncio
async def test_wrong_secret_is_not_found(db_session: AsyncSession, user: User) -> None:
    repository = ApiTokensRepository(db_session)
    await _create(repository, user)

    assert await repository.get_active_by_hash(hash_token_secret("vera_чужой")) is None


@pytest.mark.asyncio
async def test_revoked_token_is_not_returned(db_session: AsyncSession, user: User) -> None:
    repository = ApiTokensRepository(db_session)
    secret, token_id = await _create(repository, user)

    assert await repository.revoke(token_id=token_id, user_id=user.id) is True

    assert await repository.get_active_by_hash(hash_token_secret(secret)) is None


@pytest.mark.asyncio
async def test_expired_token_is_not_returned(db_session: AsyncSession, user: User) -> None:
    repository = ApiTokensRepository(db_session)
    secret, _ = await _create(
        repository,
        user,
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )

    assert await repository.get_active_by_hash(hash_token_secret(secret)) is None


@pytest.mark.asyncio
async def test_endless_token_stays_active(db_session: AsyncSession, user: User) -> None:
    repository = ApiTokensRepository(db_session)
    secret, _ = await _create(repository, user, expires_at=None)

    assert await repository.get_active_by_hash(hash_token_secret(secret)) is not None


@pytest.mark.asyncio
async def test_revoke_of_foreign_token_does_nothing(db_session: AsyncSession, user: User) -> None:
    """Чужой владелец не может отозвать токен: проверка в самом запросе."""
    repository = ApiTokensRepository(db_session)
    secret, token_id = await _create(repository, user)

    assert await repository.revoke(token_id=token_id, user_id=user.id + 999) is False
    assert await repository.get_active_by_hash(hash_token_secret(secret)) is not None


@pytest.mark.asyncio
async def test_count_active_ignores_revoked_and_expired(
    db_session: AsyncSession,
    user: User,
) -> None:
    repository = ApiTokensRepository(db_session)
    await _create(repository, user, name="Действующий")
    _, revoked_id = await _create(repository, user, name="Отозванный")
    await _create(
        repository,
        user,
        name="Истёкший",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    await repository.revoke(token_id=revoked_id, user_id=user.id)

    assert await repository.count_active_by_user(user.id) == 1


@pytest.mark.asyncio
async def test_list_returns_all_tokens_newest_first(db_session: AsyncSession, user: User) -> None:
    repository = ApiTokensRepository(db_session)
    _, first_id = await _create(repository, user, name="Первый")
    _, second_id = await _create(repository, user, name="Второй")
    await repository.revoke(token_id=first_id, user_id=user.id)

    tokens = await repository.get_by_user(user.id)

    assert [token.id for token in tokens] == [second_id, first_id]
    assert tokens[1].revoked_at is not None


@pytest.mark.asyncio
async def test_touch_last_used_is_throttled(db_session: AsyncSession, user: User) -> None:
    """Повторная отметка в течение интервала не переписывает время."""
    repository = ApiTokensRepository(db_session)
    secret, _ = await _create(repository, user)
    token = await repository.get_active_by_hash(hash_token_secret(secret))
    assert token is not None

    await repository.touch_last_used(token)
    first_seen = token.last_used_at
    await repository.touch_last_used(token)

    assert first_seen is not None
    assert token.last_used_at == first_seen

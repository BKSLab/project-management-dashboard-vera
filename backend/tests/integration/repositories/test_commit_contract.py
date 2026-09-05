"""Явный контракт `commit` у записывающих методов репозиториев.

`commit=True` завершает самостоятельную запись; `commit=False` оставляет
финальный commit владельцу составного сценария. Раньше выбор был неявным:
одни репозитории коммитили сами, другие полагались на `UnitOfWork`, и по
месту вызова это было не видно.

Видимость записи проверяется отдельным соединением: только оно отличает
«зафиксировано» от «лежит в незавершённой транзакции».
"""

import inspect

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from src.db.models.api_tokens import ApiToken, ApiTokenScope
from src.db.models.users import User
from src.exceptions.users import UsernameAlreadyExistsRepositoryError
from src.repositories.api_tokens import ApiTokensRepository
from src.repositories.users import UsersRepository

COMMIT_CONTRACT_METHODS = [
    (UsersRepository, "save"),
    (UsersRepository, "update"),
    (ApiTokensRepository, "create"),
    (ApiTokensRepository, "revoke"),
    (ApiTokensRepository, "touch_last_used"),
]


@pytest.mark.parametrize(
    ("repository_type", "method_name"),
    COMMIT_CONTRACT_METHODS,
    ids=[f"{cls.__name__}.{name}" for cls, name in COMMIT_CONTRACT_METHODS],
)
def test_commit_is_keyword_only_with_explicit_default(
    repository_type: type,
    method_name: str,
) -> None:
    """Флаг объявлен keyword-only: в вызове видно, что именно выбрано."""
    parameter = inspect.signature(getattr(repository_type, method_name)).parameters["commit"]

    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is True


def user_data(username: str) -> dict:
    """Поля нового пользователя."""
    return {
        "username": username,
        "password_hash": "hash",
        "last_name": "Транзакциев",
        "first_name": "Тест",
        "is_active": True,
    }


@pytest.mark.asyncio
async def test_commit_true_makes_the_row_visible_to_another_session(
    engine: AsyncEngine,
) -> None:
    """Самостоятельная запись видна новому соединению сразу."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        await UsersRepository(session).save(data=user_data("committed"), commit=True)

    async with AsyncSession(engine) as other:
        stored = await other.scalar(select(User).where(User.username == "committed"))

    assert stored is not None


@pytest.mark.asyncio
async def test_commit_false_keeps_the_row_invisible_until_the_owner_commits(
    engine: AsyncEngine,
) -> None:
    """Без своего commit запись не видна снаружи до фиксации владельцем."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        user = await UsersRepository(session).save(data=user_data("pending"), commit=False)

        assert user.id is not None, "Без flush запись не получила бы идентификатор."

        async with AsyncSession(engine) as other:
            invisible = await other.scalar(select(User).where(User.username == "pending"))
        assert invisible is None, "Незавершённая транзакция видна снаружи."

        # Финальный commit принадлежит владельцу сценария.
        await session.commit()

    async with AsyncSession(engine) as other:
        stored = await other.scalar(select(User).where(User.username == "pending"))

    assert stored is not None


@pytest.mark.asyncio
async def test_rollback_after_commit_false_leaves_nothing_behind(
    engine: AsyncEngine,
) -> None:
    """Откат владельца убирает запись, сделанную с ``commit=False``."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        await UsersRepository(session).save(data=user_data("rolled-back"), commit=False)
        await session.rollback()

    async with AsyncSession(engine) as other:
        stored = await other.scalar(select(User).where(User.username == "rolled-back"))

    assert stored is None


@pytest.mark.asyncio
async def test_token_create_respects_the_commit_flag(engine: AsyncEngine) -> None:
    """Токен доступа подчиняется тому же контракту."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        owner = await UsersRepository(session).save(data=user_data("token-owner"), commit=True)
        await ApiTokensRepository(session).create(
            user_id=owner.id,
            name="Ноутбук",
            token_hash="hash-pending",
            prefix="tt_pend",
            scope=ApiTokenScope.READ,
            expires_at=None,
            commit=False,
        )

        async with AsyncSession(engine) as other:
            invisible = await other.scalar(
                select(ApiToken).where(ApiToken.token_hash == "hash-pending")
            )
        assert invisible is None

        await session.commit()

    async with AsyncSession(engine) as other:
        stored = await other.scalar(select(ApiToken).where(ApiToken.token_hash == "hash-pending"))

    assert stored is not None


@pytest.mark.asyncio
async def test_two_writes_share_one_transaction(engine: AsyncEngine) -> None:
    """Две записи с ``commit=False`` фиксируются одним commit владельца.

    Именно это отличает составной use case от набора независимых записей:
    частичный результат снаружи не наблюдается ни в какой момент.
    """
    async with AsyncSession(engine, expire_on_commit=False) as session:
        users = UsersRepository(session)
        owner = await users.save(data=user_data("composite-owner"), commit=False)
        await ApiTokensRepository(session).create(
            user_id=owner.id,
            name="Составной сценарий",
            token_hash="hash-composite",
            prefix="tt_comp",
            scope=ApiTokenScope.WRITE,
            expires_at=None,
            commit=False,
        )

        async with AsyncSession(engine) as other:
            assert (
                await other.scalar(select(User).where(User.username == "composite-owner"))
            ) is None
            assert (
                await other.scalar(select(ApiToken).where(ApiToken.token_hash == "hash-composite"))
            ) is None

        await session.commit()

    async with AsyncSession(engine) as other:
        stored_user = await other.scalar(select(User).where(User.username == "composite-owner"))
        stored_token = await other.scalar(
            select(ApiToken).where(ApiToken.token_hash == "hash-composite")
        )

    assert stored_user is not None
    assert stored_token is not None


@pytest.mark.asyncio
async def test_failed_second_write_leaves_no_partial_result(engine: AsyncEngine) -> None:
    """Сбой второй записи откатывает и первую: частичного факта не остаётся."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        users = UsersRepository(session)
        await users.save(data=user_data("partial"), commit=False)
        with pytest.raises(UsernameAlreadyExistsRepositoryError):
            # Второй пользователь с тем же логином нарушает уникальность.
            await users.save(data=user_data("partial"), commit=False)

    async with AsyncSession(engine) as other:
        stored = await other.scalar(select(User).where(User.username == "partial"))

    assert stored is None

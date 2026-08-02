import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions.initial_data import SeedStateAlreadyExistsRepositoryError
from src.repositories.seed_state import SeedStateRepository


@pytest.mark.asyncio
async def test_save_and_get_by_key_on_real_postgres(
    db_session: AsyncSession,
) -> None:
    repository = SeedStateRepository(db_session)

    assert await repository.get_by_key(key="test-seed") is None

    saved = await repository.save(key="test-seed")
    loaded = await repository.get_by_key(key="test-seed")

    assert loaded is not None
    assert loaded.key == saved.key == "test-seed"


@pytest.mark.asyncio
async def test_save_on_real_postgres_rejects_duplicate_key(
    db_session: AsyncSession,
) -> None:
    repository = SeedStateRepository(db_session)
    await repository.save(key="test-seed")

    with pytest.raises(SeedStateAlreadyExistsRepositoryError):
        await repository.save(key="test-seed")

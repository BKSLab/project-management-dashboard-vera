import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions.wbs import WbsCodeAlreadyExistsRepositoryError
from src.repositories.wbs import WbsRepository


@pytest.mark.asyncio
async def test_create_item_on_real_postgres_rejects_duplicate_code(
    db_session: AsyncSession,
) -> None:
    repository = WbsRepository(db_session)
    data = {
        "parent_id": None,
        "code": "1",
        "phase_name": "Фаза",
        "title": "Работа",
        "role": None,
        "order_index": 0,
        "is_leaf": True,
    }
    await repository.create_item(data=data)

    with pytest.raises(WbsCodeAlreadyExistsRepositoryError):
        await repository.create_item(data=data)

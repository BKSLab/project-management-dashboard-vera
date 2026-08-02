import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.kanban_stages import KanbanStagesRepository


@pytest.mark.asyncio
async def test_save_and_get_stage_on_real_postgres(db_session: AsyncSession) -> None:
    repository = KanbanStagesRepository(db_session)
    saved = await repository.save(
        data={
            "name": "Тестовая стадия",
            "order_index": 10,
            "color": "#123456",
            "is_done_stage": False,
        }
    )

    loaded = await repository.get_by_id(stage_id=saved.id)

    assert loaded is not None
    assert loaded.name == "Тестовая стадия"

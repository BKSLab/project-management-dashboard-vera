import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions.kanban_tasks import KanbanTaskWbsLinkAlreadyExistsRepositoryError
from src.repositories.kanban_stages import KanbanStagesRepository
from src.repositories.kanban_tasks import KanbanTasksRepository
from src.repositories.wbs import WbsRepository


@pytest.mark.asyncio
async def test_search_ids_on_real_postgres_supports_russian_prefix(
    db_session: AsyncSession,
) -> None:
    stages_repository = KanbanStagesRepository(db_session)
    tasks_repository = KanbanTasksRepository(db_session)
    stage = await stages_repository.save(
        data={
            "name": "Бэклог",
            "order_index": 0,
            "color": "#999999",
            "is_done_stage": False,
        }
    )
    task = await tasks_repository.save(
        data={
            "stage_id": stage.id,
            "title": "Пользовательская инструкция",
            "description_md": "Описание интерфейса.",
            "position": 1.0,
        }
    )

    matching_ids = await tasks_repository.search_ids(search="пользова")
    highlights = await tasks_repository.get_search_highlights(
        task_ids=[task.id],
        search="пользова",
    )

    assert matching_ids == {task.id}
    assert "__FTS_START__" in highlights[task.id]["search_title"]


@pytest.mark.asyncio
async def test_search_ids_on_real_postgres_handles_special_symbols(
    db_session: AsyncSession,
) -> None:
    repository = KanbanTasksRepository(db_session)

    matching_ids = await repository.search_ids(search="база & данных!")

    assert isinstance(matching_ids, set)


@pytest.mark.asyncio
async def test_save_on_real_postgres_rejects_duplicate_wbs_link(
    db_session: AsyncSession,
) -> None:
    stages_repository = KanbanStagesRepository(db_session)
    tasks_repository = KanbanTasksRepository(db_session)
    wbs_repository = WbsRepository(db_session)
    stage = await stages_repository.save(
        data={
            "name": "Бэклог",
            "order_index": 0,
            "color": "#999999",
            "is_done_stage": False,
        }
    )
    item = await wbs_repository.create_item(
        data={
            "parent_id": None,
            "code": "1",
            "phase_name": "Фаза",
            "title": "Работа",
            "role": None,
            "order_index": 0,
            "is_leaf": True,
        }
    )
    task_data = {
        "wbs_item_id": item.id,
        "stage_id": stage.id,
        "title": item.title,
        "position": 0.0,
    }
    await tasks_repository.save(data=task_data)

    with pytest.raises(KanbanTaskWbsLinkAlreadyExistsRepositoryError):
        await tasks_repository.save(data=task_data)


@pytest.mark.asyncio
async def test_get_max_position_by_stage_on_real_postgres(
    db_session: AsyncSession,
) -> None:
    stages_repository = KanbanStagesRepository(db_session)
    tasks_repository = KanbanTasksRepository(db_session)
    stage = await stages_repository.save(
        data={
            "name": "В работе",
            "order_index": 2,
            "color": "#F5B800",
            "is_done_stage": False,
        }
    )
    assert await tasks_repository.get_max_position_by_stage(stage_id=stage.id) == 0.0

    for position in (1000.0, 2500.0, 1200.0):
        await tasks_repository.save(
            data={
                "stage_id": stage.id,
                "title": f"Задача {position}",
                "position": position,
            }
        )

    max_position = await tasks_repository.get_max_position_by_stage(stage_id=stage.id)

    assert max_position == 2500.0

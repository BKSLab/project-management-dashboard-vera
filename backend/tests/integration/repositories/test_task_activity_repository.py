import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.task_activity import TaskActivityEventType
from src.repositories.kanban_stages import KanbanStagesRepository
from src.repositories.kanban_tasks import KanbanTasksRepository
from src.repositories.task_activity import TaskActivityRepository


@pytest.mark.asyncio
async def test_save_and_get_for_task_on_real_postgres(
    db_session: AsyncSession,
) -> None:
    stages_repository = KanbanStagesRepository(db_session)
    tasks_repository = KanbanTasksRepository(db_session)
    activity_repository = TaskActivityRepository(db_session)
    stage = await stages_repository.save(
        data={
            "name": "Бэклог",
            "order_index": 0,
            "color": "#999999",
            "is_done_stage": False,
        }
    )
    task = await tasks_repository.save(
        data={"stage_id": stage.id, "title": "Работа", "position": 0.0}
    )

    event = await activity_repository.save(
        task_id=task.id,
        event_type=TaskActivityEventType.STAGE_CHANGED,
        from_value="Бэклог",
        to_value="В работе",
    )
    result = await activity_repository.get_for_task(task_id=task.id)

    assert [item.id for item in result] == [event.id]
    assert result[0].event_type == TaskActivityEventType.STAGE_CHANGED

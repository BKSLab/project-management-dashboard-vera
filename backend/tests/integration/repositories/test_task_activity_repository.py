import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.project_stages import ProjectStage
from src.db.models.task_activity import TaskActivityEventType
from src.repositories.task_activity import TaskActivityRepository
from src.repositories.tasks import TasksRepository


@pytest.mark.asyncio
async def test_save_and_get_for_task_on_real_postgres(
    db_session: AsyncSession,
    stage: ProjectStage,
) -> None:
    task = await TasksRepository(db_session).save(
        data={
            "project_id": stage.project_id,
            "stage_id": stage.id,
            "number": 1,
            "title": "Работа",
            "priority": "MEDIUM",
            "position": 0.0,
        }
    )
    activity_repository = TaskActivityRepository(db_session)

    event = await activity_repository.save(
        task_id=task.id,
        event_type=TaskActivityEventType.STAGE_CHANGED,
        from_value="Бэклог",
        to_value="В работе",
    )
    result = await activity_repository.get_for_task(task_id=task.id)

    assert [item.id for item in result] == [event.id]
    assert result[0].event_type == TaskActivityEventType.STAGE_CHANGED

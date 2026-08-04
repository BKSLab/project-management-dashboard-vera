from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.db.models.task_activity import TaskActivityEventType
from src.exceptions.kanban_tasks import (
    KanbanTaskFromWbsDeleteError,
    KanbanTasksRepositoryError,
    KanbanTasksServiceError,
)
from src.repositories.kanban_stages import KanbanStagesRepository
from src.repositories.kanban_tasks import KanbanTasksRepository
from src.repositories.task_activity import TaskActivityRepository
from src.repositories.task_comments import TaskCommentsRepository
from src.repositories.wbs import WbsRepository
from src.services.kanban_tasks import KanbanTasksService


def make_task(
    *,
    task_id: int = 7,
    stage_id: int = 1,
    position: float = 1000.0,
) -> SimpleNamespace:
    """Создаёт минимальную карточку для проверки сервисных сценариев."""
    timestamp = datetime(2026, 8, 4, tzinfo=UTC)
    return SimpleNamespace(
        id=task_id,
        wbs_item_id=None,
        stage_id=stage_id,
        title="Тестовая задача",
        description_md=None,
        due_date=None,
        position=position,
        created_at=timestamp,
        updated_at=timestamp,
    )


@pytest.mark.asyncio
async def test_delete_task_linked_to_wbs_raises_conflict() -> None:
    tasks_repository = AsyncMock(spec=KanbanTasksRepository)
    tasks_repository.get_by_id.return_value = SimpleNamespace(id=7, wbs_item_id=11)
    service = KanbanTasksService(
        tasks_repository=tasks_repository,
        stages_repository=AsyncMock(spec=KanbanStagesRepository),
        comments_repository=AsyncMock(spec=TaskCommentsRepository),
        activity_repository=AsyncMock(spec=TaskActivityRepository),
        wbs_repository=AsyncMock(spec=WbsRepository),
    )

    with pytest.raises(KanbanTaskFromWbsDeleteError) as exc_info:
        await service.delete_task(task_id=7)

    assert exc_info.value.status_code == 409
    tasks_repository.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_tasks_wraps_repository_error() -> None:
    tasks_repository = AsyncMock(spec=KanbanTasksRepository)
    tasks_repository.get_all.side_effect = KanbanTasksRepositoryError("БД недоступна")
    service = KanbanTasksService(
        tasks_repository=tasks_repository,
        stages_repository=AsyncMock(spec=KanbanStagesRepository),
        comments_repository=AsyncMock(spec=TaskCommentsRepository),
        activity_repository=AsyncMock(spec=TaskActivityRepository),
        wbs_repository=AsyncMock(spec=WbsRepository),
    )

    with pytest.raises(KanbanTasksServiceError) as exc_info:
        await service.get_task_list()

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_move_task_without_position_appends_to_target_stage() -> None:
    tasks_repository = AsyncMock(spec=KanbanTasksRepository)
    stages_repository = AsyncMock(spec=KanbanStagesRepository)
    activity_repository = AsyncMock(spec=TaskActivityRepository)
    task = make_task(stage_id=1)
    moved_task = make_task(stage_id=2, position=3000.0)
    tasks_repository.get_by_id.return_value = task
    tasks_repository.get_max_position_by_stage.return_value = 2000.0
    tasks_repository.update.return_value = moved_task
    stages_repository.get_by_id.side_effect = [
        SimpleNamespace(id=2, name="В работе"),
        SimpleNamespace(id=1, name="Бэклог"),
    ]
    service = KanbanTasksService(
        tasks_repository=tasks_repository,
        stages_repository=stages_repository,
        comments_repository=AsyncMock(spec=TaskCommentsRepository),
        activity_repository=activity_repository,
        wbs_repository=AsyncMock(spec=WbsRepository),
    )

    result = await service.move_task(task_id=7, stage_id=2)

    assert result.stage_id == 2
    assert result.position == 3000.0
    tasks_repository.get_max_position_by_stage.assert_awaited_once_with(stage_id=2)
    tasks_repository.update.assert_awaited_once_with(
        task=task,
        data={"stage_id": 2, "position": 3000.0},
    )
    activity_repository.save.assert_awaited_once_with(
        task_id=7,
        event_type=TaskActivityEventType.STAGE_CHANGED,
        from_value="Бэклог",
        to_value="В работе",
    )


@pytest.mark.asyncio
async def test_move_task_to_current_stage_without_position_is_noop() -> None:
    tasks_repository = AsyncMock(spec=KanbanTasksRepository)
    stages_repository = AsyncMock(spec=KanbanStagesRepository)
    activity_repository = AsyncMock(spec=TaskActivityRepository)
    task = make_task(stage_id=2)
    tasks_repository.get_by_id.return_value = task
    stages_repository.get_by_id.return_value = SimpleNamespace(id=2, name="В работе")
    service = KanbanTasksService(
        tasks_repository=tasks_repository,
        stages_repository=stages_repository,
        comments_repository=AsyncMock(spec=TaskCommentsRepository),
        activity_repository=activity_repository,
        wbs_repository=AsyncMock(spec=WbsRepository),
    )

    result = await service.move_task(task_id=7, stage_id=2)

    assert result.stage_id == 2
    tasks_repository.get_max_position_by_stage.assert_not_awaited()
    tasks_repository.update.assert_not_awaited()
    activity_repository.save.assert_not_awaited()

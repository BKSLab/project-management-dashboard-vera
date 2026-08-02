from unittest.mock import AsyncMock

import pytest

from src.exceptions.kanban_tasks import KanbanTasksRepositoryError
from src.exceptions.task_activity import TaskActivityRepositoryError, TaskActivityServiceError
from src.repositories.kanban_tasks import KanbanTasksRepository
from src.repositories.task_activity import TaskActivityRepository
from src.services.task_activity import TaskActivityService


@pytest.mark.asyncio
async def test_get_activity_wraps_repository_error() -> None:
    tasks_repository = AsyncMock(spec=KanbanTasksRepository)
    tasks_repository.get_by_id.side_effect = KanbanTasksRepositoryError("БД недоступна")
    service = TaskActivityService(
        activity_repository=AsyncMock(spec=TaskActivityRepository),
        tasks_repository=tasks_repository,
    )

    with pytest.raises(TaskActivityServiceError) as exc_info:
        await service.get_activity(task_id=1)

    assert exc_info.value.status_code == 500


@pytest.mark.asyncio
async def test_get_activity_wraps_activity_repository_error() -> None:
    tasks_repository = AsyncMock(spec=KanbanTasksRepository)
    tasks_repository.get_by_id.return_value = object()
    activity_repository = AsyncMock(spec=TaskActivityRepository)
    activity_repository.get_for_task.side_effect = TaskActivityRepositoryError("БД недоступна")
    service = TaskActivityService(
        activity_repository=activity_repository,
        tasks_repository=tasks_repository,
    )

    with pytest.raises(TaskActivityServiceError) as exc_info:
        await service.get_activity(task_id=1)

    assert exc_info.value.status_code == 500

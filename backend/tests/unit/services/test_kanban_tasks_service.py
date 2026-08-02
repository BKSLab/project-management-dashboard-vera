from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

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

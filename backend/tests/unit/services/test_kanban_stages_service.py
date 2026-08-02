from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.exceptions.kanban_stages import (
    KanbanStageHasTasksError,
    KanbanStageNotFoundError,
    KanbanStagesRepositoryError,
    KanbanStagesServiceError,
)
from src.repositories.kanban_stages import KanbanStagesRepository
from src.repositories.kanban_tasks import KanbanTasksRepository
from src.services.kanban_stages import KanbanStagesService


@pytest.mark.asyncio
async def test_update_stage_when_missing_raises_not_found() -> None:
    repository = AsyncMock(spec=KanbanStagesRepository)
    tasks_repository = AsyncMock(spec=KanbanTasksRepository)
    repository.get_by_id.return_value = None
    service = KanbanStagesService(
        stages_repository=repository,
        tasks_repository=tasks_repository,
    )

    with pytest.raises(KanbanStageNotFoundError) as exc_info:
        await service.update_stage(stage_id=999, data={"name": "Новая"})

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_stage_with_tasks_raises_conflict() -> None:
    repository = AsyncMock(spec=KanbanStagesRepository)
    tasks_repository = AsyncMock(spec=KanbanTasksRepository)
    repository.get_by_id.return_value = SimpleNamespace(id=2)
    tasks_repository.get_count_by_stage.return_value = 3
    service = KanbanStagesService(
        stages_repository=repository,
        tasks_repository=tasks_repository,
    )

    with pytest.raises(KanbanStageHasTasksError) as exc_info:
        await service.delete_stage(stage_id=2)

    assert exc_info.value.status_code == 409
    repository.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_stages_wraps_repository_error() -> None:
    repository = AsyncMock(spec=KanbanStagesRepository)
    repository.get_all.side_effect = KanbanStagesRepositoryError("БД недоступна")
    service = KanbanStagesService(
        stages_repository=repository,
        tasks_repository=AsyncMock(spec=KanbanTasksRepository),
    )

    with pytest.raises(KanbanStagesServiceError) as exc_info:
        await service.get_stage_list()

    assert exc_info.value.status_code == 500

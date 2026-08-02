from unittest.mock import AsyncMock

import pytest

from src.exceptions.wbs import (
    WbsCodeAlreadyExistsRepositoryError,
    WbsCodeConflictError,
    WbsItemNotFoundError,
    WbsRepositoryError,
    WbsServiceError,
)
from src.repositories.kanban_stages import KanbanStagesRepository
from src.repositories.kanban_tasks import KanbanTasksRepository
from src.repositories.wbs import WbsRepository
from src.services.wbs import WbsService


@pytest.mark.asyncio
async def test_update_item_when_missing_raises_not_found() -> None:
    wbs_repository = AsyncMock(spec=WbsRepository)
    wbs_repository.get_by_id.return_value = None
    service = WbsService(
        wbs_repository=wbs_repository,
        tasks_repository=AsyncMock(spec=KanbanTasksRepository),
        stages_repository=AsyncMock(spec=KanbanStagesRepository),
    )

    with pytest.raises(WbsItemNotFoundError) as exc_info:
        await service.update_item(item_id=999, data={"title": "Новое название"})

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_create_item_when_code_is_taken_raises_conflict() -> None:
    wbs_repository = AsyncMock(spec=WbsRepository)
    wbs_repository.get_children.return_value = []
    wbs_repository.create_item.side_effect = WbsCodeAlreadyExistsRepositoryError(code="1")
    service = WbsService(
        wbs_repository=wbs_repository,
        tasks_repository=AsyncMock(spec=KanbanTasksRepository),
        stages_repository=AsyncMock(spec=KanbanStagesRepository),
    )

    with pytest.raises(WbsCodeConflictError) as exc_info:
        await service.create_item(
            parent_id=None,
            title="Повторный узел",
            role=None,
            phase_name="Фаза",
        )

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_get_tree_wraps_repository_error() -> None:
    wbs_repository = AsyncMock(spec=WbsRepository)
    wbs_repository.get_all_items.side_effect = WbsRepositoryError("БД недоступна")
    service = WbsService(
        wbs_repository=wbs_repository,
        tasks_repository=AsyncMock(spec=KanbanTasksRepository),
        stages_repository=AsyncMock(spec=KanbanStagesRepository),
    )

    with pytest.raises(WbsServiceError) as exc_info:
        await service.get_tree()

    assert exc_info.value.status_code == 500

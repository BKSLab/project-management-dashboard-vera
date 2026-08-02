from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.exceptions.initial_data import InitialDataServiceError, SeedStateRepositoryError
from src.repositories.kanban_stages import KanbanStagesRepository
from src.repositories.kanban_tasks import KanbanTasksRepository
from src.repositories.seed_state import SeedStateRepository
from src.repositories.wbs import WbsRepository
from src.services.initial_data import InitialDataService


@pytest.mark.asyncio
async def test_ensure_loaded_with_marker_verifies_seed_data(tmp_path: Path) -> None:
    state_repository = AsyncMock(spec=SeedStateRepository)
    stages_repository = AsyncMock(spec=KanbanStagesRepository)
    tasks_repository = AsyncMock(spec=KanbanTasksRepository)
    wbs_repository = AsyncMock(spec=WbsRepository)
    data_path = tmp_path / "wbs.json"
    data_path.write_text(
        """[
          {
            "code": "1",
            "parent_code": null,
            "phase_name": "Фаза",
            "title": "Раздел",
            "role": null,
            "order_index": 0,
            "is_leaf": false
          },
          {
            "code": "1.1",
            "parent_code": "1",
            "phase_name": null,
            "title": "Работа",
            "role": "BE",
            "order_index": 0,
            "is_leaf": true
          }
        ]""",
        encoding="utf-8",
    )
    state_repository.get_by_key.return_value = SimpleNamespace(key="vera_wbs_v1")
    stages_repository.get_all.return_value = [
        SimpleNamespace(name=stage["name"]) for stage in InitialDataService.DEFAULT_STAGES
    ]
    wbs_repository.get_all_items.return_value = [
        SimpleNamespace(id=1, code="1"),
        SimpleNamespace(id=2, code="1.1"),
    ]
    tasks_repository.get_all.return_value = [SimpleNamespace(wbs_item_id=2)]
    service = InitialDataService(
        seed_state_repository=state_repository,
        stages_repository=stages_repository,
        tasks_repository=tasks_repository,
        wbs_repository=wbs_repository,
        data_path=data_path,
    )

    await service.ensure_loaded()

    stages_repository.get_all.assert_awaited_once()
    wbs_repository.get_all_items.assert_awaited_once()
    tasks_repository.get_all.assert_awaited_once()
    stages_repository.save.assert_not_awaited()
    wbs_repository.create_item.assert_not_awaited()
    tasks_repository.save.assert_not_awaited()
    state_repository.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_ensure_loaded_wraps_seed_state_repository_error(tmp_path: Path) -> None:
    data_path = tmp_path / "wbs.json"
    data_path.write_text(
        """[{
          "code": "1",
          "parent_code": null,
          "phase_name": "Фаза",
          "title": "Работа",
          "role": null,
          "order_index": 0,
          "is_leaf": true
        }]""",
        encoding="utf-8",
    )
    state_repository = AsyncMock(spec=SeedStateRepository)
    state_repository.get_by_key.side_effect = SeedStateRepositoryError("БД недоступна")
    service = InitialDataService(
        seed_state_repository=state_repository,
        stages_repository=AsyncMock(spec=KanbanStagesRepository),
        tasks_repository=AsyncMock(spec=KanbanTasksRepository),
        wbs_repository=AsyncMock(spec=WbsRepository),
        data_path=data_path,
    )

    with pytest.raises(InitialDataServiceError) as exc_info:
        await service.ensure_loaded()

    assert exc_info.value.status_code == 500

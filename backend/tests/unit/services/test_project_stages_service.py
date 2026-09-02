from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.exceptions.project_stages import (
    ProjectLastStageDeleteError,
    ProjectStageForeignProjectError,
    ProjectStageHasTasksError,
    ProjectStageNameAlreadyExistsRepositoryError,
    ProjectStageNameConflictError,
    ProjectStageNotFoundError,
    ProjectStagesRepositoryError,
    ProjectStagesServiceError,
)
from src.exceptions.projects import ProjectNotFoundError
from src.repositories.project_stages import ProjectStagesRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.tasks import TasksRepository
from src.repositories.unit_of_work import UnitOfWork
from src.services.project_stages import ProjectStagesService


def build_service(
    stages_repository: AsyncMock | None = None,
    projects_repository: AsyncMock | None = None,
    tasks_repository: AsyncMock | None = None,
) -> ProjectStagesService:
    """Собирает сервис стадий с подменёнными репозиториями."""
    projects = projects_repository or AsyncMock(spec=ProjectsRepository)
    if projects_repository is None:
        projects.get_by_id.return_value = SimpleNamespace(id=1)
    return ProjectStagesService(
        stages_repository=stages_repository or AsyncMock(spec=ProjectStagesRepository),
        projects_repository=projects,
        tasks_repository=tasks_repository or AsyncMock(spec=TasksRepository),
        unit_of_work=AsyncMock(spec=UnitOfWork),
    )


@pytest.mark.asyncio
async def test_get_stages_for_missing_project_raises_not_found() -> None:
    projects_repository = AsyncMock(spec=ProjectsRepository)
    projects_repository.get_by_id.return_value = None

    with pytest.raises(ProjectNotFoundError) as exc_info:
        await build_service(projects_repository=projects_repository).get_stage_list(project_id=9)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_create_stage_appends_to_end_of_board() -> None:
    stages_repository = AsyncMock(spec=ProjectStagesRepository)
    stages_repository.get_max_order_index.return_value = 4
    stages_repository.save.return_value = SimpleNamespace(
        id=9,
        project_id=1,
        name="Ревью",
        order_index=5,
        color="#a371f7",
        is_done_stage=False,
    )

    await build_service(stages_repository).create_stage(
        project_id=1,
        data={"name": "Ревью", "color": "#a371f7", "is_done_stage": False},
    )

    saved = stages_repository.save.await_args.kwargs["data"]
    assert saved["order_index"] == 5
    assert saved["project_id"] == 1


@pytest.mark.asyncio
async def test_create_stage_with_busy_name_raises_conflict() -> None:
    stages_repository = AsyncMock(spec=ProjectStagesRepository)
    stages_repository.get_max_order_index.return_value = 0
    stages_repository.save.side_effect = ProjectStageNameAlreadyExistsRepositoryError(name="Ревью")

    with pytest.raises(ProjectStageNameConflictError) as exc_info:
        await build_service(stages_repository).create_stage(
            project_id=1,
            data={"name": "Ревью", "color": "#a371f7", "is_done_stage": False},
        )

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_update_stage_when_missing_raises_not_found() -> None:
    stages_repository = AsyncMock(spec=ProjectStagesRepository)
    stages_repository.get_by_id.return_value = None

    with pytest.raises(ProjectStageNotFoundError) as exc_info:
        await build_service(stages_repository).update_stage(
            stage_id=999,
            data={"name": "Новая"},
        )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_stage_with_tasks_raises_conflict() -> None:
    stages_repository = AsyncMock(spec=ProjectStagesRepository)
    stages_repository.get_by_id.return_value = SimpleNamespace(id=2, project_id=1)
    tasks_repository = AsyncMock(spec=TasksRepository)
    tasks_repository.get_count_by_stage.return_value = 3

    with pytest.raises(ProjectStageHasTasksError) as exc_info:
        await build_service(stages_repository, tasks_repository=tasks_repository).delete_stage(
            stage_id=2
        )

    assert exc_info.value.status_code == 409
    stages_repository.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_last_stage_raises_conflict() -> None:
    stages_repository = AsyncMock(spec=ProjectStagesRepository)
    stages_repository.get_by_id.return_value = SimpleNamespace(id=2, project_id=1)
    stages_repository.get_by_project.return_value = [SimpleNamespace(id=2)]
    tasks_repository = AsyncMock(spec=TasksRepository)
    tasks_repository.get_count_by_stage.return_value = 0

    with pytest.raises(ProjectLastStageDeleteError) as exc_info:
        await build_service(stages_repository, tasks_repository=tasks_repository).delete_stage(
            stage_id=2
        )

    assert exc_info.value.status_code == 409
    stages_repository.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_stage_in_project_rejects_foreign_stage() -> None:
    stages_repository = AsyncMock(spec=ProjectStagesRepository)
    stages_repository.get_by_id.return_value = SimpleNamespace(id=2, project_id=5)

    with pytest.raises(ProjectStageForeignProjectError) as exc_info:
        await build_service(stages_repository).get_stage_in_project(project_id=1, stage_id=2)

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_get_stages_wraps_repository_error() -> None:
    stages_repository = AsyncMock(spec=ProjectStagesRepository)
    stages_repository.get_by_project.side_effect = ProjectStagesRepositoryError("БД недоступна")

    with pytest.raises(ProjectStagesServiceError) as exc_info:
        await build_service(stages_repository).get_stage_list(project_id=1)

    assert exc_info.value.status_code == 500

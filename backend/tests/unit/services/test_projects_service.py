from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.exceptions.projects import (
    ProjectKeyAlreadyExistsRepositoryError,
    ProjectKeyConflictError,
    ProjectNotFoundError,
    ProjectsRepositoryError,
    ProjectsServiceError,
)
from src.repositories.project_stages import ProjectStagesRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.tasks import TasksRepository
from src.services.projects import DEFAULT_STAGES, ProjectsService, build_project_stats

TODAY = date(2026, 9, 1)


def stage(stage_id: int, name: str, order_index: int, is_done: bool = False) -> SimpleNamespace:
    """Возвращает лёгкий дублёр стадии проекта."""
    return SimpleNamespace(
        id=stage_id,
        name=name,
        order_index=order_index,
        color="#58a6ff",
        is_done_stage=is_done,
    )


def task(
    task_id: int,
    stage_id: int,
    due_date: date | None = None,
    wbs_node_id: int | None = None,
) -> SimpleNamespace:
    """Возвращает лёгкий дублёр задачи."""
    return SimpleNamespace(
        id=task_id,
        stage_id=stage_id,
        due_date=due_date,
        wbs_node_id=wbs_node_id,
    )


def make_project(project_id: int = 7, key: str = "VERA") -> SimpleNamespace:
    """Возвращает дублёр проекта со всеми полями схемы ответа."""
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=project_id,
        key=key,
        name="Агент Вера",
        description_md=None,
        status="ACTIVE",
        color="#58a6ff",
        icon=None,
        start_date=None,
        due_date=None,
        order_index=3,
        created_at=now,
        updated_at=now,
    )


def build_service(
    projects_repository: AsyncMock | None = None,
    stages_repository: AsyncMock | None = None,
    tasks_repository: AsyncMock | None = None,
) -> ProjectsService:
    """Собирает сервис проектов с подменёнными репозиториями."""
    return ProjectsService(
        projects_repository=projects_repository or AsyncMock(spec=ProjectsRepository),
        stages_repository=stages_repository or AsyncMock(spec=ProjectStagesRepository),
        tasks_repository=tasks_repository or AsyncMock(spec=TasksRepository),
    )


@pytest.mark.asyncio
async def test_create_project_adds_default_stages() -> None:
    projects_repository = AsyncMock(spec=ProjectsRepository)
    projects_repository.get_max_order_index.return_value = 2
    projects_repository.save.return_value = make_project()
    stages_repository = AsyncMock(spec=ProjectStagesRepository)
    service = build_service(projects_repository, stages_repository)

    await service.create_project(data={"key": "VERA", "name": "Агент Вера"})

    assert projects_repository.save.await_args.kwargs["data"]["order_index"] == 3
    created_stages = stages_repository.save_many.await_args.kwargs["items"]
    assert len(created_stages) == len(DEFAULT_STAGES)
    assert [item["order_index"] for item in created_stages] == list(range(len(DEFAULT_STAGES)))
    assert {item["project_id"] for item in created_stages} == {7}
    assert sum(1 for item in created_stages if item["is_done_stage"]) == 1


@pytest.mark.asyncio
async def test_create_project_with_busy_key_raises_conflict() -> None:
    projects_repository = AsyncMock(spec=ProjectsRepository)
    projects_repository.get_max_order_index.return_value = 0
    projects_repository.save.side_effect = ProjectKeyAlreadyExistsRepositoryError(key="VERA")
    stages_repository = AsyncMock(spec=ProjectStagesRepository)
    service = build_service(projects_repository, stages_repository)

    with pytest.raises(ProjectKeyConflictError) as exc_info:
        await service.create_project(data={"key": "VERA", "name": "Агент Вера"})

    assert exc_info.value.status_code == 409
    stages_repository.save_many.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_project_when_missing_raises_not_found() -> None:
    projects_repository = AsyncMock(spec=ProjectsRepository)
    projects_repository.get_by_id.return_value = None

    with pytest.raises(ProjectNotFoundError) as exc_info:
        await build_service(projects_repository).get_project(project_id=999)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_project_removes_attachment_directories() -> None:
    projects_repository = AsyncMock(spec=ProjectsRepository)
    projects_repository.get_by_id.return_value = SimpleNamespace(id=1)
    tasks_repository = AsyncMock(spec=TasksRepository)
    tasks_repository.get_by_project.return_value = [task(11, 1), task(12, 1)]
    storage = AsyncMock()
    service = ProjectsService(
        projects_repository=projects_repository,
        stages_repository=AsyncMock(spec=ProjectStagesRepository),
        tasks_repository=tasks_repository,
        attachment_storage=storage,
    )

    await service.delete_project(project_id=1)

    projects_repository.delete.assert_awaited_once()
    assert storage.delete_task_directory.await_count == 2


@pytest.mark.asyncio
async def test_get_project_list_wraps_repository_error() -> None:
    projects_repository = AsyncMock(spec=ProjectsRepository)
    projects_repository.get_all.side_effect = ProjectsRepositoryError("БД недоступна")

    with pytest.raises(ProjectsServiceError) as exc_info:
        await build_service(projects_repository).get_project_list()

    assert exc_info.value.status_code == 500


def test_build_project_stats_counts_progress_and_deadlines() -> None:
    stages = [
        stage(1, "Бэклог", 0),
        stage(2, "В работе", 1),
        stage(3, "Готово", 2, is_done=True),
    ]
    tasks = [
        task(1, 1),
        task(2, 1, due_date=TODAY - timedelta(days=3)),
        task(3, 2, due_date=TODAY + timedelta(days=2), wbs_node_id=5),
        task(4, 2, due_date=TODAY + timedelta(days=30)),
        task(5, 3, due_date=TODAY - timedelta(days=10)),
    ]

    stats = build_project_stats(project_id=1, stages=stages, tasks=tasks, today=TODAY)

    assert stats.total_tasks == 5
    assert stats.done_tasks == 1
    assert stats.in_progress_tasks == 2
    assert stats.overdue_tasks == 1
    assert stats.due_soon_tasks == 1
    assert stats.unassigned_tasks == 4
    assert stats.completion_rate == pytest.approx(0.2)
    assert stats.next_due_date == TODAY + timedelta(days=2)
    assert [item.tasks_count for item in stats.stage_breakdown] == [2, 2, 1]


def test_build_project_stats_marks_overdue_backlog_task() -> None:
    stages = [stage(1, "Бэклог", 0), stage(2, "Готово", 1, is_done=True)]
    tasks = [task(1, 1, due_date=TODAY - timedelta(days=1))]

    stats = build_project_stats(project_id=1, stages=stages, tasks=tasks, today=TODAY)

    assert stats.overdue_tasks == 1
    assert stats.in_progress_tasks == 0
    assert stats.next_due_date is None


def test_build_project_stats_for_empty_project() -> None:
    stats = build_project_stats(project_id=1, stages=[], tasks=[], today=TODAY)

    assert stats.total_tasks == 0
    assert stats.completion_rate == 0.0
    assert stats.stage_breakdown == []

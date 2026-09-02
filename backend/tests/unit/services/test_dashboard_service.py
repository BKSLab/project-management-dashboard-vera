from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.db.models.projects import ProjectStatus
from src.db.models.tasks import TaskPriority
from src.exceptions.dashboard import DashboardServiceError
from src.exceptions.projects import ProjectsRepositoryError
from src.repositories.project_members import ProjectMembersRepository
from src.repositories.project_stages import ProjectStagesRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.tasks import TasksRepository
from src.services.dashboard import DashboardService

TODAY = date.today()
USER_ID = 1


def project(project_id: int, key: str, status: ProjectStatus) -> SimpleNamespace:
    """Возвращает дублёр проекта для дашборда."""
    return SimpleNamespace(
        id=project_id,
        key=key,
        name=f"Проект {key}",
        description_md=None,
        status=status,
        color="#58a6ff",
        icon=None,
        updated_at=datetime.now(UTC),
    )


def counters(
    project_id: int,
    total: int,
    done: int,
    overdue: int,
    next_due_date: date | None = None,
) -> SimpleNamespace:
    """Возвращает дублёр строки агрегатов задач по проекту."""
    return SimpleNamespace(
        project_id=project_id,
        total=total,
        done=done,
        overdue=overdue,
        due_soon=0,
        next_due_date=next_due_date,
    )


def task(task_id: int, project_id: int, stage_id: int, due_date: date | None) -> SimpleNamespace:
    """Возвращает дублёр задачи для сводки."""
    return SimpleNamespace(
        id=task_id,
        project_id=project_id,
        number=task_id,
        title=f"Задача {task_id}",
        stage_id=stage_id,
        priority=TaskPriority.HIGH,
        due_date=due_date,
        updated_at=datetime.now(UTC),
    )


def build_service(
    projects: list,
    stages: list,
    portfolio_counters: list,
    stage_counts: list,
    attention_tasks: list | None = None,
    recent_tasks: list | None = None,
) -> DashboardService:
    """Собирает сервис дашборда с подменёнными репозиториями."""
    projects_repository = AsyncMock(spec=ProjectsRepository)
    projects_repository.get_all.return_value = projects
    members_repository = AsyncMock(spec=ProjectMembersRepository)
    members_repository.get_project_ids_for_user.return_value = {project.id for project in projects}
    stages_repository = AsyncMock(spec=ProjectStagesRepository)
    stages_repository.get_all.return_value = stages
    tasks_repository = AsyncMock(spec=TasksRepository)
    tasks_repository.get_portfolio_counters.return_value = portfolio_counters
    tasks_repository.get_stage_counts.return_value = stage_counts
    tasks_repository.get_attention_tasks.return_value = attention_tasks or []
    tasks_repository.get_recent.return_value = recent_tasks or []
    return DashboardService(
        projects_repository=projects_repository,
        members_repository=members_repository,
        stages_repository=stages_repository,
        tasks_repository=tasks_repository,
    )


@pytest.mark.asyncio
async def test_overview_aggregates_projects_and_totals() -> None:
    projects = [
        project(1, "PROJ", ProjectStatus.ACTIVE),
        project(2, "SITE", ProjectStatus.PLANNING),
    ]
    stages = [
        SimpleNamespace(id=1, project_id=1, order_index=0, name="Бэклог", is_done_stage=False),
        SimpleNamespace(id=2, project_id=1, order_index=1, name="Работа", is_done_stage=False),
        SimpleNamespace(id=3, project_id=1, order_index=2, name="Готово", is_done_stage=True),
        SimpleNamespace(id=4, project_id=2, order_index=0, name="Бэклог", is_done_stage=False),
    ]
    service = build_service(
        projects=projects,
        stages=stages,
        portfolio_counters=[
            counters(1, total=10, done=4, overdue=2, next_due_date=TODAY),
            counters(2, total=3, done=0, overdue=0),
        ],
        stage_counts=[
            SimpleNamespace(project_id=1, stage_id=1, tasks_count=3),
            SimpleNamespace(project_id=1, stage_id=2, tasks_count=3),
            SimpleNamespace(project_id=1, stage_id=3, tasks_count=4),
            SimpleNamespace(project_id=2, stage_id=4, tasks_count=3),
        ],
    )

    result = await service.get_overview(user_id=USER_ID)

    assert result.totals.total_projects == 2
    assert result.totals.active_projects == 1
    assert result.totals.total_tasks == 13
    assert result.totals.done_tasks == 4
    assert result.totals.overdue_tasks == 2
    assert result.totals.completion_rate == pytest.approx(4 / 13)

    first, site = result.projects
    assert first.in_progress_tasks == 3
    assert first.completion_rate == pytest.approx(0.4)
    assert first.next_due_date == TODAY
    assert site.total_tasks == 3
    assert site.in_progress_tasks == 0


@pytest.mark.asyncio
async def test_overview_handles_project_without_tasks() -> None:
    service = build_service(
        projects=[project(1, "PROJ", ProjectStatus.PLANNING)],
        stages=[],
        portfolio_counters=[],
        stage_counts=[],
    )

    result = await service.get_overview(user_id=USER_ID)

    assert result.projects[0].total_tasks == 0
    assert result.projects[0].completion_rate == 0.0
    assert result.totals.completion_rate == 0.0


@pytest.mark.asyncio
async def test_overview_marks_overdue_attention_tasks() -> None:
    stages = [
        SimpleNamespace(id=1, project_id=1, order_index=0, name="Бэклог", is_done_stage=False),
    ]
    service = build_service(
        projects=[project(1, "PROJ", ProjectStatus.ACTIVE)],
        stages=stages,
        portfolio_counters=[counters(1, total=2, done=0, overdue=1)],
        stage_counts=[SimpleNamespace(project_id=1, stage_id=1, tasks_count=2)],
        attention_tasks=[
            task(11, 1, 1, TODAY - timedelta(days=1)),
            task(12, 1, 1, TODAY + timedelta(days=3)),
        ],
    )

    result = await service.get_overview(user_id=USER_ID)

    overdue, upcoming = result.attention_tasks
    assert overdue.key == "PROJ-11"
    assert overdue.is_overdue is True
    assert overdue.project_name == "Проект PROJ"
    assert upcoming.is_overdue is False


@pytest.mark.asyncio
async def test_overview_wraps_repository_error() -> None:
    projects_repository = AsyncMock(spec=ProjectsRepository)
    projects_repository.get_all.side_effect = ProjectsRepositoryError("БД недоступна")
    members_repository = AsyncMock(spec=ProjectMembersRepository)
    members_repository.get_project_ids_for_user.return_value = {1}
    service = DashboardService(
        projects_repository=projects_repository,
        members_repository=members_repository,
        stages_repository=AsyncMock(spec=ProjectStagesRepository),
        tasks_repository=AsyncMock(spec=TasksRepository),
    )

    with pytest.raises(DashboardServiceError) as exc_info:
        await service.get_overview(user_id=USER_ID)

    assert exc_info.value.status_code == 500

from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.db.models.task_activity import TaskActivityEventType
from src.db.models.tasks import TaskPriority
from src.exceptions.project_stages import (
    ProjectStageForeignProjectError,
    ProjectStageNotFoundError,
)
from src.exceptions.projects import ProjectNotFoundError
from src.exceptions.tasks import (
    TaskNotFoundError,
    TaskNumberAllocationError,
    TaskNumberAlreadyExistsRepositoryError,
    TasksRepositoryError,
    TasksServiceError,
)
from src.exceptions.wbs_nodes import WbsNodeForeignProjectError, WbsNodeNotFoundError
from src.repositories.project_stages import ProjectStagesRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.task_activity import TaskActivityRepository
from src.repositories.task_comments import TaskCommentsRepository
from src.repositories.tasks import TasksRepository
from src.repositories.wbs_nodes import WbsNodesRepository
from src.services.tasks import TasksService

PROJECT = SimpleNamespace(id=1, key="VERA")


def make_task(
    task_id: int = 10,
    number: int = 42,
    stage_id: int = 1,
    priority: TaskPriority = TaskPriority.MEDIUM,
    assignee: str | None = None,
    due_date: date | None = None,
    description_md: str | None = None,
) -> SimpleNamespace:
    """Возвращает дублёр задачи со всеми полями схемы ответа."""
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=task_id,
        project_id=1,
        stage_id=stage_id,
        wbs_node_id=None,
        number=number,
        title="Реализовать фильтрацию",
        description_md=description_md,
        priority=priority,
        role=None,
        assignee=assignee,
        due_date=due_date,
        position=1000.0,
        created_at=now,
        updated_at=now,
    )


def build_service(
    tasks_repository: AsyncMock | None = None,
    stages_repository: AsyncMock | None = None,
    activity_repository: AsyncMock | None = None,
    wbs_nodes_repository: AsyncMock | None = None,
    projects_repository: AsyncMock | None = None,
) -> TasksService:
    """Собирает сервис задач с подменёнными репозиториями."""
    projects = projects_repository or AsyncMock(spec=ProjectsRepository)
    if projects_repository is None:
        projects.get_by_id.return_value = PROJECT
    comments_repository = AsyncMock(spec=TaskCommentsRepository)
    comments_repository.get_all.return_value = []
    return TasksService(
        tasks_repository=tasks_repository or AsyncMock(spec=TasksRepository),
        projects_repository=projects,
        stages_repository=stages_repository or AsyncMock(spec=ProjectStagesRepository),
        comments_repository=comments_repository,
        activity_repository=activity_repository or AsyncMock(spec=TaskActivityRepository),
        wbs_nodes_repository=wbs_nodes_repository or AsyncMock(spec=WbsNodesRepository),
    )


@pytest.mark.asyncio
async def test_create_task_allocates_number_and_uses_first_stage() -> None:
    tasks_repository = AsyncMock(spec=TasksRepository)
    tasks_repository.get_next_number.return_value = 43
    tasks_repository.get_max_position_by_stage.return_value = 2000.0
    tasks_repository.save.return_value = make_task(number=43)
    stages_repository = AsyncMock(spec=ProjectStagesRepository)
    stages_repository.get_by_project.return_value = [
        SimpleNamespace(id=1),
        SimpleNamespace(id=2),
    ]

    result = await build_service(tasks_repository, stages_repository).create_task(
        project_id=1,
        data={"title": "Реализовать фильтрацию", "stage_id": None},
    )

    saved = tasks_repository.save.await_args.kwargs["data"]
    assert saved["number"] == 43
    assert saved["stage_id"] == 1
    assert saved["position"] == 3000.0
    assert result.key == "VERA-43"


@pytest.mark.asyncio
async def test_create_task_retries_when_number_is_taken() -> None:
    tasks_repository = AsyncMock(spec=TasksRepository)
    tasks_repository.get_next_number.side_effect = [43, 44]
    tasks_repository.get_max_position_by_stage.return_value = 0.0
    tasks_repository.save.side_effect = [
        TaskNumberAlreadyExistsRepositoryError(project_id=1, number=43),
        make_task(number=44),
    ]
    stages_repository = AsyncMock(spec=ProjectStagesRepository)
    stages_repository.get_by_project.return_value = [SimpleNamespace(id=1)]

    result = await build_service(tasks_repository, stages_repository).create_task(
        project_id=1,
        data={"title": "Реализовать фильтрацию", "stage_id": None},
    )

    assert tasks_repository.save.await_count == 2
    assert result.key == "VERA-44"


@pytest.mark.asyncio
async def test_create_task_gives_up_after_number_attempts() -> None:
    tasks_repository = AsyncMock(spec=TasksRepository)
    tasks_repository.get_next_number.return_value = 43
    tasks_repository.get_max_position_by_stage.return_value = 0.0
    tasks_repository.save.side_effect = TaskNumberAlreadyExistsRepositoryError(
        project_id=1,
        number=43,
    )
    stages_repository = AsyncMock(spec=ProjectStagesRepository)
    stages_repository.get_by_project.return_value = [SimpleNamespace(id=1)]

    with pytest.raises(TaskNumberAllocationError) as exc_info:
        await build_service(tasks_repository, stages_repository).create_task(
            project_id=1,
            data={"title": "Реализовать фильтрацию", "stage_id": None},
        )

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_create_task_in_project_without_stages_raises_not_found() -> None:
    stages_repository = AsyncMock(spec=ProjectStagesRepository)
    stages_repository.get_by_project.return_value = []

    with pytest.raises(ProjectStageNotFoundError):
        await build_service(stages_repository=stages_repository).create_task(
            project_id=1,
            data={"title": "Задача", "stage_id": None},
        )


@pytest.mark.asyncio
async def test_create_task_rejects_stage_of_another_project() -> None:
    stages_repository = AsyncMock(spec=ProjectStagesRepository)
    stages_repository.get_by_project.return_value = [SimpleNamespace(id=1)]
    stages_repository.get_by_id.return_value = SimpleNamespace(id=77, project_id=5)

    with pytest.raises(ProjectStageForeignProjectError) as exc_info:
        await build_service(stages_repository=stages_repository).create_task(
            project_id=1,
            data={"title": "Задача", "stage_id": 77},
        )

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_create_task_rejects_wbs_node_of_another_project() -> None:
    stages_repository = AsyncMock(spec=ProjectStagesRepository)
    stages_repository.get_by_project.return_value = [SimpleNamespace(id=1)]
    wbs_nodes_repository = AsyncMock(spec=WbsNodesRepository)
    wbs_nodes_repository.get_by_id.return_value = SimpleNamespace(id=8, project_id=5)
    service = build_service(
        stages_repository=stages_repository,
        wbs_nodes_repository=wbs_nodes_repository,
    )

    with pytest.raises(WbsNodeForeignProjectError):
        await service.create_task(
            project_id=1,
            data={"title": "Задача", "stage_id": None, "wbs_node_id": 8},
        )


@pytest.mark.asyncio
async def test_create_task_rejects_missing_wbs_node() -> None:
    stages_repository = AsyncMock(spec=ProjectStagesRepository)
    stages_repository.get_by_project.return_value = [SimpleNamespace(id=1)]
    wbs_nodes_repository = AsyncMock(spec=WbsNodesRepository)
    wbs_nodes_repository.get_by_id.return_value = None
    service = build_service(
        stages_repository=stages_repository,
        wbs_nodes_repository=wbs_nodes_repository,
    )

    with pytest.raises(WbsNodeNotFoundError):
        await service.create_task(
            project_id=1,
            data={"title": "Задача", "stage_id": None, "wbs_node_id": 8},
        )


@pytest.mark.asyncio
async def test_create_task_in_missing_project_raises_not_found() -> None:
    projects_repository = AsyncMock(spec=ProjectsRepository)
    projects_repository.get_by_id.return_value = None

    with pytest.raises(ProjectNotFoundError):
        await build_service(projects_repository=projects_repository).create_task(
            project_id=42,
            data={"title": "Задача", "stage_id": None},
        )


@pytest.mark.asyncio
async def test_update_task_records_priority_and_assignee_changes() -> None:
    tasks_repository = AsyncMock(spec=TasksRepository)
    task = make_task(priority=TaskPriority.LOW, assignee="Иван")
    tasks_repository.get_by_id.return_value = task
    tasks_repository.update.return_value = make_task(
        priority=TaskPriority.URGENT,
        assignee="Мария",
    )
    activity_repository = AsyncMock(spec=TaskActivityRepository)
    service = build_service(tasks_repository, activity_repository=activity_repository)

    await service.update_task(
        task_id=10,
        data={"priority": TaskPriority.URGENT, "assignee": "Мария"},
    )

    events = [call.kwargs["event_type"] for call in activity_repository.save.await_args_list]
    assert TaskActivityEventType.PRIORITY_CHANGED in events
    assert TaskActivityEventType.ASSIGNEE_CHANGED in events


@pytest.mark.asyncio
async def test_update_task_skips_history_when_values_unchanged() -> None:
    tasks_repository = AsyncMock(spec=TasksRepository)
    task = make_task(priority=TaskPriority.LOW, assignee="Иван")
    tasks_repository.get_by_id.return_value = task
    tasks_repository.update.return_value = task
    activity_repository = AsyncMock(spec=TaskActivityRepository)
    service = build_service(tasks_repository, activity_repository=activity_repository)

    await service.update_task(
        task_id=10,
        data={"priority": TaskPriority.LOW, "assignee": "Иван"},
    )

    activity_repository.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_move_task_records_stage_change_and_appends_to_end() -> None:
    tasks_repository = AsyncMock(spec=TasksRepository)
    tasks_repository.get_by_id.return_value = make_task(stage_id=1)
    tasks_repository.get_max_position_by_stage.return_value = 5000.0
    tasks_repository.update.return_value = make_task(stage_id=2)
    stages_repository = AsyncMock(spec=ProjectStagesRepository)
    stages_repository.get_by_id.side_effect = [
        SimpleNamespace(id=2, project_id=1, name="В работе"),
        SimpleNamespace(id=1, project_id=1, name="Бэклог"),
    ]
    activity_repository = AsyncMock(spec=TaskActivityRepository)
    service = build_service(
        tasks_repository,
        stages_repository,
        activity_repository=activity_repository,
    )

    await service.move_task(task_id=10, stage_id=2)

    assert tasks_repository.update.await_args.kwargs["data"]["position"] == 6000.0
    event = activity_repository.save.await_args.kwargs
    assert event["event_type"] == TaskActivityEventType.STAGE_CHANGED
    assert event["from_value"] == "Бэклог"
    assert event["to_value"] == "В работе"


@pytest.mark.asyncio
async def test_move_task_rejects_stage_of_another_project() -> None:
    tasks_repository = AsyncMock(spec=TasksRepository)
    tasks_repository.get_by_id.return_value = make_task(stage_id=1)
    stages_repository = AsyncMock(spec=ProjectStagesRepository)
    stages_repository.get_by_id.return_value = SimpleNamespace(id=9, project_id=5, name="Чужая")

    with pytest.raises(ProjectStageForeignProjectError) as exc_info:
        await build_service(tasks_repository, stages_repository).move_task(
            task_id=10,
            stage_id=9,
        )

    assert exc_info.value.status_code == 409
    tasks_repository.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_move_task_within_same_stage_without_position_is_noop() -> None:
    tasks_repository = AsyncMock(spec=TasksRepository)
    tasks_repository.get_by_id.return_value = make_task(stage_id=2)
    stages_repository = AsyncMock(spec=ProjectStagesRepository)
    stages_repository.get_by_id.return_value = SimpleNamespace(id=2, project_id=1, name="Работа")

    await build_service(tasks_repository, stages_repository).move_task(task_id=10, stage_id=2)

    tasks_repository.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_task_when_missing_raises_not_found() -> None:
    tasks_repository = AsyncMock(spec=TasksRepository)
    tasks_repository.get_by_id.return_value = None

    with pytest.raises(TaskNotFoundError) as exc_info:
        await build_service(tasks_repository).get_task(task_id=999)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_task_removes_attachment_directory() -> None:
    tasks_repository = AsyncMock(spec=TasksRepository)
    tasks_repository.get_by_id.return_value = make_task()
    storage = AsyncMock()
    service = build_service(tasks_repository)
    service.attachment_storage = storage

    await service.delete_task(task_id=10)

    tasks_repository.delete.assert_awaited_once()
    storage.delete_task_directory.assert_awaited_once_with(10)


@pytest.mark.asyncio
async def test_get_task_list_wraps_repository_error() -> None:
    tasks_repository = AsyncMock(spec=TasksRepository)
    tasks_repository.get_by_project.side_effect = TasksRepositoryError("БД недоступна")

    with pytest.raises(TasksServiceError) as exc_info:
        await build_service(tasks_repository).get_task_list(project_id=1)

    assert exc_info.value.status_code == 500

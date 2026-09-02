from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.project_stages import ProjectStage
from src.exceptions.tasks import TaskNumberAlreadyExistsRepositoryError
from src.repositories.project_stages import ProjectStagesRepository
from src.repositories.tasks import TasksRepository
from src.repositories.wbs_nodes import WbsNodesRepository

TODAY = date.today()


def task_data(stage: ProjectStage, number: int, **overrides) -> dict:
    """Собирает минимальные поля задачи для репозитория."""
    return {
        "project_id": stage.project_id,
        "stage_id": stage.id,
        "number": number,
        "title": f"Задача {number}",
        "priority": "MEDIUM",
        "position": float(number) * 1000,
        **overrides,
    }


@pytest.mark.asyncio
async def test_duplicate_number_within_project_raises_domain_error(
    db_session: AsyncSession,
    stage: ProjectStage,
) -> None:
    repository = TasksRepository(db_session)
    await repository.save(data=task_data(stage, 1))

    with pytest.raises(TaskNumberAlreadyExistsRepositoryError) as exc_info:
        await repository.save(data=task_data(stage, 1))

    assert exc_info.value.number == 1


@pytest.mark.asyncio
async def test_get_next_number_follows_existing_tasks(
    db_session: AsyncSession,
    stage: ProjectStage,
) -> None:
    repository = TasksRepository(db_session)

    assert await repository.get_next_number(project_id=stage.project_id) == 1

    await repository.save(data=task_data(stage, 7))

    assert await repository.get_next_number(project_id=stage.project_id) == 8


@pytest.mark.asyncio
async def test_search_finds_task_by_number_and_text(
    db_session: AsyncSession,
    stage: ProjectStage,
) -> None:
    repository = TasksRepository(db_session)
    task = await repository.save(
        data=task_data(
            stage,
            142,
            title="Пользовательская фильтрация",
            description_md="Фильтры по статусу.",
        )
    )

    by_key = await repository.search_ids(project_id=stage.project_id, search="VERA-142")
    by_number = await repository.search_ids(project_id=stage.project_id, search="142")
    by_prefix = await repository.search_ids(project_id=stage.project_id, search="пользова")

    assert by_key == {task.id}
    assert by_number == {task.id}
    assert by_prefix == {task.id}


@pytest.mark.asyncio
async def test_ranked_search_returns_at_most_top_30(
    db_session: AsyncSession,
    stage: ProjectStage,
) -> None:
    repository = TasksRepository(db_session)
    for number in range(1, 36):
        await repository.save(data=task_data(stage, number, title=f"Поисковая задача {number}"))

    tasks = await repository.search_ranked(
        project_id=stage.project_id,
        search="поисковая",
        limit=30,
    )

    assert len(tasks) == 30
    assert all("Поисковая" in task.title for task in tasks)


@pytest.mark.asyncio
async def test_project_statistics_are_aggregated_without_loading_tasks(
    db_session: AsyncSession,
    stage: ProjectStage,
) -> None:
    repository = TasksRepository(db_session)
    await repository.save(
        data=task_data(
            stage,
            1,
            priority="HIGH",
            assignee="Анна",
            due_date=TODAY - timedelta(days=1),
        )
    )
    await repository.save(data=task_data(stage, 2, priority="LOW", assignee=None))

    statistics = await repository.get_project_statistics(
        project_id=stage.project_id,
        today=TODAY,
    )

    assert statistics.total == 2
    assert statistics.overdue == 1
    assert statistics.by_stage == {stage.id: 2}
    assert statistics.by_priority == {"HIGH": 1, "LOW": 1}
    assert statistics.by_assignee == {"Анна": 1, "не назначен": 1}


@pytest.mark.asyncio
async def test_portfolio_counters_split_done_and_overdue(
    db_session: AsyncSession,
    stage: ProjectStage,
) -> None:
    done_stage = await ProjectStagesRepository(db_session).save(
        data={
            "project_id": stage.project_id,
            "name": "Готово",
            "order_index": 2,
            "color": "#3fb950",
            "is_done_stage": True,
        }
    )
    repository = TasksRepository(db_session)
    await repository.save(data=task_data(stage, 1, due_date=TODAY - timedelta(days=2)))
    await repository.save(data=task_data(stage, 2, due_date=TODAY + timedelta(days=3)))
    await repository.save(
        data=task_data(stage, 3, stage_id=done_stage.id, due_date=TODAY - timedelta(days=9))
    )

    rows = await repository.get_portfolio_counters(
        today=TODAY,
        soon_until=TODAY + timedelta(days=7),
    )

    row = next(item for item in rows if item.project_id == stage.project_id)
    assert row.total == 3
    assert row.done == 1
    assert row.overdue == 1
    assert row.due_soon == 1
    assert row.next_due_date == TODAY + timedelta(days=3)


@pytest.mark.asyncio
async def test_clear_wbs_node_releases_tasks_without_deleting(
    db_session: AsyncSession,
    stage: ProjectStage,
) -> None:
    node = await WbsNodesRepository(db_session).save(
        data={
            "project_id": stage.project_id,
            "parent_id": None,
            "title": "Backend",
            "position": 1000.0,
        }
    )
    repository = TasksRepository(db_session)
    task = await repository.save(data=task_data(stage, 1, wbs_node_id=node.id))

    released = await repository.clear_wbs_node(node_ids={node.id})
    tasks = await repository.get_by_project(project_id=stage.project_id)

    assert released == 1
    assert [item.id for item in tasks] == [task.id]
    assert tasks[0].wbs_node_id is None

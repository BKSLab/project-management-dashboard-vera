"""Прогресс полосы и критический путь шкалы календаря."""

from datetime import date
from types import SimpleNamespace

from src.services.critical_path import checklist_progress, critical_path

OPEN, DONE = 1, 2


def task(task_id: int, start: date | None, due: date | None, stage_id: int = OPEN, **extra):
    """Минимальная задача для расчёта."""
    return SimpleNamespace(id=task_id, stage_id=stage_id, start_date=start, due_date=due, **extra)


def link(link_id: int, predecessor: int, successor: int, lag: int = 0):
    """Связь Finish-to-Start."""
    return SimpleNamespace(
        id=link_id, predecessor_task_id=predecessor, successor_task_id=successor, lag_days=lag
    )


def checklist(*marks: bool) -> dict:
    return {"title": "Чек-лист", "items": [{"text": "x", "is_completed": m} for m in marks]}


def test_progress_counts_checked_items_and_done_task_is_full() -> None:
    assert (
        checklist_progress(
            task(1, None, None, checklist=checklist(True, False, False)), is_done=False
        )
        == 33
    )
    assert (
        checklist_progress(task(1, None, None, checklist=checklist(True, True)), is_done=False)
        == 100
    )
    assert checklist_progress(task(1, None, None, checklist=None), is_done=True) == 100


def test_progress_is_unknown_without_checklist_items() -> None:
    assert checklist_progress(task(1, None, None, checklist=None), is_done=False) is None
    assert checklist_progress(task(1, None, None, checklist=checklist()), is_done=False) is None
    assert checklist_progress(SimpleNamespace(), is_done=False) is None


def test_longest_chain_is_critical_and_parallel_branch_has_slack() -> None:
    tasks = {
        1: task(1, date(2026, 9, 1), date(2026, 9, 5)),
        2: task(2, date(2026, 9, 5), date(2026, 9, 10)),
        3: task(3, date(2026, 9, 5), date(2026, 9, 7)),
    }
    result = critical_path(
        tasks=tasks,
        dependencies=[link(10, 1, 2), link(11, 1, 3)],
        done_stage_ids={DONE},
        project_due_date=None,
        latest_open_due_date=date(2026, 9, 10),
    )

    assert result.task_ids == {1, 2}
    assert result.dependency_ids == {10}
    assert result.finish_date == date(2026, 9, 10)


def test_earlier_project_deadline_makes_late_chain_negative_slack() -> None:
    tasks = {
        1: task(1, date(2026, 9, 1), date(2026, 9, 5)),
        2: task(2, date(2026, 9, 6), date(2026, 9, 12)),
        3: task(3, date(2026, 9, 1), date(2026, 9, 3)),
    }
    result = critical_path(
        tasks=tasks,
        dependencies=[link(10, 1, 2, lag=1)],
        done_stage_ids={DONE},
        project_due_date=date(2026, 9, 11),
        latest_open_due_date=date(2026, 9, 12),
    )

    assert result.task_ids == {1, 2}
    assert result.finish_date == date(2026, 9, 11)


def test_done_and_undated_tasks_are_never_critical() -> None:
    tasks = {
        1: task(1, date(2026, 9, 1), date(2026, 9, 20), stage_id=DONE),
        2: task(2, None, None),
        3: task(3, None, date(2026, 9, 10)),
    }
    result = critical_path(
        tasks=tasks,
        dependencies=[link(10, 1, 3), link(11, 2, 3)],
        done_stage_ids={DONE},
        project_due_date=None,
        latest_open_due_date=date(2026, 9, 10),
    )

    assert result.task_ids == {3}
    assert result.dependency_ids == set()


def test_without_any_target_date_nothing_is_critical() -> None:
    result = critical_path(
        tasks={1: task(1, date(2026, 9, 1), date(2026, 9, 2))},
        dependencies=[],
        done_stage_ids=set(),
        project_due_date=None,
        latest_open_due_date=None,
    )

    assert result.task_ids == set()


def test_cycle_does_not_hang_and_is_not_critical() -> None:
    tasks = {
        1: task(1, date(2026, 9, 1), date(2026, 9, 2)),
        2: task(2, date(2026, 9, 3), date(2026, 9, 4)),
    }
    result = critical_path(
        tasks=tasks,
        dependencies=[link(10, 1, 2), link(11, 2, 1)],
        done_stage_ids=set(),
        project_due_date=None,
        latest_open_due_date=date(2026, 9, 4),
    )

    assert result.task_ids == set()


def test_long_chain_does_not_hit_recursion_limit() -> None:
    size = 3000
    tasks = {i: task(i, date(2026, 1, 1), date(2026, 1, 1)) for i in range(1, size + 1)}
    result = critical_path(
        tasks=tasks,
        dependencies=[link(i, i, i + 1) for i in range(1, size)],
        done_stage_ids=set(),
        project_due_date=None,
        latest_open_due_date=date(2026, 1, 1),
    )

    assert len(result.task_ids) == size

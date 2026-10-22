from datetime import date

from src.utils.workload import DayLoad, load_level, spread_task


def test_tasks_are_counted_only_on_working_days_inside_view():
    loads: dict[date, DayLoad] = {}
    spread_task(
        loads,
        key="A-1",
        start_date=date(2026, 12, 30),
        due_date=date(2027, 1, 12),
        date_from=date(2026, 12, 28),
        date_to=date(2027, 1, 11),
    )
    assert {day: load.tasks for day, load in loads.items()} == {
        date(2026, 12, 30): 1,
        date(2027, 1, 11): 1,
    }
    assert loads[date(2026, 12, 30)].keys == ["A-1"]
    spread_task(
        loads,
        key="A-2",
        start_date=None,
        due_date=date(2027, 1, 9),
        date_from=date(2027, 1, 1),
        date_to=date(2027, 1, 31),
    )
    assert date(2027, 1, 9) not in loads


def test_count_levels_and_missing_dates():
    assert [load_level(tasks=value) for value in range(5)] == [0, 1, 2, 3, 3]
    loads = {}
    spread_task(
        loads,
        key="A-1",
        start_date=None,
        due_date=None,
        date_from=date(2026, 10, 1),
        date_to=date(2026, 10, 31),
    )
    assert loads == {}

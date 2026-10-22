"""Загрузка по количеству задач на рабочих днях. Уровни: 1 — норма, 2 — плотно, 3 и более — перегруз."""

from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache

from src.utils.holidays_ru import holiday_days

OFF_KINDS = frozenset({"HOLIDAY", "DAY_OFF"})


@lru_cache(maxsize=16)
def _year_adjustments(year: int) -> dict[date, str]:
    """Отклонения года от пятидневки: дата → код."""
    return {day: kind for day, kind, _ in holiday_days(year) or []}


def is_working_day(day: date) -> bool:
    """Рабочий ли день по производственному календарю РФ.

    Для года без опубликованного календаря — обычная пятидневка.
    """
    kind = _year_adjustments(day.year).get(day)
    if kind == "WORKING_DAY" or kind == "SHORT_DAY":
        return True
    if kind in OFF_KINDS:
        return False
    return day.weekday() < 5


def task_interval(start_date: date | None, due_date: date | None) -> tuple[date, date] | None:
    """Интервал задачи с подменой отсутствующей границы известной."""
    first = start_date or due_date
    last = due_date or start_date
    if first is None or last is None:
        return None
    if last < first:
        first, last = last, first
    return first, last


def working_days(first: date, last: date) -> list[date]:
    """Рабочие дни отрезка включительно."""
    return [
        first + timedelta(days=offset)
        for offset in range((last - first).days + 1)
        if is_working_day(first + timedelta(days=offset))
    ]


@dataclass(slots=True)
class DayLoad:
    """Загрузка по количеству задач на рабочих днях. Уровни: 1 — норма, 2 — плотно, 3 и более — перегруз."""

    tasks: int = 0
    keys: list[str] = field(default_factory=list)


def spread_task(
    loads: dict[date, DayLoad],
    *,
    key: str,
    start_date: date | None,
    due_date: date | None,
    date_from: date,
    date_to: date,
) -> None:
    """Раскладывает задачу по рабочим дням периода и добавляет в ``loads``."""
    interval = task_interval(start_date, due_date)
    if interval is None:
        return
    days = working_days(*interval)
    if not days:
        return
    for day in days:
        if day < date_from or day > date_to:
            continue
        load = loads.setdefault(day, DayLoad())
        load.tasks += 1
        load.keys.append(key)


def load_level(*, tasks: int) -> int:
    """Daily workload by task count: free, normal, busy, overloaded."""
    return min(max(tasks, 0), 3)

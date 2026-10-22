"""Прогресс и критический путь для шкалы (гантта) календаря проекта.

Модуль чистый: не ходит в БД, считает по уже загруженным задачам и связям,
поэтому календарь не делает ради этих полей ни одного лишнего запроса.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from src.db.models.tasks import Task


def checklist_progress(task: Task, *, is_done: bool) -> int | None:
    """Возвращает процент выполнения задачи для заливки полосы.

    Выполненная задача — 100. Иначе доля отмеченных пунктов чек-листа,
    округлённая вниз (99,5% не показываем как 100%). Без чек-листа или
    с пустым чек-листом — ``None``: прогресс неизвестен, полоса без заливки.
    """
    if is_done:
        return 100
    checklist = getattr(task, "checklist", None) or {}
    items = checklist.get("items") or []
    if not items:
        return None
    completed = sum(1 for item in items if item.get("is_completed") is True)
    return completed * 100 // len(items)


@dataclass(slots=True)
class CriticalPathResult:
    """Задачи и связи критического пути проекта."""

    task_ids: set[int]
    dependency_ids: set[int]
    finish_date: date | None


def critical_path(
    *,
    tasks: dict[int, Task],
    dependencies,
    done_stage_ids: set[int],
    project_due_date: date | None,
    latest_open_due_date: date | None,
) -> CriticalPathResult:
    """Считает критический путь обратным проходом по связям Finish-to-Start.

    Цель ``F`` — самый поздний срок открытой задачи проекта; если дедлайн
    проекта раньше, то дедлайн (тогда всё, что в него не влезает, получает
    отрицательный запас). Так на шкале всегда видна цепочка, определяющая
    окончание проекта, даже когда до дедлайна есть запас. Для открытой задачи с датами поздний финиш
    ``LF = min(F, min по последователям (LS(s) - lag))``, поздний старт
    ``LS = LF - длительность``, запас ``slack = LF - срок``. Критична задача
    с ``slack <= 0``; связь критична, если критичны обе задачи и у связи нет
    свободного запаса (``старт последователя - lag - срок предшественника <= 0``).
    Выполненные задачи и задачи без дат в расчёт не входят.
    """
    candidates = [value for value in (project_due_date, latest_open_due_date) if value]
    finish = min(candidates) if candidates else None
    if finish is None:
        return CriticalPathResult(task_ids=set(), dependency_ids=set(), finish_date=None)

    def bounds(task: Task) -> tuple[date, date] | None:
        start = task.start_date or task.due_date
        end = task.due_date or task.start_date
        if start is None or end is None:
            return None
        return start, end

    open_tasks = {
        task_id: dates
        for task_id, task in tasks.items()
        if task.stage_id not in done_stage_ids and (dates := bounds(task)) is not None
    }
    successors: dict[int, list] = defaultdict(list)
    for dependency in dependencies:
        if (
            dependency.predecessor_task_id in open_tasks
            and dependency.successor_task_id in open_tasks
        ):
            successors[dependency.predecessor_task_id].append(dependency)

    # Обратный проход в топологическом порядке (Кан) — без рекурсии, чтобы
    # длинная цепочка не упёрлась в предел глубины стека.
    pending = {task_id: len(successors[task_id]) for task_id in open_tasks}
    predecessors: dict[int, list] = defaultdict(list)
    for items in successors.values():
        for dependency in items:
            predecessors[dependency.successor_task_id].append(dependency)
    queue = [task_id for task_id, count in pending.items() if count == 0]
    late_finish: dict[int, date] = {}
    while queue:
        task_id = queue.pop()
        value = finish
        for dependency in successors[task_id]:
            successor_start, successor_end = open_tasks[dependency.successor_task_id]
            successor_late_start = late_finish[dependency.successor_task_id] - (
                successor_end - successor_start
            )
            value = min(value, successor_late_start - timedelta(days=dependency.lag_days))
        late_finish[task_id] = value
        for dependency in predecessors[task_id]:
            pending[dependency.predecessor_task_id] -= 1
            if pending[dependency.predecessor_task_id] == 0:
                queue.append(dependency.predecessor_task_id)
    # Цикл сервис связей не допускает; если он всё же есть, его задачи не критичны.

    critical = {
        task_id
        for task_id, (_, end) in open_tasks.items()
        if task_id in late_finish and late_finish[task_id] <= end
    }
    critical_links = {
        dependency.id
        for items in successors.values()
        for dependency in items
        if dependency.predecessor_task_id in critical
        and dependency.successor_task_id in critical
        and (
            open_tasks[dependency.successor_task_id][0]
            - timedelta(days=dependency.lag_days)
            - open_tasks[dependency.predecessor_task_id][1]
        ).days
        <= 0
    }
    return CriticalPathResult(task_ids=critical, dependency_ids=critical_links, finish_date=finish)

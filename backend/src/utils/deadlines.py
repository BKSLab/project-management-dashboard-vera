from datetime import date

from sqlalchemy import and_
from sqlalchemy.sql.elements import ColumnElement

DUE_SOON_DAYS = 7


def is_task_overdue(*, due_date: date | None, is_done: bool, today: date) -> bool:
    """Возвращает единый признак просроченной задачи."""
    return not is_done and due_date is not None and due_date < today


def is_task_due_soon(
    *,
    due_date: date | None,
    is_done: bool,
    today: date,
    soon_until: date,
) -> bool:
    """Возвращает признак незавершённой задачи с близким сроком."""
    return not is_done and due_date is not None and today <= due_date <= soon_until


def overdue_sql(
    *,
    due_date_column: ColumnElement,
    is_done_column: ColumnElement,
    today: date,
) -> ColumnElement[bool]:
    """Строит SQL-предикат с той же семантикой просрочки."""
    return and_(is_done_column.is_(False), due_date_column.is_not(None), due_date_column < today)


def due_soon_sql(
    *,
    due_date_column: ColumnElement,
    is_done_column: ColumnElement,
    today: date,
    soon_until: date,
) -> ColumnElement[bool]:
    """Строит SQL-предикат близкого срока с общей семантикой."""
    return and_(
        is_done_column.is_(False),
        due_date_column.is_not(None),
        due_date_column >= today,
        due_date_column <= soon_until,
    )

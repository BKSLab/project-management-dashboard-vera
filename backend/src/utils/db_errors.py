"""Нормализация деталей ошибок ограничений разных async-драйверов PostgreSQL."""

from sqlalchemy.exc import IntegrityError


def get_integrity_constraint_name(error: IntegrityError) -> str | None:
    """Возвращает имя ограничения из DBAPI-обёртки или исходной ошибки драйвера."""
    original = error.orig
    constraint_name = getattr(original, "constraint_name", None)
    if isinstance(constraint_name, str):
        return constraint_name
    driver_error = getattr(original, "__cause__", None)
    nested_constraint_name = getattr(driver_error, "constraint_name", None)
    return nested_constraint_name if isinstance(nested_constraint_name, str) else None

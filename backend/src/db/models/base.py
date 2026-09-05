from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Базовая модель.

    `eager_defaults` включён явно: PostgreSQL возвращает серверные значения
    прямо из `INSERT ... RETURNING` и `UPDATE ... RETURNING`, поэтому после
    записи не нужен отдельный SELECT ради `created_at` и `updated_at`.
    Без него SQLAlchemy пометила бы эти поля устаревшими, и запись
    превращалась бы в два обращения к базе вместо одного.
    """

    __mapper_args__ = {"eager_defaults": True}


class TimestampMixin:
    """Миксин с таймстемпами создания/обновления записи."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Дата и время создания записи.",
        comment="Дата и время создания записи.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="Дата и время последнего обновления записи.",
        comment="Дата и время последнего обновления записи.",
    )

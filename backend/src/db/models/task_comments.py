from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Computed, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .tasks import Task


class TaskComment(Base):
    """Комментарий к задаче канбана."""

    __tablename__ = "task_comments"
    __table_args__ = (
        Index("ix_task_comments_search_vector", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        doc="Идентификатор комментария.",
        comment="Уникальный идентификатор комментария.",
    )
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        doc="Задача комментария.",
        comment="Идентификатор задачи, к которой относится комментарий.",
    )
    author_name: Mapped[str | None] = mapped_column(
        String(length=255),
        nullable=True,
        doc="Подпись автора.",
        comment="Необязательная свободная подпись автора комментария.",
    )
    body_md: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Текст комментария.",
        comment="Текст комментария в формате Markdown.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Дата создания комментария.",
        comment="Дата и время создания комментария.",
    )
    search_vector: Mapped[object] = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('russian', coalesce(body_md, '')), 'A') || "
            "setweight(to_tsvector('russian', coalesce(author_name, '')), 'B')",
            persisted=True,
        ),
        nullable=False,
        doc="Вычисляемый FTS-вектор комментария.",
        comment="Взвешенный FTS-вектор текста и автора комментария.",
    )

    task: Mapped[Task] = relationship("Task", back_populates="comments")

    def __repr__(self) -> str:
        return f"<TaskComment(id={self.id}, task_id={self.task_id})>"

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Computed, Date, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .kanban_stages import KanbanStage
    from .task_activity import TaskActivity
    from .task_comments import TaskComment
    from .wbs import WbsItem


class KanbanTask(Base, TimestampMixin):
    """Карточка канбан-доски."""

    __tablename__ = "kanban_tasks"
    __table_args__ = (
        UniqueConstraint("wbs_item_id", name="uq_kanban_tasks_wbs_item_id"),
        Index("ix_kanban_tasks_search_vector", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        doc="Идентификатор задачи канбана.",
        comment="Уникальный идентификатор задачи.",
    )
    wbs_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("wbs_items.id", ondelete="SET NULL"),
        nullable=True,
        doc="Связь с листовым узлом ИСР.",
        comment="Связанный листовой узел ИСР; NULL для ручной задачи.",
    )
    stage_id: Mapped[int] = mapped_column(
        ForeignKey("kanban_stages.id", ondelete="RESTRICT"),
        nullable=False,
        doc="Текущая стадия задачи.",
        comment="Идентификатор текущей стадии задачи.",
    )
    title: Mapped[str] = mapped_column(
        String(length=512),
        nullable=False,
        doc="Заголовок задачи.",
        comment="Заголовок задачи канбана.",
    )
    description_md: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Markdown-описание задачи.",
        comment="Описание задачи в формате Markdown.",
    )
    due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        doc="Срок исполнения.",
        comment="Плановая дата завершения задачи.",
    )
    position: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        doc="Позиция внутри стадии.",
        comment="Позиция сортировки задачи внутри стадии.",
    )
    search_vector: Mapped[object] = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('russian', coalesce(title, '')), 'A') || "
            "setweight(to_tsvector('russian', coalesce(description_md, '')), 'B')",
            persisted=True,
        ),
        nullable=False,
        doc="Вычисляемый FTS-вектор задачи.",
        comment="Взвешенный FTS-вектор заголовка и описания задачи.",
    )

    wbs_item: Mapped[WbsItem | None] = relationship("WbsItem", back_populates="task")
    stage: Mapped[KanbanStage] = relationship("KanbanStage", back_populates="tasks")
    comments: Mapped[list[TaskComment]] = relationship(
        "TaskComment",
        back_populates="task",
        cascade="all, delete-orphan",
    )
    activity: Mapped[list[TaskActivity]] = relationship(
        "TaskActivity",
        back_populates="task",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<KanbanTask(id={self.id}, title={self.title!r})>"

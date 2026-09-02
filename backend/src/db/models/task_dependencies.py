from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .projects import Project
    from .tasks import Task


class TaskDependencyType(str, enum.Enum):
    """Поддерживаемая семантика связи задач."""

    FINISH_TO_START = "FINISH_TO_START"


class TaskDependency(Base):
    """Направленная зависимость predecessor → successor внутри проекта."""

    __tablename__ = "task_dependencies"
    __table_args__ = (
        UniqueConstraint(
            "predecessor_task_id",
            "successor_task_id",
            name="uq_task_dependencies_predecessor_successor",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    predecessor_task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    successor_task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dependency_type: Mapped[TaskDependencyType] = mapped_column(
        Enum(TaskDependencyType, name="task_dependency_type"),
        nullable=False,
        default=TaskDependencyType.FINISH_TO_START,
    )
    lag_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    project: Mapped[Project] = relationship("Project", back_populates="task_dependencies")
    predecessor: Mapped[Task] = relationship(
        "Task",
        foreign_keys=[predecessor_task_id],
        back_populates="successor_links",
    )
    successor: Mapped[Task] = relationship(
        "Task",
        foreign_keys=[successor_task_id],
        back_populates="predecessor_links",
    )

    def __repr__(self) -> str:
        return (
            f"<TaskDependency(id={self.id}, predecessor={self.predecessor_task_id}, "
            f"successor={self.successor_task_id})>"
        )

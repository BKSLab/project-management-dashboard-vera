from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .projects import Project
    from .tasks import Task


class ProjectStage(Base):
    """Колонка канбан-доски конкретного проекта."""

    __tablename__ = "project_stages"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_project_stages_project_name"),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        doc="Идентификатор стадии.",
        comment="Уникальный идентификатор стадии канбана.",
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Проект, которому принадлежит стадия.",
        comment="Идентификатор проекта-владельца стадии.",
    )
    name: Mapped[str] = mapped_column(
        String(length=100),
        nullable=False,
        doc="Название стадии.",
        comment="Название стадии канбан-доски.",
    )
    order_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Порядок колонки на доске.",
        comment="Порядок отображения колонки на канбан-доске.",
    )
    color: Mapped[str] = mapped_column(
        String(length=20),
        nullable=False,
        doc="HEX-цвет стадии.",
        comment="HEX-цвет стадии в интерфейсе.",
    )
    is_done_stage: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Признак завершающей стадии.",
        comment="Признак стадии, завершающей выполнение задачи.",
    )

    project: Mapped[Project] = relationship("Project", back_populates="stages")
    tasks: Mapped[list[Task]] = relationship("Task", back_populates="stage")

    def __repr__(self) -> str:
        return f"<ProjectStage(id={self.id}, project_id={self.project_id}, name={self.name!r})>"

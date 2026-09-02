from __future__ import annotations

import enum
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .projects import Project
    from .wbs_nodes import WbsNode


class ProjectMilestoneStatus(str, enum.Enum):
    """Простой статус проектной вехи без отдельного workflow."""

    PLANNED = "PLANNED"
    ACHIEVED = "ACHIEVED"


class ProjectMilestone(Base, TimestampMixin):
    """Календарная веха проекта."""

    __tablename__ = "project_milestones"
    __table_args__ = (Index("ix_project_milestones_project_due_date", "project_id", "due_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(length=255), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[ProjectMilestoneStatus] = mapped_column(
        Enum(ProjectMilestoneStatus, name="project_milestone_status"),
        nullable=False,
        default=ProjectMilestoneStatus.PLANNED,
    )
    wbs_node_id: Mapped[int | None] = mapped_column(
        ForeignKey("wbs_nodes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    description_md: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[Project] = relationship("Project", back_populates="milestones")
    wbs_node: Mapped[WbsNode | None] = relationship("WbsNode", back_populates="milestones")

    def __repr__(self) -> str:
        return (
            f"<ProjectMilestone(id={self.id}, project_id={self.project_id}, title={self.title!r})>"
        )

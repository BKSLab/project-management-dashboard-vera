from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .project_members import ProjectMember
    from .tasks import Task


class TaskParticipantRole(str, enum.Enum):
    """Роль участника команды в конкретной задаче."""

    EXECUTOR = "EXECUTOR"
    REPORTER = "REPORTER"
    OBSERVER = "OBSERVER"


class TaskParticipant(Base, TimestampMixin):
    """Ролевое назначение члена проектной команды на задачу."""

    __tablename__ = "task_participants"
    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "project_member_id",
            "role",
            name="uq_task_participants_task_member_role",
        ),
        Index(
            "uq_task_participants_executor",
            "task_id",
            unique=True,
            postgresql_where=text("role = 'EXECUTOR'"),
        ),
        Index(
            "uq_task_participants_reporter",
            "task_id",
            unique=True,
            postgresql_where=text("role = 'REPORTER'"),
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        doc="Идентификатор назначения.",
        comment="Уникальный идентификатор ролевого назначения на задачу.",
    )
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Задача назначения.",
        comment="Идентификатор задачи.",
    )
    project_member_id: Mapped[int] = mapped_column(
        ForeignKey("project_members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Участник команды проекта.",
        comment="Идентификатор участия пользователя в проекте.",
    )
    role: Mapped[TaskParticipantRole] = mapped_column(
        Enum(TaskParticipantRole, name="task_participant_role"),
        nullable=False,
        doc="Роль в задаче: исполнитель, постановщик или наблюдатель.",
        comment="Роль участника в задаче.",
    )

    task: Mapped[Task] = relationship("Task", back_populates="participants")
    project_member: Mapped[ProjectMember] = relationship(
        "ProjectMember",
        back_populates="task_participations",
    )

    def __repr__(self) -> str:
        return (
            f"<TaskParticipant(task_id={self.task_id}, "
            f"project_member_id={self.project_member_id}, role={self.role})>"
        )

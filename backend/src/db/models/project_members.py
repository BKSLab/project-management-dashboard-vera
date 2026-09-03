from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .projects import Project
    from .task_participants import TaskParticipant
    from .users import User


class ProjectRole(str, enum.Enum):
    """Роль пользователя в проекте."""

    OWNER = "OWNER"
    MEMBER = "MEMBER"


class ProjectMember(Base, TimestampMixin):
    """Участие пользователя в проекте.

    Доступ к проекту и всему его содержимому проверяется через наличие этой
    строки. Владелец получает её при создании проекта, поэтому выборки не
    различают владельца и приглашённого участника.
    """

    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_members_project_user"),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        doc="Идентификатор участия.",
        comment="Уникальный идентификатор участия в проекте.",
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Проект, к которому открыт доступ.",
        comment="Идентификатор проекта.",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Пользователь, имеющий доступ.",
        comment="Идентификатор пользователя.",
    )
    role: Mapped[ProjectRole] = mapped_column(
        Enum(ProjectRole, name="project_role"),
        nullable=False,
        default=ProjectRole.MEMBER,
        doc="Роль в проекте: владелец или участник.",
        comment="Роль пользователя в проекте.",
    )

    project: Mapped[Project] = relationship("Project", back_populates="members")
    user: Mapped[User] = relationship("User", back_populates="memberships")
    task_participations: Mapped[list[TaskParticipant]] = relationship(
        "TaskParticipant",
        back_populates="project_member",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return (
            f"<ProjectMember(project_id={self.project_id}, "
            f"user_id={self.user_id}, role={self.role})>"
        )

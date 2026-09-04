from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .projects import Project
    from .tasks import Task
    from .users import User


class ProjectStickerColor(str, enum.Enum):
    """Ограниченная спокойная палитра стикеров проекта."""

    NEUTRAL = "neutral"
    YELLOW = "yellow"
    BLUE = "blue"
    GREEN = "green"
    RED = "red"
    VIOLET = "violet"


class ProjectSticker(Base, TimestampMixin):
    """Короткая общая заметка на доске проекта."""

    __tablename__ = "project_stickers"
    __table_args__ = (
        CheckConstraint(
            "char_length(btrim(body)) BETWEEN 1 AND 2000",
            name="ck_project_stickers_body_length",
        ),
        CheckConstraint("revision >= 1", name="ck_project_stickers_revision_positive"),
        CheckConstraint(
            "canvas_x BETWEEN -1000000.0 AND 1000000.0",
            name="ck_project_stickers_canvas_x_range",
        ),
        CheckConstraint(
            "canvas_y BETWEEN -1000000.0 AND 1000000.0",
            name="ck_project_stickers_canvas_y_range",
        ),
        Index("ix_project_stickers_project_created", "project_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        doc="Идентификатор стикера.",
        comment="Уникальный идентификатор стикера Project Board.",
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Проект, которому принадлежит стикер.",
        comment="Идентификатор проекта-владельца стикера.",
    )
    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Текст стикера без пользовательского HTML.",
        comment="Текст общего стикера проекта.",
    )
    color: Mapped[ProjectStickerColor] = mapped_column(
        Enum(
            ProjectStickerColor,
            name="project_sticker_color",
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        nullable=False,
        default=ProjectStickerColor.YELLOW,
        doc="Цвет из ограниченной палитры.",
        comment="Визуальный цвет стикера.",
    )
    canvas_x: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=40.0,
        doc="Координата X левого верхнего угла стикера на холсте.",
        comment="Координата X стикера на Project Board.",
    )
    canvas_y: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=40.0,
        doc="Координата Y левого верхнего угла стикера на холсте.",
        comment="Координата Y стикера на Project Board.",
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Пользователь-создатель, если профиль ещё существует.",
        comment="Идентификатор автора стикера.",
    )
    created_by_username_snapshot: Mapped[str] = mapped_column(
        String(length=50),
        nullable=False,
        doc="Неизменяемый логин автора на момент создания.",
        comment="Fallback-логин автора стикера.",
    )
    created_by_display_name_snapshot: Mapped[str] = mapped_column(
        String(length=302),
        nullable=False,
        doc="Неизменяемое имя автора на момент создания.",
        comment="Fallback-имя автора стикера.",
    )
    revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        doc="Версия для optimistic concurrency.",
        comment="Монотонная ревизия стикера.",
    )

    project: Mapped[Project] = relationship("Project", back_populates="stickers")
    created_by: Mapped[User | None] = relationship("User")
    task_links: Mapped[list[ProjectStickerTaskLink]] = relationship(
        "ProjectStickerTaskLink",
        back_populates="sticker",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ProjectStickerTaskLink.task_id",
    )

    def __repr__(self) -> str:
        return (
            f"<ProjectSticker(id={self.id}, project_id={self.project_id}, "
            f"revision={self.revision})>"
        )


class ProjectStickerTaskLink(Base):
    """Связь стикера с задачей того же проекта."""

    __tablename__ = "project_sticker_task_links"

    sticker_id: Mapped[int] = mapped_column(
        ForeignKey("project_stickers.id", ondelete="CASCADE"),
        primary_key=True,
        doc="Связанный стикер.",
        comment="Идентификатор стикера.",
    )
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
        doc="Связанная задача.",
        comment="Идентификатор задачи.",
    )

    sticker: Mapped[ProjectSticker] = relationship(
        "ProjectSticker",
        back_populates="task_links",
    )
    task: Mapped[Task] = relationship("Task")

    def __repr__(self) -> str:
        return f"<ProjectStickerTaskLink(sticker_id={self.sticker_id}, task_id={self.task_id})>"

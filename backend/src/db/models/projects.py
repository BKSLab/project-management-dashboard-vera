from __future__ import annotations

import enum
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Computed, Date, Enum, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .documents import Document
    from .project_stages import ProjectStage
    from .tasks import Task
    from .wbs_nodes import WbsNode


class ProjectStatus(str, enum.Enum):
    """Жизненный статус проекта."""

    PLANNING = "PLANNING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class Project(Base, TimestampMixin):
    """Проект — корневая сущность трекера."""

    __tablename__ = "projects"
    __table_args__ = (Index("ix_projects_search_vector", "search_vector", postgresql_using="gin"),)

    id: Mapped[int] = mapped_column(
        primary_key=True,
        doc="Идентификатор проекта.",
        comment="Уникальный идентификатор проекта.",
    )
    key: Mapped[str] = mapped_column(
        String(length=10),
        unique=True,
        nullable=False,
        index=True,
        doc="Короткий код проекта, используемый как префикс номера задачи.",
        comment="Уникальный короткий код проекта в верхнем регистре.",
    )
    name: Mapped[str] = mapped_column(
        String(length=255),
        nullable=False,
        doc="Название проекта.",
        comment="Человекочитаемое название проекта.",
    )
    description_md: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Markdown-описание проекта.",
        comment="Описание проекта в формате Markdown.",
    )
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="project_status"),
        nullable=False,
        default=ProjectStatus.PLANNING,
        doc="Текущий статус проекта.",
        comment="Жизненный статус проекта.",
    )
    color: Mapped[str] = mapped_column(
        String(length=20),
        nullable=False,
        doc="HEX-цвет проекта в интерфейсе.",
        comment="HEX-цвет, которым проект обозначается в интерфейсе.",
    )
    icon: Mapped[str | None] = mapped_column(
        String(length=8),
        nullable=True,
        doc="Эмодзи-иконка проекта.",
        comment="Необязательная эмодзи-иконка проекта.",
    )
    start_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        doc="Дата старта проекта.",
        comment="Плановая дата начала проекта.",
    )
    due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        doc="Плановая дата завершения проекта.",
        comment="Плановая дата завершения проекта.",
    )
    order_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Порядок проекта в списке.",
        comment="Порядок отображения проекта в списке и переключателе.",
    )
    search_vector: Mapped[object] = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('russian', coalesce(name, '')), 'A') || "
            "setweight(to_tsvector('russian', coalesce(description_md, '')), 'B')",
            persisted=True,
        ),
        nullable=False,
        doc="Вычисляемый FTS-вектор проекта.",
        comment="Взвешенный FTS-вектор названия и описания проекта.",
    )

    stages: Mapped[list[ProjectStage]] = relationship(
        "ProjectStage",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    tasks: Mapped[list[Task]] = relationship(
        "Task",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    wbs_nodes: Mapped[list[WbsNode]] = relationship(
        "WbsNode",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    documents: Mapped[list[Document]] = relationship(
        "Document",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, key={self.key!r}, name={self.name!r})>"

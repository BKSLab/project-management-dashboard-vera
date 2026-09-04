from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .projects import Project
    from .users import User


class AnalyticsReport(Base):
    """Снимок аналитического свода, сформированного моделью по кнопке.

    Запись неизменяема: свод описывает состояние проектов на момент запроса,
    поэтому у него нет ``updated_at`` — новый анализ создаёт новую строку.
    """

    __tablename__ = "analytics_reports"
    __table_args__ = (
        Index("ix_analytics_reports_project_created", "project_id", "created_at"),
        Index("ix_analytics_reports_author_created", "created_by_user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        comment="Уникальный идентификатор аналитического свода.",
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        comment="Проект свода; NULL — свод по всему портфелю пользователя.",
    )
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Пользователь, запросивший анализ; NULL после удаления профиля.",
    )
    created_by_display_name_snapshot: Mapped[str] = mapped_column(
        String(length=302),
        nullable=False,
        comment="Имя автора запроса на момент формирования свода.",
    )
    llm_model: Mapped[str] = mapped_column(
        String(length=255),
        nullable=False,
        comment="Модель, сформировавшая свод: своды разных моделей несравнимы.",
    )
    duration_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Длительность формирования свода в миллисекундах.",
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Тело свода: оценка состояния, находки, прогресс и рекомендации.",
    )
    context_summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        comment="Что вошло в контекст модели и что было отсечено лимитом.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Момент формирования свода.",
    )

    project: Mapped[Project | None] = relationship("Project")
    created_by: Mapped[User | None] = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<AnalyticsReport(id={self.id}, project_id={self.project_id}, "
            f"created_at={self.created_at})>"
        )

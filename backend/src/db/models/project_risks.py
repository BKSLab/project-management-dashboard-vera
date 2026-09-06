from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.schemas.enums import RiskRating, RiskResponseStrategy, RiskSource, RiskStatus

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .projects import Project


class ProjectRisk(Base, TimestampMixin):
    """Зарегистрированное рисковое событие проекта."""

    __tablename__ = "project_risks"
    __table_args__ = (
        CheckConstraint(
            "char_length(btrim(title)) BETWEEN 1 AND 255", name="ck_project_risks_title"
        ),
        CheckConstraint(
            "char_length(btrim(description)) BETWEEN 1 AND 20000",
            name="ck_project_risks_description",
        ),
        Index("ix_project_risks_project_status", "project_id", "status"),
        Index("ix_project_risks_project_level", "project_id", "risk_level"),
        Index("ix_project_risks_project_review", "project_id", "review_date"),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True, doc="Идентификатор риска.", comment="Номер риска RISK-id."
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        doc="Проект риска.",
        comment="Проект, которому принадлежит риск.",
    )
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Необязательная задача того же проекта.",
        comment="При удалении задачи ссылка обнуляется, риск сохраняется.",
    )
    title: Mapped[str] = mapped_column(
        String(255), nullable=False, doc="Название события.", comment="Краткое название риска."
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Markdown-описание события и последствий.",
        comment="Описание риска в Markdown.",
    )
    probability: Mapped[RiskRating] = mapped_column(
        Enum(RiskRating, name="risk_rating"),
        nullable=False,
        doc="Вероятность события.",
        comment="Выбранная вероятность LOW/MEDIUM/HIGH.",
    )
    impact: Mapped[RiskRating] = mapped_column(
        Enum(RiskRating, name="risk_rating"),
        nullable=False,
        doc="Влияние события на проект.",
        comment="Выбранное влияние LOW/MEDIUM/HIGH.",
    )
    risk_level: Mapped[RiskRating] = mapped_column(
        Enum(RiskRating, name="risk_rating"),
        nullable=False,
        doc="Оценка, вычисленная сервисом по матрице.",
        comment="Итоговый уровень риска; клиент его не задаёт.",
    )
    status: Mapped[RiskStatus] = mapped_column(
        Enum(RiskStatus, name="risk_status"),
        nullable=False,
        server_default=RiskStatus.OPEN.value,
        doc="Состояние рискового события.",
        comment="OPEN, MITIGATING, OCCURRED или CLOSED.",
    )
    response_strategy: Mapped[RiskResponseStrategy] = mapped_column(
        Enum(RiskResponseStrategy, name="risk_response_strategy"),
        nullable=False,
        doc="Стратегия работы с риском.",
        comment="Избежать, снизить, передать или принять.",
    )
    mitigation_plan: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="",
        doc="Превентивные меры в Markdown.",
        comment="Что сделать заранее для снижения вероятности или влияния.",
    )
    response_plan: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default="",
        doc="Действия при реализации события в Markdown.",
        comment="План реагирования на риск.",
    )
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Ответственный участник проекта.",
        comment="Пользователь, отвечающий за риск; назначение проверяется сервисом.",
    )
    review_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        doc="Следующая дата пересмотра.",
        comment="Дата контроля, не срок реализации риска.",
    )
    source: Mapped[RiskSource] = mapped_column(
        Enum(RiskSource, name="risk_source"),
        nullable=False,
        server_default=RiskSource.MANUAL.value,
        doc="Происхождение принятого человеком риска.",
        comment="MANUAL либо подтверждённое человеком AI_SUGGESTED.",
    )

    project: Mapped[Project] = relationship("Project", back_populates="risks")

    @property
    def key(self) -> str:
        """Возвращает стабильный публичный номер риска."""
        return f"RISK-{self.id}"

    def __repr__(self) -> str:
        return f"<ProjectRisk(id={self.id}, project_id={self.project_id}, status={self.status})>"

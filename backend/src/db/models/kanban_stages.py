from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .kanban_tasks import KanbanTask


class KanbanStage(Base):
    """Колонка канбан-доски."""

    __tablename__ = "kanban_stages"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        doc="Идентификатор стадии канбана.",
        comment="Уникальный идентификатор стадии канбана.",
    )
    name: Mapped[str] = mapped_column(
        String(length=100),
        nullable=False,
        doc="Название стадии канбана.",
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
        doc="HEX-цвет колонки.",
        comment="HEX-цвет стадии в интерфейсе.",
    )
    is_done_stage: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Признак завершающей стадии.",
        comment="Признак стадии, завершающей выполнение задачи.",
    )

    tasks: Mapped[list[KanbanTask]] = relationship(
        "KanbanTask",
        back_populates="stage",
    )

    def __repr__(self) -> str:
        return f"<KanbanStage(id={self.id}, name={self.name!r})>"

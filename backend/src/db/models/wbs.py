from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .kanban_tasks import KanbanTask


class WbsRole(str, enum.Enum):
    """Роль, ответственная за пункт ИСР."""

    PM = "PM"
    BE = "BE"
    FE = "FE"
    UXR = "UXR"
    UXD = "UXD"
    EXPERT = "EXPERT"
    QA = "QA"
    BA = "BA"
    MKT = "MKT"


class WbsItem(Base):
    """Узел иерархической структуры работ (ИСР)."""

    __tablename__ = "wbs_items"
    __table_args__ = (UniqueConstraint("code", name="uq_wbs_items_code"),)

    id: Mapped[int] = mapped_column(
        primary_key=True,
        doc="Идентификатор узла ИСР.",
        comment="Уникальный идентификатор узла ИСР.",
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("wbs_items.id", ondelete="CASCADE"),
        nullable=True,
        doc="Родительский узел дерева. NULL — фаза верхнего уровня.",
        comment="Родительский узел; NULL для корневой фазы.",
    )
    code: Mapped[str] = mapped_column(
        String(length=20),
        nullable=False,
        doc='Код узла в нотации ИСР, например "1.1.1".',
        comment="Иерархический код узла ИСР.",
    )
    phase_name: Mapped[str | None] = mapped_column(
        String(length=255),
        nullable=True,
        doc="Название фазы. Заполнено только у узлов верхнего уровня.",
        comment="Название фазы для корневого узла.",
    )
    title: Mapped[str] = mapped_column(
        String(length=512),
        nullable=False,
        doc="Название задачи/подзадачи.",
        comment="Название работы или раздела ИСР.",
    )
    role: Mapped[WbsRole | None] = mapped_column(
        Enum(WbsRole, name="wbs_role"),
        nullable=True,
        doc="Роль, ответственная за узел.",
        comment="Ответственная роль за выполнение работы.",
    )
    order_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Порядок среди братских узлов.",
        comment="Порядок отображения среди соседних узлов.",
    )
    is_leaf: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc="Признак того, что у узла есть связанная KanbanTask.",
        comment="Признак листового узла со связанной задачей канбана.",
    )

    children: Mapped[list[WbsItem]] = relationship(
        "WbsItem",
        back_populates="parent",
        cascade="all, delete-orphan",
    )
    parent: Mapped[WbsItem | None] = relationship(
        "WbsItem",
        back_populates="children",
        remote_side=[id],
    )
    task: Mapped[KanbanTask | None] = relationship(
        "KanbanTask",
        back_populates="wbs_item",
        uselist=False,
    )

    def __repr__(self) -> str:
        return f"<WbsItem(code={self.code}, title={self.title!r})>"

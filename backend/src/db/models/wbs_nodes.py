from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .projects import Project
    from .tasks import Task


class WbsNode(Base, TimestampMixin):
    """Структурный узел ИСР — контейнер для задач проекта.

    Узел не является задачей и не имеет собственного статуса. Номера ИСР
    (``1``, ``1.1``, ``1.2.1``) не хранятся: они вычисляются из ``parent_id``
    и ``position``. Координаты раскладки также не хранятся — их считает
    frontend.
    """

    __tablename__ = "wbs_nodes"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        doc="Идентификатор структурного узла.",
        comment="Уникальный идентификатор узла ИСР.",
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Проект, которому принадлежит узел. Узел не существует вне проекта.",
        comment="Идентификатор проекта-владельца узла ИСР.",
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("wbs_nodes.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Родительский узел. NULL — верхний уровень структуры.",
        comment="Родительский узел ИСР; NULL для узла верхнего уровня.",
    )
    title: Mapped[str] = mapped_column(
        String(length=255),
        nullable=False,
        doc="Название структурного блока.",
        comment="Название раздела ИСР.",
    )
    position: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        doc="Разреженная позиция среди узлов одного уровня.",
        comment="Позиция сортировки узла среди соседних узлов.",
    )

    project: Mapped[Project] = relationship("Project", back_populates="wbs_nodes")
    children: Mapped[list[WbsNode]] = relationship(
        "WbsNode",
        back_populates="parent",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    parent: Mapped[WbsNode | None] = relationship(
        "WbsNode",
        back_populates="children",
        remote_side=[id],
    )
    tasks: Mapped[list[Task]] = relationship("Task", back_populates="wbs_node")

    def __repr__(self) -> str:
        return f"<WbsNode(id={self.id}, project_id={self.project_id}, title={self.title!r})>"

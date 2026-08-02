from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .documents import Document
    from .kanban_tasks import KanbanTask
    from .wbs import WbsItem


class DocumentLink(Base):
    """Связь документа с задачей канбана или узлом ИСР."""

    __tablename__ = "document_links"
    __table_args__ = (
        CheckConstraint(
            "(kanban_task_id IS NOT NULL) <> (wbs_item_id IS NOT NULL)",
            name="ck_document_links_exactly_one_target",
        ),
        UniqueConstraint(
            "document_id",
            "kanban_task_id",
            name="uq_document_links_document_task",
        ),
        UniqueConstraint(
            "document_id",
            "wbs_item_id",
            name="uq_document_links_document_wbs",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        doc="Идентификатор связи документа.",
        comment="Уникальный идентификатор связи документа.",
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        doc="Документ, для которого создана связь.",
        comment="Идентификатор связанного документа.",
    )
    kanban_task_id: Mapped[int | None] = mapped_column(
        ForeignKey("kanban_tasks.id", ondelete="CASCADE"),
        nullable=True,
        doc="Заполнено, если связь с конкретной задачей канбана.",
        comment="Идентификатор связанной задачи канбана.",
    )
    wbs_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("wbs_items.id", ondelete="CASCADE"),
        nullable=True,
        doc="Заполнено, если связь с узлом ИСР.",
        comment="Идентификатор связанного узла ИСР.",
    )

    document: Mapped[Document] = relationship("Document")
    kanban_task: Mapped[KanbanTask | None] = relationship("KanbanTask")
    wbs_item: Mapped[WbsItem | None] = relationship("WbsItem")

    def __repr__(self) -> str:
        return (
            f"<DocumentLink(document_id={self.document_id}, "
            f"kanban_task_id={self.kanban_task_id}, wbs_item_id={self.wbs_item_id})>"
        )

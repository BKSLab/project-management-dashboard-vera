from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .documents import Document
    from .tasks import Task


class DocumentLink(Base):
    """Связь документа проекта с задачей."""

    __tablename__ = "document_links"
    __table_args__ = (
        UniqueConstraint("document_id", "task_id", name="uq_document_links_document_task"),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        doc="Идентификатор связи документа.",
        comment="Уникальный идентификатор связи документа.",
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Документ, для которого создана связь.",
        comment="Идентификатор связанного документа.",
    )
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Задача, с которой связан документ.",
        comment="Идентификатор связанной задачи.",
    )

    document: Mapped[Document] = relationship("Document")
    task: Mapped[Task] = relationship("Task")

    def __repr__(self) -> str:
        return f"<DocumentLink(document_id={self.document_id}, task_id={self.task_id})>"

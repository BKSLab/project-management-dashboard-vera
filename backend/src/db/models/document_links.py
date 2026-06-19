from typing import Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class DocumentLink(Base):
    """Связь документа с задачей канбана или узлом ИСР."""

    __tablename__ = 'document_links'

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey('documents.id', ondelete='CASCADE'),
        nullable=False,
        doc='Документ, для которого создана связь.'
    )
    kanban_task_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('kanban_tasks.id', ondelete='CASCADE'),
        nullable=True,
        doc='Заполнено, если связь с конкретной задачей канбана.'
    )
    wbs_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('wbs_items.id', ondelete='CASCADE'),
        nullable=True,
        doc='Заполнено, если связь с узлом ИСР.'
    )

    document: Mapped['Document'] = relationship('Document')
    kanban_task: Mapped[Optional['KanbanTask']] = relationship('KanbanTask')
    wbs_item: Mapped[Optional['WbsItem']] = relationship('WbsItem')

    def __repr__(self) -> str:
        return (
            f'<DocumentLink(document_id={self.document_id}, '
            f'kanban_task_id={self.kanban_task_id}, wbs_item_id={self.wbs_item_id})>'
        )

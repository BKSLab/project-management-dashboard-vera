import enum
from typing import Optional

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class WbsRole(str, enum.Enum):
    """Роль, ответственная за пункт ИСР."""

    PM = 'PM'
    BE = 'BE'
    FE = 'FE'
    UXR = 'UXR'
    UXD = 'UXD'
    EXPERT = 'EXPERT'
    QA = 'QA'
    BA = 'BA'
    MKT = 'MKT'


class WbsItem(Base):
    """Узел иерархической структуры работ (ИСР)."""

    __tablename__ = 'wbs_items'

    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('wbs_items.id', ondelete='CASCADE'),
        nullable=True,
        doc='Родительский узел дерева. NULL — фаза верхнего уровня.'
    )
    code: Mapped[str] = mapped_column(
        String(length=20),
        nullable=False,
        doc='Код узла в нотации ИСР, например "1.1.1".'
    )
    phase_name: Mapped[Optional[str]] = mapped_column(
        String(length=255),
        nullable=True,
        doc='Название фазы. Заполнено только у узлов верхнего уровня.'
    )
    title: Mapped[str] = mapped_column(
        String(length=512),
        nullable=False,
        doc='Название задачи/подзадачи.'
    )
    role: Mapped[Optional[WbsRole]] = mapped_column(
        Enum(WbsRole, name='wbs_role'),
        nullable=True,
        doc='Роль, ответственная за узел.'
    )
    order_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc='Порядок среди братских узлов.'
    )
    is_leaf: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc='Признак того, что у узла есть связанная KanbanTask.'
    )

    children: Mapped[list['WbsItem']] = relationship(
        'WbsItem',
        back_populates='parent',
        cascade='all, delete-orphan',
    )
    parent: Mapped[Optional['WbsItem']] = relationship(
        'WbsItem',
        back_populates='children',
        remote_side=[id],
    )
    task: Mapped[Optional['KanbanTask']] = relationship(
        'KanbanTask',
        back_populates='wbs_item',
        uselist=False,
    )

    def __repr__(self) -> str:
        return f'<WbsItem(code={self.code}, title={self.title!r})>'

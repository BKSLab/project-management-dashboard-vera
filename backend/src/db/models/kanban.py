import enum
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class TaskActivityEventType(str, enum.Enum):
    """Тип события в истории изменений задачи."""

    STAGE_CHANGED = 'STAGE_CHANGED'
    DUE_DATE_CHANGED = 'DUE_DATE_CHANGED'
    DESCRIPTION_CHANGED = 'DESCRIPTION_CHANGED'
    COMMENT_ADDED = 'COMMENT_ADDED'


class KanbanStage(Base):
    """Колонка канбан-доски."""

    __tablename__ = 'kanban_stages'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(length=100),
        nullable=False,
        doc='Название стадии («Backlog», «To Do» и т.д.).'
    )
    order_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc='Порядок колонок на доске.'
    )
    color: Mapped[str] = mapped_column(
        String(length=20),
        nullable=False,
        doc='HEX-цвет колонки.'
    )
    is_done_stage: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        doc='Признак завершающей стадии для расчёта прогресса ИСР.'
    )

    tasks: Mapped[list['KanbanTask']] = relationship(
        'KanbanTask',
        back_populates='stage',
    )

    def __repr__(self) -> str:
        return f'<KanbanStage(name={self.name!r})>'


class KanbanTask(Base, TimestampMixin):
    """Карточка канбан-доски."""

    __tablename__ = 'kanban_tasks'

    id: Mapped[int] = mapped_column(primary_key=True)
    wbs_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey('wbs_items.id', ondelete='SET NULL'),
        unique=True,
        nullable=True,
        doc='1:1 связь с листовым узлом ИСР. NULL — задача создана вручную.'
    )
    stage_id: Mapped[int] = mapped_column(
        ForeignKey('kanban_stages.id', ondelete='RESTRICT'),
        nullable=False,
        doc='Текущая стадия задачи.'
    )
    title: Mapped[str] = mapped_column(
        String(length=512),
        nullable=False,
        doc='Заголовок задачи.'
    )
    description_md: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc='Markdown-описание задачи.'
    )
    due_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        doc='Срок исполнения.'
    )
    position: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        doc='Позиция сортировки внутри стадии.'
    )

    wbs_item: Mapped[Optional['WbsItem']] = relationship(
        'WbsItem',
        back_populates='task',
    )
    stage: Mapped['KanbanStage'] = relationship(
        'KanbanStage',
        back_populates='tasks',
    )
    comments: Mapped[list['TaskComment']] = relationship(
        'TaskComment',
        back_populates='task',
        cascade='all, delete-orphan',
    )
    activity: Mapped[list['TaskActivity']] = relationship(
        'TaskActivity',
        back_populates='task',
        cascade='all, delete-orphan',
    )

    def __repr__(self) -> str:
        return f'<KanbanTask(title={self.title!r})>'


class TaskComment(Base):
    """Комментарий к задаче канбана."""

    __tablename__ = 'task_comments'

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey('kanban_tasks.id', ondelete='CASCADE'),
        nullable=False,
        doc='Задача, к которой относится комментарий.'
    )
    author_name: Mapped[Optional[str]] = mapped_column(
        String(length=255),
        nullable=True,
        doc='Свободная подпись автора комментария.'
    )
    body_md: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc='Текст комментария в markdown.'
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        doc='Дата и время создания комментария.'
    )

    task: Mapped['KanbanTask'] = relationship(
        'KanbanTask',
        back_populates='comments',
    )

    def __repr__(self) -> str:
        return f'<TaskComment(task_id={self.task_id})>'


class TaskActivity(Base):
    """Запись истории изменений задачи."""

    __tablename__ = 'task_activity'

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey('kanban_tasks.id', ondelete='CASCADE'),
        nullable=False,
        doc='Задача, к которой относится событие.'
    )
    event_type: Mapped[TaskActivityEventType] = mapped_column(
        Enum(TaskActivityEventType, name='task_activity_event_type'),
        nullable=False,
        doc='Тип события.'
    )
    from_value: Mapped[Optional[str]] = mapped_column(
        String(length=255),
        nullable=True,
        doc='Текстовое представление старого значения.'
    )
    to_value: Mapped[Optional[str]] = mapped_column(
        String(length=255),
        nullable=True,
        doc='Текстовое представление нового значения.'
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        doc='Дата и время события.'
    )

    task: Mapped['KanbanTask'] = relationship(
        'KanbanTask',
        back_populates='activity',
    )

    def __repr__(self) -> str:
        return f'<TaskActivity(task_id={self.task_id}, event_type={self.event_type})>'

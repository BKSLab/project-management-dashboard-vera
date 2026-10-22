"""Персональные водяные знаки просмотренного содержимого задачи."""

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class TaskView(Base):
    __tablename__ = "task_views"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        doc="Человек, открывший карточку.",
        comment="Пользователь персонального просмотра.",
    )
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        primary_key=True,
        doc="Просмотренная задача.",
        comment="Задача персонального просмотра.",
    )
    revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        doc="Последняя подтверждённая версия содержимого.",
        comment="Монотонный водяной знак; запоздавший просмотр не стирает новый.",
    )
    deadline_revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        doc="Последняя просмотренная версия уже наступившей просрочки.",
        comment="Не подтверждается, если при открытии срок ещё не был нарушен.",
    )

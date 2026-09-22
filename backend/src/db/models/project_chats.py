"""Единственная общая переписка команды проекта."""

from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class ProjectChat(TimestampMixin, Base):
    """Счётчик сериализует события одного чата в порядке commit."""

    __tablename__ = "project_chats"
    __table_args__ = (UniqueConstraint("id", "project_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, doc="ID чата.", comment="ID чата.")
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        unique=True,
        doc="Проект чата.",
        comment="Проект чата.",
    )
    last_event_seq: Mapped[int] = mapped_column(
        BigInteger,
        server_default="0",
        doc="Последний курсор событий.",
        comment="Последний курсор событий.",
    )

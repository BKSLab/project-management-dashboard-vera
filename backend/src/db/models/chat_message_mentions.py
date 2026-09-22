"""Явные упоминания участников, выбранных в редакторе."""

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ChatMessageMention(Base):
    """Одно упоминание пользователя в сообщении."""

    __tablename__ = "chat_message_mentions"

    message_id: Mapped[int] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        primary_key=True,
        doc="Сообщение.",
        comment="Сообщение.",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        doc="Упомянутый участник.",
        comment="Упомянутый участник.",
    )

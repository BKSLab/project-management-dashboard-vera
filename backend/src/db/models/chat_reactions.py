"""Идемпотентные реакции участников."""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class ChatReaction(TimestampMixin, Base):
    """Один пользователь может поставить каждую реакцию один раз."""

    __tablename__ = "chat_reactions"

    message_id: Mapped[int] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        primary_key=True,
        doc="Сообщение.",
        comment="Сообщение.",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        doc="Участник.",
        comment="Участник.",
    )
    reaction: Mapped[str] = mapped_column(
        String(16), primary_key=True, doc="Символ реакции.", comment="Символ реакции."
    )

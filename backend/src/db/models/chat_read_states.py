"""Граница прочитанного вместо декартова произведения участников и сообщений."""

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class ChatReadState(TimestampMixin, Base):
    """Монотонная граница прочитанного участника."""

    __tablename__ = "chat_read_states"

    chat_id: Mapped[int] = mapped_column(
        ForeignKey("project_chats.id", ondelete="CASCADE"),
        primary_key=True,
        doc="Чат.",
        comment="Чат.",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        doc="Участник.",
        comment="Участник.",
    )
    last_read_seq: Mapped[int] = mapped_column(
        BigInteger,
        server_default="0",
        doc="Порядок последнего прочитанного сообщения.",
        comment="Порядок последнего прочитанного сообщения.",
    )

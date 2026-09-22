"""Журнал событий одновременно служит outbox и источником resync."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ChatEvent(Base):
    """Долговечное событие; временные presence/typing сюда не попадают."""

    __tablename__ = "chat_events"
    __table_args__ = (
        UniqueConstraint("chat_id", "seq"),
        Index("ix_chat_events_pending", "id", postgresql_where=text("published_at IS NULL")),
    )

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, doc="ID записи outbox.", comment="ID записи outbox."
    )
    chat_id: Mapped[int] = mapped_column(
        ForeignKey("project_chats.id", ondelete="CASCADE"),
        doc="Чат события.",
        comment="Чат события.",
    )
    seq: Mapped[int] = mapped_column(
        BigInteger, doc="Курсор внутри чата.", comment="Курсор внутри чата."
    )
    event_type: Mapped[str] = mapped_column(
        String(40), doc="Тип изменения.", comment="Тип изменения."
    )
    payload: Mapped[dict] = mapped_column(
        JSONB,
        doc="ID изменённых объектов без копии переписки.",
        comment="ID изменённых объектов без копии переписки.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        doc="Время события.",
        comment="Время события.",
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), doc="Время передачи Redis.", comment="Время передачи Redis."
    )

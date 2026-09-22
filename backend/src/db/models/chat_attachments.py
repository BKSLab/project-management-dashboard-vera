"""Загрузки чата, включая ещё не отправленные черновики."""

from uuid import UUID

from sqlalchemy import ForeignKey, ForeignKeyConstraint, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class ChatAttachment(TimestampMixin, Base):
    """Файл привязывается к сообщению один раз в транзакции отправки."""

    __tablename__ = "chat_attachments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["message_id", "chat_id"],
            ["chat_messages.id", "chat_messages.chat_id"],
            ondelete="CASCADE",
        ),
        Index("ix_chat_attachments_drafts", "chat_id", "uploader_id", "created_at"),
        Index("ix_chat_attachments_message", "message_id"),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, doc="ID загрузки.", comment="ID загрузки."
    )
    chat_id: Mapped[int] = mapped_column(
        ForeignKey("project_chats.id", ondelete="CASCADE"), doc="Чат.", comment="Чат."
    )
    message_id: Mapped[int | None] = mapped_column(
        doc="Сообщение; NULL у черновика.", comment="Сообщение; NULL у черновика."
    )
    uploader_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        doc="Автор загрузки.",
        comment="Автор загрузки.",
    )
    storage_key: Mapped[str] = mapped_column(
        String(500), doc="Внутренний ключ файла.", comment="Внутренний ключ файла."
    )
    original_name: Mapped[str] = mapped_column(
        String(255), doc="Безопасное имя.", comment="Безопасное имя."
    )
    content_type: Mapped[str] = mapped_column(
        String(150), doc="Проверенный MIME.", comment="Проверенный MIME."
    )
    size_bytes: Mapped[int] = mapped_column(
        doc="Размер содержимого.", comment="Размер содержимого."
    )

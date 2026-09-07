"""Проверяемый результат извлечения файла, общий для FTS и embeddings."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class KnowledgeAttachmentText(Base):
    __tablename__ = "knowledge_attachment_texts"

    attachment_id: Mapped[int] = mapped_column(
        ForeignKey("task_attachments.id", ondelete="CASCADE"), primary_key=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

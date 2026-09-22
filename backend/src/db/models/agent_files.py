"""Приватные загрузки участника для вложений в сообщениях агента."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AgentFile(Base):
    """Файл личного диалога; в общую базу знаний попадает только копия в задаче."""

    __tablename__ = "agent_files"

    id: Mapped[UUID] = mapped_column(primary_key=True, doc="ID загрузки.", comment="ID загрузки.")
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("agent_conversations.id", ondelete="CASCADE"),
        index=True,
        doc="Личный диалог файла.",
        comment="Личный диалог файла.",
    )
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_messages.id", ondelete="SET NULL"),
        doc="Первая реплика с файлом.",
        comment="Первая реплика с файлом.",
    )
    original_name: Mapped[str] = mapped_column(
        String(512), doc="Имя файла участника.", comment="Имя файла участника."
    )
    content_type: Mapped[str] = mapped_column(
        String(255), doc="MIME-тип файла.", comment="MIME-тип файла."
    )
    size: Mapped[int] = mapped_column(doc="Размер в байтах.", comment="Размер в байтах.")
    storage_key: Mapped[str] = mapped_column(
        String(512),
        doc="Внутренний ключ приватного хранилища.",
        comment="Внутренний ключ приватного хранилища.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        doc="Время загрузки.",
        comment="Время загрузки.",
    )

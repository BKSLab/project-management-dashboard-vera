from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class KnowledgeEntityType(str, enum.Enum):
    """Тип исходной сущности семантического индекса."""

    PROJECT = "PROJECT"
    TASK = "TASK"
    DOCUMENT = "DOCUMENT"
    COMMENT = "COMMENT"
    ATTACHMENT = "ATTACHMENT"


class KnowledgeIndexOperation(str, enum.Enum):
    """Операция, которую должен выполнить индексатор."""

    UPSERT = "UPSERT"
    DELETE = "DELETE"
    REINDEX_PROJECT = "REINDEX_PROJECT"
    DELETE_COLLECTION = "DELETE_COLLECTION"


class KnowledgeIndexStatus(str, enum.Enum):
    """Состояние постоянного задания индексации."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class KnowledgeIndexJob(Base, TimestampMixin):
    """Постоянное задание синхронизации PostgreSQL с Qdrant.

    ``project_id`` намеренно не является внешним ключом: задание удаления
    collection должно пережить удаление самого проекта из PostgreSQL.
    """

    __tablename__ = "knowledge_index_jobs"
    __table_args__ = (
        Index(
            "ix_knowledge_index_jobs_ready",
            "status",
            "available_at",
            "id",
        ),
        Index("ix_knowledge_index_jobs_project_status", "project_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    entity_type: Mapped[KnowledgeEntityType] = mapped_column(
        Enum(KnowledgeEntityType, name="knowledge_entity_type"),
        nullable=False,
    )
    entity_id: Mapped[str | None] = mapped_column(String(length=64), nullable=True)
    operation: Mapped[KnowledgeIndexOperation] = mapped_column(
        Enum(KnowledgeIndexOperation, name="knowledge_index_operation"),
        nullable=False,
    )
    status: Mapped[KnowledgeIndexStatus] = mapped_column(
        Enum(KnowledgeIndexStatus, name="knowledge_index_status"),
        nullable=False,
        default=KnowledgeIndexStatus.PENDING,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    chunks_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<KnowledgeIndexJob(id={self.id}, project_id={self.project_id}, "
            f"entity_type={self.entity_type}, operation={self.operation}, status={self.status})>"
        )

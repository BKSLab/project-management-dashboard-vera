import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class AgentConversation(TimestampMixin, Base):
    """Личный диалог проекта, общего помощника или внешнего API."""

    __tablename__ = "agent_conversations"
    __table_args__ = (
        Index("ix_agent_conversations_owner_project", "user_id", "project_id", "updated_at"),
        Index("ix_agent_conversations_owner", "user_id", "updated_at"),
        CheckConstraint("channel IN ('web', 'api')", name="ck_agent_conversation_channel"),
        Index("uq_agent_conversation_external", "user_id", "api_key_id", "external_key",
              unique=True, postgresql_where=text("external_key IS NOT NULL"),
              postgresql_nulls_not_distinct=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, doc="ID диалога.", comment="ID диалога.")
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        doc="Проект диалога.",
        comment="Проект диалога.",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        doc="Владелец переписки.",
        comment="Владелец переписки.",
    )
    title: Mapped[str] = mapped_column(
        String(120), doc="Название разговора.", comment="Название разговора."
    )
    summary: Mapped[str] = mapped_column(
        Text,
        server_default="",
        doc="Память о ранних репликах; не факты проекта.",
        comment="Память о ранних репликах; не факты проекта.",
    )
    summary_through_id: Mapped[int] = mapped_column(
        server_default="0",
        doc="Последняя реплика, включённая в память.",
        comment="Последняя реплика, включённая в память.",
    )

    channel: Mapped[str] = mapped_column(String(16), server_default="web")
    external_key: Mapped[str | None] = mapped_column(String(255))
    api_key_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("api_keys.id", ondelete="SET NULL"))

    def __repr__(self) -> str:
        return f"<AgentConversation(id={self.id}, project_id={self.project_id}, user_id={self.user_id})>"

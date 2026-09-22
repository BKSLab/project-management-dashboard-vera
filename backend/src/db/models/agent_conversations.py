from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class AgentConversation(TimestampMixin, Base):
    """Личный диалог участника в границах одного проекта."""

    __tablename__ = "agent_conversations"
    __table_args__ = (
        Index("ix_agent_conversations_owner_project", "user_id", "project_id", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, doc="ID диалога.", comment="ID диалога.")
    project_id: Mapped[int] = mapped_column(
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

    def __repr__(self) -> str:
        return f"<AgentConversation(id={self.id}, project_id={self.project_id}, user_id={self.user_id})>"

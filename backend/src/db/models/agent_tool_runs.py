"""Журнал действий агента, подтверждений и идемпотентных результатов."""

from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class AgentToolRun(TimestampMixin, Base):
    """Один вызов изменяющего инструмента от имени участника проекта."""

    __tablename__ = "agent_tool_runs"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", "request_id", name="uq_agent_tool_request"),
        CheckConstraint(
            "status IN ('pending', 'completed', 'rejected', 'failed')", name="ck_agent_tool_status"
        ),
        Index("ix_agent_tool_message", "message_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, doc="ID действия.", comment="ID действия.")
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
        doc="Проект действия.",
        comment="Проект действия.",
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        doc="Инициатор действия.",
        comment="Инициатор действия.",
    )
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("agent_messages.id", ondelete="CASCADE"),
        doc="Ответ чата; null для MCP.",
        comment="Ответ чата; null для MCP.",
    )
    request_id: Mapped[UUID] = mapped_column(
        doc="Ключ идемпотентного вызова.", comment="Ключ идемпотентного вызова."
    )
    tool_name: Mapped[str] = mapped_column(
        String(64), doc="Имя инструмента.", comment="Имя инструмента."
    )
    title: Mapped[str] = mapped_column(
        String(255),
        doc="Название действия для участника.",
        comment="Название действия для участника.",
    )
    arguments: Mapped[dict] = mapped_column(
        JSONB, doc="Проверенные аргументы действия.", comment="Проверенные аргументы действия."
    )
    status: Mapped[str] = mapped_column(
        String(16), doc="Ожидание решения или результат.", comment="Ожидание решения или результат."
    )
    result: Mapped[dict] = mapped_column(
        JSONB,
        server_default=text("'{}'::jsonb"),
        doc="Сохранённый результат вызова.",
        comment="Сохранённый результат вызова.",
    )

    def __repr__(self) -> str:
        return f"<AgentToolRun(id={self.id}, tool_name={self.tool_name}, status={self.status})>"

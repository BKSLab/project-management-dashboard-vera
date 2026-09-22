"""Постоянные проектные диалоги, сообщения и очередь ответов агента."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c7a94b215f60"
down_revision = "f4a72c908e16"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_conversations",
        sa.Column("id", sa.Integer(), primary_key=True, comment="ID диалога."),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            comment="Проект диалога.",
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="Владелец переписки.",
        ),
        sa.Column("title", sa.String(120), nullable=False, comment="Название разговора."),
        sa.Column(
            "summary",
            sa.Text(),
            nullable=False,
            server_default="",
            comment="Память о ранних репликах; не факты проекта.",
        ),
        sa.Column(
            "summary_through_id",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Последняя реплика, включённая в память.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Дата и время создания записи.",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Дата и время последнего обновления записи.",
        ),
    )
    op.create_index(
        "ix_agent_conversations_owner_project",
        "agent_conversations",
        ["user_id", "project_id", "updated_at"],
    )
    op.create_table(
        "agent_messages",
        sa.Column("id", sa.Integer(), primary_key=True, comment="ID реплики."),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("agent_conversations.id", ondelete="CASCADE"),
            nullable=False,
            comment="Диалог реплики.",
        ),
        sa.Column(
            "request_id", sa.Uuid(), nullable=False, comment="Ключ повторной отправки вопроса."
        ),
        sa.Column("role", sa.String(16), nullable=False, comment="Автор: участник или агент."),
        sa.Column(
            "content", sa.Text(), nullable=False, server_default="", comment="Текст реплики."
        ),
        sa.Column(
            "sources",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Проверенные источники ответа.",
        ),
        sa.Column("status", sa.String(16), nullable=False, comment="Состояние подготовки ответа."),
        sa.Column("error", sa.Text(), comment="Безопасное описание ошибки."),
        sa.Column("run_id", sa.Uuid(), comment="Владелец текущей попытки исполнения."),
        sa.Column("started_at", sa.DateTime(timezone=True), comment="Начало попытки."),
        sa.Column("completed_at", sa.DateTime(timezone=True), comment="Завершение попытки."),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Время отправки.",
        ),
        sa.UniqueConstraint(
            "conversation_id", "request_id", "role", name="uq_agent_message_request_role"
        ),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_agent_message_role"),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed')",
            name="ck_agent_message_status",
        ),
        sa.CheckConstraint(
            "role = 'assistant' OR status = 'completed'", name="ck_agent_user_message_complete"
        ),
    )
    op.create_index("ix_agent_messages_conversation", "agent_messages", ["conversation_id", "id"])
    op.create_index("ix_agent_messages_queue", "agent_messages", ["status", "id"])
    op.create_index(
        "uq_agent_conversation_active",
        "agent_messages",
        ["conversation_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'processing')"),
    )


def downgrade() -> None:
    op.drop_table("agent_messages")
    op.drop_table("agent_conversations")

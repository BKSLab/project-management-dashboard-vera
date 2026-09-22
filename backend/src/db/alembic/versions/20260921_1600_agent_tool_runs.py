"""Журнал идемпотентных действий и решений проектного агента."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "ed781b034ac9"
down_revision = "c7a94b215f60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_tool_runs",
        sa.Column("id", sa.Uuid(), primary_key=True, comment="ID действия."),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            comment="Проект действия.",
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="Инициатор действия.",
        ),
        sa.Column(
            "message_id",
            sa.Integer(),
            sa.ForeignKey("agent_messages.id", ondelete="CASCADE"),
            nullable=True,
            comment="Ответ чата; null для MCP.",
        ),
        sa.Column("request_id", sa.Uuid(), nullable=False, comment="Ключ идемпотентного вызова."),
        sa.Column("tool_name", sa.String(64), nullable=False, comment="Имя инструмента."),
        sa.Column(
            "title", sa.String(255), nullable=False, comment="Название действия для участника."
        ),
        sa.Column(
            "arguments",
            postgresql.JSONB(),
            nullable=False,
            comment="Проверенные аргументы действия.",
        ),
        sa.Column(
            "status", sa.String(16), nullable=False, comment="Ожидание решения или результат."
        ),
        sa.Column(
            "result",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
            comment="Сохранённый результат вызова.",
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
        sa.UniqueConstraint("project_id", "user_id", "request_id", name="uq_agent_tool_request"),
        sa.CheckConstraint(
            "status IN ('pending', 'completed', 'rejected', 'failed')", name="ck_agent_tool_status"
        ),
    )
    op.create_index("ix_agent_tool_message", "agent_tool_runs", ["message_id", "created_at"])
    op.add_column(
        "agent_messages",
        sa.Column(
            "files",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment="Метаданные файлов, выбранных участником при отправке.",
        ),
    )
    op.create_table(
        "agent_files",
        sa.Column("id", sa.Uuid(), primary_key=True, comment="ID загрузки."),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("agent_conversations.id", ondelete="CASCADE"),
            nullable=False,
            comment="Личный диалог файла.",
        ),
        sa.Column(
            "message_id",
            sa.Integer(),
            sa.ForeignKey("agent_messages.id", ondelete="SET NULL"),
            nullable=True,
            comment="Первая реплика с файлом.",
        ),
        sa.Column("original_name", sa.String(512), nullable=False, comment="Имя файла участника."),
        sa.Column("content_type", sa.String(255), nullable=False, comment="MIME-тип файла."),
        sa.Column("size", sa.Integer(), nullable=False, comment="Размер в байтах."),
        sa.Column(
            "storage_key",
            sa.String(512),
            nullable=False,
            comment="Внутренний ключ приватного хранилища.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Время загрузки.",
        ),
    )
    op.create_index("ix_agent_files_conversation_id", "agent_files", ["conversation_id"])


def downgrade() -> None:
    op.drop_table("agent_files")
    op.drop_column("agent_messages", "files")
    op.drop_table("agent_tool_runs")

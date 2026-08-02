"""add task attachments

Revision ID: d5e4f3a2b1c0
Revises: c4d3e2f1a0b9
Create Date: 2026-08-02 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5e4f3a2b1c0"
down_revision: str | Sequence[str] | None = "c4d3e2f1a0b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создаёт таблицу метаданных файлов задач."""
    op.create_table(
        "task_attachments",
        sa.Column(
            "id", sa.Integer(), nullable=False, comment="Уникальный идентификатор файла задачи."
        ),
        sa.Column(
            "task_id",
            sa.Integer(),
            nullable=False,
            comment="Идентификатор задачи, к которой прикреплён файл.",
        ),
        sa.Column(
            "original_name",
            sa.String(length=512),
            nullable=False,
            comment="Исходное имя файла без компонентов пути.",
        ),
        sa.Column(
            "storage_key",
            sa.String(length=255),
            nullable=False,
            comment="Относительный путь файла внутри каталога uploads.",
        ),
        sa.Column(
            "content_type",
            sa.String(length=255),
            nullable=False,
            comment="MIME-тип, используемый при выдаче содержимого файла.",
        ),
        sa.Column(
            "size", sa.BigInteger(), nullable=False, comment="Положительный размер файла в байтах."
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата и время добавления файла к задаче.",
        ),
        sa.CheckConstraint("size > 0", name="ck_task_attachments_size_positive"),
        sa.ForeignKeyConstraint(["task_id"], ["kanban_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_task_attachments_storage_key"),
    )
    op.create_index("ix_task_attachments_task_id", "task_attachments", ["task_id"])


def downgrade() -> None:
    """Удаляет таблицу метаданных файлов задач."""
    op.drop_index("ix_task_attachments_task_id", table_name="task_attachments")
    op.drop_table("task_attachments")

"""move timestamp defaults to PostgreSQL

Revision ID: d9e8f7a6b5c4
Revises: c8d7e6f5a4b3
Create Date: 2026-08-02 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d9e8f7a6b5c4"
down_revision: str | Sequence[str] | None = "c8d7e6f5a4b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Добавляет серверные значения времени для новых записей."""
    for table_name, columns in {
        "documents": ("created_at", "updated_at"),
        "kanban_tasks": ("created_at", "updated_at"),
        "task_comments": ("created_at",),
        "task_activity": ("created_at",),
    }.items():
        for column_name in columns:
            op.alter_column(
                table_name,
                column_name,
                existing_type=sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
            )


def downgrade() -> None:
    """Удаляет серверные значения времени."""
    for table_name, columns in {
        "documents": ("created_at", "updated_at"),
        "kanban_tasks": ("created_at", "updated_at"),
        "task_comments": ("created_at",),
        "task_activity": ("created_at",),
    }.items():
        for column_name in columns:
            op.alter_column(
                table_name,
                column_name,
                existing_type=sa.DateTime(timezone=True),
                server_default=None,
            )

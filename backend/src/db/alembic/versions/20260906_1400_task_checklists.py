"""Чек-лист как часть задачи и версия его изменений.

Revision ID: b8c34dae125f
Revises: a7b23c9d014e
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b8c34dae125f"
down_revision = "a7b23c9d014e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column(
            "checklist",
            postgresql.JSONB(),
            nullable=True,
            comment="Чек-лист с упорядоченными пунктами.",
        ),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "checklist_revision",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Версия чек-листа.",
        ),
    )
    op.execute("ALTER TYPE task_activity_event_type ADD VALUE IF NOT EXISTS 'CHECKLIST_CHANGED'")


def downgrade() -> None:
    op.drop_column("tasks", "checklist_revision")
    op.drop_column("tasks", "checklist")
    # Метка общего enum остаётся: история уже могла сохранить такие события.

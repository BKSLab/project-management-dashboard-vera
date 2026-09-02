"""task start date

Revision ID: e14b9c73a602
Revises: c8e2f6a41d73
Create Date: 2026-09-02 19:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e14b9c73a602"
down_revision: Union[str, Sequence[str], None] = "c8e2f6a41d73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляет начало планового интервала и событие его изменения."""
    op.add_column(
        "tasks",
        sa.Column(
            "start_date",
            sa.Date(),
            nullable=True,
            comment="Плановая дата начала задачи.",
        ),
    )
    op.execute("ALTER TYPE task_activity_event_type ADD VALUE IF NOT EXISTS 'START_DATE_CHANGED'")


def downgrade() -> None:
    """Удаляет дату начала; значение PostgreSQL enum остаётся совместимым."""
    op.drop_column("tasks", "start_date")

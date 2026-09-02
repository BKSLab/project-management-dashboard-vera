"""calendar task due date index

Revision ID: c8e2f6a41d73
Revises: a3f81c72d5b4
Create Date: 2026-09-02 18:30:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c8e2f6a41d73"
down_revision: Union[str, Sequence[str], None] = "a3f81c72d5b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляет индекс диапазона дедлайнов внутри проекта."""
    op.create_index(
        "ix_tasks_project_due_date",
        "tasks",
        ["project_id", "due_date"],
        unique=False,
    )


def downgrade() -> None:
    """Удаляет индекс диапазона дедлайнов."""
    op.drop_index("ix_tasks_project_due_date", table_name="tasks")

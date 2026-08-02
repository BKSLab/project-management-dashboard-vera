"""name task-to-WBS uniqueness constraint

Revision ID: c4d3e2f1a0b9
Revises: b3c2d1e0f9a8
Create Date: 2026-08-02 14:50:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c4d3e2f1a0b9"
down_revision: str | Sequence[str] | None = "b3c2d1e0f9a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Задаёт стабильное имя ограничению связи задачи с узлом ИСР."""
    op.execute(
        "ALTER TABLE kanban_tasks "
        "RENAME CONSTRAINT kanban_tasks_wbs_item_id_key TO uq_kanban_tasks_wbs_item_id"
    )


def downgrade() -> None:
    """Возвращает исходное имя ограничения связи задачи с узлом ИСР."""
    op.execute(
        "ALTER TABLE kanban_tasks "
        "RENAME CONSTRAINT uq_kanban_tasks_wbs_item_id TO kanban_tasks_wbs_item_id_key"
    )

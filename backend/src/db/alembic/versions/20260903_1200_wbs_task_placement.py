"""wbs task placement

Revision ID: b7d41f0ac9e2
Revises: b61c8d3f4a72
Create Date: 2026-09-03 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7d41f0ac9e2"
down_revision: Union[str, Sequence[str], None] = "b61c8d3f4a72"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляет порядок задачи внутри раздела ИСР и координаты на холсте."""
    op.add_column(
        "tasks",
        sa.Column(
            "wbs_position",
            sa.Float(),
            nullable=True,
            comment="Позиция сортировки задачи внутри раздела ИСР.",
        ),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "canvas_x",
            sa.Float(),
            nullable=True,
            comment="Координата X карточки задачи на холсте ИСР.",
        ),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "canvas_y",
            sa.Float(),
            nullable=True,
            comment="Координата Y карточки задачи на холсте ИСР.",
        ),
    )
    # Уже распределённые задачи получают разреженные позиции в текущем порядке
    # отображения, чтобы структура не перестроилась после обновления.
    op.execute(
        """
        UPDATE tasks
        SET wbs_position = ordered.new_position
        FROM (
            SELECT
                id,
                row_number() OVER (
                    PARTITION BY wbs_node_id ORDER BY position, id
                ) * 1000.0 AS new_position
            FROM tasks
            WHERE wbs_node_id IS NOT NULL
        ) AS ordered
        WHERE tasks.id = ordered.id
        """
    )


def downgrade() -> None:
    """Удаляет позицию внутри раздела и координаты холста."""
    op.drop_column("tasks", "canvas_y")
    op.drop_column("tasks", "canvas_x")
    op.drop_column("tasks", "wbs_position")

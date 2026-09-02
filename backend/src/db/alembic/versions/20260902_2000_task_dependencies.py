"""task dependencies

Revision ID: a38d5b72c104
Revises: f27c4a91be38
Create Date: 2026-09-02 20:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a38d5b72c104"
down_revision: Union[str, Sequence[str], None] = "f27c4a91be38"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляет направленные зависимости Finish-to-Start."""
    dependency_type = sa.Enum("FINISH_TO_START", name="task_dependency_type")
    op.create_table(
        "task_dependencies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("predecessor_task_id", sa.Integer(), nullable=False),
        sa.Column("successor_task_id", sa.Integer(), nullable=False),
        sa.Column("dependency_type", dependency_type, nullable=False),
        sa.Column("lag_days", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["predecessor_task_id"],
            ["tasks.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["successor_task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "predecessor_task_id",
            "successor_task_id",
            name="uq_task_dependencies_predecessor_successor",
        ),
    )
    op.create_index(
        "ix_task_dependencies_project_id",
        "task_dependencies",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_task_dependencies_predecessor_task_id",
        "task_dependencies",
        ["predecessor_task_id"],
        unique=False,
    )
    op.create_index(
        "ix_task_dependencies_successor_task_id",
        "task_dependencies",
        ["successor_task_id"],
        unique=False,
    )


def downgrade() -> None:
    """Удаляет зависимости задач."""
    op.drop_index("ix_task_dependencies_successor_task_id", table_name="task_dependencies")
    op.drop_index("ix_task_dependencies_predecessor_task_id", table_name="task_dependencies")
    op.drop_index("ix_task_dependencies_project_id", table_name="task_dependencies")
    op.drop_table("task_dependencies")
    sa.Enum(name="task_dependency_type").drop(op.get_bind(), checkfirst=True)

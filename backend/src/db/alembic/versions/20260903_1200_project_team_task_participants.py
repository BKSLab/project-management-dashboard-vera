"""project team task participants

Revision ID: b61c8d3f4a72
Revises: a38d5b72c104
Create Date: 2026-09-03 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b61c8d3f4a72"
down_revision: Union[str, Sequence[str], None] = "a38d5b72c104"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляет ролевые назначения реальных участников команды на задачи."""
    participant_role = sa.Enum(
        "EXECUTOR",
        "REPORTER",
        "OBSERVER",
        name="task_participant_role",
    )
    op.create_table(
        "task_participants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("project_member_id", sa.Integer(), nullable=False),
        sa.Column("role", participant_role, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["project_member_id"],
            ["project_members.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "task_id",
            "project_member_id",
            "role",
            name="uq_task_participants_task_member_role",
        ),
    )
    op.create_index(
        "ix_task_participants_task_id",
        "task_participants",
        ["task_id"],
        unique=False,
    )
    op.create_index(
        "ix_task_participants_project_member_id",
        "task_participants",
        ["project_member_id"],
        unique=False,
    )
    op.create_index(
        "uq_task_participants_executor",
        "task_participants",
        ["task_id"],
        unique=True,
        postgresql_where=sa.text("role = 'EXECUTOR'"),
    )
    op.create_index(
        "uq_task_participants_reporter",
        "task_participants",
        ["task_id"],
        unique=True,
        postgresql_where=sa.text("role = 'REPORTER'"),
    )


def downgrade() -> None:
    """Удаляет ролевые назначения задач."""
    op.drop_index("uq_task_participants_reporter", table_name="task_participants")
    op.drop_index("uq_task_participants_executor", table_name="task_participants")
    op.drop_index("ix_task_participants_project_member_id", table_name="task_participants")
    op.drop_index("ix_task_participants_task_id", table_name="task_participants")
    op.drop_table("task_participants")
    sa.Enum(name="task_participant_role").drop(op.get_bind(), checkfirst=True)

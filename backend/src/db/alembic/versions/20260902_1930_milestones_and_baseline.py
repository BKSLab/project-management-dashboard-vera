"""milestones and task baseline

Revision ID: f27c4a91be38
Revises: e14b9c73a602
Create Date: 2026-09-02 19:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f27c4a91be38"
down_revision: Union[str, Sequence[str], None] = "e14b9c73a602"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляет вехи, baseline и фактическое завершение задач."""
    milestone_status = sa.Enum("PLANNED", "ACHIEVED", name="project_milestone_status")
    op.create_table(
        "project_milestones",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("status", milestone_status, nullable=False),
        sa.Column("wbs_node_id", sa.Integer(), nullable=True),
        sa.Column("description_md", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата и время создания записи.",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата и время последнего обновления записи.",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["wbs_node_id"], ["wbs_nodes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_project_milestones_project_due_date",
        "project_milestones",
        ["project_id", "due_date"],
        unique=False,
    )
    op.create_index(
        "ix_project_milestones_project_id",
        "project_milestones",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_project_milestones_wbs_node_id",
        "project_milestones",
        ["wbs_node_id"],
        unique=False,
    )
    op.add_column(
        "tasks",
        sa.Column(
            "baseline_start_date",
            sa.Date(),
            nullable=True,
            comment="Дата начала утверждённого baseline.",
        ),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "baseline_due_date",
            sa.Date(),
            nullable=True,
            comment="Дата завершения утверждённого baseline.",
        ),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Момент последнего перехода задачи в завершающую стадию.",
        ),
    )
    op.execute("ALTER TYPE task_activity_event_type ADD VALUE IF NOT EXISTS 'BASELINE_CHANGED'")
    op.execute("ALTER TYPE knowledge_entity_type ADD VALUE IF NOT EXISTS 'MILESTONE'")


def downgrade() -> None:
    """Удаляет вехи и календарные поля; enum остаются совместимыми."""
    op.drop_column("tasks", "completed_at")
    op.drop_column("tasks", "baseline_due_date")
    op.drop_column("tasks", "baseline_start_date")
    op.drop_index("ix_project_milestones_wbs_node_id", table_name="project_milestones")
    op.drop_index("ix_project_milestones_project_id", table_name="project_milestones")
    op.drop_index("ix_project_milestones_project_due_date", table_name="project_milestones")
    op.drop_table("project_milestones")
    sa.Enum(name="project_milestone_status").drop(op.get_bind(), checkfirst=True)

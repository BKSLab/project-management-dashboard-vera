"""Паспорт проекта и история сроков.

Revision ID: e2f47a910c63
Revises: d7e91c4a2f10
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e2f47a910c63"
down_revision = "d7e91c4a2f10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Сохраняет прежние описания и фиксирует известные сроки без выдуманной истории."""
    op.add_column("projects", sa.Column("description_sections", postgresql.JSONB(), nullable=True))
    op.add_column(
        "projects",
        sa.Column("due_date_has_been_set", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "project_deadline_changes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("previous_due_date", sa.Date(), nullable=True),
        sa.Column("new_due_date", sa.Date(), nullable=True),
        sa.Column(
            "changed_by_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("changed_by_name", sa.String(350), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_project_deadline_changes_project_id", "project_deadline_changes", ["project_id"]
    )
    op.execute("UPDATE projects SET due_date_has_been_set = true WHERE due_date IS NOT NULL")
    op.execute(
        "INSERT INTO project_deadline_changes (project_id, new_due_date, changed_by_name, comment) "
        "SELECT id, due_date, 'Система', 'Срок на момент включения истории изменений.' "
        "FROM projects WHERE due_date IS NOT NULL"
    )


def downgrade() -> None:
    """Удаляет новые поля, сохраняя собранное описание проекта."""
    op.drop_index("ix_project_deadline_changes_project_id", table_name="project_deadline_changes")
    op.drop_table("project_deadline_changes")
    op.drop_column("projects", "due_date_has_been_set")
    op.drop_column("projects", "description_sections")

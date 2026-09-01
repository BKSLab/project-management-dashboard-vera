"""project knowledge indexing jobs

Revision ID: e7b5d29c41a0
Revises: c2a71f5b48d9
Create Date: 2026-09-01 21:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e7b5d29c41a0"
down_revision: Union[str, Sequence[str], None] = "c2a71f5b48d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляет постоянную очередь синхронизации с Qdrant."""
    entity_type = postgresql.ENUM(
        "PROJECT",
        "TASK",
        "DOCUMENT",
        "COMMENT",
        "ATTACHMENT",
        name="knowledge_entity_type",
        create_type=False,
    )
    operation = postgresql.ENUM(
        "UPSERT",
        "DELETE",
        "REINDEX_PROJECT",
        "DELETE_COLLECTION",
        name="knowledge_index_operation",
        create_type=False,
    )
    job_status = postgresql.ENUM(
        "PENDING",
        "PROCESSING",
        "SUCCEEDED",
        "FAILED",
        name="knowledge_index_status",
        create_type=False,
    )
    entity_type.create(op.get_bind(), checkfirst=True)
    operation.create(op.get_bind(), checkfirst=True)
    job_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "knowledge_index_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", entity_type, nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("operation", operation, nullable=False),
        sa.Column("status", job_status, nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_knowledge_index_jobs_project_id"),
        "knowledge_index_jobs",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_index_jobs_ready",
        "knowledge_index_jobs",
        ["status", "available_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_knowledge_index_jobs_project_status",
        "knowledge_index_jobs",
        ["project_id", "status"],
        unique=False,
    )
    op.execute(
        sa.text(
            """
            INSERT INTO knowledge_index_jobs (
                project_id, entity_type, entity_id, operation, status,
                attempts, available_at, created_at, updated_at
            )
            SELECT
                id, 'PROJECT', NULL, 'REINDEX_PROJECT', 'PENDING',
                0, now(), now(), now()
            FROM projects
            """
        )
    )


def downgrade() -> None:
    """Удаляет очередь индексации и её enum-типы."""
    op.drop_index("ix_knowledge_index_jobs_project_status", table_name="knowledge_index_jobs")
    op.drop_index("ix_knowledge_index_jobs_ready", table_name="knowledge_index_jobs")
    op.drop_index(op.f("ix_knowledge_index_jobs_project_id"), table_name="knowledge_index_jobs")
    op.drop_table("knowledge_index_jobs")
    sa.Enum(name="knowledge_index_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="knowledge_index_operation").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="knowledge_entity_type").drop(op.get_bind(), checkfirst=True)

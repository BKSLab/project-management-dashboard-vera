"""Кэш описаний версий документов и файлов; первичные тексты сохраняются."""

import sqlalchemy as sa
from alembic import op

revision = "a81f247e930b"
down_revision = "f29c7618a403"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_source_summaries",
        sa.Column(
            "project_id",
            sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("source_id", sa.String(64), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE")),
        sa.Column(
            "attachment_id", sa.Integer(), sa.ForeignKey("task_attachments.id", ondelete="CASCADE")
        ),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "(document_id IS NOT NULL) <> (attachment_id IS NOT NULL)",
            name="ck_knowledge_summary_owner",
        ),
    )
    # Существующие документы тоже получают описание через штатную очередь.
    # Индексатор переиспользует неизменённые embeddings и готовые саммари.
    op.execute("""
        INSERT INTO knowledge_index_jobs
            (project_id, entity_type, operation, status, attempts)
        SELECT project_id, 'PROJECT', 'REINDEX_PROJECT', 'PENDING', 0
        FROM (
            SELECT project_id FROM documents
            UNION
            SELECT t.project_id FROM task_attachments a JOIN tasks t ON t.id = a.task_id
        ) sources
        WHERE NOT EXISTS (
            SELECT 1 FROM knowledge_index_jobs j
            WHERE j.project_id = sources.project_id AND j.status IN ('PENDING', 'PROCESSING')
        )
    """)


def downgrade() -> None:
    op.drop_table("knowledge_source_summaries")

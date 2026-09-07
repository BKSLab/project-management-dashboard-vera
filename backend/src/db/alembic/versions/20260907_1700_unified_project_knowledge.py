"""Единые проектные источники, происхождение документов и outbox всех сущностей."""

import sqlalchemy as sa
from alembic import op

from src.db.knowledge_outbox import install_outbox

revision = "f4a72c908e16"
down_revision = "e2f47a910c63"
branch_labels = None
depends_on = None

# Снимок политик этой миграции: будущие таблицы добавляются следующей миграцией.
RULES = [
    (
        "projects",
        "self",
        "id owner_id key name description_md status start_date due_date description_sections due_date_has_been_set",
    ),
    (
        "tasks",
        "project",
        "id project_id stage_id wbs_node_id number title description_md checklist checklist_revision priority role assignee start_date due_date baseline_start_date baseline_due_date completed_at position wbs_position",
    ),
    ("documents", "project", "id project_id slug title content_md origin_attachment_id"),
    ("task_comments", "task", "id task_id author_name body_md"),
    ("task_attachments", "task", "id task_id original_name storage_key content_type size"),
    (
        "project_milestones",
        "project",
        "id project_id title description_md due_date status wbs_node_id",
    ),
    (
        "project_risks",
        "project",
        "id project_id task_id title description mitigation_plan response_plan probability impact risk_level status response_strategy owner_user_id review_date source",
    ),
    ("wbs_nodes", "project", "id project_id parent_id title position"),
    ("project_stages", "project", "id project_id name order_index color is_done_stage"),
    (
        "project_stickers",
        "project",
        "id project_id body color created_by_user_id created_by_username_snapshot created_by_display_name_snapshot revision",
    ),
    ("project_members", "project", "id project_id user_id role"),
    ("task_activity", "task", "id task_id event_type from_value to_value"),
    (
        "project_deadline_changes",
        "project",
        "id project_id previous_due_date new_due_date changed_by_user_id changed_by_name comment",
    ),
    (
        "analytics_reports",
        "project",
        "id project_id created_by_user_id created_by_display_name_snapshot llm_model payload context_summary",
    ),
    ("document_links", "task", "id document_id task_id"),
    ("project_sticker_task_links", "task", "sticker_id task_id"),
    (
        "task_dependencies",
        "project",
        "id project_id predecessor_task_id successor_task_id dependency_type lag_days",
    ),
    ("task_participants", "task", "id task_id project_member_id role"),
    ("users", "user", "id username first_name last_name middle_name is_active"),
]


def upgrade():
    op.add_column(
        "knowledge_index_jobs", sa.Column("transaction_id", sa.BigInteger(), nullable=True)
    )
    op.create_index(
        "uq_knowledge_jobs_transaction",
        "knowledge_index_jobs",
        ["project_id", "transaction_id"],
        unique=True,
    )
    op.add_column(
        "documents",
        sa.Column(
            "origin_attachment_id",
            sa.Integer(),
            sa.ForeignKey("task_attachments.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_documents_origin_attachment_id", "documents", ["origin_attachment_id"])
    op.create_table(
        "knowledge_attachment_texts",
        sa.Column(
            "attachment_id",
            sa.Integer(),
            sa.ForeignKey("task_attachments.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("original_chars", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    install_outbox(
        op.get_bind(), [(table, scope, fields.split()) for table, scope, fields in RULES]
    )


def downgrade():
    for table, _, _ in RULES:
        op.execute(f'DROP TRIGGER IF EXISTS knowledge_changed ON "{table}"')
    op.execute("DROP FUNCTION IF EXISTS knowledge_project_changed()")
    op.drop_table("knowledge_attachment_texts")
    op.drop_index("ix_documents_origin_attachment_id", table_name="documents")
    op.drop_constraint("documents_origin_attachment_id_fkey", "documents", type_="foreignkey")
    op.drop_column("documents", "origin_attachment_id")
    op.drop_index("uq_knowledge_jobs_transaction", table_name="knowledge_index_jobs")
    op.drop_column("knowledge_index_jobs", "transaction_id")

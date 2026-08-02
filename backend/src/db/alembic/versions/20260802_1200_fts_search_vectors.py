"""add generated FTS vectors and GIN indexes

Revision ID: c8d7e6f5a4b3
Revises: 51e52abf163d
Create Date: 2026-08-02 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c8d7e6f5a4b3"
down_revision: str | Sequence[str] | None = "51e52abf163d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add automatically maintained full-text search vectors."""
    op.add_column(
        "kanban_tasks",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('russian', coalesce(title, '')), 'A') || "
                "setweight(to_tsvector('russian', coalesce(description_md, '')), 'B')",
                persisted=True,
            ),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_kanban_tasks_search_vector",
        "kanban_tasks",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )

    op.add_column(
        "documents",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('russian', coalesce(title, '')), 'A') || "
                "setweight(to_tsvector('russian', coalesce(content_md, '')), 'B')",
                persisted=True,
            ),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_documents_search_vector",
        "documents",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )

    op.add_column(
        "task_comments",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('russian', coalesce(body_md, '')), 'A') || "
                "setweight(to_tsvector('russian', coalesce(author_name, '')), 'B')",
                persisted=True,
            ),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_task_comments_search_vector",
        "task_comments",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    """Remove full-text search vectors and indexes."""
    op.drop_index("ix_task_comments_search_vector", table_name="task_comments")
    op.drop_column("task_comments", "search_vector")
    op.drop_index("ix_documents_search_vector", table_name="documents")
    op.drop_column("documents", "search_vector")
    op.drop_index("ix_kanban_tasks_search_vector", table_name="kanban_tasks")
    op.drop_column("kanban_tasks", "search_vector")

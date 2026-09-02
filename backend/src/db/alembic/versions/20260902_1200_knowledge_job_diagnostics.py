"""knowledge job diagnostics

Revision ID: 4d8e61c7b2a9
Revises: e7b5d29c41a0
Create Date: 2026-09-02 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "4d8e61c7b2a9"
down_revision: Union[str, Sequence[str], None] = "e7b5d29c41a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляет длительность обработки и число построенных chunks."""
    op.add_column(
        "knowledge_index_jobs",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "knowledge_index_jobs",
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "knowledge_index_jobs",
        sa.Column("chunks_count", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Удаляет диагностические поля заданий индексации."""
    op.drop_column("knowledge_index_jobs", "chunks_count")
    op.drop_column("knowledge_index_jobs", "finished_at")
    op.drop_column("knowledge_index_jobs", "started_at")

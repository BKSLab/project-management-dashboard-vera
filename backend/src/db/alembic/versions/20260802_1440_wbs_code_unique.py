"""make WBS codes unique

Revision ID: b3c2d1e0f9a8
Revises: a2b1c0d9e8f7
Create Date: 2026-08-02 14:40:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "b3c2d1e0f9a8"
down_revision: str | Sequence[str] | None = "a2b1c0d9e8f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Гарантирует уникальность иерархического кода ИСР."""
    op.create_unique_constraint("uq_wbs_items_code", "wbs_items", ["code"])


def downgrade() -> None:
    """Удаляет ограничение уникальности кода ИСР."""
    op.drop_constraint("uq_wbs_items_code", "wbs_items", type_="unique")

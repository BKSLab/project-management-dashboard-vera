"""add initial data seed state

Revision ID: e0f9a8b7c6d5
Revises: d9e8f7a6b5c4
Create Date: 2026-08-02 14:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e0f9a8b7c6d5"
down_revision: str | Sequence[str] | None = "d9e8f7a6b5c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создаёт таблицу маркеров одноразовой загрузки."""
    op.create_table(
        "seed_state",
        sa.Column(
            "key",
            sa.String(length=100),
            nullable=False,
            comment="Версионированный ключ успешно загруженного набора данных.",
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата и время успешной загрузки набора начальных данных.",
        ),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    """Удаляет таблицу маркеров загрузки."""
    op.drop_table("seed_state")

"""project sticker canvas coordinates

Revision ID: e1f5a9d7c2b4
Revises: c94a7e2d1b63
Create Date: 2026-09-04 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1f5a9d7c2b4"
down_revision: str | Sequence[str] | None = "c94a7e2d1b63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Добавляет положение стикеров и раскладывает существующие без наложения."""
    op.add_column(
        "project_stickers",
        sa.Column(
            "canvas_x",
            sa.Float(),
            server_default=sa.text("40.0"),
            nullable=False,
            comment="Координата X стикера на Project Board.",
        ),
    )
    op.add_column(
        "project_stickers",
        sa.Column(
            "canvas_y",
            sa.Float(),
            server_default=sa.text("40.0"),
            nullable=False,
            comment="Координата Y стикера на Project Board.",
        ),
    )
    op.execute(
        """
        WITH ordered AS (
            SELECT
                id,
                row_number() OVER (
                    PARTITION BY project_id ORDER BY created_at, id
                ) - 1 AS slot
            FROM project_stickers
        )
        UPDATE project_stickers AS sticker
        SET
            canvas_x = 40.0 + (ordered.slot % 5) * 258.0,
            canvas_y = 40.0 + (ordered.slot / 5) * 258.0
        FROM ordered
        WHERE sticker.id = ordered.id
        """
    )
    op.create_check_constraint(
        "ck_project_stickers_canvas_x_range",
        "project_stickers",
        "canvas_x BETWEEN -1000000.0 AND 1000000.0",
    )
    op.create_check_constraint(
        "ck_project_stickers_canvas_y_range",
        "project_stickers",
        "canvas_y BETWEEN -1000000.0 AND 1000000.0",
    )
    op.alter_column("project_stickers", "canvas_x", server_default=None)
    op.alter_column("project_stickers", "canvas_y", server_default=None)


def downgrade() -> None:
    """Удаляет координаты холста стикеров."""
    op.drop_constraint(
        "ck_project_stickers_canvas_y_range",
        "project_stickers",
        type_="check",
    )
    op.drop_constraint(
        "ck_project_stickers_canvas_x_range",
        "project_stickers",
        type_="check",
    )
    op.drop_column("project_stickers", "canvas_y")
    op.drop_column("project_stickers", "canvas_x")

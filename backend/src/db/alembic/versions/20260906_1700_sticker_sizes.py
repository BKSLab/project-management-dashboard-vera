"""Размеры стикеров Project Board.

Revision ID: d7e91c4a2f10
Revises: b8c34dae125f
"""

import sqlalchemy as sa
from alembic import op

revision = "d7e91c4a2f10"
down_revision = "b8c34dae125f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project_stickers", sa.Column("width", sa.Float(), nullable=False, server_default="230")
    )
    op.add_column(
        "project_stickers", sa.Column("height", sa.Float(), nullable=False, server_default="230")
    )
    op.create_check_constraint(
        "ck_project_stickers_width_range", "project_stickers", "width BETWEEN 160.0 AND 520.0"
    )
    op.create_check_constraint(
        "ck_project_stickers_height_range", "project_stickers", "height BETWEEN 160.0 AND 520.0"
    )
    op.alter_column("project_stickers", "width", server_default=None)
    op.alter_column("project_stickers", "height", server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_project_stickers_height_range", "project_stickers", type_="check")
    op.drop_constraint("ck_project_stickers_width_range", "project_stickers", type_="check")
    op.drop_column("project_stickers", "height")
    op.drop_column("project_stickers", "width")

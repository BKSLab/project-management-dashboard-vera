"""project board stickers

Revision ID: c94a7e2d1b63
Revises: b7d41f0ac9e2
Create Date: 2026-09-04 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c94a7e2d1b63"
down_revision: str | Sequence[str] | None = "b7d41f0ac9e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

sticker_color = postgresql.ENUM(
    "neutral",
    "yellow",
    "blue",
    "green",
    "red",
    "violet",
    name="project_sticker_color",
    create_type=False,
)


def upgrade() -> None:
    """Создаёт стикеры проекта и их связи с задачами."""
    sticker_color.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "project_stickers",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
            comment="Уникальный идентификатор стикера Project Board.",
        ),
        sa.Column(
            "project_id",
            sa.Integer(),
            nullable=False,
            comment="Идентификатор проекта-владельца стикера.",
        ),
        sa.Column("body", sa.Text(), nullable=False, comment="Текст общего стикера проекта."),
        sa.Column("color", sticker_color, nullable=False, comment="Визуальный цвет стикера."),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            nullable=True,
            comment="Идентификатор автора стикера.",
        ),
        sa.Column(
            "created_by_username_snapshot",
            sa.String(length=50),
            nullable=False,
            comment="Fallback-логин автора стикера.",
        ),
        sa.Column(
            "created_by_display_name_snapshot",
            sa.String(length=302),
            nullable=False,
            comment="Fallback-имя автора стикера.",
        ),
        sa.Column(
            "revision",
            sa.Integer(),
            server_default="1",
            nullable=False,
            comment="Монотонная ревизия стикера.",
        ),
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
        sa.CheckConstraint(
            "char_length(btrim(body)) BETWEEN 1 AND 2000",
            name="ck_project_stickers_body_length",
        ),
        sa.CheckConstraint(
            "revision >= 1",
            name="ck_project_stickers_revision_positive",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_project_stickers_created_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_project_stickers_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_stickers"),
    )
    op.create_index(
        "ix_project_stickers_created_by_user_id",
        "project_stickers",
        ["created_by_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_project_stickers_project_id",
        "project_stickers",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_project_stickers_project_created",
        "project_stickers",
        ["project_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "project_sticker_task_links",
        sa.Column(
            "sticker_id",
            sa.Integer(),
            nullable=False,
            comment="Идентификатор стикера.",
        ),
        sa.Column(
            "task_id",
            sa.Integer(),
            nullable=False,
            comment="Идентификатор задачи.",
        ),
        sa.ForeignKeyConstraint(
            ["sticker_id"],
            ["project_stickers.id"],
            name="fk_project_sticker_task_links_sticker_id_project_stickers",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name="fk_project_sticker_task_links_task_id_tasks",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "sticker_id",
            "task_id",
            name="pk_project_sticker_task_links",
        ),
    )
    op.create_index(
        "ix_project_sticker_task_links_task_id",
        "project_sticker_task_links",
        ["task_id"],
        unique=False,
    )


def downgrade() -> None:
    """Удаляет связи задач и стикеры Project Board."""
    op.drop_index(
        "ix_project_sticker_task_links_task_id",
        table_name="project_sticker_task_links",
    )
    op.drop_table("project_sticker_task_links")
    op.drop_index("ix_project_stickers_project_created", table_name="project_stickers")
    op.drop_index("ix_project_stickers_project_id", table_name="project_stickers")
    op.drop_index("ix_project_stickers_created_by_user_id", table_name="project_stickers")
    op.drop_table("project_stickers")
    sticker_color.drop(op.get_bind(), checkfirst=True)

"""users and project members

Revision ID: c2a71f5b48d9
Revises: 8f4c1a90d3e7
Create Date: 2026-09-01 18:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2a71f5b48d9"
down_revision: Union[str, Sequence[str], None] = "8f4c1a90d3e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Вводит пользователей и владение проектами."""
    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
            comment="Уникальный идентификатор пользователя.",
        ),
        sa.Column(
            "username",
            sa.String(length=50),
            nullable=False,
            comment="Уникальный логин пользователя.",
        ),
        sa.Column(
            "password_hash",
            sa.String(length=255),
            nullable=False,
            comment="Хеш пароля пользователя.",
        ),
        sa.Column(
            "last_name",
            sa.String(length=100),
            nullable=False,
            comment="Фамилия пользователя.",
        ),
        sa.Column(
            "first_name",
            sa.String(length=100),
            nullable=False,
            comment="Имя пользователя.",
        ),
        sa.Column(
            "middle_name",
            sa.String(length=100),
            nullable=True,
            comment="Отчество пользователя; может отсутствовать.",
        ),
        sa.Column(
            "email",
            sa.String(length=255),
            nullable=True,
            comment="Необязательная электронная почта пользователя.",
        ),
        sa.Column(
            "phone",
            sa.String(length=32),
            nullable=True,
            comment="Необязательный телефон пользователя.",
        ),
        sa.Column(
            "telegram",
            sa.String(length=64),
            nullable=True,
            comment="Необязательный контакт в Telegram.",
        ),
        sa.Column(
            "avatar_key",
            sa.String(length=255),
            nullable=True,
            comment="Относительный путь фотографии внутри каталога uploads.",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            comment="Заблокированный пользователь не может войти.",
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    # Существующие проекты создавались без владельца и были демонстрационными:
    # обязательное поле нельзя добавить на непустую таблицу, поэтому чистим её.
    op.execute("DELETE FROM projects")

    op.add_column(
        "projects",
        sa.Column(
            "owner_id",
            sa.Integer(),
            nullable=False,
            comment="Идентификатор пользователя-владельца проекта.",
        ),
    )
    op.create_index(op.f("ix_projects_owner_id"), "projects", ["owner_id"], unique=False)
    op.create_foreign_key(
        "fk_projects_owner_id_users",
        "projects",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_table(
        "project_members",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
            comment="Уникальный идентификатор участия в проекте.",
        ),
        sa.Column(
            "project_id",
            sa.Integer(),
            nullable=False,
            comment="Идентификатор проекта.",
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=False,
            comment="Идентификатор пользователя.",
        ),
        sa.Column(
            "role",
            sa.Enum("OWNER", "MEMBER", name="project_role"),
            nullable=False,
            comment="Роль пользователя в проекте.",
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
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_members_project_user"),
    )
    op.create_index(
        op.f("ix_project_members_project_id"),
        "project_members",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_members_user_id"),
        "project_members",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Убирает пользователей и владение проектами."""
    op.drop_index(op.f("ix_project_members_user_id"), table_name="project_members")
    op.drop_index(op.f("ix_project_members_project_id"), table_name="project_members")
    op.drop_table("project_members")
    sa.Enum(name="project_role").drop(op.get_bind(), checkfirst=False)

    op.drop_constraint("fk_projects_owner_id_users", "projects", type_="foreignkey")
    op.drop_index(op.f("ix_projects_owner_id"), table_name="projects")
    op.drop_column("projects", "owner_id")

    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_table("users")

"""api tokens for external clients

Revision ID: a3f81c72d5b4
Revises: e7b5d29c41a0
Create Date: 2026-09-02 14:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a3f81c72d5b4"
down_revision: Union[str, Sequence[str], None] = "e7b5d29c41a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляет токены доступа внешних клиентов."""
    scope = postgresql.ENUM(
        "READ",
        "WRITE",
        name="api_token_scope",
        create_type=False,
    )
    scope.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "api_tokens",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
            comment="Уникальный идентификатор токена.",
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=False,
            comment="Пользователь, от имени которого работает токен.",
        ),
        sa.Column(
            "name",
            sa.String(length=100),
            nullable=False,
            comment="Имя, по которому владелец узнаёт токен в списке.",
        ),
        sa.Column(
            "token_hash",
            sa.String(length=64),
            nullable=False,
            comment="Хеш секрета; сам секрет не хранится.",
        ),
        sa.Column(
            "prefix",
            sa.String(length=8),
            nullable=False,
            comment="Префикс секрета для узнавания токена человеком.",
        ),
        sa.Column(
            "scope",
            scope,
            nullable=False,
            comment="READ разрешает только чтение, WRITE — ещё и изменение.",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Момент истечения токена; NULL означает отсутствие срока.",
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Момент отзыва токена владельцем.",
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Приблизительное время последнего использования токена.",
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_api_tokens_user_id"),
        "api_tokens",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_api_tokens_token_hash"),
        "api_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_api_tokens_user_created",
        "api_tokens",
        ["user_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Удаляет токены доступа и их enum-тип."""
    op.drop_index("ix_api_tokens_user_created", table_name="api_tokens")
    op.drop_index(op.f("ix_api_tokens_token_hash"), table_name="api_tokens")
    op.drop_index(op.f("ix_api_tokens_user_id"), table_name="api_tokens")
    op.drop_table("api_tokens")
    postgresql.ENUM(name="api_token_scope").drop(op.get_bind(), checkfirst=True)

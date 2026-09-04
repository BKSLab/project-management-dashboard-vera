"""analytics reports

Revision ID: d5f83a17c204
Revises: c94a7e2d1b63
Create Date: 2026-09-04 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d5f83a17c204"
down_revision: str | Sequence[str] | None = "c94a7e2d1b63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Создаёт журнал аналитических сводов дашборда."""
    op.create_table(
        "analytics_reports",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
            comment="Уникальный идентификатор аналитического свода.",
        ),
        sa.Column(
            "project_id",
            sa.Integer(),
            nullable=True,
            comment="Проект свода; NULL — свод по всему портфелю пользователя.",
        ),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            nullable=True,
            comment="Пользователь, запросивший анализ; NULL после удаления профиля.",
        ),
        sa.Column(
            "created_by_display_name_snapshot",
            sa.String(length=302),
            nullable=False,
            comment="Имя автора запроса на момент формирования свода.",
        ),
        sa.Column(
            "llm_model",
            sa.String(length=255),
            nullable=False,
            comment="Модель, сформировавшая свод: своды разных моделей несравнимы.",
        ),
        sa.Column(
            "duration_ms",
            sa.Integer(),
            nullable=False,
            comment="Длительность формирования свода в миллисекундах.",
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Тело свода: оценка состояния, находки, прогресс и рекомендации.",
        ),
        sa.Column(
            "context_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Что вошло в контекст модели и что было отсечено лимитом.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Момент формирования свода.",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name="fk_analytics_reports_project_id_projects",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_analytics_reports_created_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_analytics_reports"),
    )
    op.create_index(
        "ix_analytics_reports_project_created",
        "analytics_reports",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_analytics_reports_author_created",
        "analytics_reports",
        ["created_by_user_id", "created_at"],
    )


def downgrade() -> None:
    """Удаляет журнал аналитических сводов дашборда."""
    op.drop_index("ix_analytics_reports_author_created", table_name="analytics_reports")
    op.drop_index("ix_analytics_reports_project_created", table_name="analytics_reports")
    op.drop_table("analytics_reports")

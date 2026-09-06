"""Реестр рисков проекта.

Revision ID: f6a12b8c903d
Revises: d5f83a17c204
Create Date: 2026-09-06 12:00:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f6a12b8c903d"
down_revision = "d5f83a17c204"
branch_labels = None
depends_on = None

ENUMS = {
    "risk_rating": ("LOW", "MEDIUM", "HIGH"),
    "risk_status": ("OPEN", "MITIGATING", "OCCURRED", "CLOSED"),
    "risk_response_strategy": ("AVOID", "MITIGATE", "TRANSFER", "ACCEPT"),
    "risk_source": ("MANUAL", "AI_SUGGESTED"),
}


def upgrade() -> None:
    """Добавляет только новую схему; существующие бизнес-данные не изменяются."""
    for name, values in ENUMS.items():
        postgresql.ENUM(*values, name=name).create(op.get_bind(), checkfirst=True)
    rating = postgresql.ENUM(*ENUMS["risk_rating"], name="risk_rating", create_type=False)
    op.create_table(
        "project_risks",
        sa.Column("id", sa.Integer(), primary_key=True, comment="Номер риска RISK-id."),
        sa.Column(
            "project_id", sa.Integer(), nullable=False, comment="Проект, которому принадлежит риск."
        ),
        sa.Column(
            "task_id",
            sa.Integer(),
            nullable=True,
            comment="При удалении задачи ссылка обнуляется, риск сохраняется.",
        ),
        sa.Column("title", sa.String(255), nullable=False, comment="Краткое название риска."),
        sa.Column("description", sa.Text(), nullable=False, comment="Описание риска в Markdown."),
        sa.Column(
            "probability", rating, nullable=False, comment="Выбранная вероятность LOW/MEDIUM/HIGH."
        ),
        sa.Column("impact", rating, nullable=False, comment="Выбранное влияние LOW/MEDIUM/HIGH."),
        sa.Column(
            "risk_level",
            rating,
            nullable=False,
            comment="Итоговый уровень риска; клиент его не задаёт.",
        ),
        sa.Column(
            "status",
            postgresql.ENUM(*ENUMS["risk_status"], name="risk_status", create_type=False),
            nullable=False,
            server_default="OPEN",
            comment="OPEN, MITIGATING, OCCURRED или CLOSED.",
        ),
        sa.Column(
            "response_strategy",
            postgresql.ENUM(
                *ENUMS["risk_response_strategy"], name="risk_response_strategy", create_type=False
            ),
            nullable=False,
            comment="Избежать, снизить, передать или принять.",
        ),
        sa.Column(
            "mitigation_plan",
            sa.Text(),
            nullable=False,
            server_default="",
            comment="Что сделать заранее для снижения вероятности или влияния.",
        ),
        sa.Column(
            "response_plan",
            sa.Text(),
            nullable=False,
            server_default="",
            comment="План реагирования на риск.",
        ),
        sa.Column(
            "owner_user_id",
            sa.Integer(),
            nullable=True,
            comment="Пользователь, отвечающий за риск; назначение проверяется сервисом.",
        ),
        sa.Column(
            "review_date",
            sa.Date(),
            nullable=True,
            comment="Дата контроля, не срок реализации риска.",
        ),
        sa.Column(
            "source",
            postgresql.ENUM(*ENUMS["risk_source"], name="risk_source", create_type=False),
            nullable=False,
            server_default="MANUAL",
            comment="MANUAL либо подтверждённое человеком AI_SUGGESTED.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Дата и время создания записи.",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment="Дата и время последнего обновления записи.",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.CheckConstraint(
            "char_length(btrim(title)) BETWEEN 1 AND 255", name="ck_project_risks_title"
        ),
        sa.CheckConstraint(
            "char_length(btrim(description)) BETWEEN 1 AND 20000",
            name="ck_project_risks_description",
        ),
    )
    for suffix, columns in (
        ("project_status", ["project_id", "status"]),
        ("project_level", ["project_id", "risk_level"]),
        ("project_review", ["project_id", "review_date"]),
        ("task_id", ["task_id"]),
        ("owner_user_id", ["owner_user_id"]),
    ):
        op.create_index(f"ix_project_risks_{suffix}", "project_risks", columns)


def downgrade() -> None:
    """Удаляет таблицу нового домена и его собственные перечисления."""
    op.drop_table("project_risks")
    for name, values in reversed(ENUMS.items()):
        postgresql.ENUM(*values, name=name).drop(op.get_bind(), checkfirst=True)

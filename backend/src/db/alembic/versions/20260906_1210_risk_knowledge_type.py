"""Тип риска в существующей очереди знаний.

Revision ID: a7b23c9d014e
Revises: f6a12b8c903d
Create Date: 2026-09-06 12:10:00
"""

from alembic import op

revision = "a7b23c9d014e"
down_revision = "f6a12b8c903d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Расширяет тип исходной сущности; существующие задания сохраняются."""
    op.execute("ALTER TYPE knowledge_entity_type ADD VALUE IF NOT EXISTS 'RISK'")


def downgrade() -> None:
    """Сохраняет метку RISK для уже записанных outbox-заданий.

    PostgreSQL не поддерживает DROP VALUE. Удаление метки потребовало бы
    удаления либо преобразования заданий, а миграции проекта выполняют
    только DDL. Неиспользуемая метка совместима со схемой до реестра рисков.
    """

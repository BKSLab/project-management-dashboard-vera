"""protect document link integrity

Revision ID: a2b1c0d9e8f7
Revises: f1a0b9c8d7e6
Create Date: 2026-08-02 14:30:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a2b1c0d9e8f7"
down_revision: str | Sequence[str] | None = "f1a0b9c8d7e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Запрещает двойные цели и повторные связи документов."""
    op.create_check_constraint(
        "ck_document_links_exactly_one_target",
        "document_links",
        "(kanban_task_id IS NOT NULL) <> (wbs_item_id IS NOT NULL)",
    )
    op.create_unique_constraint(
        "uq_document_links_document_task",
        "document_links",
        ["document_id", "kanban_task_id"],
    )
    op.create_unique_constraint(
        "uq_document_links_document_wbs",
        "document_links",
        ["document_id", "wbs_item_id"],
    )


def downgrade() -> None:
    """Удаляет ограничения целостности связей документов."""
    op.drop_constraint("uq_document_links_document_wbs", "document_links", type_="unique")
    op.drop_constraint("uq_document_links_document_task", "document_links", type_="unique")
    op.drop_constraint("ck_document_links_exactly_one_target", "document_links", type_="check")

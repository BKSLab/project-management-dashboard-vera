"""project-first schema

Revision ID: 8f4c1a90d3e7
Revises:
Create Date: 2026-09-01 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "8f4c1a90d3e7"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PROJECT_SEARCH_VECTOR = (
    "setweight(to_tsvector('russian', coalesce(name, '')), 'A') || "
    "setweight(to_tsvector('russian', coalesce(description_md, '')), 'B')"
)
TASK_SEARCH_VECTOR = (
    "setweight(to_tsvector('russian', coalesce(title, '')), 'A') || "
    "setweight(to_tsvector('russian', coalesce(description_md, '')), 'B')"
)
COMMENT_SEARCH_VECTOR = (
    "setweight(to_tsvector('russian', coalesce(body_md, '')), 'A') || "
    "setweight(to_tsvector('russian', coalesce(author_name, '')), 'B')"
)
DOCUMENT_SEARCH_VECTOR = (
    "setweight(to_tsvector('russian', coalesce(title, '')), 'A') || "
    "setweight(to_tsvector('russian', coalesce(content_md, '')), 'B')"
)


def upgrade() -> None:
    """Создаёт схему трекера, построенную вокруг проекта."""
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False, comment="Уникальный идентификатор проекта."),
        sa.Column(
            "key",
            sa.String(length=10),
            nullable=False,
            comment="Уникальный короткий код проекта в верхнем регистре.",
        ),
        sa.Column(
            "name",
            sa.String(length=255),
            nullable=False,
            comment="Человекочитаемое название проекта.",
        ),
        sa.Column(
            "description_md",
            sa.Text(),
            nullable=True,
            comment="Описание проекта в формате Markdown.",
        ),
        sa.Column(
            "status",
            sa.Enum(
                "PLANNING",
                "ACTIVE",
                "PAUSED",
                "COMPLETED",
                "ARCHIVED",
                name="project_status",
            ),
            nullable=False,
            comment="Жизненный статус проекта.",
        ),
        sa.Column(
            "color",
            sa.String(length=20),
            nullable=False,
            comment="HEX-цвет, которым проект обозначается в интерфейсе.",
        ),
        sa.Column(
            "icon",
            sa.String(length=8),
            nullable=True,
            comment="Необязательная эмодзи-иконка проекта.",
        ),
        sa.Column(
            "start_date",
            sa.Date(),
            nullable=True,
            comment="Плановая дата начала проекта.",
        ),
        sa.Column(
            "due_date",
            sa.Date(),
            nullable=True,
            comment="Плановая дата завершения проекта.",
        ),
        sa.Column(
            "order_index",
            sa.Integer(),
            nullable=False,
            comment="Порядок отображения проекта в списке и переключателе.",
        ),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(PROJECT_SEARCH_VECTOR, persisted=True),
            nullable=False,
            comment="Взвешенный FTS-вектор названия и описания проекта.",
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
    op.create_index(op.f("ix_projects_key"), "projects", ["key"], unique=True)
    op.create_index(
        "ix_projects_search_vector",
        "projects",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )

    op.create_table(
        "project_stages",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
            comment="Уникальный идентификатор стадии канбана.",
        ),
        sa.Column(
            "project_id",
            sa.Integer(),
            nullable=False,
            comment="Идентификатор проекта-владельца стадии.",
        ),
        sa.Column(
            "name",
            sa.String(length=100),
            nullable=False,
            comment="Название стадии канбан-доски.",
        ),
        sa.Column(
            "order_index",
            sa.Integer(),
            nullable=False,
            comment="Порядок отображения колонки на канбан-доске.",
        ),
        sa.Column(
            "color",
            sa.String(length=20),
            nullable=False,
            comment="HEX-цвет стадии в интерфейсе.",
        ),
        sa.Column(
            "is_done_stage",
            sa.Boolean(),
            nullable=False,
            comment="Признак стадии, завершающей выполнение задачи.",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name", name="uq_project_stages_project_name"),
    )
    op.create_index(
        op.f("ix_project_stages_project_id"),
        "project_stages",
        ["project_id"],
        unique=False,
    )

    op.create_table(
        "wbs_nodes",
        sa.Column("id", sa.Integer(), nullable=False, comment="Уникальный идентификатор узла ИСР."),
        sa.Column(
            "project_id",
            sa.Integer(),
            nullable=False,
            comment="Идентификатор проекта-владельца узла ИСР.",
        ),
        sa.Column(
            "parent_id",
            sa.Integer(),
            nullable=True,
            comment="Родительский узел ИСР; NULL для узла верхнего уровня.",
        ),
        sa.Column(
            "title",
            sa.String(length=255),
            nullable=False,
            comment="Название раздела ИСР.",
        ),
        sa.Column(
            "position",
            sa.Float(),
            nullable=False,
            comment="Позиция сортировки узла среди соседних узлов.",
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
        sa.ForeignKeyConstraint(["parent_id"], ["wbs_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_wbs_nodes_parent_id"), "wbs_nodes", ["parent_id"], unique=False)
    op.create_index(op.f("ix_wbs_nodes_project_id"), "wbs_nodes", ["project_id"], unique=False)

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), nullable=False, comment="Уникальный идентификатор задачи."),
        sa.Column(
            "project_id",
            sa.Integer(),
            nullable=False,
            comment="Идентификатор проекта-владельца задачи.",
        ),
        sa.Column(
            "stage_id",
            sa.Integer(),
            nullable=False,
            comment="Идентификатор текущей стадии задачи.",
        ),
        sa.Column(
            "wbs_node_id",
            sa.Integer(),
            nullable=True,
            comment="Идентификатор раздела ИСР; NULL для нераспределённой задачи.",
        ),
        sa.Column(
            "number",
            sa.Integer(),
            nullable=False,
            comment="Номер задачи внутри проекта для отображения вида KEY-42.",
        ),
        sa.Column(
            "title",
            sa.String(length=512),
            nullable=False,
            comment="Заголовок задачи.",
        ),
        sa.Column(
            "description_md",
            sa.Text(),
            nullable=True,
            comment="Описание задачи в формате Markdown.",
        ),
        sa.Column(
            "priority",
            sa.Enum("LOW", "MEDIUM", "HIGH", "URGENT", name="task_priority"),
            nullable=False,
            comment="Приоритет выполнения задачи.",
        ),
        sa.Column(
            "role",
            sa.Enum(
                "PM",
                "BE",
                "FE",
                "UXR",
                "UXD",
                "EXPERT",
                "QA",
                "BA",
                "MKT",
                name="task_role",
            ),
            nullable=True,
            comment="Ответственная за выполнение задачи роль.",
        ),
        sa.Column(
            "assignee",
            sa.String(length=255),
            nullable=True,
            comment="Необязательное имя исполнителя задачи.",
        ),
        sa.Column(
            "due_date",
            sa.Date(),
            nullable=True,
            comment="Плановая дата завершения задачи.",
        ),
        sa.Column(
            "position",
            sa.Float(),
            nullable=False,
            comment="Позиция сортировки задачи внутри стадии.",
        ),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(TASK_SEARCH_VECTOR, persisted=True),
            nullable=False,
            comment="Взвешенный FTS-вектор заголовка и описания задачи.",
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
        sa.ForeignKeyConstraint(["stage_id"], ["project_stages.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["wbs_node_id"], ["wbs_nodes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "number", name="uq_tasks_project_number"),
    )
    op.create_index(op.f("ix_tasks_project_id"), "tasks", ["project_id"], unique=False)
    op.create_index(op.f("ix_tasks_stage_id"), "tasks", ["stage_id"], unique=False)
    op.create_index(op.f("ix_tasks_wbs_node_id"), "tasks", ["wbs_node_id"], unique=False)
    op.create_index(
        "ix_tasks_search_vector",
        "tasks",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )

    op.create_table(
        "documents",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
            comment="Уникальный идентификатор документа.",
        ),
        sa.Column(
            "project_id",
            sa.Integer(),
            nullable=False,
            comment="Идентификатор проекта-владельца документа.",
        ),
        sa.Column(
            "slug",
            sa.String(length=255),
            nullable=False,
            comment="URL-идентификатор документа внутри проекта.",
        ),
        sa.Column(
            "title",
            sa.String(length=255),
            nullable=False,
            comment="Человекочитаемый заголовок документа.",
        ),
        sa.Column(
            "content_md",
            sa.Text(),
            nullable=False,
            comment="Содержимое документа в формате Markdown.",
        ),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(DOCUMENT_SEARCH_VECTOR, persisted=True),
            nullable=False,
            comment="Взвешенный FTS-вектор заголовка и содержимого документа.",
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "slug", name="uq_documents_project_slug"),
    )
    op.create_index(op.f("ix_documents_project_id"), "documents", ["project_id"], unique=False)
    op.create_index(op.f("ix_documents_slug"), "documents", ["slug"], unique=False)
    op.create_index(
        "ix_documents_search_vector",
        "documents",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )

    op.create_table(
        "document_links",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
            comment="Уникальный идентификатор связи документа.",
        ),
        sa.Column(
            "document_id",
            sa.Integer(),
            nullable=False,
            comment="Идентификатор связанного документа.",
        ),
        sa.Column(
            "task_id",
            sa.Integer(),
            nullable=False,
            comment="Идентификатор связанной задачи.",
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "task_id", name="uq_document_links_document_task"),
    )
    op.create_index(
        op.f("ix_document_links_document_id"),
        "document_links",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_document_links_task_id"),
        "document_links",
        ["task_id"],
        unique=False,
    )

    op.create_table(
        "task_comments",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
            comment="Уникальный идентификатор комментария.",
        ),
        sa.Column(
            "task_id",
            sa.Integer(),
            nullable=False,
            comment="Идентификатор задачи, к которой относится комментарий.",
        ),
        sa.Column(
            "author_name",
            sa.String(length=255),
            nullable=True,
            comment="Необязательная свободная подпись автора комментария.",
        ),
        sa.Column(
            "body_md",
            sa.Text(),
            nullable=False,
            comment="Текст комментария в формате Markdown.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата и время создания комментария.",
        ),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(COMMENT_SEARCH_VECTOR, persisted=True),
            nullable=False,
            comment="Взвешенный FTS-вектор текста и автора комментария.",
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_task_comments_search_vector",
        "task_comments",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )

    op.create_table(
        "task_activity",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
            comment="Уникальный идентификатор события.",
        ),
        sa.Column(
            "task_id",
            sa.Integer(),
            nullable=False,
            comment="Идентификатор задачи, к которой относится событие.",
        ),
        sa.Column(
            "event_type",
            sa.Enum(
                "STAGE_CHANGED",
                "DUE_DATE_CHANGED",
                "DESCRIPTION_CHANGED",
                "PRIORITY_CHANGED",
                "ASSIGNEE_CHANGED",
                "WBS_NODE_CHANGED",
                "COMMENT_ADDED",
                name="task_activity_event_type",
            ),
            nullable=False,
            comment="Тип изменения задачи.",
        ),
        sa.Column(
            "from_value",
            sa.String(length=255),
            nullable=True,
            comment="Текстовое представление предыдущего значения.",
        ),
        sa.Column(
            "to_value",
            sa.String(length=255),
            nullable=True,
            comment="Текстовое представление нового значения.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата и время фиксации события.",
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "task_attachments",
        sa.Column(
            "id",
            sa.Integer(),
            nullable=False,
            comment="Уникальный идентификатор файла задачи.",
        ),
        sa.Column(
            "task_id",
            sa.Integer(),
            nullable=False,
            comment="Идентификатор задачи, к которой прикреплён файл.",
        ),
        sa.Column(
            "original_name",
            sa.String(length=512),
            nullable=False,
            comment="Исходное имя файла без компонентов пути.",
        ),
        sa.Column(
            "storage_key",
            sa.String(length=255),
            nullable=False,
            comment="Относительный путь файла внутри каталога uploads.",
        ),
        sa.Column(
            "content_type",
            sa.String(length=255),
            nullable=False,
            comment="MIME-тип, используемый при выдаче содержимого файла.",
        ),
        sa.Column(
            "size",
            sa.BigInteger(),
            nullable=False,
            comment="Положительный размер файла в байтах.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата и время добавления файла к задаче.",
        ),
        sa.CheckConstraint("size > 0", name="ck_task_attachments_size_positive"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_task_attachments_storage_key"),
    )
    op.create_index(
        op.f("ix_task_attachments_task_id"),
        "task_attachments",
        ["task_id"],
        unique=False,
    )


def downgrade() -> None:
    """Полностью удаляет схему трекера."""
    op.drop_index(op.f("ix_task_attachments_task_id"), table_name="task_attachments")
    op.drop_table("task_attachments")

    op.drop_table("task_activity")
    sa.Enum(name="task_activity_event_type").drop(op.get_bind(), checkfirst=False)

    op.drop_index("ix_task_comments_search_vector", table_name="task_comments")
    op.drop_table("task_comments")

    op.drop_index(op.f("ix_document_links_task_id"), table_name="document_links")
    op.drop_index(op.f("ix_document_links_document_id"), table_name="document_links")
    op.drop_table("document_links")

    op.drop_index("ix_documents_search_vector", table_name="documents")
    op.drop_index(op.f("ix_documents_slug"), table_name="documents")
    op.drop_index(op.f("ix_documents_project_id"), table_name="documents")
    op.drop_table("documents")

    op.drop_index("ix_tasks_search_vector", table_name="tasks")
    op.drop_index(op.f("ix_tasks_wbs_node_id"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_stage_id"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_project_id"), table_name="tasks")
    op.drop_table("tasks")
    sa.Enum(name="task_role").drop(op.get_bind(), checkfirst=False)
    sa.Enum(name="task_priority").drop(op.get_bind(), checkfirst=False)

    op.drop_index(op.f("ix_wbs_nodes_project_id"), table_name="wbs_nodes")
    op.drop_index(op.f("ix_wbs_nodes_parent_id"), table_name="wbs_nodes")
    op.drop_table("wbs_nodes")

    op.drop_index(op.f("ix_project_stages_project_id"), table_name="project_stages")
    op.drop_table("project_stages")

    op.drop_index("ix_projects_search_vector", table_name="projects")
    op.drop_index(op.f("ix_projects_key"), table_name="projects")
    op.drop_table("projects")
    sa.Enum(name="project_status").drop(op.get_bind(), checkfirst=False)

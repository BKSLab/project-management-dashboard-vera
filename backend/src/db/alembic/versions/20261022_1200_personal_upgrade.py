"""Личные задачи, доски, отчёты и агент: расширение существующей схемы P.

Старые сущности и ключи сохраняются. Откат допускается, пока нет данных,
которые старая версия приложения не может представить; для них нужен экспорт.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from src.db.knowledge_outbox import install_outbox
from src.db.task_attention_ddl import install_attention

revision = "b62dfe210a84"
down_revision = "a81f247e930b"
branch_labels = None
depends_on = None

UPGRADE_OUTBOX_RULES = (
    (
        "task_reports",
        "task",
        (
            "id",
            "task_id",
            "revision",
            "body_md",
            "author_name",
            "source_comment_id",
            "source_comment_original_id",
            "source_author_name",
            "created_at",
        ),
    ),
    (
        "projects",
        "self",
        (
            "id",
            "owner_id",
            "key",
            "name",
            "description_md",
            "status",
            "start_date",
            "due_date",
            "description_sections",
            "due_date_has_been_set",
            "created_at",
            "updated_at",
        ),
    ),
    (
        "tasks",
        "project",
        (
            "id",
            "project_id",
            "stage_id",
            "status",
            "wbs_node_id",
            "number",
            "title",
            "description_md",
            "checklist",
            "checklist_revision",
            "priority",
            "role",
            "assignee",
            "start_date",
            "due_date",
            "baseline_start_date",
            "baseline_due_date",
            "completed_at",
            "position",
            "wbs_position",
            "created_at",
            "updated_at",
        ),
    ),
    (
        "documents",
        "project",
        (
            "id",
            "project_id",
            "slug",
            "title",
            "content_md",
            "origin_attachment_id",
            "created_at",
            "updated_at",
        ),
    ),
    ("task_comments", "task", ("id", "task_id", "author_name", "body_md", "created_at")),
    (
        "task_attachments",
        "task",
        ("id", "task_id", "original_name", "storage_key", "content_type", "size", "created_at"),
    ),
    (
        "project_milestones",
        "project",
        (
            "id",
            "project_id",
            "title",
            "description_md",
            "due_date",
            "status",
            "wbs_node_id",
            "created_at",
            "updated_at",
        ),
    ),
    (
        "project_risks",
        "project",
        (
            "id",
            "project_id",
            "task_id",
            "title",
            "description",
            "mitigation_plan",
            "response_plan",
            "probability",
            "impact",
            "risk_level",
            "status",
            "response_strategy",
            "owner_user_id",
            "review_date",
            "source",
            "created_at",
            "updated_at",
        ),
    ),
    (
        "wbs_nodes",
        "project",
        ("id", "project_id", "parent_id", "title", "position", "created_at", "updated_at"),
    ),
    (
        "project_stages",
        "project",
        ("id", "project_id", "name", "order_index", "color", "is_done_stage"),
    ),
    (
        "project_stickers",
        "project",
        (
            "id",
            "project_id",
            "board_id",
            "body",
            "color",
            "created_by_user_id",
            "created_by_username_snapshot",
            "created_by_display_name_snapshot",
            "revision",
            "created_at",
            "updated_at",
        ),
    ),
    (
        "project_members",
        "project",
        ("id", "project_id", "user_id", "role", "created_at", "updated_at"),
    ),
    (
        "task_activity",
        "task",
        (
            "id",
            "task_id",
            "event_type",
            "from_value",
            "to_value",
            "actor_user_id",
            "actor_name",
            "via_api_key_label",
            "created_at",
        ),
    ),
    (
        "project_deadline_changes",
        "project",
        (
            "id",
            "project_id",
            "previous_due_date",
            "new_due_date",
            "changed_by_user_id",
            "changed_by_name",
            "comment",
            "created_at",
        ),
    ),
    (
        "analytics_reports",
        "project",
        (
            "id",
            "project_id",
            "created_by_user_id",
            "created_by_display_name_snapshot",
            "llm_model",
            "payload",
            "context_summary",
            "created_at",
        ),
    ),
    ("document_links", "task", ("id", "document_id", "task_id")),
    ("project_sticker_task_links", "task", ("sticker_id", "task_id")),
    (
        "task_dependencies",
        "project",
        (
            "id",
            "project_id",
            "predecessor_task_id",
            "successor_task_id",
            "dependency_type",
            "lag_days",
            "created_at",
        ),
    ),
    (
        "task_participants",
        "task",
        ("id", "task_id", "project_member_id", "user_id", "role", "created_at", "updated_at"),
    ),
    ("users", "user", ("id", "username", "first_name", "last_name", "middle_name", "is_active")),
)
LEGACY_OUTBOX_RULES = (
    (
        "projects",
        "self",
        (
            "id",
            "owner_id",
            "key",
            "name",
            "description_md",
            "status",
            "start_date",
            "due_date",
            "description_sections",
            "due_date_has_been_set",
            "created_at",
            "updated_at",
        ),
    ),
    (
        "tasks",
        "project",
        (
            "id",
            "project_id",
            "stage_id",
            "wbs_node_id",
            "number",
            "title",
            "description_md",
            "checklist",
            "checklist_revision",
            "priority",
            "role",
            "assignee",
            "start_date",
            "due_date",
            "baseline_start_date",
            "baseline_due_date",
            "completed_at",
            "position",
            "wbs_position",
            "created_at",
            "updated_at",
        ),
    ),
    (
        "documents",
        "project",
        (
            "id",
            "project_id",
            "slug",
            "title",
            "content_md",
            "origin_attachment_id",
            "created_at",
            "updated_at",
        ),
    ),
    ("task_comments", "task", ("id", "task_id", "author_name", "body_md", "created_at")),
    (
        "task_attachments",
        "task",
        ("id", "task_id", "original_name", "storage_key", "content_type", "size", "created_at"),
    ),
    (
        "project_milestones",
        "project",
        (
            "id",
            "project_id",
            "title",
            "description_md",
            "due_date",
            "status",
            "wbs_node_id",
            "created_at",
            "updated_at",
        ),
    ),
    (
        "project_risks",
        "project",
        (
            "id",
            "project_id",
            "task_id",
            "title",
            "description",
            "mitigation_plan",
            "response_plan",
            "probability",
            "impact",
            "risk_level",
            "status",
            "response_strategy",
            "owner_user_id",
            "review_date",
            "source",
            "created_at",
            "updated_at",
        ),
    ),
    (
        "wbs_nodes",
        "project",
        ("id", "project_id", "parent_id", "title", "position", "created_at", "updated_at"),
    ),
    (
        "project_stages",
        "project",
        ("id", "project_id", "name", "order_index", "color", "is_done_stage"),
    ),
    (
        "project_stickers",
        "project",
        (
            "id",
            "project_id",
            "body",
            "color",
            "created_by_user_id",
            "created_by_username_snapshot",
            "created_by_display_name_snapshot",
            "revision",
            "created_at",
            "updated_at",
        ),
    ),
    (
        "project_members",
        "project",
        ("id", "project_id", "user_id", "role", "created_at", "updated_at"),
    ),
    (
        "task_activity",
        "task",
        ("id", "task_id", "event_type", "from_value", "to_value", "created_at"),
    ),
    (
        "project_deadline_changes",
        "project",
        (
            "id",
            "project_id",
            "previous_due_date",
            "new_due_date",
            "changed_by_user_id",
            "changed_by_name",
            "comment",
            "created_at",
        ),
    ),
    (
        "analytics_reports",
        "project",
        (
            "id",
            "project_id",
            "created_by_user_id",
            "created_by_display_name_snapshot",
            "llm_model",
            "payload",
            "context_summary",
            "created_at",
        ),
    ),
    ("document_links", "task", ("id", "document_id", "task_id")),
    ("project_sticker_task_links", "task", ("sticker_id", "task_id")),
    (
        "task_dependencies",
        "project",
        (
            "id",
            "project_id",
            "predecessor_task_id",
            "successor_task_id",
            "dependency_type",
            "lag_days",
            "created_at",
        ),
    ),
    (
        "task_participants",
        "task",
        ("id", "task_id", "project_member_id", "role", "created_at", "updated_at"),
    ),
    ("users", "user", ("id", "username", "first_name", "last_name", "middle_name", "is_active")),
)


def upgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS knowledge_changed ON project_stickers")
    postgresql.ENUM("NEW", "IN_PROGRESS", "REVIEW", "DONE", "CANCELLED", name="task_status").create(
        op.get_bind(), checkfirst=True
    )
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Uuid(), nullable=False, comment="Первичный ключ."),
        sa.Column(
            "label",
            sa.String(length=160),
            nullable=False,
            comment="Отображаемое имя ключа; попадает в историю задач как «через ключ».",
        ),
        sa.Column(
            "key_hash", sa.Text(), nullable=False, comment="Хеш секрета; сам ключ не хранится."
        ),
        sa.Column(
            "key_prefix",
            sa.String(length=16),
            nullable=False,
            comment="Первые символы ключа для узнавания и поиска.",
        ),
        sa.Column(
            "owner_user_id",
            sa.Integer(),
            nullable=True,
            comment="Локальный владелец ключа; доступ ограничен его правами.",
        ),
        sa.Column(
            "owner_name",
            sa.String(length=255),
            nullable=True,
            comment="Снимок имени владельца для списка ключей.",
        ),
        sa.Column(
            "kind",
            sa.String(length=16),
            server_default="service",
            nullable=False,
            comment="personal|service; права ограничены доступом владельца.",
        ),
        sa.Column(
            "scopes",
            sa.JSON(),
            nullable=False,
            comment="Список строк вида tasks:read. Пустой список — ключ не открывает ничего.",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="NULL — бессрочный ключ.",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            comment="False — ключ отозван и не принимается.",
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Заполняется вместе с is_active=false.",
        ),
        sa.Column(
            "revoked_by_user_id",
            sa.Integer(),
            nullable=True,
            comment="Пользователь, отозвавший ключ.",
        ),
        sa.Column(
            "revoked_by_name",
            sa.String(length=255),
            nullable=True,
            comment="Снимок имени на момент отзыва.",
        ),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            nullable=True,
            comment="Пользователь, выпустивший ключ.",
        ),
        sa.Column(
            "created_by_name",
            sa.String(length=255),
            nullable=True,
            comment="Снимок имени на момент выдачи.",
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Обновляется не чаще раза в несколько минут.",
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
        sa.CheckConstraint("kind IN ('personal', 'service')", name="ck_api_keys_kind"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["revoked_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_prefix"),
    )
    op.create_index(op.f("ix_api_keys_kind"), "api_keys", ["kind"], unique=False)
    op.create_index(op.f("ix_api_keys_owner_user_id"), "api_keys", ["owner_user_id"], unique=False)
    op.create_table(
        "api_key_usage",
        sa.Column(
            "id", sa.BigInteger(), nullable=False, comment="Уникальный идентификатор обращения."
        ),
        sa.Column("api_key_id", sa.Uuid(), nullable=True, comment="Ключ, которым выполнен запрос."),
        sa.Column(
            "key_prefix",
            sa.String(length=16),
            nullable=True,
            comment="Снимок префикса: читается и после удаления ключа.",
        ),
        sa.Column(
            "at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Время начала обработки запроса.",
        ),
        sa.Column(
            "channel",
            sa.String(length=8),
            nullable=False,
            comment="REST-запрос или вызов инструмента MCP.",
        ),
        sa.Column(
            "method",
            sa.String(length=8),
            nullable=False,
            comment="HTTP-метод запроса или CALL для инструмента MCP.",
        ),
        sa.Column(
            "route",
            sa.String(length=255),
            nullable=False,
            comment="По нему группируется статистика.",
        ),
        sa.Column(
            "path",
            sa.String(length=512),
            nullable=False,
            comment="Без строки запроса — параметры лежат в query.",
        ),
        sa.Column(
            "query",
            sa.JSON(),
            nullable=False,
            comment="Значения усечены; секреты сюда не попадают.",
        ),
        sa.Column(
            "actor_login",
            sa.String(length=255),
            nullable=True,
            comment="Логин локального владельца ключа.",
        ),
        sa.Column(
            "status_code",
            sa.Integer(),
            nullable=False,
            comment="2xx — успех, 4xx — ошибка клиента, 5xx — сбой сервиса.",
        ),
        sa.Column(
            "duration_ms", sa.Integer(), nullable=False, comment="Замер вокруг обработки запроса."
        ),
        sa.Column(
            "response_bytes",
            sa.Integer(),
            nullable=True,
            comment="Объём отданных данных, если известен.",
        ),
        sa.Column(
            "client_ip",
            sa.String(length=64),
            nullable=True,
            comment="Из X-Forwarded-For или адреса соединения.",
        ),
        sa.ForeignKeyConstraint(["api_key_id"], ["api_keys.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_key_usage_at", "api_key_usage", ["at"], unique=False)
    op.create_index("ix_api_key_usage_key_at", "api_key_usage", ["api_key_id", "at"], unique=False)
    op.create_table(
        "project_boards",
        sa.Column(
            "id", sa.Integer(), nullable=False, comment="Уникальный идентификатор доски проекта."
        ),
        sa.Column(
            "project_id",
            sa.Integer(),
            nullable=True,
            comment="Идентификатор проекта-владельца доски; NULL — личная доска без проекта.",
        ),
        sa.Column(
            "title", sa.String(length=120), nullable=False, comment="Название доски проекта."
        ),
        sa.Column(
            "position",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="Порядок доски среди досок проекта.",
        ),
        sa.Column(
            "created_by_user_id", sa.Integer(), nullable=True, comment="Идентификатор автора доски."
        ),
        sa.Column(
            "revision",
            sa.Integer(),
            server_default="1",
            nullable=False,
            comment="Монотонная ревизия доски.",
        ),
        sa.Column(
            "editor_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default='{"version":1,"groups":[],"locked":[],"templates":[]}',
            nullable=False,
            comment="Версионированная metadata редактора; CAS использует revision доски.",
        ),
        sa.Column(
            "archived_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Дата мягкого удаления доски; NULL у активной.",
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
            "char_length(btrim(title)) BETWEEN 1 AND 120", name="ck_project_boards_title_length"
        ),
        sa.CheckConstraint(
            "project_id IS NOT NULL OR created_by_user_id IS NOT NULL",
            name="ck_project_boards_free_has_owner",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_project_boards_revision_positive"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_project_boards_owner_active",
        "project_boards",
        ["created_by_user_id", "archived_at", "position"],
        unique=False,
        postgresql_where=sa.text("project_id IS NULL"),
    )
    op.create_index(
        "ix_project_boards_project_active",
        "project_boards",
        ["project_id", "archived_at", "position"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_boards_project_id"), "project_boards", ["project_id"], unique=False
    )
    op.create_table(
        "board_shapes",
        sa.Column(
            "id", sa.Integer(), nullable=False, comment="Уникальный идентификатор фигуры доски."
        ),
        sa.Column(
            "board_id",
            sa.Integer(),
            nullable=False,
            comment="Идентификатор доски; фигура удаляется вместе с доской.",
        ),
        sa.Column(
            "kind",
            sa.Enum("rect", "ellipse", "diamond", "text", "arrow", "line", name="board_shape_kind"),
            nullable=False,
            comment="rect, ellipse, diamond, text, arrow или line.",
        ),
        sa.Column("x", sa.Float(), nullable=False, comment="X левого верхнего угла рамки."),
        sa.Column("y", sa.Float(), nullable=False, comment="Y левого верхнего угла рамки."),
        sa.Column("w", sa.Float(), nullable=False, comment="Ширина рамки фигуры на холсте."),
        sa.Column("h", sa.Float(), nullable=False, comment="Высота рамки фигуры на холсте."),
        sa.Column(
            "points",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
            comment="Ломаная стрелки/линии; NULL у остальных фигур.",
        ),
        sa.Column(
            "start_ref",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
            comment='Привязка начала: {"type", "id", "anchor"}; только у arrow/line.',
        ),
        sa.Column(
            "end_ref",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
            comment='Привязка конца: {"type", "id", "anchor"}; только у arrow/line.',
        ),
        sa.Column(
            "style",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="Цвета-токены палитры, толщина, пунктир, наконечники, шрифт.",
        ),
        sa.Column(
            "label",
            sa.Text(),
            server_default="",
            nullable=False,
            comment="Текст внутри фигуры или надпись.",
        ),
        sa.Column(
            "z_index",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="Порядок наложения на доске.",
        ),
        sa.Column(
            "created_by_user_id",
            sa.Integer(),
            nullable=True,
            comment="Идентификатор автора фигуры.",
        ),
        sa.Column(
            "revision",
            sa.Integer(),
            server_default="1",
            nullable=False,
            comment="Монотонная ревизия фигуры.",
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
            "(kind IN ('arrow', 'line')) = (points IS NOT NULL)",
            name="ck_board_shapes_points_only_linear",
        ),
        sa.CheckConstraint(
            "kind IN ('arrow', 'line') OR (start_ref IS NULL AND end_ref IS NULL)",
            name="ck_board_shapes_refs_only_linear",
        ),
        sa.CheckConstraint(
            "kind IN ('arrow', 'line') OR (w BETWEEN 1.0 AND 20000.0 AND h BETWEEN 1.0 AND 20000.0)",
            name="ck_board_shapes_box_size",
        ),
        sa.CheckConstraint("char_length(label) <= 2000", name="ck_board_shapes_label_length"),
        sa.CheckConstraint("revision >= 1", name="ck_board_shapes_revision_positive"),
        sa.CheckConstraint(
            "w BETWEEN 0.0 AND 2000000.0 AND h BETWEEN 0.0 AND 2000000.0",
            name="ck_board_shapes_size_range",
        ),
        sa.CheckConstraint(
            "x BETWEEN -1000000.0 AND 1000000.0 AND y BETWEEN -1000000.0 AND 1000000.0",
            name="ck_board_shapes_xy_range",
        ),
        sa.ForeignKeyConstraint(["board_id"], ["project_boards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_board_shapes_board_id"), "board_shapes", ["board_id"], unique=False)
    op.create_table(
        "chat_agent_turns",
        sa.Column("id", sa.Integer(), nullable=False, comment="ID хода."),
        sa.Column("chat_id", sa.Integer(), nullable=False, comment="Чат хода."),
        sa.Column("project_id", sa.Integer(), nullable=False, comment="Проект хода."),
        sa.Column(
            "request_message_id",
            sa.Integer(),
            nullable=False,
            comment="Сообщение участника, обращённое к Тиму.",
        ),
        sa.Column(
            "reply_message_id", sa.Integer(), nullable=False, comment="Сообщение Тима с ответом."
        ),
        sa.Column(
            "requester_id",
            sa.Integer(),
            nullable=False,
            comment="Кто позвал Тима; его права действуют в ответе.",
        ),
        sa.Column(
            "status", sa.String(length=16), nullable=False, comment="Состояние подготовки ответа."
        ),
        sa.Column(
            "progress",
            sa.String(length=200),
            nullable=True,
            comment="Что Тим делает сейчас, пока готовит ответ; NULL — статуса нет или ответ завершён.",
        ),
        sa.Column("error", sa.Text(), nullable=True, comment="Безопасное описание ошибки."),
        sa.Column(
            "sources",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
            comment="Проверенные источники ответа (карточки сущностей).",
        ),
        sa.Column(
            "run_id", sa.Uuid(), nullable=True, comment="Владелец текущей попытки исполнения."
        ),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=True, comment="Начало попытки."
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True), nullable=True, comment="Завершение попытки."
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
            "status IN ('queued', 'processing', 'completed', 'failed')",
            name="ck_chat_agent_turn_status",
        ),
        sa.ForeignKeyConstraint(
            ["chat_id", "project_id"],
            ["project_chats.id", "project_chats.project_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["reply_message_id"], ["chat_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["request_message_id"], ["chat_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reply_message_id"),
        sa.UniqueConstraint("request_message_id"),
    )
    op.create_index("ix_chat_agent_turns_queue", "chat_agent_turns", ["status", "id"], unique=False)
    op.create_table(
        "task_views",
        sa.Column(
            "user_id", sa.Integer(), nullable=False, comment="Пользователь персонального просмотра."
        ),
        sa.Column(
            "task_id", sa.Integer(), nullable=False, comment="Задача персонального просмотра."
        ),
        sa.Column(
            "revision",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="Монотонный водяной знак; запоздавший просмотр не стирает новый.",
        ),
        sa.Column(
            "deadline_revision",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="Не подтверждается, если при открытии срок ещё не был нарушен.",
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "task_id"),
    )
    op.create_table(
        "task_reports",
        sa.Column("id", sa.Integer(), nullable=False, comment="ID версии отчёта."),
        sa.Column("task_id", sa.Integer(), nullable=False, comment="Задача отчёта."),
        sa.Column("revision", sa.Integer(), nullable=False, comment="Монотонный номер публикации."),
        sa.Column("body_md", sa.Text(), nullable=False, comment="Снимок текста отчёта."),
        sa.Column("author_id", sa.Integer(), nullable=True, comment="Кто опубликовал версию."),
        sa.Column(
            "author_name",
            sa.String(length=255),
            nullable=False,
            comment="Снимок имени публикатора.",
        ),
        sa.Column(
            "source_comment_id",
            sa.Integer(),
            nullable=True,
            comment="Ссылка на существующий комментарий.",
        ),
        sa.Column(
            "source_comment_original_id",
            sa.Integer(),
            nullable=True,
            comment="ID источника сохраняется после удаления комментария.",
        ),
        sa.Column(
            "source_author_name",
            sa.String(length=255),
            nullable=True,
            comment="Снимок автора комментария.",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
            comment="Дата публикации версии.",
        ),
        sa.CheckConstraint("revision > 0", name="ck_task_reports_revision"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_comment_id"], ["task_comments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", "revision", name="uq_task_reports_revision"),
    )
    op.add_column(
        "agent_conversations",
        sa.Column("channel", sa.String(length=16), server_default="web", nullable=False),
    )
    op.add_column(
        "agent_conversations", sa.Column("external_key", sa.String(length=255), nullable=True)
    )
    op.add_column("agent_conversations", sa.Column("api_key_id", sa.Uuid(), nullable=True))
    op.alter_column(
        "agent_conversations",
        "project_id",
        existing_type=sa.INTEGER(),
        nullable=True,
        existing_comment="Проект диалога.",
    )
    op.create_index(
        "ix_agent_conversations_owner",
        "agent_conversations",
        ["user_id", "updated_at"],
        unique=False,
    )
    op.create_index(
        "uq_agent_conversation_external",
        "agent_conversations",
        ["user_id", "api_key_id", "external_key"],
        unique=True,
        postgresql_where=sa.text("external_key IS NOT NULL"),
        postgresql_nulls_not_distinct=True,
    )
    op.create_foreign_key(
        "fk_agent_conversations_api_key_id",
        "agent_conversations",
        "api_keys",
        ["api_key_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "agent_messages",
        sa.Column(
            "page_context",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Контекст страницы виджета: route, project_key, task_id, board_id.",
        ),
    )
    op.add_column(
        "agent_messages",
        sa.Column(
            "verbatim",
            sa.Text(),
            nullable=True,
            comment="Дословная реплика пользователя; только она разрешает агенту запись.",
        ),
    )
    op.add_column(
        "agent_messages",
        sa.Column(
            "key_scopes",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Права сервисного ключа на момент вопроса; NULL — вопрос из интерфейса.",
        ),
    )
    op.add_column(
        "agent_messages",
        sa.Column(
            "project_id",
            sa.Integer(),
            nullable=True,
            comment="Проект, в котором агент ответил в беседе по трекеру; NULL — обзор.",
        ),
    )
    op.add_column(
        "agent_messages",
        sa.Column(
            "progress",
            sa.String(length=200),
            nullable=True,
            comment="Что Тим делает сейчас, пока готовит ответ; NULL — статуса нет или ответ завершён.",
        ),
    )
    op.create_index(
        "ix_agent_messages_request_result", "agent_messages", ["request_id", "role"], unique=False
    )
    op.create_foreign_key(
        "fk_agent_messages_project_id",
        "agent_messages",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "agent_tool_runs",
        sa.Column(
            "chat_turn_id",
            sa.Integer(),
            nullable=True,
            comment="Ответ Тима в чате проекта; null для виджета и MCP.",
        ),
    )
    op.alter_column(
        "agent_tool_runs",
        "project_id",
        existing_type=sa.INTEGER(),
        nullable=True,
        comment="Проект действия; null — личное действие вне проекта.",
        existing_comment="Проект действия.",
    )
    op.create_index(
        "ix_agent_tool_chat_turn", "agent_tool_runs", ["chat_turn_id", "created_at"], unique=False
    )
    op.create_index(
        "uq_agent_tool_personal_request",
        "agent_tool_runs",
        ["user_id", "request_id"],
        unique=True,
        postgresql_where=sa.text("project_id IS NULL"),
    )
    op.create_foreign_key(
        "fk_agent_tool_runs_chat_turn_id",
        "agent_tool_runs",
        "chat_agent_turns",
        ["chat_turn_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.add_column(
        "chat_messages",
        sa.Column(
            "author_kind",
            sa.String(length=16),
            server_default="user",
            nullable=False,
            comment="Автор: user — участник, agent — Тим.",
        ),
    )
    op.add_column(
        "project_stickers",
        sa.Column(
            "board_id",
            sa.Integer(),
            nullable=True,
            comment="Идентификатор доски; стикер удаляется вместе с доской.",
        ),
    )
    op.add_column(
        "project_stickers",
        sa.Column(
            "z_index",
            sa.Integer(),
            server_default="0",
            nullable=False,
            comment="Порядок наложения стикера на доске.",
        ),
    )
    op.alter_column(
        "project_stickers",
        "project_id",
        existing_type=sa.INTEGER(),
        nullable=True,
        comment="Идентификатор проекта-владельца стикера; NULL — доска без проекта.",
        existing_comment="Идентификатор проекта-владельца стикера.",
    )
    op.alter_column(
        "project_stickers",
        "color",
        existing_type=postgresql.ENUM(
            "neutral", "yellow", "blue", "green", "red", "violet", name="project_sticker_color"
        ),
        type_=sa.String(length=7),
        comment="Цвет стикера: hex #rrggbb в нижнем регистре.",
        existing_comment="Визуальный цвет стикера.",
        existing_nullable=False,
        postgresql_using="CASE color::text WHEN 'neutral' THEN '#f3efe4' WHEN 'yellow' THEN '#fff19a' WHEN 'blue' THEN '#c9edff' WHEN 'green' THEN '#d8f5b5' WHEN 'red' THEN '#ffbbb5' WHEN 'violet' THEN '#e4d2ff' END",
    )
    op.create_index(
        op.f("ix_project_stickers_board_id"), "project_stickers", ["board_id"], unique=False
    )
    op.create_foreign_key(
        "fk_project_stickers_board_id",
        "project_stickers",
        "project_boards",
        ["board_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.add_column(
        "projects",
        sa.Column(
            "icon_image_key",
            sa.String(length=2048),
            nullable=True,
            comment="Локальный ключ картинки проекта в uploads; наружу не отдаётся.",
        ),
    )
    op.add_column(
        "projects",
        sa.Column(
            "icon_image_content_type",
            sa.String(length=50),
            nullable=True,
            comment="Проверенный MIME-тип картинки проекта: png, jpeg или webp.",
        ),
    )
    op.alter_column(
        "projects",
        "icon",
        existing_type=sa.VARCHAR(length=8),
        type_=sa.String(length=64),
        existing_comment="Необязательная эмодзи-иконка проекта.",
        existing_nullable=True,
    )
    op.add_column(
        "task_activity",
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            nullable=True,
            comment="Пользователь, от имени которого сделано изменение; NULL — неизвестен.",
        ),
    )
    op.add_column(
        "task_activity",
        sa.Column(
            "actor_name",
            sa.String(length=255),
            nullable=True,
            comment="Снимок имени автора изменения на момент события.",
        ),
    )
    op.add_column(
        "task_activity",
        sa.Column(
            "via_api_key_label",
            sa.String(length=160),
            nullable=True,
            comment="Имя API-ключа: изменение сделано агентом «через ключ»; NULL — напрямую.",
        ),
    )
    op.create_foreign_key(
        "fk_task_activity_actor_user_id",
        "task_activity",
        "users",
        ["actor_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "task_comments",
        sa.Column(
            "author_id",
            sa.Integer(),
            nullable=True,
            comment="Автор комментария; NULL — пользователь удалён, подпись осталась в author_name.",
        ),
    )
    op.create_index(
        op.f("ix_task_comments_author_id"), "task_comments", ["author_id"], unique=False
    )
    op.create_foreign_key(
        "fk_task_comments_author_id",
        "task_comments",
        "users",
        ["author_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "task_participants",
        sa.Column(
            "user_id",
            sa.Integer(),
            nullable=True,
            comment="Идентификатор пользователя-участника задачи вне проекта; NULL у проектной.",
        ),
    )
    op.alter_column(
        "task_participants",
        "project_member_id",
        existing_type=sa.INTEGER(),
        nullable=True,
        comment="Идентификатор участия пользователя в проекте; NULL у задачи вне проекта.",
    )
    op.create_index(
        op.f("ix_task_participants_user_id"), "task_participants", ["user_id"], unique=False
    )
    op.create_unique_constraint(
        "uq_task_participants_task_user_role", "task_participants", ["task_id", "user_id", "role"]
    )
    op.create_foreign_key(
        "fk_task_participants_user_id",
        "task_participants",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.add_column(
        "tasks",
        sa.Column(
            "status",
            sa.Enum("NEW", "IN_PROGRESS", "REVIEW", "DONE", "CANCELLED", name="task_status"),
            nullable=True,
            comment="Статус разовой задачи; NULL у проектной задачи.",
        ),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "attention_revision",
            sa.Integer(),
            server_default="1",
            nullable=False,
            comment="Монотонная версия; обновляется триггерами вместе с содержимым.",
        ),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "attention_deadline_revision",
            sa.Integer(),
            server_default="1",
            nullable=False,
            comment="Отдельная версия нарушения срока; обычные комментарии её не меняют.",
        ),
    )
    op.alter_column(
        "tasks",
        "project_id",
        existing_type=sa.INTEGER(),
        nullable=True,
        existing_comment="Идентификатор проекта-владельца задачи.",
    )
    op.alter_column(
        "tasks",
        "stage_id",
        existing_type=sa.INTEGER(),
        nullable=True,
        existing_comment="Идентификатор текущей стадии задачи.",
    )
    op.create_index(
        "uq_tasks_personal_number",
        "tasks",
        ["number"],
        unique=True,
        postgresql_where=sa.text("project_id IS NULL"),
    )
    op.create_table(
        "calendar_feed_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.execute(
        "INSERT INTO project_boards (project_id, title, position, created_by_user_id) SELECT id, 'Основная', 0, owner_id FROM projects"
    )
    op.execute(
        "UPDATE project_stickers s SET board_id = b.id FROM project_boards b WHERE b.project_id = s.project_id"
    )
    op.alter_column("project_stickers", "board_id", nullable=False)
    op.execute(
        "UPDATE agent_messages m SET project_id = c.project_id FROM agent_conversations c WHERE c.id = m.conversation_id"
    )
    op.create_check_constraint(
        "ck_agent_conversation_channel", "agent_conversations", "channel IN ('web', 'api')"
    )
    op.create_check_constraint(
        "ck_agent_tool_single_origin",
        "agent_tool_runs",
        "message_id IS NULL OR chat_turn_id IS NULL",
    )
    op.create_check_constraint(
        "ck_chat_message_author_kind", "chat_messages", "author_kind IN ('user', 'agent')"
    )
    op.create_check_constraint(
        "ck_chat_agent_message_author",
        "chat_messages",
        "author_kind = 'user' OR author_user_id IS NULL",
    )
    op.create_check_constraint(
        "ck_task_participants_one_person",
        "task_participants",
        "(project_member_id IS NULL) <> (user_id IS NULL)",
    )
    op.create_check_constraint(
        "ck_tasks_stage_in_project", "tasks", "(project_id IS NULL) = (stage_id IS NULL)"
    )
    op.create_check_constraint(
        "ck_tasks_status_outside_project", "tasks", "(project_id IS NULL) = (status IS NOT NULL)"
    )
    op.create_check_constraint(
        "ck_tasks_personal_no_wbs",
        "tasks",
        "project_id IS NOT NULL OR (wbs_node_id IS NULL AND wbs_position IS NULL AND canvas_x IS NULL AND canvas_y IS NULL)",
    )
    op.execute("ALTER TYPE knowledge_entity_type ADD VALUE IF NOT EXISTS 'TASK_REPORT'")
    op.execute("ALTER TYPE task_activity_event_type ADD VALUE IF NOT EXISTS 'TASK_MOVED'")
    op.execute("ALTER TYPE task_activity_event_type ADD VALUE IF NOT EXISTS 'LINKS_REMOVED'")
    op.alter_column(
        "agent_tool_runs",
        "message_id",
        existing_type=sa.INTEGER(),
        comment="Ответ Тима в виджете; null для чата проекта и MCP.",
        existing_comment="Ответ чата; null для MCP.",
        existing_nullable=True,
    )
    op.alter_column(
        "task_comments",
        "author_name",
        existing_type=sa.VARCHAR(length=255),
        comment="Снимок полного имени автора: для полнотекстового поиска и удалённых авторов.",
        existing_comment="Необязательная свободная подпись автора комментария.",
        existing_nullable=True,
    )
    op.alter_column(
        "task_participants",
        "id",
        existing_type=sa.INTEGER(),
        comment="Уникальный идентификатор ролевого назначения на задачу.",
        existing_nullable=False,
        autoincrement=True,
    )
    op.alter_column(
        "task_participants",
        "task_id",
        existing_type=sa.INTEGER(),
        comment="Идентификатор задачи.",
        existing_nullable=False,
    )
    op.alter_column(
        "task_participants",
        "role",
        existing_type=postgresql.ENUM(
            "EXECUTOR", "REPORTER", "OBSERVER", name="task_participant_role"
        ),
        comment="Роль участника в задаче.",
        existing_nullable=False,
    )
    op.alter_column(
        "task_participants",
        "created_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        comment="Дата и время создания записи.",
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "task_participants",
        "updated_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        comment="Дата и время последнего обновления записи.",
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "tasks",
        "checklist",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        comment="Название, стабильные ID, тексты и отметки пунктов; NULL — чек-листа нет.",
        existing_comment="Чек-лист с упорядоченными пунктами.",
        existing_nullable=True,
    )
    op.alter_column(
        "tasks",
        "checklist_revision",
        existing_type=sa.INTEGER(),
        comment="Монотонная версия, сохраняется и после удаления чек-листа.",
        existing_comment="Версия чек-листа.",
        existing_nullable=False,
        existing_server_default=sa.text("0"),
    )
    op.alter_column(
        "calendar_feed_tokens", "id", comment="Уникальный идентификатор ссылки подписки."
    )
    op.alter_column(
        "calendar_feed_tokens",
        "user_id",
        comment="Пользователь, чей календарь отдаёт ссылка; одна ссылка на пользователя.",
    )
    op.alter_column(
        "calendar_feed_tokens",
        "token_hash",
        comment="Хеш секрета ссылки подписки; сам секрет не хранится.",
    )
    op.alter_column("calendar_feed_tokens", "created_at", comment="Дата и время создания записи.")
    op.alter_column(
        "calendar_feed_tokens", "updated_at", comment="Дата и время последнего обновления записи."
    )
    install_outbox(op.get_bind(), rules=UPGRADE_OUTBOX_RULES)
    install_attention(op.get_bind())
    op.execute(
        "INSERT INTO knowledge_index_jobs (project_id, entity_type, operation, status, attempts) SELECT id, 'PROJECT', 'REINDEX_PROJECT', 'PENDING', 0 FROM projects WHERE NOT EXISTS (SELECT 1 FROM knowledge_index_jobs j WHERE j.project_id = projects.id AND j.status IN ('PENDING', 'PROCESSING'))"
    )


def downgrade() -> None:
    _assert_legacy_compatible()
    for table, _scope, _fields in UPGRADE_OUTBOX_RULES:
        op.execute(f'DROP TRIGGER IF EXISTS knowledge_changed ON "{table}"')
    op.execute("DROP FUNCTION IF EXISTS task_attention_revision() CASCADE")
    op.execute("DROP FUNCTION IF EXISTS task_attention_child() CASCADE")
    op.execute("DROP FUNCTION IF EXISTS task_attention_notify() CASCADE")
    op.execute("DROP FUNCTION IF EXISTS task_attention_stage() CASCADE")
    op.execute("DROP FUNCTION IF EXISTS task_attention_dependency() CASCADE")
    op.drop_constraint("ck_agent_conversation_channel", "agent_conversations", type_="check")
    op.drop_constraint("ck_agent_tool_single_origin", "agent_tool_runs", type_="check")
    op.drop_constraint("ck_chat_message_author_kind", "chat_messages", type_="check")
    op.drop_constraint("ck_chat_agent_message_author", "chat_messages", type_="check")
    op.drop_constraint("ck_task_participants_one_person", "task_participants", type_="check")
    op.drop_constraint("ck_tasks_stage_in_project", "tasks", type_="check")
    op.drop_constraint("ck_tasks_status_outside_project", "tasks", type_="check")
    op.drop_constraint("ck_tasks_personal_no_wbs", "tasks", type_="check")
    op.drop_index(
        "uq_tasks_personal_number",
        table_name="tasks",
        postgresql_where=sa.text("project_id IS NULL"),
    )
    op.alter_column(
        "tasks",
        "stage_id",
        existing_type=sa.INTEGER(),
        nullable=False,
        existing_comment="Идентификатор текущей стадии задачи.",
    )
    op.alter_column(
        "tasks",
        "project_id",
        existing_type=sa.INTEGER(),
        nullable=False,
        existing_comment="Идентификатор проекта-владельца задачи.",
    )
    op.drop_column("tasks", "attention_deadline_revision")
    op.drop_column("tasks", "attention_revision")
    op.drop_column("tasks", "status")
    op.drop_constraint("fk_task_participants_user_id", "task_participants", type_="foreignkey")
    op.drop_constraint("uq_task_participants_task_user_role", "task_participants", type_="unique")
    op.drop_index(op.f("ix_task_participants_user_id"), table_name="task_participants")
    op.alter_column(
        "task_participants",
        "project_member_id",
        existing_type=sa.INTEGER(),
        nullable=False,
        comment=None,
        existing_comment="Идентификатор участия пользователя в проекте; NULL у задачи вне проекта.",
    )
    op.drop_column("task_participants", "user_id")
    op.drop_constraint("fk_task_comments_author_id", "task_comments", type_="foreignkey")
    op.drop_index(op.f("ix_task_comments_author_id"), table_name="task_comments")
    op.drop_column("task_comments", "author_id")
    op.drop_constraint("fk_task_activity_actor_user_id", "task_activity", type_="foreignkey")
    op.drop_column("task_activity", "via_api_key_label")
    op.drop_column("task_activity", "actor_name")
    op.drop_column("task_activity", "actor_user_id")
    op.alter_column(
        "projects",
        "icon",
        existing_type=sa.String(length=64),
        type_=sa.VARCHAR(length=8),
        existing_comment="Необязательная эмодзи-иконка проекта.",
        existing_nullable=True,
    )
    op.drop_column("projects", "icon_image_content_type")
    op.drop_column("projects", "icon_image_key")
    op.drop_constraint("fk_project_stickers_board_id", "project_stickers", type_="foreignkey")
    op.drop_index(op.f("ix_project_stickers_board_id"), table_name="project_stickers")
    op.alter_column(
        "project_stickers",
        "color",
        existing_type=sa.String(length=7),
        type_=postgresql.ENUM(
            "neutral", "yellow", "blue", "green", "red", "violet", name="project_sticker_color"
        ),
        comment="Визуальный цвет стикера.",
        existing_comment="Цвет стикера: hex #rrggbb в нижнем регистре.",
        existing_nullable=False,
        postgresql_using="(CASE color WHEN '#f3efe4' THEN 'neutral' WHEN '#fff19a' THEN 'yellow' WHEN '#c9edff' THEN 'blue' WHEN '#d8f5b5' THEN 'green' WHEN '#ffbbb5' THEN 'red' WHEN '#e4d2ff' THEN 'violet' END)::project_sticker_color",
    )
    op.alter_column(
        "project_stickers",
        "project_id",
        existing_type=sa.INTEGER(),
        nullable=False,
        comment="Идентификатор проекта-владельца стикера.",
        existing_comment="Идентификатор проекта-владельца стикера; NULL — доска без проекта.",
    )
    op.drop_column("project_stickers", "z_index")
    op.drop_column("project_stickers", "board_id")
    op.drop_column("chat_messages", "author_kind")
    op.drop_constraint("fk_agent_tool_runs_chat_turn_id", "agent_tool_runs", type_="foreignkey")
    op.drop_index(
        "uq_agent_tool_personal_request",
        table_name="agent_tool_runs",
        postgresql_where=sa.text("project_id IS NULL"),
    )
    op.drop_index("ix_agent_tool_chat_turn", table_name="agent_tool_runs")
    op.alter_column(
        "agent_tool_runs",
        "project_id",
        existing_type=sa.INTEGER(),
        nullable=False,
        comment="Проект действия.",
        existing_comment="Проект действия; null — личное действие вне проекта.",
    )
    op.drop_column("agent_tool_runs", "chat_turn_id")
    op.drop_constraint("fk_agent_messages_project_id", "agent_messages", type_="foreignkey")
    op.drop_index("ix_agent_messages_request_result", table_name="agent_messages")
    op.drop_column("agent_messages", "progress")
    op.drop_column("agent_messages", "project_id")
    op.drop_column("agent_messages", "key_scopes")
    op.drop_column("agent_messages", "verbatim")
    op.drop_column("agent_messages", "page_context")
    op.drop_constraint(
        "fk_agent_conversations_api_key_id", "agent_conversations", type_="foreignkey"
    )
    op.drop_index(
        "uq_agent_conversation_external",
        table_name="agent_conversations",
        postgresql_where=sa.text("external_key IS NOT NULL"),
        postgresql_nulls_not_distinct=True,
    )
    op.drop_index("ix_agent_conversations_owner", table_name="agent_conversations")
    op.alter_column(
        "agent_conversations",
        "project_id",
        existing_type=sa.INTEGER(),
        nullable=False,
        existing_comment="Проект диалога.",
    )
    op.drop_column("agent_conversations", "api_key_id")
    op.drop_column("agent_conversations", "external_key")
    op.drop_column("agent_conversations", "channel")
    op.drop_table("task_reports")
    op.drop_table("task_views")
    op.drop_index("ix_chat_agent_turns_queue", table_name="chat_agent_turns")
    op.drop_table("chat_agent_turns")
    op.drop_index(op.f("ix_board_shapes_board_id"), table_name="board_shapes")
    op.drop_table("board_shapes")
    op.drop_index(op.f("ix_project_boards_project_id"), table_name="project_boards")
    op.drop_index("ix_project_boards_project_active", table_name="project_boards")
    op.drop_index(
        "ix_project_boards_owner_active",
        table_name="project_boards",
        postgresql_where=sa.text("project_id IS NULL"),
    )
    op.drop_table("project_boards")
    op.drop_index("ix_api_key_usage_key_at", table_name="api_key_usage")
    op.drop_index("ix_api_key_usage_at", table_name="api_key_usage")
    op.drop_table("api_key_usage")
    op.drop_index(op.f("ix_api_keys_owner_user_id"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_kind"), table_name="api_keys")
    op.drop_table("api_keys")
    op.drop_table("calendar_feed_tokens")
    postgresql.ENUM(name="task_status").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="board_shape_kind").drop(op.get_bind(), checkfirst=True)
    op.alter_column(
        "tasks",
        "checklist_revision",
        existing_type=sa.INTEGER(),
        comment="Версия чек-листа.",
        existing_comment="Монотонная версия, сохраняется и после удаления чек-листа.",
        existing_nullable=False,
        existing_server_default=sa.text("0"),
    )
    op.alter_column(
        "tasks",
        "checklist",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        comment="Чек-лист с упорядоченными пунктами.",
        existing_comment="Название, стабильные ID, тексты и отметки пунктов; NULL — чек-листа нет.",
        existing_nullable=True,
    )
    op.alter_column(
        "task_participants",
        "updated_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        comment=None,
        existing_comment="Дата и время последнего обновления записи.",
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "task_participants",
        "created_at",
        existing_type=postgresql.TIMESTAMP(timezone=True),
        comment=None,
        existing_comment="Дата и время создания записи.",
        existing_nullable=False,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "task_participants",
        "role",
        existing_type=postgresql.ENUM(
            "EXECUTOR", "REPORTER", "OBSERVER", name="task_participant_role"
        ),
        comment=None,
        existing_comment="Роль участника в задаче.",
        existing_nullable=False,
    )
    op.alter_column(
        "task_participants",
        "task_id",
        existing_type=sa.INTEGER(),
        comment=None,
        existing_comment="Идентификатор задачи.",
        existing_nullable=False,
    )
    op.alter_column(
        "task_participants",
        "id",
        existing_type=sa.INTEGER(),
        comment=None,
        existing_comment="Уникальный идентификатор ролевого назначения на задачу.",
        existing_nullable=False,
        autoincrement=True,
    )
    op.alter_column(
        "task_comments",
        "author_name",
        existing_type=sa.VARCHAR(length=255),
        comment="Необязательная свободная подпись автора комментария.",
        existing_comment="Снимок полного имени автора: для полнотекстового поиска и удалённых авторов.",
        existing_nullable=True,
    )
    op.alter_column(
        "agent_tool_runs",
        "message_id",
        existing_type=sa.INTEGER(),
        comment="Ответ чата; null для MCP.",
        existing_comment="Ответ Тима в виджете; null для чата проекта и MCP.",
        existing_nullable=True,
    )
    install_outbox(op.get_bind(), rules=LEGACY_OUTBOX_RULES)


def _assert_legacy_compatible() -> None:
    checks = (
        "SELECT EXISTS (SELECT 1 FROM tasks WHERE project_id IS NULL)",
        "SELECT EXISTS (SELECT 1 FROM agent_conversations WHERE project_id IS NULL OR channel <> 'web')",
        "SELECT EXISTS (SELECT 1 FROM agent_tool_runs WHERE project_id IS NULL OR chat_turn_id IS NOT NULL)",
        "SELECT EXISTS (SELECT 1 FROM task_reports)",
        "SELECT EXISTS (SELECT 1 FROM board_shapes)",
        "SELECT EXISTS (SELECT 1 FROM api_keys)",
        "SELECT EXISTS (SELECT 1 FROM calendar_feed_tokens)",
        "SELECT EXISTS (SELECT 1 FROM chat_agent_turns)",
        "SELECT EXISTS (SELECT 1 FROM projects WHERE icon_image_key IS NOT NULL OR length(icon) > 8)",
        'SELECT EXISTS (SELECT 1 FROM project_boards WHERE project_id IS NULL OR title <> \'Основная\' OR archived_at IS NOT NULL OR editor_metadata <> \'{"version":1,"groups":[],"locked":[],"templates":[]}\'::jsonb)',
        "SELECT EXISTS (SELECT 1 FROM project_boards GROUP BY project_id HAVING count(*) > 1)",
        "SELECT EXISTS (SELECT 1 FROM project_stickers WHERE color NOT IN ('#f3efe4','#fff19a','#c9edff','#d8f5b5','#ffbbb5','#e4d2ff'))",
    )
    if any(op.get_bind().exec_driver_sql(sql).scalar() for sql in checks):
        raise RuntimeError(
            "Откат остановлен: есть данные новых возможностей. Сначала экспортируйте их и подготовьте обратное преобразование."
        )

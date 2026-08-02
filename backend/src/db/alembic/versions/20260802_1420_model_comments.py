"""document database columns

Revision ID: f1a0b9c8d7e6
Revises: e0f9a8b7c6d5
Create Date: 2026-08-02 14:20:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f1a0b9c8d7e6"
down_revision: str | Sequence[str] | None = "e0f9a8b7c6d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


COLUMN_COMMENTS: dict[str, dict[str, str]] = {
    "document_links": {
        "id": "Уникальный идентификатор связи документа.",
        "document_id": "Идентификатор связанного документа.",
        "kanban_task_id": "Идентификатор связанной задачи канбана.",
        "wbs_item_id": "Идентификатор связанного узла ИСР.",
    },
    "documents": {
        "id": "Уникальный идентификатор документа.",
        "slug": "Уникальный URL-идентификатор документа.",
        "title": "Человекочитаемый заголовок документа.",
        "content_md": "Содержимое документа в формате Markdown.",
        "search_vector": "Взвешенный FTS-вектор заголовка и содержимого документа.",
        "created_at": "Дата и время создания записи.",
        "updated_at": "Дата и время последнего обновления записи.",
    },
    "kanban_stages": {
        "id": "Уникальный идентификатор стадии канбана.",
        "name": "Название стадии канбан-доски.",
        "order_index": "Порядок отображения колонки на канбан-доске.",
        "color": "HEX-цвет стадии в интерфейсе.",
        "is_done_stage": "Признак стадии, завершающей выполнение задачи.",
    },
    "kanban_tasks": {
        "id": "Уникальный идентификатор задачи.",
        "wbs_item_id": "Связанный листовой узел ИСР; NULL для ручной задачи.",
        "stage_id": "Идентификатор текущей стадии задачи.",
        "title": "Заголовок задачи канбана.",
        "description_md": "Описание задачи в формате Markdown.",
        "due_date": "Плановая дата завершения задачи.",
        "position": "Позиция сортировки задачи внутри стадии.",
        "search_vector": "Взвешенный FTS-вектор заголовка и описания задачи.",
        "created_at": "Дата и время создания записи.",
        "updated_at": "Дата и время последнего обновления записи.",
    },
    "task_activity": {
        "id": "Уникальный идентификатор события.",
        "task_id": "Идентификатор задачи, к которой относится событие.",
        "event_type": "Тип изменения задачи.",
        "from_value": "Текстовое представление предыдущего значения.",
        "to_value": "Текстовое представление нового значения.",
        "created_at": "Дата и время фиксации события.",
    },
    "task_comments": {
        "id": "Уникальный идентификатор комментария.",
        "task_id": "Идентификатор задачи, к которой относится комментарий.",
        "author_name": "Необязательная свободная подпись автора комментария.",
        "body_md": "Текст комментария в формате Markdown.",
        "created_at": "Дата и время создания комментария.",
        "search_vector": "Взвешенный FTS-вектор текста и автора комментария.",
    },
    "wbs_items": {
        "id": "Уникальный идентификатор узла ИСР.",
        "parent_id": "Родительский узел; NULL для корневой фазы.",
        "code": "Иерархический код узла ИСР.",
        "phase_name": "Название фазы для корневого узла.",
        "title": "Название работы или раздела ИСР.",
        "role": "Ответственная роль за выполнение работы.",
        "order_index": "Порядок отображения среди соседних узлов.",
        "is_leaf": "Признак листового узла со связанной задачей канбана.",
    },
}


def upgrade() -> None:
    """Добавляет описания колонок в метаданные PostgreSQL."""
    for table_name, columns in COLUMN_COMMENTS.items():
        for column_name, comment in columns.items():
            op.alter_column(table_name, column_name, comment=comment)


def downgrade() -> None:
    """Удаляет описания колонок из метаданных PostgreSQL."""
    for table_name, columns in reversed(COLUMN_COMMENTS.items()):
        for column_name in reversed(columns):
            op.alter_column(table_name, column_name, comment=None)

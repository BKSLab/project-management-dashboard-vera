"""Upgrade the old personal head with real stickers, WBS and private history."""

from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

LEGACY_HEAD = "a81f247e930b"
COLORS = {
    "neutral": "#f3efe4",
    "yellow": "#fff19a",
    "blue": "#c9edff",
    "green": "#d8f5b5",
    "red": "#ffbbb5",
    "violet": "#e4d2ff",
}
TABLES = (
    "users",
    "projects",
    "wbs_nodes",
    "tasks",
    "project_stickers",
    "project_sticker_task_links",
    "agent_conversations",
    "agent_messages",
    "agent_tool_runs",
    "agent_files",
    "task_attachments",
    "project_chats",
    "chat_messages",
    "chat_attachments",
)


def snapshot(connection, table):
    """JSON preserves every old column, including timestamps and receipt payloads."""
    return (
        connection.execute(
            text(f'SELECT to_jsonb(item) FROM "{table}" item ORDER BY to_jsonb(item)::text')
        )
        .scalars()
        .all()
    )


async def test_personal_upgrade_preserves_legacy_data(postgres_container, tmp_path):
    database = f"personal_upgrade_{uuid4().hex}"
    url = postgres_container.get_connection_url().replace("psycopg2", "asyncpg")
    admin = create_async_engine(url, isolation_level="AUTOCOMMIT")
    async with admin.connect() as connection:
        await connection.execute(text(f'CREATE DATABASE "{database}"'))
    engine = create_async_engine(admin.url.set(database=database))
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "src/db/alembic"))
    local_keys = ("tasks/old-note.md", "agent/old-note.md", "chat/old-note.md")
    for storage_key in local_keys:
        file = tmp_path / storage_key
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(b"Existing private local file")

    def verify(connection):
        config.attributes["connection"] = connection
        command.upgrade(config, LEGACY_HEAD)
        statements = (
            "INSERT INTO users (id, username, password_hash, first_name, last_name, is_active) VALUES (10, 'local_owner', 'synthetic-hash', 'Test', 'Owner', true)",
            "INSERT INTO projects (id, owner_id, key, name, color, status, order_index) VALUES (10, 10, 'OLD', 'Existing project', '#58a6ff', 'ACTIVE', 0), (11, 10, 'EMPTY', 'No stickers yet', '#3fb950', 'PLANNING', 1)",
            "INSERT INTO project_stages (id, project_id, name, order_index, color, is_done_stage) VALUES (10, 10, 'Working', 0, '#58a6ff', false)",
            "INSERT INTO wbs_nodes (id, project_id, parent_id, title, position) VALUES (10, 10, NULL, 'Parent', 1000), (11, 10, 10, 'Child', 1500)",
            "INSERT INTO tasks (id, project_id, stage_id, number, title, priority, position, wbs_node_id, wbs_position, canvas_x, canvas_y) VALUES (10, 10, 10, 1, 'Assigned to WBS', 'HIGH', 1000, 11, 2500, NULL, NULL), (11, 10, 10, 2, 'WBS pool', 'MEDIUM', 2000, NULL, NULL, NULL, NULL), (12, 10, 10, 3, 'Free WBS card', 'LOW', 3000, NULL, NULL, 512.5, -72.25)",
            "INSERT INTO agent_conversations (id, project_id, user_id, title, summary, summary_through_id) VALUES (10, 10, 10, 'Private project dialogue', 'Existing conversation memory', 100)",
            "INSERT INTO agent_messages (id, conversation_id, request_id, role, content, sources, files, status) VALUES (100, 10, '00000000-0000-0000-0000-000000000001', 'user', 'Original question', '[]', '[]', 'completed'), (101, 10, '00000000-0000-0000-0000-000000000001', 'assistant', 'Original answer', '[{\"source_id\":\"task:10\"}]', '[]', 'completed')",
            "INSERT INTO task_attachments (id, task_id, original_name, storage_key, content_type, size) VALUES (10, 10, 'old-note.md', 'tasks/old-note.md', 'text/markdown', 27)",
            "INSERT INTO agent_files (id, conversation_id, message_id, original_name, storage_key, content_type, size) VALUES ('00000000-0000-0000-0000-000000000010', 10, 100, 'old-note.md', 'agent/old-note.md', 'text/markdown', 27)",
            "INSERT INTO chat_messages (id, chat_id, project_id, seq, author_user_id, content, client_message_id) SELECT 10, id, project_id, 1, 10, 'Old team message', '00000000-0000-0000-0000-000000000011' FROM project_chats WHERE project_id=10",
            "INSERT INTO chat_attachments (id, chat_id, message_id, uploader_id, storage_key, original_name, content_type, size_bytes) SELECT '00000000-0000-0000-0000-000000000012', id, 10, 10, 'chat/old-note.md', 'old-note.md', 'text/markdown', 27 FROM project_chats WHERE project_id=10",
        )
        for statement in statements:
            connection.execute(text(statement))
        for index, color in enumerate(COLORS, start=1):
            connection.execute(
                text(
                    "INSERT INTO project_stickers (id, project_id, body, color, canvas_x, canvas_y, width, height, created_by_user_id, created_by_username_snapshot, created_by_display_name_snapshot, revision) VALUES (:id, 10, :body, CAST(:color AS project_sticker_color), :x, :y, :width, :height, 10, 'local_owner', 'Owner Test', :revision)"
                ),
                {
                    "id": index,
                    "body": f"Existing {color} note",
                    "color": color,
                    "x": -120.25 + index * 17,
                    "y": 42.5 + index * 13,
                    "width": 160 + index * 20,
                    "height": 180 + index * 15,
                    "revision": index,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO project_sticker_task_links (sticker_id, task_id) VALUES (:id, 10)"
                ),
                {"id": index},
            )
        for status in ("pending", "completed", "rejected", "failed"):
            connection.execute(
                text(
                    "INSERT INTO agent_tool_runs (id, project_id, user_id, message_id, request_id, tool_name, title, arguments, status, result) VALUES (:id, 10, 10, 101, :request_id, 'create_task', 'Existing receipt', CAST(:arguments AS jsonb), :status, CAST(:result AS jsonb))"
                ),
                {
                    "id": uuid4(),
                    "request_id": uuid4(),
                    "status": status,
                    "arguments": '{"title":"Saved task"}',
                    "result": '{"task_id":10,"receipt":"preserve"}',
                },
            )
        connection.commit()
        before = {table: snapshot(connection, table) for table in TABLES}
        connection.commit()

        command.upgrade(config, "head")
        connection.commit()
        for table, old_rows in before.items():
            current_rows = snapshot(connection, table)
            assert len(current_rows) == len(old_rows), table
            # New nullable/context fields must not replace any legacy data.
            by_id = {str(row.get("id", row)): row for row in current_rows}
            for old in old_rows:
                current = by_id[str(old.get("id", old))]
                expected = dict(old)
                if table == "project_stickers":
                    expected["color"] = COLORS[old["color"]]
                    assert current["board_id"] is not None
                assert {key: current[key] for key in expected} == expected, table

        assert connection.execute(
            text(
                "SELECT project_id, title, position, created_by_user_id FROM project_boards ORDER BY project_id"
            )
        ).all() == [(10, "Основная", 0, 10), (11, "Основная", 0, 10)]
        assert connection.execute(text("SELECT DISTINCT project_id FROM agent_messages")).all() == [
            (10,)
        ]
        assert connection.execute(
            text("SELECT DISTINCT channel FROM agent_conversations")
        ).all() == [("web",)]
        assert connection.execute(text("SELECT DISTINCT author_kind FROM chat_messages")).all() == [
            ("user",)
        ]

        # A report is searchable project knowledge and creates an outbox job.
        connection.execute(text("DELETE FROM knowledge_index_jobs"))
        connection.commit()
        connection.execute(
            text(
                "INSERT INTO task_reports (task_id, revision, body_md, author_id, author_name) VALUES (10, 1, 'Published result', 10, 'Owner Test')"
            )
        )
        assert connection.execute(text("SELECT project_id FROM knowledge_index_jobs")).all() == [
            (10,)
        ]
        connection.rollback()
        connection.execute(text("DELETE FROM knowledge_index_jobs"))
        connection.commit()
        connection.execute(text("UPDATE project_stickers SET canvas_x = canvas_x + 1 WHERE id = 1"))
        assert (
            connection.execute(text("SELECT count(*) FROM knowledge_index_jobs")).scalar_one() == 0
        )
        connection.execute(text("UPDATE project_stickers SET body = 'Changed note' WHERE id = 1"))
        assert connection.execute(text("SELECT project_id FROM knowledge_index_jobs")).all() == [
            (10,)
        ]
        connection.rollback()

    try:
        async with engine.connect() as connection:
            await connection.run_sync(verify)
        for storage_key in local_keys:
            assert (tmp_path / storage_key).read_bytes() == b"Existing private local file"
    finally:
        await engine.dispose()
        async with admin.connect() as connection:
            await connection.execute(text(f'DROP DATABASE "{database}"'))
        await admin.dispose()

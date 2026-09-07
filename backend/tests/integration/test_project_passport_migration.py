"""Переход на паспорт сохраняет старый текст и отмечает существующий срок."""

from datetime import date
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine


async def test_passport_migration_preserves_existing_projects(postgres_container):
    name = f"passport_migration_{uuid4().hex}"
    url = postgres_container.get_connection_url().replace("psycopg2", "asyncpg")
    admin = create_async_engine(url, isolation_level="AUTOCOMMIT")
    async with admin.connect() as connection:
        await connection.execute(text(f'CREATE DATABASE "{name}"'))
    engine = create_async_engine(admin.url.set(database=name))
    await admin.dispose()
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "src/db/alembic"))

    def verify(connection):
        config.attributes["connection"] = connection
        command.upgrade(config, "d7e91c4a2f10")
        connection.execute(
            text(
                "INSERT INTO users (id, username, password_hash, first_name, last_name, is_active) VALUES (1, 'owner', '!', 'Иван', 'Тестов', true)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO projects (id, owner_id, key, name, description_md, color, status, order_index, due_date) VALUES (1, 1, 'OLD', 'Старый', '**Исходное описание**', '#334455', 'ACTIVE', 0, '2026-10-01'), (2, 1, 'OPEN', 'Без срока', NULL, '#334455', 'ACTIVE', 1, NULL)"
            )
        )
        connection.commit()
        command.upgrade(config, "head")
        connection.commit()
        assert connection.execute(
            text(
                "SELECT description_md, description_sections, due_date_has_been_set FROM projects ORDER BY id"
            )
        ).all() == [
            ("**Исходное описание**", None, True),
            (None, None, False),
        ]
        assert connection.execute(
            text(
                "SELECT project_id, previous_due_date, new_due_date, changed_by_user_id, changed_by_name FROM project_deadline_changes"
            )
        ).one() == (1, None, date(2026, 10, 1), None, "Система")
        connection.commit()
        command.downgrade(config, "d7e91c4a2f10")
        connection.commit()
        assert "project_deadline_changes" not in inspect(connection).get_table_names()
        assert (
            connection.execute(text("SELECT description_md FROM projects WHERE id=1")).scalar_one()
            == "**Исходное описание**"
        )
        connection.commit()
        command.upgrade(config, "head")
        connection.commit()
        assert (
            connection.execute(text("SELECT count(*) FROM project_deadline_changes")).scalar_one()
            == 1
        )

    try:
        async with engine.connect() as connection:
            await connection.run_sync(verify)
    finally:
        await engine.dispose()

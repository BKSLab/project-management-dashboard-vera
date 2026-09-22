"""Изолированная PostgreSQL БД для проверок общего чата."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.redis import RedisContainer

from src.core.settings import ChatSettings, get_settings
from src.db.models import Base, Project, ProjectMember, User
from src.dependencies.scopes import build_chat_scope
from src.realtime.runtime import build_chat_runtime
from src.services.chat_attachments import ChatAttachmentsService
from src.services.chat_presenter import ChatPresenter
from src.services.project_chats import ProjectChatService
from src.storage.chat_attachments import ChatAttachmentStorage


@pytest_asyncio.fixture
async def chat_env(postgres_container, tmp_path):
    """Изолированная БД и небольшой pool проявляют утечки и гонки commit."""
    name = f"chat_test_{uuid4().hex}"
    admin = create_async_engine(
        postgres_container.get_connection_url().replace("psycopg2", "asyncpg"),
        isolation_level="AUTOCOMMIT",
    )
    async with admin.connect() as connection:
        await connection.execute(text(f'CREATE DATABASE "{name}"'))
    engine = create_async_engine(
        admin.url.set(database=name), pool_size=2, max_overflow=0, pool_timeout=2
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as db:
        db.add_all(
            [
                User(
                    id=i,
                    username=f"chatuser{i}",
                    password_hash="!",
                    first_name="Участник",
                    last_name=str(i),
                    is_active=True,
                )
                for i in (1, 2, 3)
            ]
        )
        await db.flush()
        db.add_all(
            [
                Project(id=i, owner_id=1, key=f"C{i}", name=f"Чат {i}", color="#334455")
                for i in (1, 2)
            ]
        )
        await db.flush()
        db.add_all(
            [
                ProjectMember(project_id=p, user_id=u, role="OWNER" if u == 1 else "MEMBER")
                for p, u in ((1, 1), (1, 2), (2, 1))
            ]
        )
        await db.commit()
    service = ProjectChatService(
        build_chat_scope(session_factory=factory, invite_code="unused"), ChatPresenter()
    )
    files = ChatAttachmentsService(service, ChatAttachmentStorage(tmp_path / "chat"), 24)
    try:
        yield SimpleNamespace(service=service, files=files, factory=factory, engine=engine)
    finally:
        await engine.dispose()
        async with admin.connect() as connection:
            await connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        await admin.dispose()


@pytest.fixture(scope="session")
def chat_redis_container():
    """Настоящий Redis проверяет Pub/Sub и Lua, а не их имитацию."""
    with RedisContainer("redis:7.4-alpine") as container:
        yield container


@pytest_asyncio.fixture
async def runtimes(chat_env, chat_redis_container):
    url = f"redis://{chat_redis_container.get_container_host_ip()}:{chat_redis_container.get_exposed_port(6379)}/0"
    config = get_settings().model_copy(
        update={
            "app": get_settings().app.model_copy(
                update={"uploads_path": chat_env.files.storage.root.parent}
            ),
            "chat": ChatSettings(
                chat_redis_url=url, chat_outbox_poll_seconds=0.05, chat_ephemeral_sweep_seconds=0.1
            ),
        }
    )
    transport = Redis.from_url(url)
    await transport.flushdb()
    first = build_chat_runtime(settings=config, session_factory=chat_env.factory)
    second = build_chat_runtime(settings=config, session_factory=chat_env.factory)
    await first.start()
    await second.start()
    try:
        yield SimpleNamespace(
            first=first, second=second, config=config, env=chat_env, transport=transport
        )
    finally:
        await first.close()
        await second.close()
        await transport.aclose()

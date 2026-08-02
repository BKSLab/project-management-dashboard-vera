import os
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from docker.errors import DockerException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from testcontainers.postgres import PostgresContainer

from main import app
from src.db.models import Base


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    """Поднимает один PostgreSQL 16 на весь интеграционный прогон."""
    try:
        with PostgresContainer("postgres:16-alpine") as container:
            yield container
    except DockerException as error:
        if os.getenv("CI"):
            raise
        pytest.skip(f"Docker недоступен для integration-тестов: {error}")


@pytest_asyncio.fixture(scope="session")
async def engine(postgres_container: PostgresContainer) -> AsyncGenerator[AsyncEngine, None]:
    """Создаёт схему приложения в тестовом PostgreSQL."""
    url = postgres_container.get_connection_url().replace("psycopg2", "asyncpg")
    test_engine = create_async_engine(url)
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield test_engine
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Изолирует тест репозитория внешней транзакцией с rollback."""
    async with engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            yield session
        await transaction.rollback()


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Generator[None, None, None]:
    """Не допускает протекания FastAPI overrides между API-тестами."""
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def api_client() -> AsyncGenerator[AsyncClient, None]:
    """Возвращает HTTP-клиент, работающий напрямую с ASGI-приложением."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client

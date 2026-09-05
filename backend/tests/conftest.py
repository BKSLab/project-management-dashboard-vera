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
from src.db.models.api_tokens import ApiTokenScope
from src.dependencies.access import (
    require_comment_access,
    require_document_access,
    require_link_access,
    require_project_access,
    require_project_ownership,
    require_stage_access,
    require_task_access,
)
from src.dependencies.auth import get_principal
from src.services.access import AccessGrant
from src.services.auth import Principal


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


@pytest_asyncio.fixture
async def engine(postgres_container: PostgresContainer) -> AsyncGenerator[AsyncEngine, None]:
    """Создаёт схему приложения в тестовом PostgreSQL.

    Движок создаётся на каждый тест: asyncpg привязывает соединения к event
    loop, а pytest-asyncio даёт каждому тесту свой цикл. Контейнер при этом
    остаётся общим на весь прогон, поэтому накладные расходы невелики.
    """
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


@pytest.fixture
def current_principal() -> Principal:
    """Принципал, от имени которого идут API-тесты."""
    return Principal(
        user_id=1,
        username="tester",
        last_name="Тестов",
        first_name="Тест",
        middle_name=None,
        scope=ApiTokenScope.WRITE,
        via_api_token=False,
    )


@pytest.fixture(autouse=True)
def authenticate(current_principal: Principal) -> Generator[None, None, None]:
    """Подменяет аутентификацию и разрешение доступа во всех API-тестах.

    Проверки самой авторизации живут в отдельных тестах, а остальным нужно
    проверять поведение эндпоинтов, а не стену входа.
    """
    grant = AccessGrant(project_id=1, resource_id=1, is_owner=True)
    app.dependency_overrides.update(
        {
            get_principal: lambda: current_principal,
            require_project_access: lambda: grant,
            require_project_ownership: lambda: grant,
            require_task_access: lambda: grant,
            require_stage_access: lambda: grant,
            require_document_access: lambda: grant,
            require_comment_access: lambda: grant,
            require_link_access: lambda: grant,
        }
    )
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

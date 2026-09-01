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
from src.db.models.documents import Document
from src.db.models.project_stages import ProjectStage
from src.db.models.projects import Project
from src.db.models.task_comments import TaskComment
from src.db.models.tasks import Task
from src.db.models.users import User
from src.dependencies.access import (
    get_accessible_comment,
    get_accessible_document,
    get_accessible_link,
    get_accessible_project,
    get_accessible_stage,
    get_accessible_task,
    get_owned_project,
)
from src.dependencies.auth import get_current_user


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
def current_user() -> User:
    """Пользователь, от имени которого идут API-тесты."""
    return User(
        id=1,
        username="tester",
        password_hash="hash",
        last_name="Тестов",
        first_name="Тест",
        is_active=True,
    )


@pytest.fixture(autouse=True)
def authenticate(current_user: User) -> Generator[None, None, None]:
    """Подменяет сессию и разрешение доступа во всех API-тестах.

    Проверки самой авторизации живут в отдельных тестах, а остальным нужно
    проверять поведение эндпоинтов, а не стену входа.
    """
    project = Project(id=1, owner_id=current_user.id, key="TEST", name="Тест", color="#58a6ff")
    app.dependency_overrides.update(
        {
            get_current_user: lambda: current_user,
            get_accessible_project: lambda: project,
            get_owned_project: lambda: project,
            get_accessible_task: lambda: Task(id=1, project_id=project.id),
            get_accessible_stage: lambda: ProjectStage(id=1, project_id=project.id),
            get_accessible_document: lambda: Document(id=1, project_id=project.id),
            get_accessible_comment: lambda: TaskComment(id=1, task_id=1),
            get_accessible_link: lambda: None,
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

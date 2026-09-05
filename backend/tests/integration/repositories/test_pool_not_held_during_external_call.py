"""Пул соединений остаётся доступным во время внешнего вызова.

Это проверка ресурсного инварианта, а не логики. Она берёт заведомо
маленький пул, запускает столько AI-сценариев, сколько в нём соединений,
и, пока все они «ждут модель», выполняет обычный запрос к базе.

Со старой схемой — request-scoped сессия на весь сценарий — обычный
запрос не получил бы соединения и упал бы по таймауту пула. С короткими
областями он проходит.
"""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from src.clients.llm import LlmClient
from src.db.models import Base
from src.db.models.projects import Project
from src.repositories.project_stages import ProjectStagesRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.task_activity import TaskActivityRepository
from src.repositories.tasks import TasksRepository
from src.repositories.unit_of_work import UnitOfWork
from src.repositories.wbs_nodes import WbsNodesRepository
from src.schemas.wbs_suggestion import WbsSuggestionSchema
from src.services.db_scope import WbsSuggestionScope
from src.services.knowledge_events import KnowledgeEvents
from src.services.wbs_suggestion import WbsSuggestionService

POOL_SIZE = 2
CONCURRENT_SCENARIOS = POOL_SIZE
POOL_TIMEOUT_SECONDS = 3.0


@pytest.fixture
async def small_pool_engine(postgres_container: PostgresContainer):
    """Движок с заведомо маленьким пулом и коротким ожиданием.

    Маленький пул делает проблему наблюдаемой: удержание соединения на
    время внешнего вызова исчерпает его за два запроса.
    """
    url = postgres_container.get_connection_url().replace("psycopg2", "asyncpg")
    engine = create_async_engine(
        url,
        pool_size=POOL_SIZE,
        max_overflow=0,
        pool_timeout=POOL_TIMEOUT_SECONDS,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


def build_service(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    external_call_started: asyncio.Event,
    release_external_call: asyncio.Event,
) -> WbsSuggestionService:
    """Собирает сервис, чей внешний вызов управляется тестом."""

    @asynccontextmanager
    async def scope():
        async with session_factory() as session:
            yield WbsSuggestionScope(
                projects=ProjectsRepository(session),
                wbs_nodes=WbsNodesRepository(session),
                tasks=TasksRepository(session),
                stages=ProjectStagesRepository(session),
                activity=TaskActivityRepository(session),
                knowledge_events=KnowledgeEvents(
                    repository=AsyncMock(),
                    enabled=False,
                ),
                unit_of_work=UnitOfWork(session),
            )

    llm_client = AsyncMock(spec=LlmClient)

    async def blocked_model(**_kwargs) -> WbsSuggestionSchema:
        external_call_started.set()
        await release_external_call.wait()
        return WbsSuggestionSchema()

    llm_client.get_structured_response.side_effect = blocked_model
    return WbsSuggestionService(scope=scope, llm_client=llm_client)


async def seed_project(session_factory: async_sessionmaker[AsyncSession], marker: str) -> int:
    """Создаёт проект со стадией и задачей, чтобы сценарию было что читать.

    Контейнер общий на весь прогон, поэтому имена уникальны для каждого
    теста: иначе второй тест упал бы на ограничении уникальности.
    """
    async with session_factory() as session:
        owner = await session.scalar(
            text(
                "INSERT INTO users (username, password_hash, last_name, first_name, is_active) "
                "VALUES (:username, 'hash', 'Пулов', 'Пётр', true) RETURNING id"
            ),
            {"username": f"pool-owner-{marker}"},
        )
        project = await ProjectsRepository(session).save(
            data={
                "owner_id": owner,
                "key": f"P{marker}",
                "name": "Проект пула",
                "status": "PLANNING",
                "color": "#58a6ff",
                "order_index": 0,
            }
        )
        stage = await ProjectStagesRepository(session).save(
            data={
                "project_id": project.id,
                "name": "В работе",
                "order_index": 1,
                "color": "#58a6ff",
                "is_done_stage": False,
            }
        )
        await TasksRepository(session).save(
            data={
                "project_id": project.id,
                "stage_id": stage.id,
                "number": 1,
                "title": "Задача пула",
                "position": 1000.0,
            }
        )
        await session.commit()
        return project.id


@pytest.mark.asyncio
async def test_ordinary_query_succeeds_while_model_calls_are_in_flight(
    small_pool_engine,
) -> None:
    """Обычное чтение проходит, пока все AI-сценарии ждут модель.

    Если бы сценарий держал соединение на время внешнего вызова, пул из
    двух соединений оказался бы исчерпан и этот запрос упал бы по
    таймауту ожидания.
    """
    session_factory = async_sessionmaker(small_pool_engine, expire_on_commit=False)
    project_id = await seed_project(session_factory, marker="AA")

    started = asyncio.Event()
    release = asyncio.Event()
    service = build_service(
        session_factory,
        external_call_started=started,
        release_external_call=release,
    )

    scenarios = [
        asyncio.create_task(service.suggest(project_id=project_id))
        for _ in range(CONCURRENT_SCENARIOS)
    ]
    try:
        await asyncio.wait_for(started.wait(), timeout=POOL_TIMEOUT_SECONDS * 2)
        # Даём всем сценариям дойти до внешнего вызова.
        await asyncio.sleep(0.2)

        async with session_factory() as session:
            found = await asyncio.wait_for(
                session.scalar(select(Project.key).where(Project.id == project_id)),
                timeout=POOL_TIMEOUT_SECONDS,
            )

        assert found == "PAA", "Обычный запрос не получил соединения из пула."
    finally:
        release.set()
        await asyncio.gather(*scenarios, return_exceptions=True)


@pytest.mark.asyncio
async def test_failed_external_call_returns_the_connection(small_pool_engine) -> None:
    """Сбой внешнего вызова не оставляет соединение выведенным из пула.

    Иначе несколько отказов подряд навсегда лишили бы приложение пула.
    """
    session_factory = async_sessionmaker(small_pool_engine, expire_on_commit=False)
    project_id = await seed_project(session_factory, marker="BB")

    service = build_service(
        session_factory,
        external_call_started=asyncio.Event(),
        release_external_call=asyncio.Event(),
    )
    service.llm_client.get_structured_response.side_effect = RuntimeError("модель упала")

    for _ in range(POOL_SIZE + 2):
        with pytest.raises(Exception):  # noqa: B017 - важен сам факт отказа
            await service.suggest(project_id=project_id)

    async with session_factory() as session:
        found = await asyncio.wait_for(
            session.scalar(select(Project.key).where(Project.id == project_id)),
            timeout=POOL_TIMEOUT_SECONDS,
        )

    assert found == "PBB", "После серии отказов пул остался исчерпанным."

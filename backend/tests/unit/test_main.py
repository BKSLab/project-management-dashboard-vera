"""Проверки composition root: создание и освобождение ресурсов приложения."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI

import src.main as main_module
from src.core.app_state import RUNTIME_STATE_KEY, SETTINGS_STATE_KEY
from src.exceptions.clients import VectorStoreClientError


@pytest.fixture
def composition(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Подменяет тяжёлые ресурсы и возвращает наблюдаемые за ними дублёры."""
    db_session = object()

    @asynccontextmanager
    async def session_factory():
        yield db_session

    http_client = object()
    qdrant_sdk = object()
    runtime = SimpleNamespace(
        qdrant_client=SimpleNamespace(backfill_payload_indexes=AsyncMock()),
    )
    created = SimpleNamespace(http=0, qdrant=0, runtime=0)

    def create_http_client(settings):
        created.http += 1
        return http_client

    def create_qdrant_client(settings):
        created.qdrant += 1
        return qdrant_sdk

    def build_runtime(*, settings, http_client, qdrant_client):
        created.runtime += 1
        return runtime

    settings = SimpleNamespace(
        app=SimpleNamespace(app_name="Test app", mcp_path="/mcp"),
        knowledge=SimpleNamespace(knowledge_enabled=True),
    )
    close_runtime = AsyncMock()
    dispose_engine = AsyncMock()
    check_db = AsyncMock()
    worker_started = asyncio.Event()
    worker_built = SimpleNamespace(session_factory=None, settings=None, runtime=None)

    class FakeWorker:
        """Индексатор, собранный composition root-ом приложения."""

        async def run(self, stop_event: asyncio.Event) -> None:
            worker_started.set()
            await stop_event.wait()

    def build_worker(*, session_factory, settings, runtime):
        worker_built.session_factory = session_factory
        worker_built.settings = settings
        worker_built.runtime = runtime
        return FakeWorker()

    monkeypatch.setattr(main_module, "async_session_factory", session_factory)
    monkeypatch.setattr(main_module, "check_db_connection", check_db)
    monkeypatch.setattr(main_module, "create_http_client", create_http_client)
    monkeypatch.setattr(main_module, "create_qdrant_client", create_qdrant_client)
    monkeypatch.setattr(main_module, "build_knowledge_runtime", build_runtime)
    monkeypatch.setattr(main_module, "build_knowledge_worker", build_worker)
    monkeypatch.setattr(main_module, "close_knowledge_runtime", close_runtime)
    monkeypatch.setattr(main_module, "engine", SimpleNamespace(dispose=dispose_engine))
    monkeypatch.setattr(main_module, "settings", settings)

    # Настоящий session manager MCP запускается один раз на экземпляр, а
    # тестов lifespan несколько: подменяем его на новый контекст в каждом.
    @asynccontextmanager
    async def session_manager_run():
        yield

    monkeypatch.setattr(
        main_module,
        "mcp_server",
        SimpleNamespace(session_manager=SimpleNamespace(run=session_manager_run)),
    )

    return SimpleNamespace(
        db_session=db_session,
        runtime=runtime,
        settings=settings,
        created=created,
        close_runtime=close_runtime,
        dispose_engine=dispose_engine,
        check_db=check_db,
        worker_started=worker_started,
        worker_built=worker_built,
    )


async def test_lifespan_creates_and_closes_resources_exactly_once(
    composition: SimpleNamespace,
) -> None:
    """Каждый сетевой ресурс создаётся и закрывается ровно один раз."""
    async with main_module.lifespan(FastAPI()):
        await asyncio.wait_for(composition.worker_started.wait(), timeout=1)

    assert composition.created.http == 1
    assert composition.created.qdrant == 1
    assert composition.created.runtime == 1
    composition.check_db.assert_awaited_once_with(db_session=composition.db_session)
    composition.close_runtime.assert_awaited_once_with(composition.runtime)
    composition.dispose_engine.assert_awaited_once_with()


async def test_lifespan_gives_the_worker_its_dependencies_explicitly(
    composition: SimpleNamespace,
) -> None:
    """Индексатор получает ресурсы приложения, а не ищет их сам.

    Пока worker брал фабрику сессий и клиентов из модульных globals, его
    зависимости не были видны ни в сигнатуре, ни в composition root.
    """
    async with main_module.lifespan(FastAPI()):
        await asyncio.wait_for(composition.worker_started.wait(), timeout=1)

    assert composition.worker_built.runtime is composition.runtime
    assert composition.worker_built.settings is composition.settings
    assert composition.worker_built.session_factory is not None


async def test_lifespan_publishes_resources_in_request_state(
    composition: SimpleNamespace,
) -> None:
    """Ресурсы попадают в состояние запроса, доступное и MCP-транспорту."""
    async with main_module.lifespan(FastAPI()) as state:
        assert state[RUNTIME_STATE_KEY] is composition.runtime
        assert state[SETTINGS_STATE_KEY] is composition.settings


async def test_lifespan_starts_application_when_qdrant_is_unavailable(
    composition: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Недоступный Qdrant не блокирует запуск основного трекера."""
    backfill = AsyncMock(side_effect=VectorStoreClientError("Qdrant offline"))
    composition.runtime.qdrant_client.backfill_payload_indexes = backfill
    warning = Mock()
    monkeypatch.setattr(main_module.logger, "warning", warning)

    async with main_module.lifespan(FastAPI()):
        await asyncio.wait_for(composition.worker_started.wait(), timeout=1)

    backfill.assert_awaited_once_with()
    assert composition.runtime.payload_indexes_backfill_pending is True
    composition.close_runtime.assert_awaited_once_with(composition.runtime)
    warning.assert_called_once_with(
        "⚠️ Qdrant недоступен при старте; backfill payload-индексов отложен.",
        exc_info=True,
    )


async def test_lifespan_cancels_a_stuck_worker_and_still_frees_resources(
    monkeypatch: pytest.MonkeyPatch,
    composition: SimpleNamespace,
) -> None:
    """Зависший индексатор снимается, ресурсы всё равно освобождаются.

    Без отмены остановка приложения ждала бы worker неограниченно долго,
    а клиенты и пул соединений остались бы открытыми.
    """
    cancelled = asyncio.Event()

    class StuckWorker:
        """Индексатор, не реагирующий на признак остановки."""

        async def run(self, stop_event: asyncio.Event) -> None:
            composition.worker_started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

    monkeypatch.setattr(
        main_module,
        "build_knowledge_worker",
        lambda **_kwargs: StuckWorker(),
    )

    async with main_module.lifespan(FastAPI()):
        await asyncio.wait_for(composition.worker_started.wait(), timeout=1)

    assert cancelled.is_set()
    composition.close_runtime.assert_awaited_once_with(composition.runtime)
    composition.dispose_engine.assert_awaited_once_with()


async def test_lifespan_does_not_start_the_worker_when_knowledge_is_disabled(
    composition: SimpleNamespace,
) -> None:
    """С выключенной базой знаний индексатор не собирается и не запускается."""
    composition.settings.knowledge.knowledge_enabled = False

    async with main_module.lifespan(FastAPI()):
        pass

    assert composition.worker_started.is_set() is False
    assert composition.worker_built.runtime is None
    composition.dispose_engine.assert_awaited_once_with()

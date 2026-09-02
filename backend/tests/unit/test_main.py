import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI

import src.main as main_module
from src.exceptions.knowledge import KnowledgeProviderError


@pytest.mark.asyncio
async def test_lifespan_starts_application_when_qdrant_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Недоступный Qdrant не блокирует запуск основного трекера."""
    db_session = object()

    @asynccontextmanager
    async def session_factory():
        yield db_session

    backfill = AsyncMock(side_effect=KnowledgeProviderError("Qdrant offline"))
    runtime = SimpleNamespace(qdrant_client=SimpleNamespace(backfill_payload_indexes=backfill))
    check_db = AsyncMock()
    close_runtime = AsyncMock()
    dispose_engine = AsyncMock()
    warning = Mock()
    worker_started = asyncio.Event()

    async def run_worker(stop_event: asyncio.Event) -> None:
        worker_started.set()
        await stop_event.wait()

    monkeypatch.setattr(main_module, "async_session_factory", session_factory)
    monkeypatch.setattr(main_module, "check_db_connection", check_db)
    monkeypatch.setattr(main_module, "get_knowledge_runtime", lambda: runtime)
    monkeypatch.setattr(main_module, "run_knowledge_worker", run_worker)
    monkeypatch.setattr(main_module, "close_knowledge_runtime", close_runtime)
    monkeypatch.setattr(main_module, "engine", SimpleNamespace(dispose=dispose_engine))
    monkeypatch.setattr(main_module.logger, "warning", warning)
    monkeypatch.setattr(
        main_module,
        "settings",
        SimpleNamespace(
            app=SimpleNamespace(app_name="Test app", mcp_path="/mcp"),
            knowledge=SimpleNamespace(knowledge_enabled=True),
        ),
    )

    async with main_module.lifespan(FastAPI()):
        await asyncio.wait_for(worker_started.wait(), timeout=1)

    check_db.assert_awaited_once_with(db_session=db_session)
    backfill.assert_awaited_once_with()
    assert runtime.payload_indexes_backfill_pending is True
    close_runtime.assert_awaited_once_with()
    dispose_engine.assert_awaited_once_with()
    warning.assert_called_once_with(
        "⚠️ Qdrant недоступен при старте; backfill payload-индексов отложен.",
        exc_info=True,
    )

import asyncio
from contextlib import AbstractAsyncContextManager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, call

import pytest

from src.db.models.knowledge_index_jobs import KnowledgeEntityType, KnowledgeIndexOperation
from src.exceptions.knowledge import KnowledgeProviderError
from src.knowledge.worker import (
    _backfill_payload_indexes_if_pending,
    _execute_task_jobs,
    _prepare_and_execute_job,
    _prepare_and_execute_task_jobs,
    run_knowledge_worker,
)
from src.services.knowledge_index import KnowledgeIndexService, PreparedIndexAction


def job(job_id: int) -> SimpleNamespace:
    """Возвращает TASK UPSERT job для теста деления пачки."""
    return SimpleNamespace(id=job_id, project_id=1, entity_id=str(job_id), attempts=1)


def action(entity_id: int) -> PreparedIndexAction:
    """Возвращает подготовленное действие без документов для теста деления."""
    return PreparedIndexAction(
        project_id=1,
        entity_type=KnowledgeEntityType.TASK,
        operation=KnowledgeIndexOperation.UPSERT,
        entity_id=entity_id,
    )


class TrackedSessionContext(AbstractAsyncContextManager):
    """Отмечает время жизни сессии для проверки границ внешнего вызова."""

    def __init__(self, state: dict[str, bool]) -> None:
        self.state = state
        self.session = object()

    async def __aenter__(self) -> object:
        self.state["active"] = True
        return self.session

    async def __aexit__(self, *args: Any) -> None:
        self.state["active"] = False


@pytest.mark.asyncio
async def test_failed_task_batch_is_split_and_good_jobs_succeed() -> None:
    service = AsyncMock(spec=KnowledgeIndexService)

    async def fail_batch_with_bad_task(actions) -> dict[int, int]:
        entity_ids = [item.entity_id for item in actions]
        if 2 in entity_ids:
            raise RuntimeError("bad task")
        return {entity_id: 1 for entity_id in entity_ids}

    service.execute_task_upserts.side_effect = fail_batch_with_bad_task

    results = await _execute_task_jobs(
        service=service,
        jobs=[job(1), job(2), job(3)],
        actions=[action(1), action(2), action(3)],
    )

    assert service.execute_task_upserts.await_args_list == [
        call([action(1), action(2), action(3)]),
        call([action(1)]),
        call([action(2), action(3)]),
        call([action(2)]),
        call([action(3)]),
    ]
    assert [result.job.id for result in results if result.error is None] == [1, 3]
    failed = [result for result in results if result.error is not None]
    assert len(failed) == 1
    assert failed[0].job.id == 2


@pytest.mark.asyncio
async def test_single_external_call_runs_after_database_session_closed(monkeypatch) -> None:
    state = {"active": False}
    service = AsyncMock(spec=KnowledgeIndexService)
    prepared = action(1)

    async def prepare(_job) -> PreparedIndexAction:
        assert state["active"] is True
        return prepared

    async def execute_prepared(_action) -> int:
        assert state["active"] is False
        return 4

    service.prepare.side_effect = prepare
    service.execute_prepared.side_effect = execute_prepared
    monkeypatch.setattr(
        "src.knowledge.worker.async_session_factory",
        lambda: TrackedSessionContext(state),
    )
    monkeypatch.setattr(
        "src.knowledge.worker._build_index_service",
        lambda **_kwargs: service,
    )

    result = await _prepare_and_execute_job(
        job=job(1),
        settings=SimpleNamespace(),
    )

    assert result.error is None
    assert result.chunks_count == 4


@pytest.mark.asyncio
async def test_task_batch_external_call_runs_after_database_session_closed(monkeypatch) -> None:
    state = {"active": False}
    service = AsyncMock(spec=KnowledgeIndexService)
    prepared = [action(1), action(2)]

    async def prepare_task_upserts(*_args, **_kwargs) -> list[PreparedIndexAction]:
        assert state["active"] is True
        return prepared

    async def execute_task_upserts(_actions) -> dict[int, int]:
        assert state["active"] is False
        return {1: 1, 2: 1}

    service.prepare_task_upserts.side_effect = prepare_task_upserts
    service.execute_task_upserts.side_effect = execute_task_upserts
    monkeypatch.setattr(
        "src.knowledge.worker.async_session_factory",
        lambda: TrackedSessionContext(state),
    )
    monkeypatch.setattr(
        "src.knowledge.worker._build_index_service",
        lambda **_kwargs: service,
    )

    results = await _prepare_and_execute_task_jobs(
        jobs=[job(1), job(2)],
        settings=SimpleNamespace(),
    )

    assert [result.chunks_count for result in results] == [1, 1]
    assert all(result.error is None for result in results)


@pytest.mark.asyncio
async def test_pending_payload_index_backfill_stops_after_first_success() -> None:
    backfill = AsyncMock(side_effect=[KnowledgeProviderError("offline"), 2])
    runtime = SimpleNamespace(
        payload_indexes_backfill_pending=True,
        qdrant_client=SimpleNamespace(backfill_payload_indexes=backfill),
    )

    await _backfill_payload_indexes_if_pending(runtime)
    assert runtime.payload_indexes_backfill_pending is True

    await _backfill_payload_indexes_if_pending(runtime)
    assert runtime.payload_indexes_backfill_pending is False

    await _backfill_payload_indexes_if_pending(runtime)
    assert backfill.await_count == 2


@pytest.mark.asyncio
async def test_unavailable_qdrant_does_not_stop_worker_cycle(monkeypatch) -> None:
    stop_event = asyncio.Event()
    backfill = AsyncMock(side_effect=KnowledgeProviderError("offline"))
    runtime = SimpleNamespace(
        payload_indexes_backfill_pending=True,
        qdrant_client=SimpleNamespace(backfill_payload_indexes=backfill),
    )
    maintain_queue = AsyncMock()
    process_next = AsyncMock()

    async def process_then_stop() -> bool:
        stop_event.set()
        return True

    process_next.side_effect = process_then_stop
    settings = SimpleNamespace(
        knowledge=SimpleNamespace(knowledge_index_poll_seconds=0.01),
    )
    monkeypatch.setattr("src.knowledge.worker.get_settings", lambda: settings)
    monkeypatch.setattr("src.knowledge.worker.get_knowledge_runtime", lambda: runtime)
    monkeypatch.setattr("src.knowledge.worker._maintain_queue", maintain_queue)
    monkeypatch.setattr("src.knowledge.worker._process_next", process_next)

    await run_knowledge_worker(stop_event)

    backfill.assert_awaited_once_with()
    process_next.assert_awaited_once_with()
    assert runtime.payload_indexes_backfill_pending is True

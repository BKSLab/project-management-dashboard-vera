"""Проверки цикла фонового индексатора знаний.

Worker получает конфигурацию, очередь, фабрику индексатора и клиентов
конструктором, поэтому здесь ничего не подменяется через модульные
globals: дублёры передаются так же, как в приложении передаются
настоящие зависимости.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest

from src.db.models.knowledge_index_jobs import KnowledgeEntityType, KnowledgeIndexOperation
from src.exceptions.clients import VectorStoreClientError
from src.knowledge.worker import KnowledgeWorker, WorkerConfig
from src.services.knowledge_index import KnowledgeIndexService, PreparedIndexAction
from src.services.knowledge_queue import JobOutcome, KnowledgeQueueService

CONFIG = WorkerConfig(
    poll_seconds=0.01,
    batch_size=8,
    max_attempts=3,
    retention=timedelta(days=7),
    cleanup_interval_seconds=3600,
)


def job(
    job_id: int,
    *,
    entity_type: KnowledgeEntityType = KnowledgeEntityType.TASK,
    operation: KnowledgeIndexOperation = KnowledgeIndexOperation.UPSERT,
) -> SimpleNamespace:
    """Задание очереди в том виде, в каком его отдаёт сервис очереди."""
    return SimpleNamespace(
        id=job_id,
        project_id=1,
        entity_id=str(job_id),
        entity_type=entity_type,
        operation=operation,
        attempts=1,
    )


def action(entity_id: int) -> PreparedIndexAction:
    """Подготовленное действие индексации без документов."""
    return PreparedIndexAction(
        project_id=1,
        entity_type=KnowledgeEntityType.TASK,
        operation=KnowledgeIndexOperation.UPSERT,
        entity_id=entity_id,
    )


class ScopeTracker:
    """Фабрика индексатора, помнящая, открыта ли сейчас DB-область."""

    def __init__(self, service: KnowledgeIndexService) -> None:
        self.service = service
        self.active = False
        self.opened = 0

    @asynccontextmanager
    async def __call__(self):
        self.active = True
        self.opened += 1
        try:
            yield self.service
        finally:
            self.active = False


def make_worker(
    *,
    service: KnowledgeIndexService | None = None,
    queue: KnowledgeQueueService | None = None,
    runtime: object | None = None,
    config: WorkerConfig = CONFIG,
) -> tuple[KnowledgeWorker, ScopeTracker]:
    """Собирает worker с наблюдаемыми зависимостями."""
    tracker = ScopeTracker(service or AsyncMock(spec=KnowledgeIndexService))
    worker = KnowledgeWorker(
        config=config,
        queue=queue or AsyncMock(spec=KnowledgeQueueService),
        index_service=tracker,
        runtime=runtime
        or SimpleNamespace(
            payload_indexes_backfill_pending=False,
            qdrant_client=SimpleNamespace(backfill_payload_indexes=AsyncMock()),
        ),
    )
    return worker, tracker


def test_worker_config_is_taken_from_settings_once() -> None:
    """Конфигурация цикла снимается с настроек и дальше неизменна."""
    settings = SimpleNamespace(
        knowledge=SimpleNamespace(
            knowledge_index_poll_seconds=5,
            knowledge_embedding_batch_size=16,
            knowledge_index_max_attempts=4,
            knowledge_job_retention_days=14,
        )
    )

    config = WorkerConfig.from_settings(settings)

    assert (config.poll_seconds, config.batch_size, config.max_attempts) == (5, 16, 4)
    assert config.retention == timedelta(days=14)
    with pytest.raises(AttributeError):
        config.batch_size = 1


async def test_failed_task_batch_is_split_and_good_jobs_succeed() -> None:
    """Одна плохая задача не лишает индексации остальные из пачки."""
    service = AsyncMock(spec=KnowledgeIndexService)

    async def fail_batch_with_bad_task(actions) -> dict[int, int]:
        entity_ids = [item.entity_id for item in actions]
        if 2 in entity_ids:
            raise RuntimeError("bad task")
        return {entity_id: 1 for entity_id in entity_ids}

    service.execute_task_upserts.side_effect = fail_batch_with_bad_task
    worker, _ = make_worker(service=service)

    results = await worker._execute_task_jobs(
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


async def test_single_external_call_runs_after_database_scope_closed() -> None:
    """Внешний вызов одиночного задания идёт без открытой DB-области."""
    service = AsyncMock(spec=KnowledgeIndexService)
    worker, tracker = make_worker(service=service)

    async def prepare(_job) -> PreparedIndexAction:
        assert tracker.active is True
        return action(1)

    async def execute_prepared(_action) -> int:
        assert tracker.active is False
        return 4

    service.prepare.side_effect = prepare
    service.execute_prepared.side_effect = execute_prepared

    result = await worker._prepare_and_execute_job(job(1))

    assert result.error is None
    assert result.chunks_count == 4
    assert tracker.opened == 1


async def test_task_batch_external_call_runs_after_database_scope_closed() -> None:
    """Внешний вызов TASK-пачки тоже идёт без открытой DB-области."""
    service = AsyncMock(spec=KnowledgeIndexService)
    worker, tracker = make_worker(service=service)

    async def prepare_task_upserts(*_args, **_kwargs) -> list[PreparedIndexAction]:
        assert tracker.active is True
        return [action(1), action(2)]

    async def execute_task_upserts(_actions) -> dict[int, int]:
        assert tracker.active is False
        return {1: 1, 2: 1}

    service.prepare_task_upserts.side_effect = prepare_task_upserts
    service.execute_task_upserts.side_effect = execute_task_upserts

    results = await worker._prepare_and_execute_task_jobs([job(1), job(2)])

    assert [result.chunks_count for result in results] == [1, 1]
    assert all(result.error is None for result in results)


async def test_cancellation_is_not_recorded_as_a_failed_job() -> None:
    """Остановка приложения не тратит попытку задания.

    Иначе каждый рестарт приближал бы задание к статусу FAILED, хотя
    ошибки индексации не было.
    """
    service = AsyncMock(spec=KnowledgeIndexService)
    service.prepare.side_effect = asyncio.CancelledError()
    queue = AsyncMock(spec=KnowledgeQueueService)
    worker, _ = make_worker(service=service, queue=queue)

    with pytest.raises(asyncio.CancelledError):
        await worker._prepare_and_execute_job(job(1))

    queue.finish.assert_not_awaited()


async def test_processing_persists_outcomes_through_the_queue_service() -> None:
    """Статусы пачки сохраняет сервис очереди, а не сам цикл."""
    service = AsyncMock(spec=KnowledgeIndexService)
    service.prepare_task_upserts.return_value = [action(1), action(2)]
    service.execute_task_upserts.return_value = {1: 3, 2: 5}
    queue = AsyncMock(spec=KnowledgeQueueService)
    queue.claim_next_batch.return_value = [job(1), job(2)]
    worker, _ = make_worker(service=service, queue=queue)

    assert await worker._process_next() is True

    queue.claim_next_batch.assert_awaited_once_with(limit=CONFIG.batch_size)
    outcomes, kwargs = queue.finish.await_args.args[0], queue.finish.await_args.kwargs
    assert outcomes == [
        JobOutcome(job_id=1, chunks_count=3),
        JobOutcome(job_id=2, chunks_count=5),
    ]
    assert kwargs == {"max_attempts": CONFIG.max_attempts}


async def test_failed_job_is_persisted_with_its_error_text() -> None:
    """Неуспешное задание уходит в очередь с текстом ошибки."""
    service = AsyncMock(spec=KnowledgeIndexService)
    service.prepare.side_effect = RuntimeError("документ недоступен")
    queue = AsyncMock(spec=KnowledgeQueueService)
    queue.claim_next_batch.return_value = [
        job(1, entity_type=KnowledgeEntityType.DOCUMENT)
    ]
    worker, _ = make_worker(service=service, queue=queue)

    assert await worker._process_next() is True

    outcomes = queue.finish.await_args.args[0]
    assert outcomes == [JobOutcome(job_id=1, error="документ недоступен")]


async def test_empty_queue_is_not_reported_as_processed() -> None:
    """Пустая очередь не считается обработкой и не трогает индексатор."""
    queue = AsyncMock(spec=KnowledgeQueueService)
    queue.claim_next_batch.return_value = []
    worker, tracker = make_worker(queue=queue)

    assert await worker._process_next() is False

    assert tracker.opened == 0
    queue.finish.assert_not_awaited()


async def test_startup_returns_interrupted_jobs_and_purges_old_ones() -> None:
    """При старте прерванные задания возвращаются, старые успешные удаляются."""
    stop_event = asyncio.Event()
    stop_event.set()
    queue = AsyncMock(spec=KnowledgeQueueService)
    worker, _ = make_worker(queue=queue)

    await worker.run(stop_event)

    queue.reset_interrupted.assert_awaited_once_with()
    queue.purge_succeeded.assert_awaited_once_with(retention=CONFIG.retention)


async def test_pending_payload_index_backfill_stops_after_first_success() -> None:
    """Отложенный backfill повторяется до первого успеха и больше не идёт."""
    backfill = AsyncMock(side_effect=[VectorStoreClientError("offline"), 2])
    runtime = SimpleNamespace(
        payload_indexes_backfill_pending=True,
        qdrant_client=SimpleNamespace(backfill_payload_indexes=backfill),
    )
    worker, _ = make_worker(runtime=runtime)

    await worker._backfill_payload_indexes_if_pending()
    assert runtime.payload_indexes_backfill_pending is True

    await worker._backfill_payload_indexes_if_pending()
    assert runtime.payload_indexes_backfill_pending is False

    await worker._backfill_payload_indexes_if_pending()
    assert backfill.await_count == 2


async def test_unavailable_qdrant_does_not_stop_worker_cycle() -> None:
    """Недоступный Qdrant не прерывает цикл: очередь продолжает разбираться."""
    stop_event = asyncio.Event()
    backfill = AsyncMock(side_effect=VectorStoreClientError("offline"))
    runtime = SimpleNamespace(
        payload_indexes_backfill_pending=True,
        qdrant_client=SimpleNamespace(backfill_payload_indexes=backfill),
    )
    queue = AsyncMock(spec=KnowledgeQueueService)

    async def claim_then_stop(**_kwargs):
        stop_event.set()
        return []

    queue.claim_next_batch.side_effect = claim_then_stop
    worker, _ = make_worker(queue=queue, runtime=runtime)

    await worker.run(stop_event)

    backfill.assert_awaited_once_with()
    queue.claim_next_batch.assert_awaited_once_with(limit=CONFIG.batch_size)
    assert runtime.payload_indexes_backfill_pending is True


async def test_loop_survives_a_failing_iteration() -> None:
    """Сбой одной итерации логируется, но не выносит цикл наружу."""
    stop_event = asyncio.Event()
    queue = AsyncMock(spec=KnowledgeQueueService)
    attempts = {"count": 0}

    async def fail_then_stop(**_kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("очередь недоступна")
        stop_event.set()
        return []

    queue.claim_next_batch.side_effect = fail_then_stop
    worker, _ = make_worker(queue=queue)

    await worker.run(stop_event)

    assert attempts["count"] == 2

"""Очередь ограничивает конкурентность и отменяет все активные ответы."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.agent.worker import AgentWorker
from src.services.agent_conversations import AgentConversationsService


async def test_worker_recovers_after_queue_error_and_limits_parallel_answers():
    service = AsyncMock(spec=AgentConversationsService)
    release, occupied, finished, stop = (asyncio.Event() for _ in range(4))
    calls = active = maximum = processed = claimed = 0

    async def process():
        nonlocal calls, active, maximum, processed, claimed
        calls += 1
        if calls == 1:
            raise RuntimeError("БД временно недоступна")
        if claimed == 4:
            return False
        claimed += 1
        active += 1
        maximum = max(maximum, active)
        if active == 2:
            occupied.set()
        try:
            await release.wait()
            processed += 1
            if processed == 4:
                finished.set()
            return True
        finally:
            active -= 1

    service.process_next.side_effect = process
    worker = AgentWorker(service=service, poll_seconds=0.01, concurrency=2)
    task = asyncio.create_task(worker.run(stop))
    try:
        await asyncio.wait_for(occupied.wait(), timeout=2)
        assert active == 2 and claimed == 2
        release.set()
        await asyncio.wait_for(finished.wait(), timeout=2)
    finally:
        release.set()
        stop.set()
        await asyncio.wait_for(task, timeout=2)
    assert processed == 4 and maximum == 2 and active == 0


async def test_cancelling_worker_waits_for_all_running_answers_to_stop():
    service = AsyncMock(spec=AgentConversationsService)
    occupied, stop = asyncio.Event(), asyncio.Event()
    active = cancelled = 0

    async def process():
        nonlocal active, cancelled
        active += 1
        if active == 2:
            occupied.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled += 1
            raise
        finally:
            active -= 1

    service.process_next.side_effect = process
    worker = AgentWorker(service=service, poll_seconds=0.01, concurrency=2)
    task = asyncio.create_task(worker.run(stop))
    try:
        await asyncio.wait_for(occupied.wait(), timeout=2)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, timeout=2)
    assert cancelled == 2 and active == 0

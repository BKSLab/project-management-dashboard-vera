"""Однозапросные операции очереди индексации."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.db.models.knowledge_index_jobs import KnowledgeEntityType, KnowledgeIndexOperation
from src.repositories.knowledge_index_jobs import KnowledgeIndexJobsRepository


@pytest.mark.asyncio
async def test_add_many_writes_the_batch_in_one_statement_without_commit() -> None:
    """Пачка пишется одним запросом внутри чужой транзакции, пустая пачка не трогает базу."""
    # Задания попадают в текущую транзакцию, но не фиксируются отдельно. Outbox обязан оказаться в базе тем же commit, что и бизнес-факт: иначе задание индексации может пережить откат породившего его изменения.
    session = MagicMock()
    session.add_all = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    repository = KnowledgeIndexJobsRepository(session)

    jobs = await repository.add_many(
        project_id=1,
        entity_type=KnowledgeEntityType.TASK,
        operation=KnowledgeIndexOperation.UPSERT,
        entity_ids=["7", "8"],
    )

    assert [job.entity_id for job in jobs] == ["7", "8"]
    session.add_all.assert_called_once()
    session.flush.assert_awaited_once()
    session.commit.assert_not_awaited()
    # Пачка вставляется одной операцией, а не построчно.
    session = MagicMock()
    session.add_all = MagicMock()
    session.flush = AsyncMock()
    repository = KnowledgeIndexJobsRepository(session)

    await repository.add_many(
        project_id=1,
        entity_type=KnowledgeEntityType.TASK,
        operation=KnowledgeIndexOperation.UPSERT,
        entity_ids=[str(index) for index in range(10)],
    )

    assert session.add_all.call_count == 1
    assert session.flush.await_count == 1
    # Пустой набор не порождает ни одного обращения к базе.
    session = MagicMock()
    session.add_all = MagicMock()
    session.flush = AsyncMock()
    repository = KnowledgeIndexJobsRepository(session)

    assert (
        await repository.add_many(
            project_id=1,
            entity_type=KnowledgeEntityType.TASK,
            operation=KnowledgeIndexOperation.UPSERT,
            entity_ids=[],
        )
        == []
    )
    session.add_all.assert_not_called()
    session.flush.assert_not_awaited()

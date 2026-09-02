from unittest.mock import AsyncMock, MagicMock

import pytest

from src.db.models.knowledge_index_jobs import KnowledgeEntityType, KnowledgeIndexOperation
from src.repositories.knowledge_index_jobs import KnowledgeIndexJobsRepository


@pytest.mark.asyncio
async def test_enqueue_flushes_without_committing_transaction() -> None:
    session = MagicMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.commit = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = None
    session.execute.return_value = result
    repository = KnowledgeIndexJobsRepository(session)

    job = await repository.enqueue(
        project_id=1,
        entity_type=KnowledgeEntityType.TASK,
        operation=KnowledgeIndexOperation.UPSERT,
        entity_id=7,
    )

    assert job.entity_id == "7"
    session.flush.assert_awaited_once()
    session.refresh.assert_awaited_once_with(job)
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_enqueue_many_deduplicates_ids_inside_batch() -> None:
    repository = KnowledgeIndexJobsRepository(MagicMock())
    repository.enqueue = AsyncMock(side_effect=[MagicMock(id=1), MagicMock(id=2)])

    jobs = await repository.enqueue_many(
        project_id=1,
        entity_type=KnowledgeEntityType.TASK,
        operation=KnowledgeIndexOperation.UPSERT,
        entity_ids=[7, 7, 8],
    )

    assert [job.id for job in jobs] == [1, 2]
    assert [call.kwargs["entity_id"] for call in repository.enqueue.await_args_list] == [7, 8]

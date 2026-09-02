from unittest.mock import AsyncMock

import pytest

from src.db.models.knowledge_index_jobs import KnowledgeEntityType
from src.exceptions.knowledge import KnowledgeEventsServiceError, KnowledgeIndexJobsRepositoryError
from src.services.knowledge_events import KnowledgeEvents


@pytest.mark.asyncio
async def test_event_queue_failure_is_propagated() -> None:
    repository = AsyncMock()
    repository.enqueue.side_effect = KnowledgeIndexJobsRepositoryError("database unavailable")
    events = KnowledgeEvents(repository=repository)

    with pytest.raises(KnowledgeEventsServiceError):
        await events.upsert(
            project_id=7,
            entity_type=KnowledgeEntityType.TASK,
            entity_id=42,
        )

    repository.enqueue.assert_awaited_once()


@pytest.mark.asyncio
async def test_disabled_events_do_not_touch_queue() -> None:
    repository = AsyncMock()
    events = KnowledgeEvents(repository=repository, enabled=False)

    await events.reindex_project(7)

    repository.enqueue.assert_not_called()

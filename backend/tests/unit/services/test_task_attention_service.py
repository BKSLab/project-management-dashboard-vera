from datetime import date
from unittest.mock import AsyncMock

import pytest

from src.exceptions.task_attention import TaskAttentionVersionError
from src.repositories.task_attention import TaskAttentionRepository
from src.repositories.unit_of_work import UnitOfWork
from src.schemas.task_attention import TaskViewSchema
from src.services.task_attention import TaskAttentionService, attention_item


def row(**overrides):
    return (
        dict(
            task_id=1,
            revision=5,
            deadline_revision=2,
            due_date=date(2026, 10, 9),
            closed=False,
            seen_revision=5,
            seen_deadline_revision=0,
        )
        | overrides
    )


def test_view_before_deadline_does_not_acknowledge_future_breach():
    item = attention_item(row(), date(2026, 10, 9))
    assert not item.is_overdue
    item = attention_item(row(), date(2026, 10, 10))
    assert item.is_overdue
    assert not item.is_updated
    assert not attention_item(row(seen_deadline_revision=2), date(2026, 10, 10)).is_overdue


def test_closed_and_missing_deadline_do_not_count():
    assert not attention_item(row(closed=True), date(2026, 10, 10)).is_overdue
    assert not attention_item(row(due_date=None), date(2026, 10, 10)).is_overdue


@pytest.mark.asyncio
async def test_future_view_does_not_write_state():
    repository = AsyncMock(spec=TaskAttentionRepository)
    repository.get_rows.return_value = [row()]
    uow = AsyncMock(spec=UnitOfWork)
    service = TaskAttentionService(repository, uow)
    with pytest.raises(TaskAttentionVersionError):
        await service.mark_viewed(
            1, 1, TaskViewSchema(revision=6, deadline_revision=2, overdue=False)
        )
    repository.mark_viewed.assert_not_called()
    uow.commit.assert_not_called()

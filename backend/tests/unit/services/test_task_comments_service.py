from unittest.mock import AsyncMock

import pytest

from src.exceptions.task_comments import (
    TaskCommentNotFoundError,
    TaskCommentsRepositoryError,
    TaskCommentsServiceError,
)
from src.exceptions.tasks import TaskNotFoundError
from src.repositories.task_activity import TaskActivityRepository
from src.repositories.task_comments import TaskCommentsRepository
from src.repositories.tasks import TasksRepository
from src.services.task_comments import TaskCommentsService


@pytest.mark.asyncio
async def test_add_comment_when_task_missing_raises_not_found() -> None:
    comments_repository = AsyncMock(spec=TaskCommentsRepository)
    tasks_repository = AsyncMock(spec=TasksRepository)
    activity_repository = AsyncMock(spec=TaskActivityRepository)
    tasks_repository.get_by_id.return_value = None
    service = TaskCommentsService(
        comments_repository=comments_repository,
        tasks_repository=tasks_repository,
        activity_repository=activity_repository,
    )

    with pytest.raises(TaskNotFoundError) as exc_info:
        await service.add_comment(task_id=999, author_name=None, body_md="Текст")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_comments_wraps_repository_error() -> None:
    comments_repository = AsyncMock(spec=TaskCommentsRepository)
    comments_repository.get_for_task.side_effect = TaskCommentsRepositoryError("БД недоступна")
    tasks_repository = AsyncMock(spec=TasksRepository)
    tasks_repository.get_by_id.return_value = object()
    service = TaskCommentsService(
        comments_repository=comments_repository,
        tasks_repository=tasks_repository,
        activity_repository=AsyncMock(spec=TaskActivityRepository),
    )

    with pytest.raises(TaskCommentsServiceError) as exc_info:
        await service.get_comments(task_id=1)

    assert exc_info.value.status_code == 500
    comments_repository.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_comment_when_missing_raises_not_found() -> None:
    comments_repository = AsyncMock(spec=TaskCommentsRepository)
    comments_repository.get_by_id.return_value = None
    service = TaskCommentsService(
        comments_repository=comments_repository,
        tasks_repository=AsyncMock(spec=TasksRepository),
        activity_repository=AsyncMock(spec=TaskActivityRepository),
    )

    with pytest.raises(TaskCommentNotFoundError) as exc_info:
        await service.delete_comment(comment_id=999)

    assert exc_info.value.status_code == 404

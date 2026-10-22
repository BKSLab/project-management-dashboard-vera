"""Две PostgreSQL транзакции не публикуют две версии по одной прочитанной ревизии."""

import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.api_tokens import ApiTokenScope
from src.db.models.tasks import Task
from src.db.models.users import User
from src.exceptions.task_reports import TaskReportConflictError
from src.repositories.task_comments import TaskCommentsRepository
from src.repositories.task_reports import TaskReportsRepository
from src.repositories.tasks import TasksRepository
from src.repositories.unit_of_work import UnitOfWork
from src.schemas.enums import TaskStatus
from src.schemas.task_reports import TaskReportSchema
from src.services.access import AccessGrant, AccessService
from src.services.auth import Principal
from src.services.task_reports import TaskReportsService


@pytest.mark.asyncio
@pytest.mark.parametrize("expected_revision", [0, 1])
async def test_concurrent_publication_commits_one_revision(engine, expected_revision):
    """Проверяет первую и последующую публикации с настоящим row lock и rollback."""
    async with AsyncSession(engine, expire_on_commit=False) as seed:
        user = User(username="race." + uuid4().hex, password_hash="test", last_name="Автор", first_name="Тест")
        seed.add(user)
        await seed.flush()
        task = Task(number=100003, title="Конкурентный отчёт", status=TaskStatus.NEW)
        seed.add(task)
        await seed.flush()
        task_id, user_id = task.id, user.id
        if expected_revision:
            await TaskReportsRepository(seed).append(
                {
                    "task_id": task_id,
                    "revision": 1,
                    "body_md": "Прежний результат",
                    "author_id": user_id,
                    "author_name": "Автор",
                }
            )
        await seed.commit()

    actor = Principal(
        user_id=user_id, username=user.username, last_name="Автор", first_name="Тест", middle_name=None, scope=ApiTokenScope.WRITE, via_api_token=False
    )
    barrier = asyncio.Barrier(2)

    async def publish(body):
        async with AsyncSession(engine, expire_on_commit=False) as session:
            access = AsyncMock(spec=AccessService)

            async def authorize(**kwargs):
                assert kwargs == {"task_id": task_id, "user_id": user_id}
                await asyncio.wait_for(barrier.wait(), timeout=5)
                return AccessGrant(None, task_id, True)

            access.ensure_task_access.side_effect = authorize
            service = TaskReportsService(
                TaskReportsRepository(session),
                TasksRepository(session),
                TaskCommentsRepository(session),
                access,
                UnitOfWork(session),
            )
            return await service.publish(task_id, actor, expected_revision, body)

    try:
        results = await asyncio.wait_for(
            asyncio.gather(publish("Результат А"), publish("Результат Б"), return_exceptions=True),
            timeout=15,
        )
        saved = [item for item in results if isinstance(item, TaskReportSchema)]
        conflicts = [item for item in results if isinstance(item, TaskReportConflictError)]
        assert len(saved) == len(conflicts) == 1, results
        assert saved[0].revision == expected_revision + 1
        assert conflicts[0].status_code == 409
        async with AsyncSession(engine) as check:
            history = await TaskReportsRepository(check).history(task_id)
            assert len(history) == expected_revision + 1
            assert history[0].body_md == saved[0].body_md
            assert history[0].revision == expected_revision + 1
            if expected_revision:
                assert history[1].body_md == "Прежний результат"
    finally:
        async with AsyncSession(engine) as cleanup:
            await cleanup.execute(delete(Task).where(Task.id == task_id))
            await cleanup.execute(delete(User).where(User.id == user_id))
            await cleanup.commit()

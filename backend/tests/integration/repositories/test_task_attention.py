"""Просмотры и изменения на реальном PostgreSQL, включая запоздалый ack."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import update

from src.db.models.task_comments import TaskComment
from src.db.models.task_participants import TaskParticipant, TaskParticipantRole
from src.db.models.tasks import Task
from src.db.models.users import User
from src.repositories.task_attention import TaskAttentionRepository
from src.repositories.unit_of_work import UnitOfWork
from src.schemas.enums import TaskStatus
from src.schemas.task_attention import TaskViewSchema
from src.services.task_attention import TaskAttentionService


async def add_user(session, username):
    user = User(username=username, password_hash="test", last_name=username, first_name="Тест", is_active=True)
    session.add(user)
    await session.flush()
    return user


async def arrange(session):
    alice = await add_user(session, "attention-alice")
    bob = await add_user(session, "attention-bob")
    outsider = await add_user(session, "attention-outsider")
    task = Task(number=1, title="Просмотр", status=TaskStatus.NEW, priority="MEDIUM")
    session.add(task)
    await session.flush()
    session.add_all(
        [
            TaskParticipant(task_id=task.id, user_id=alice.id, role=TaskParticipantRole.EXECUTOR),
            TaskParticipant(task_id=task.id, user_id=bob.id, role=TaskParticipantRole.OBSERVER),
        ]
    )
    await session.flush()
    service = TaskAttentionService(TaskAttentionRepository(session), UnitOfWork(session))
    return alice, bob, outsider, task, service


@pytest.mark.asyncio
async def test_view_is_personal_and_comments_after_snapshot_are_not_lost(db_session):
    alice, bob, outsider, task, service = await arrange(db_session)
    assert (await service.snapshot(alice.id)).new_tasks == 1
    assert (await service.snapshot(bob.id)).new_tasks == 1
    assert (await service.snapshot(outsider.id)).total == 0

    before = await service.token(alice.id, task.id)
    db_session.add(
        TaskComment(task_id=task.id, author_id=bob.id, body_md="Пришло во время загрузки")
    )
    await db_session.flush()
    await service.mark_viewed(alice.id, task.id, TaskViewSchema.model_validate(before.model_dump()))
    after = await service.snapshot(alice.id)
    assert after.new_tasks == 0
    assert after.updated_tasks == 1
    assert after.total == 1
    assert (await service.snapshot(bob.id)).new_tasks == 1

    latest = await service.token(alice.id, task.id)
    await service.mark_viewed(alice.id, task.id, TaskViewSchema.model_validate(latest.model_dump()))
    await service.mark_viewed(alice.id, task.id, TaskViewSchema.model_validate(before.model_dump()))
    assert (await service.snapshot(alice.id)).total == 0


@pytest.mark.asyncio
async def test_overdue_appears_after_view_and_stays_acknowledged_until_new_breach(db_session):
    alice, bob, _, task, service = await arrange(db_session)
    today = datetime.now(UTC).date()
    await db_session.execute(update(Task).where(Task.id == task.id).values(due_date=today))
    before = await service.token(alice.id, task.id)
    assert not before.overdue
    await service.mark_viewed(alice.id, task.id, TaskViewSchema.model_validate(before.model_dump()))

    await db_session.execute(
        update(Task).where(Task.id == task.id).values(due_date=today - timedelta(days=1))
    )
    overdue = await service.token(alice.id, task.id)
    assert overdue.is_overdue
    await service.mark_viewed(
        alice.id, task.id, TaskViewSchema.model_validate(overdue.model_dump())
    )
    assert (await service.snapshot(alice.id)).overdue_tasks == 0
    assert (await service.snapshot(bob.id)).overdue_tasks == 1

    db_session.add(TaskComment(task_id=task.id, author_id=bob.id, body_md="Новый комментарий"))
    await db_session.flush()
    state = await service.snapshot(alice.id)
    assert state.updated_tasks == 1
    assert state.overdue_tasks == 0

    await db_session.execute(update(Task).where(Task.id == task.id).values(status=TaskStatus.DONE))
    assert (await service.snapshot(alice.id)).overdue_tasks == 0
    await db_session.execute(
        update(Task).where(Task.id == task.id).values(status=TaskStatus.IN_PROGRESS)
    )
    assert (await service.snapshot(alice.id)).overdue_tasks == 1


@pytest.mark.asyncio
async def test_total_deduplicates_categories_and_noop_order_does_not_create_update(db_session):
    alice, _, _, task, service = await arrange(db_session)
    await db_session.execute(
        update(Task)
        .where(Task.id == task.id)
        .values(due_date=datetime.now(UTC).date() - timedelta(days=1))
    )
    state = await service.snapshot(alice.id)
    assert state.new_tasks == state.overdue_tasks == state.total == 1
    token = await service.token(alice.id, task.id)
    await service.mark_viewed(alice.id, task.id, TaskViewSchema.model_validate(token.model_dump()))
    await db_session.execute(update(Task).where(Task.id == task.id).values(position=1234))
    assert (await service.snapshot(alice.id)).total == 0
    await db_session.execute(
        update(Task).where(Task.id == task.id).values(title="Изменённое название")
    )
    assert (await service.snapshot(alice.id)).updated_tasks == 1


@pytest.mark.asyncio
async def test_more_than_500_tasks_and_removed_participant(db_session):
    alice, _, _, task, service = await arrange(db_session)
    tasks = [
        Task(number=i, title=f"Задача {i}", status=TaskStatus.NEW, priority="MEDIUM")
        for i in range(2, 503)
    ]
    db_session.add_all(tasks)
    await db_session.flush()
    db_session.add_all(
        [
            TaskParticipant(task_id=item.id, user_id=alice.id, role=TaskParticipantRole.OBSERVER)
            for item in tasks
        ]
    )
    await db_session.flush()
    assert (await service.snapshot(alice.id)).total == 502
    from src.repositories.tasks import TasksRepository

    selected = await TasksRepository(db_session).get_for_person(
        user_id=alice.id,
        roles={TaskParticipantRole.EXECUTOR, TaskParticipantRole.OBSERVER},
        include_closed=True,
        limit=1,
        attention_task_ids={task.id},
    )
    assert [item.id for item in selected] == [task.id]
    from sqlalchemy import delete

    await db_session.execute(
        delete(TaskParticipant).where(
            TaskParticipant.task_id == task.id, TaskParticipant.user_id == alice.id
        )
    )
    assert (await service.snapshot(alice.id)).total == 501

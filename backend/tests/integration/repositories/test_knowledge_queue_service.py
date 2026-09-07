"""Очередь индексации на настоящем PostgreSQL: статусы, повторы, захват.

Сервис очереди открывает собственные короткие сессии, поэтому обычная
фикстура `db_session` с внешним rollback здесь не годится: проверять
нужно то, что реально зафиксировано в базе. Тест работает через отдельную
фабрику сессий над тем же контейнером.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from src.db.models import Base
from src.db.models.knowledge_index_jobs import (
    KnowledgeEntityType,
    KnowledgeIndexJob,
    KnowledgeIndexOperation,
    KnowledgeIndexStatus,
)
from src.db.models.projects import Project
from src.db.models.users import User
from src.knowledge.composition import build_knowledge_queue_scope
from src.services.knowledge_queue import JobOutcome, KnowledgeQueueService

MAX_ATTEMPTS = 3


@pytest.fixture
async def session_factory(postgres_container: PostgresContainer):
    """Фабрика сессий над тестовым PostgreSQL с готовой схемой."""
    url = postgres_container.get_connection_url().replace("psycopg2", "asyncpg")
    engine = create_async_engine(url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def project_id(session_factory) -> int:
    """Проект очереди с уникальным ключом.

    Контейнер общий на весь прогон, поэтому данные тестов не должны
    пересекаться по уникальным полям.
    """
    marker = datetime.now(UTC).strftime("%H%M%S%f")
    async with session_factory() as session:
        user = User(
            username=f"queue-{marker}",
            password_hash="hash",
            last_name="Очередь",
            first_name="Тест",
            is_active=True,
        )
        session.add(user)
        await session.flush()
        project = Project(
            owner_id=user.id,
            key=f"Q{marker[-6:]}",
            name="Очередь индексации",
            color="#58a6ff",
        )
        session.add(project)
        await session.flush()
        # Автоматический outbox создания проверяется отдельно; здесь тестируется lifecycle.
        await session.execute(
            delete(KnowledgeIndexJob).where(KnowledgeIndexJob.project_id == project.id)
        )
        await session.commit()
        saved_project_id = project.id
        saved_user_id = user.id
    yield saved_project_id
    async with session_factory() as session:
        await session.execute(delete(Project).where(Project.id == saved_project_id))
        await session.execute(
            delete(KnowledgeIndexJob).where(KnowledgeIndexJob.project_id == saved_project_id)
        )
        await session.execute(delete(User).where(User.id == saved_user_id))
        await session.commit()


async def enqueue(session_factory, *, project_id: int, entity_ids: list[str]) -> list[int]:
    """Ставит TASK UPSERT задания и возвращает их идентификаторы."""
    async with session_factory() as session:
        jobs = [
            KnowledgeIndexJob(
                project_id=project_id,
                entity_type=KnowledgeEntityType.TASK,
                entity_id=entity_id,
                operation=KnowledgeIndexOperation.UPSERT,
                status=KnowledgeIndexStatus.PENDING,
                available_at=datetime.now(UTC),
            )
            for entity_id in entity_ids
        ]
        session.add_all(jobs)
        await session.commit()
        return [job.id for job in jobs]


async def load(session_factory, job_id: int) -> KnowledgeIndexJob:
    """Читает задание из базы новой сессией."""
    async with session_factory() as session:
        return await session.get(KnowledgeIndexJob, job_id)


def make_queue(session_factory) -> KnowledgeQueueService:
    """Сервис очереди с продовой сборкой короткой области."""
    return KnowledgeQueueService(scope=build_knowledge_queue_scope(session_factory))


async def test_claim_moves_job_to_processing_and_counts_attempt(
    session_factory,
    project_id: int,
) -> None:
    """Захват переводит задание в PROCESSING и тратит попытку."""
    (job_id,) = await enqueue(session_factory, project_id=project_id, entity_ids=["1"])
    queue = make_queue(session_factory)

    claimed = await queue.claim_next_batch(limit=8)

    assert [job.id for job in claimed] == [job_id]
    stored = await load(session_factory, job_id)
    assert stored.status is KnowledgeIndexStatus.PROCESSING
    assert stored.attempts == 1


async def test_success_is_persisted_with_chunk_count(
    session_factory,
    project_id: int,
) -> None:
    """Успешное задание получает статус, время завершения и число фрагментов."""
    (job_id,) = await enqueue(session_factory, project_id=project_id, entity_ids=["1"])
    queue = make_queue(session_factory)
    await queue.claim_next_batch(limit=8)

    await queue.finish([JobOutcome(job_id=job_id, chunks_count=7)], max_attempts=MAX_ATTEMPTS)

    stored = await load(session_factory, job_id)
    assert stored.status is KnowledgeIndexStatus.SUCCEEDED
    assert stored.chunks_count == 7
    assert stored.finished_at is not None


async def test_failure_schedules_a_retry_before_attempts_are_exhausted(
    session_factory,
    project_id: int,
) -> None:
    """Неуспешное задание возвращается в очередь с отложенным сроком.

    Немедленный повтор упёрся бы в ту же недоступную зависимость, поэтому
    задание становится доступным не сразу.
    """
    (job_id,) = await enqueue(session_factory, project_id=project_id, entity_ids=["1"])
    queue = make_queue(session_factory)
    await queue.claim_next_batch(limit=8)

    await queue.finish(
        [JobOutcome(job_id=job_id, error="embedding недоступен")],
        max_attempts=MAX_ATTEMPTS,
    )

    stored = await load(session_factory, job_id)
    assert stored.status is KnowledgeIndexStatus.PENDING
    assert stored.last_error == "embedding недоступен"
    assert stored.available_at > datetime.now(UTC)


async def test_delayed_job_is_not_claimed_before_its_time(
    session_factory,
    project_id: int,
) -> None:
    """Отложенное после сбоя задание не забирается раньше срока."""
    (job_id,) = await enqueue(session_factory, project_id=project_id, entity_ids=["1"])
    queue = make_queue(session_factory)
    await queue.claim_next_batch(limit=8)
    await queue.finish([JobOutcome(job_id=job_id, error="сбой")], max_attempts=MAX_ATTEMPTS)

    assert await queue.claim_next_batch(limit=8) == []


async def test_exhausted_attempts_end_in_failed(
    session_factory,
    project_id: int,
) -> None:
    """Исчерпав попытки, задание становится окончательно неуспешным."""
    (job_id,) = await enqueue(session_factory, project_id=project_id, entity_ids=["1"])
    queue = make_queue(session_factory)

    for _ in range(MAX_ATTEMPTS):
        async with session_factory() as session:
            job = await session.get(KnowledgeIndexJob, job_id)
            job.available_at = datetime.now(UTC) - timedelta(seconds=1)
            await session.commit()
        await queue.claim_next_batch(limit=8)
        await queue.finish([JobOutcome(job_id=job_id, error="сбой")], max_attempts=MAX_ATTEMPTS)

    stored = await load(session_factory, job_id)
    assert stored.status is KnowledgeIndexStatus.FAILED
    assert stored.attempts == MAX_ATTEMPTS


async def test_concurrent_claims_never_take_the_same_job(
    session_factory,
    project_id: int,
) -> None:
    """Два одновременных захвата делят очередь, а не дублируют задания.

    Иначе один и тот же документ индексировался бы дважды, а счётчик
    попыток расходовался бы вдвое быстрее.
    """
    job_ids = await enqueue(
        session_factory,
        project_id=project_id,
        entity_ids=[str(number) for number in range(1, 5)],
    )
    queue = make_queue(session_factory)

    first, second = await asyncio.gather(
        queue.claim_next_batch(limit=2),
        queue.claim_next_batch(limit=2),
    )

    claimed = [job.id for job in first] + [job.id for job in second]
    assert len(claimed) == len(set(claimed))
    assert set(claimed) <= set(job_ids)
    assert claimed


async def test_interrupted_jobs_return_to_the_queue_on_startup(
    session_factory,
    project_id: int,
) -> None:
    """Прерванные остановкой задания снова становятся доступными."""
    (job_id,) = await enqueue(session_factory, project_id=project_id, entity_ids=["1"])
    queue = make_queue(session_factory)
    await queue.claim_next_batch(limit=8)

    reset = await queue.reset_interrupted()

    assert reset >= 1
    stored = await load(session_factory, job_id)
    assert stored.status is KnowledgeIndexStatus.PENDING


async def test_retention_removes_only_old_succeeded_jobs(
    session_factory,
    project_id: int,
) -> None:
    """Уборка трогает только давно выполненные задания."""
    old_id, fresh_id, pending_id = await enqueue(
        session_factory,
        project_id=project_id,
        entity_ids=["1", "2", "3"],
    )
    async with session_factory() as session:
        old = await session.get(KnowledgeIndexJob, old_id)
        old.status = KnowledgeIndexStatus.SUCCEEDED
        old.finished_at = datetime.now(UTC) - timedelta(days=30)
        fresh = await session.get(KnowledgeIndexJob, fresh_id)
        fresh.status = KnowledgeIndexStatus.SUCCEEDED
        fresh.finished_at = datetime.now(UTC)
        await session.commit()
    queue = make_queue(session_factory)

    deleted = await queue.purge_succeeded(retention=timedelta(days=7))

    assert deleted == 1
    async with session_factory() as session:
        remaining = set(
            (
                await session.execute(
                    select(KnowledgeIndexJob.id).where(KnowledgeIndexJob.project_id == project_id)
                )
            )
            .scalars()
            .all()
        )
    assert remaining == {fresh_id, pending_id}


async def test_queue_uses_a_fresh_session_per_operation(
    session_factory,
    project_id: int,
) -> None:
    """Между операциями очереди соединение не удерживается.

    Именно поэтому worker может ждать эмбеддинги, не занимая пул: сессия
    живёт ровно одну операцию очереди.
    """
    sessions: list[AsyncSession] = []
    scope = build_knowledge_queue_scope(session_factory)

    @asynccontextmanager
    async def tracking_scope():
        async with scope() as db:
            sessions.append(db.jobs.db_session)
            yield db

    queue = KnowledgeQueueService(scope=tracking_scope)
    await enqueue(session_factory, project_id=project_id, entity_ids=["1"])

    await queue.claim_next_batch(limit=8)
    await queue.claim_next_batch(limit=8)

    assert len(sessions) == 2
    assert sessions[0] is not sessions[1]
    assert not any(session.in_transaction() for session in sessions)


async def test_outbox_tracks_each_committed_transaction_and_rollback_is_atomic(
    session_factory, project_id
):
    async with session_factory() as session:
        record = await session.get(Project, project_id)
        record.name = "Не фиксировать"
        await session.flush()
        assert await session.scalar(
            select(KnowledgeIndexJob.id).where(KnowledgeIndexJob.project_id == project_id)
        )
        await session.rollback()
    async with session_factory() as session:
        assert (
            await session.scalar(
                select(KnowledgeIndexJob.id).where(KnowledgeIndexJob.project_id == project_id)
            )
            is None
        )
        record = await session.get(Project, project_id)
        record.name = "Первая версия"
        await session.commit()
    queue = make_queue(session_factory)
    (first,) = await queue.claim_next_batch(limit=8)
    async with session_factory() as session:
        record = await session.get(Project, project_id)
        record.name = "Вторая версия"
        await session.flush()
        record.description_md = "Ещё одно изменение в той же транзакции"
        await session.commit()
        jobs = list(
            (
                await session.execute(
                    select(KnowledgeIndexJob)
                    .where(KnowledgeIndexJob.project_id == project_id)
                    .order_by(KnowledgeIndexJob.id)
                )
            ).scalars()
        )
        assert len(jobs) == 2 and jobs[0].transaction_id != jobs[1].transaction_id
    assert await queue.claim_next_batch(limit=8) == []
    await queue.finish([JobOutcome(job_id=first.id, chunks_count=2)], max_attempts=3)
    (second,) = await queue.claim_next_batch(limit=8)
    assert second.id != first.id

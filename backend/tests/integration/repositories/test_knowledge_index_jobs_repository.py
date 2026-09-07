"""Проектная очередь: транзакционная дедупликация, объединение и исключение гонок."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from src.db.models.knowledge_index_jobs import (
    KnowledgeEntityType,
    KnowledgeIndexJob,
    KnowledgeIndexOperation,
    KnowledgeIndexStatus,
)
from src.db.models.projects import Project
from src.repositories.knowledge_index_jobs import KnowledgeIndexJobsRepository
from src.services.knowledge_events import KnowledgeEvents


async def test_queue_deduplicates_with_automatic_outbox_and_records_success(db_session, project):
    repository = KnowledgeIndexJobsRepository(db_session)
    events = KnowledgeEvents(repository=repository)
    await events.upsert(project_id=project.id, entity_type=KnowledgeEntityType.TASK, entity_id=7)
    await events.delete(
        project_id=project.id, entity_type=KnowledgeEntityType.DOCUMENT, entity_id=9
    )
    await events.reindex_project(project.id)
    assert (await repository.get_status_counts(project.id))[KnowledgeIndexStatus.PENDING] == 1
    (claimed,) = await repository.claim_next_batch(limit=10)
    assert claimed.entity_type == KnowledgeEntityType.PROJECT
    assert claimed.operation == KnowledgeIndexOperation.REINDEX_PROJECT
    assert claimed.transaction_id is not None and claimed.attempts == 1
    assert claimed.started_at and claimed.finished_at is None
    await repository.mark_succeeded(claimed.id, chunks_count=7)
    await db_session.refresh(claimed)
    assert claimed.status == KnowledgeIndexStatus.SUCCEEDED and claimed.chunks_count == 7
    assert claimed.finished_at >= claimed.started_at


async def test_failed_job_records_finish_time_and_zero_chunks(db_session, project):
    repository = KnowledgeIndexJobsRepository(db_session)
    (claimed,) = await repository.claim_next_batch(limit=10)
    await repository.mark_failed(claimed.id, "embedding unavailable", max_attempts=1)
    await db_session.refresh(claimed)
    assert claimed.status == KnowledgeIndexStatus.FAILED
    assert claimed.finished_at and claimed.chunks_count == 0


async def test_batch_coalesces_one_project_and_processing_blocks_older_ids(db_session, project):
    repository = KnowledgeIndexJobsRepository(db_session)
    first = (
        await db_session.execute(
            select(KnowledgeIndexJob).where(KnowledgeIndexJob.project_id == project.id)
        )
    ).scalar_one()
    newer = KnowledgeIndexJob(
        project_id=project.id,
        entity_type=KnowledgeEntityType.PROJECT,
        operation=KnowledgeIndexOperation.REINDEX_PROJECT,
        status=KnowledgeIndexStatus.PROCESSING,
    )
    other = KnowledgeIndexJob(
        project_id=project.id + 100,
        entity_type=KnowledgeEntityType.PROJECT,
        operation=KnowledgeIndexOperation.REINDEX_PROJECT,
        status=KnowledgeIndexStatus.PENDING,
    )
    db_session.add_all([newer, other])
    await db_session.flush()
    assert [job.id for job in await repository.claim_next_batch(limit=10)] == [other.id]
    await repository.mark_succeeded(newer.id)
    await repository.mark_succeeded(other.id)
    extra = KnowledgeIndexJob(
        project_id=project.id,
        entity_type=KnowledgeEntityType.PROJECT,
        operation=KnowledgeIndexOperation.REINDEX_PROJECT,
        status=KnowledgeIndexStatus.PENDING,
    )
    db_session.add(extra)
    await db_session.flush()
    assert [job.id for job in await repository.claim_next_batch(limit=10)] == [first.id, extra.id]
    assert await repository.claim_next_batch(limit=10) == []


@pytest.mark.asyncio
async def test_retention_deletes_only_old_succeeded_jobs(
    db_session,
    project: Project,
) -> None:
    repository = KnowledgeIndexJobsRepository(db_session)
    old_succeeded = KnowledgeIndexJob(
        project_id=project.id,
        entity_type=KnowledgeEntityType.TASK,
        entity_id="1",
        operation=KnowledgeIndexOperation.UPSERT,
        status=KnowledgeIndexStatus.SUCCEEDED,
        available_at=datetime.now(UTC),
        finished_at=datetime.now(UTC) - timedelta(days=31),
        chunks_count=1,
    )
    recent_succeeded = KnowledgeIndexJob(
        project_id=project.id,
        entity_type=KnowledgeEntityType.TASK,
        entity_id="2",
        operation=KnowledgeIndexOperation.UPSERT,
        status=KnowledgeIndexStatus.SUCCEEDED,
        available_at=datetime.now(UTC),
        finished_at=datetime.now(UTC) - timedelta(days=1),
        chunks_count=1,
    )
    old_failed = KnowledgeIndexJob(
        project_id=project.id,
        entity_type=KnowledgeEntityType.TASK,
        entity_id="3",
        operation=KnowledgeIndexOperation.UPSERT,
        status=KnowledgeIndexStatus.FAILED,
        available_at=datetime.now(UTC),
        finished_at=datetime.now(UTC) - timedelta(days=31),
        chunks_count=0,
    )
    db_session.add_all([old_succeeded, recent_succeeded, old_failed])
    await db_session.commit()

    deleted = await repository.delete_succeeded_before(datetime.now(UTC) - timedelta(days=30))
    remaining = list(
        (
            await db_session.execute(
                select(KnowledgeIndexJob).where(
                    KnowledgeIndexJob.id.in_((old_succeeded.id, recent_succeeded.id, old_failed.id))
                )
            )
        )
        .scalars()
        .all()
    )

    assert deleted == 1
    assert {job.id for job in remaining} == {recent_succeeded.id, old_failed.id}

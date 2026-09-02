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


@pytest.mark.asyncio
async def test_queue_deduplicates_and_claims_pending_job(db_session, project: Project) -> None:
    repository = KnowledgeIndexJobsRepository(db_session)

    first = await repository.enqueue(
        project_id=project.id,
        entity_type=KnowledgeEntityType.TASK,
        entity_id=42,
        operation=KnowledgeIndexOperation.UPSERT,
    )
    duplicate = await repository.enqueue(
        project_id=project.id,
        entity_type=KnowledgeEntityType.TASK,
        entity_id=42,
        operation=KnowledgeIndexOperation.UPSERT,
    )

    assert duplicate.id == first.id
    assert (await repository.get_status_counts(project.id))[KnowledgeIndexStatus.PENDING] == 1

    claimed = await repository.claim_next()

    assert claimed is not None
    assert claimed.id == first.id
    assert claimed.status is KnowledgeIndexStatus.PROCESSING
    assert claimed.attempts == 1
    assert claimed.started_at is not None
    assert claimed.finished_at is None
    assert claimed.chunks_count is None

    await repository.mark_succeeded(claimed.id, chunks_count=7)
    await db_session.refresh(claimed)

    assert claimed.finished_at is not None
    assert claimed.finished_at >= claimed.started_at
    assert claimed.chunks_count == 7
    assert (await repository.get_status_counts(project.id))[KnowledgeIndexStatus.SUCCEEDED] == 1


@pytest.mark.asyncio
async def test_failed_job_records_finish_time_and_zero_chunks(
    db_session,
    project: Project,
) -> None:
    repository = KnowledgeIndexJobsRepository(db_session)
    queued = await repository.enqueue(
        project_id=project.id,
        entity_type=KnowledgeEntityType.PROJECT,
        entity_id=project.id,
        operation=KnowledgeIndexOperation.UPSERT,
    )
    claimed = await repository.claim_next()
    assert claimed is not None

    await repository.mark_failed(claimed.id, "embedding unavailable", max_attempts=1)
    await db_session.refresh(queued)

    assert queued.status is KnowledgeIndexStatus.FAILED
    assert queued.started_at is not None
    assert queued.finished_at is not None
    assert queued.chunks_count == 0


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


@pytest.mark.asyncio
async def test_claim_batch_contains_only_task_upserts_from_same_project(
    db_session,
    project: Project,
) -> None:
    repository = KnowledgeIndexJobsRepository(db_session)
    for entity_id in (1, 2):
        await repository.enqueue(
            project_id=project.id,
            entity_type=KnowledgeEntityType.TASK,
            entity_id=entity_id,
            operation=KnowledgeIndexOperation.UPSERT,
        )
    await repository.enqueue(
        project_id=project.id,
        entity_type=KnowledgeEntityType.DOCUMENT,
        entity_id=3,
        operation=KnowledgeIndexOperation.UPSERT,
    )
    await repository.enqueue(
        project_id=project.id + 1,
        entity_type=KnowledgeEntityType.TASK,
        entity_id=4,
        operation=KnowledgeIndexOperation.UPSERT,
    )

    claimed = await repository.claim_next_batch(limit=10)

    assert [job.entity_id for job in claimed] == ["1", "2"]
    assert {job.project_id for job in claimed} == {project.id}
    assert {job.entity_type for job in claimed} == {KnowledgeEntityType.TASK}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "barrier",
    [KnowledgeIndexOperation.REINDEX_PROJECT, KnowledgeIndexOperation.DELETE_COLLECTION],
)
async def test_claim_batch_stops_before_project_barrier(
    db_session,
    project: Project,
    barrier: KnowledgeIndexOperation,
) -> None:
    repository = KnowledgeIndexJobsRepository(db_session)
    first = await repository.enqueue(
        project_id=project.id,
        entity_type=KnowledgeEntityType.TASK,
        entity_id=1,
        operation=KnowledgeIndexOperation.UPSERT,
    )
    barrier_job = await repository.enqueue(
        project_id=project.id,
        entity_type=KnowledgeEntityType.PROJECT,
        operation=barrier,
    )
    last = await repository.enqueue(
        project_id=project.id,
        entity_type=KnowledgeEntityType.TASK,
        entity_id=2,
        operation=KnowledgeIndexOperation.UPSERT,
    )

    claimed = await repository.claim_next_batch(limit=10)

    assert [job.id for job in claimed] == [first.id]
    await repository.mark_succeeded(first.id)
    assert (await repository.claim_next()).id == barrier_job.id
    await repository.mark_succeeded(barrier_job.id)
    assert (await repository.claim_next()).id == last.id

import pytest

from src.db.models.knowledge_index_jobs import (
    KnowledgeEntityType,
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

    await repository.mark_succeeded(claimed.id)
    assert (await repository.get_status_counts(project.id))[KnowledgeIndexStatus.SUCCEEDED] == 1

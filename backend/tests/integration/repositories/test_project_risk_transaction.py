from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from src.db.models.knowledge_index_jobs import (
    KnowledgeEntityType,
    KnowledgeIndexJob,
    KnowledgeIndexOperation,
)
from src.exceptions.knowledge import KnowledgeEventsServiceError
from src.exceptions.project_risks import ProjectRiskServiceError
from src.mcp_server.services import build_risks_service
from src.repositories.project_members import ProjectMembersRepository
from src.schemas.project_risks import ProjectRiskFilters
from tests.unit.services.test_project_risks_service import create_data


async def test_risk_and_outbox_are_committed_together_in_postgres(db_session, project, user):
    await ProjectMembersRepository(db_session).save(
        {"project_id": project.id, "user_id": user.id, "role": "OWNER"}
    )
    await db_session.commit()
    service = build_risks_service(
        db_session, SimpleNamespace(knowledge=SimpleNamespace(knowledge_enabled=True))
    )
    saved = await service.create_risk(
        project_id=project.id, user_id=user.id, data=create_data(owner_user_id=user.id)
    )
    assert saved.risk_level == "HIGH"
    job = (
        await db_session.execute(
            select(KnowledgeIndexJob).where(KnowledgeIndexJob.project_id == project.id)
        )
    ).scalar_one()
    assert job.entity_type == KnowledgeEntityType.RISK
    assert job.entity_id == str(saved.id)
    assert job.operation == KnowledgeIndexOperation.UPSERT


async def test_outbox_failure_rolls_back_flushed_risk_in_postgres(db_session, project, user):
    project_id = project.id
    await ProjectMembersRepository(db_session).save(
        {"project_id": project.id, "user_id": user.id, "role": "OWNER"}
    )
    await db_session.commit()
    service = build_risks_service(
        db_session, SimpleNamespace(knowledge=SimpleNamespace(knowledge_enabled=True))
    )
    service.knowledge_events.upsert = AsyncMock(
        side_effect=KnowledgeEventsServiceError("outbox unavailable")
    )
    with pytest.raises(ProjectRiskServiceError):
        await service.create_risk(project_id=project.id, user_id=user.id, data=create_data())
    assert (
        await service.risks_repository.get_count(
            project_id=project_id, filters=ProjectRiskFilters()
        )
        == 0
    )

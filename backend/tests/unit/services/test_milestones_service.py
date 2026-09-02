from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.db.models.knowledge_index_jobs import KnowledgeEntityType
from src.db.models.project_milestones import ProjectMilestoneStatus
from src.exceptions.milestones import MilestoneNotFoundError
from src.exceptions.wbs_nodes import WbsNodeForeignProjectError
from src.repositories.milestones import MilestonesRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.unit_of_work import UnitOfWork
from src.repositories.wbs_nodes import WbsNodesRepository
from src.services.knowledge_events import KnowledgeEvents
from src.services.milestones import MilestonesService


def milestone(milestone_id: int = 1, project_id: int = 1):
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=milestone_id,
        project_id=project_id,
        title="MVP",
        due_date=date(2026, 9, 30),
        status=ProjectMilestoneStatus.PLANNED,
        wbs_node_id=None,
        description_md="Публичный запуск.",
        created_at=now,
        updated_at=now,
    )


def build_service():
    milestones = AsyncMock(spec=MilestonesRepository)
    projects = AsyncMock(spec=ProjectsRepository)
    projects.get_by_id.return_value = SimpleNamespace(id=1)
    nodes = AsyncMock(spec=WbsNodesRepository)
    uow = AsyncMock(spec=UnitOfWork)
    events = AsyncMock(spec=KnowledgeEvents)
    service = MilestonesService(milestones, projects, nodes, uow, events)
    return service, milestones, projects, nodes, uow, events


@pytest.mark.asyncio
async def test_create_milestone_uses_uow_and_transactional_knowledge_event() -> None:
    service, repository, _, nodes, uow, events = build_service()
    repository.save.return_value = milestone()
    nodes.get_by_id.return_value = SimpleNamespace(id=7, project_id=1)

    result = await service.create_milestone(
        1,
        {
            "title": "MVP",
            "due_date": date(2026, 9, 30),
            "status": ProjectMilestoneStatus.PLANNED,
            "wbs_node_id": 7,
            "description_md": "Публичный запуск.",
        },
    )

    assert result.title == "MVP"
    events.upsert.assert_awaited_once_with(
        project_id=1,
        entity_type=KnowledgeEntityType.MILESTONE,
        entity_id=1,
    )
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_milestone_rejects_foreign_wbs_node() -> None:
    service, repository, _, nodes, uow, _ = build_service()
    nodes.get_by_id.return_value = SimpleNamespace(id=7, project_id=2)

    with pytest.raises(WbsNodeForeignProjectError):
        await service.create_milestone(
            1,
            {"title": "MVP", "due_date": date(2026, 9, 30), "wbs_node_id": 7},
        )

    repository.save.assert_not_awaited()
    uow.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_operational_milestone_update_does_not_reindex_text() -> None:
    service, repository, _, _, uow, events = build_service()
    current = milestone()
    repository.get_by_id.return_value = current
    current.due_date = date(2026, 10, 1)
    repository.update.return_value = current

    await service.update_milestone(1, 1, {"due_date": date(2026, 10, 1)})

    events.upsert.assert_not_awaited()
    uow.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_milestone_from_another_project_is_hidden_as_not_found() -> None:
    service, repository, _, _, _, _ = build_service()
    repository.get_by_id.return_value = milestone(project_id=2)

    with pytest.raises(MilestoneNotFoundError):
        await service.update_milestone(1, 1, {"title": "Чужая"})


@pytest.mark.asyncio
async def test_delete_milestone_enqueues_delete_and_commits() -> None:
    service, repository, _, _, uow, events = build_service()
    repository.get_by_id.return_value = milestone()

    await service.delete_milestone(1, 1)

    repository.delete.assert_awaited_once()
    events.delete.assert_awaited_once_with(
        project_id=1,
        entity_type=KnowledgeEntityType.MILESTONE,
        entity_id=1,
    )
    uow.commit.assert_awaited_once()

from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.project_milestones import ProjectMilestoneStatus
from src.db.models.project_stages import ProjectStage
from src.repositories.milestones import MilestonesRepository
from src.repositories.wbs_nodes import WbsNodesRepository


@pytest.mark.asyncio
async def test_milestone_crud_and_range_on_real_postgres(
    db_session: AsyncSession,
    stage: ProjectStage,
) -> None:
    node = await WbsNodesRepository(db_session).save(
        data={
            "project_id": stage.project_id,
            "parent_id": None,
            "title": "Release",
            "position": 1000.0,
        }
    )
    repository = MilestonesRepository(db_session)
    inside = await repository.save(
        {
            "project_id": stage.project_id,
            "title": "MVP",
            "due_date": date(2026, 9, 30),
            "status": ProjectMilestoneStatus.PLANNED,
            "wbs_node_id": node.id,
            "description_md": "Первая версия.",
        }
    )
    await repository.save(
        {
            "project_id": stage.project_id,
            "title": "Позже",
            "due_date": date(2026, 12, 1),
            "status": ProjectMilestoneStatus.PLANNED,
        }
    )

    result = await repository.get_range(
        project_id=stage.project_id,
        date_from=date(2026, 9, 1),
        date_to=date(2026, 9, 30),
    )
    inside.status = ProjectMilestoneStatus.ACHIEVED
    updated = await repository.update(inside, {"status": ProjectMilestoneStatus.ACHIEVED})

    assert [item.id for item in result] == [inside.id]
    assert updated.status is ProjectMilestoneStatus.ACHIEVED

    await repository.delete(inside)
    assert await repository.get_by_id(inside.id) is None

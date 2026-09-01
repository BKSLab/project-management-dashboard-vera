import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.project_stages import ProjectStage
from src.db.models.projects import Project
from src.db.models.wbs_nodes import WbsNode
from src.repositories.tasks import TasksRepository
from src.repositories.wbs_nodes import WbsNodesRepository


async def create_node(
    repository: WbsNodesRepository,
    project_id: int,
    title: str,
    position: float,
    parent_id: int | None = None,
) -> WbsNode:
    """Создаёт узел ИСР в указанном проекте."""
    return await repository.save(
        data={
            "project_id": project_id,
            "parent_id": parent_id,
            "title": title,
            "position": position,
        }
    )


@pytest.mark.asyncio
async def test_get_by_project_returns_nodes_in_position_order(
    db_session: AsyncSession,
    project: Project,
) -> None:
    repository = WbsNodesRepository(db_session)
    await create_node(repository, project.id, "Frontend", 2000.0)
    await create_node(repository, project.id, "Backend", 1000.0)

    nodes = await repository.get_by_project(project_id=project.id)

    assert [item.title for item in nodes] == ["Backend", "Frontend"]


@pytest.mark.asyncio
async def test_delete_node_cascades_children_and_keeps_tasks(
    db_session: AsyncSession,
    stage: ProjectStage,
) -> None:
    repository = WbsNodesRepository(db_session)
    tasks_repository = TasksRepository(db_session)
    parent = await create_node(repository, stage.project_id, "Backend", 1000.0)
    child = await create_node(repository, stage.project_id, "API", 1000.0, parent_id=parent.id)
    task = await tasks_repository.save(
        data={
            "project_id": stage.project_id,
            "stage_id": stage.id,
            "number": 1,
            "title": "Задача раздела",
            "priority": "MEDIUM",
            "position": 1000.0,
            "wbs_node_id": child.id,
        }
    )

    await tasks_repository.clear_wbs_node(node_ids={parent.id, child.id})
    await repository.delete(node=parent)

    assert await repository.get_by_project(project_id=stage.project_id) == []
    remaining = await tasks_repository.get_by_id(task_id=task.id)
    assert remaining is not None
    assert remaining.wbs_node_id is None


@pytest.mark.asyncio
async def test_update_positions_compacts_level(
    db_session: AsyncSession,
    project: Project,
) -> None:
    repository = WbsNodesRepository(db_session)
    first = await create_node(repository, project.id, "Backend", 1000.0)
    second = await create_node(repository, project.id, "Frontend", 1000.0000001)

    await repository.update_positions(positions={first.id: 1000.0, second.id: 2000.0})
    nodes = await repository.get_by_project(project_id=project.id)

    assert [item.position for item in nodes] == [1000.0, 2000.0]

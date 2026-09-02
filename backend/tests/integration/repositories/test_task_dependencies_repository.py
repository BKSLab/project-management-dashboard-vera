import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.project_stages import ProjectStage
from src.db.models.task_dependencies import TaskDependencyType
from src.exceptions.task_dependencies import TaskDependencyAlreadyExistsRepositoryError
from src.repositories.task_dependencies import TaskDependenciesRepository
from src.repositories.tasks import TasksRepository


async def make_task(
    db_session: AsyncSession,
    stage: ProjectStage,
    number: int,
):
    return await TasksRepository(db_session).save(
        {
            "project_id": stage.project_id,
            "stage_id": stage.id,
            "number": number,
            "title": f"Задача {number}",
            "position": number * 1000.0,
        }
    )


@pytest.mark.asyncio
async def test_dependency_pair_is_unique_on_real_postgres(
    db_session: AsyncSession,
    stage: ProjectStage,
) -> None:
    predecessor = await make_task(db_session, stage, 1)
    successor = await make_task(db_session, stage, 2)
    repository = TaskDependenciesRepository(db_session)
    payload = {
        "project_id": stage.project_id,
        "predecessor_task_id": predecessor.id,
        "successor_task_id": successor.id,
        "dependency_type": TaskDependencyType.FINISH_TO_START,
        "lag_days": 0,
    }
    await repository.save(payload)
    await db_session.commit()

    with pytest.raises(TaskDependencyAlreadyExistsRepositoryError):
        await repository.save(payload)


@pytest.mark.asyncio
async def test_task_deletion_cascades_dependency_on_real_postgres(
    db_session: AsyncSession,
    stage: ProjectStage,
) -> None:
    tasks = TasksRepository(db_session)
    predecessor = await make_task(db_session, stage, 1)
    successor = await make_task(db_session, stage, 2)
    repository = TaskDependenciesRepository(db_session)
    item = await repository.save(
        {
            "project_id": stage.project_id,
            "predecessor_task_id": predecessor.id,
            "successor_task_id": successor.id,
            "dependency_type": TaskDependencyType.FINISH_TO_START,
            "lag_days": 2,
        }
    )
    await db_session.commit()

    await tasks.delete(predecessor)

    assert await repository.get_by_id(item.id) is None

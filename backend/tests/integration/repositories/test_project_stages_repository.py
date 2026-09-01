import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.projects import Project
from src.exceptions.project_stages import ProjectStageNameAlreadyExistsRepositoryError
from src.repositories.project_stages import ProjectStagesRepository


@pytest.mark.asyncio
async def test_save_many_creates_ordered_board(
    db_session: AsyncSession,
    project: Project,
) -> None:
    repository = ProjectStagesRepository(db_session)

    await repository.save_many(
        items=[
            {
                "project_id": project.id,
                "name": name,
                "order_index": index,
                "color": "#58a6ff",
                "is_done_stage": name == "Готово",
            }
            for index, name in enumerate(("Бэклог", "В работе", "Готово"))
        ]
    )
    stages = await repository.get_by_project(project_id=project.id)

    assert [item.name for item in stages] == ["Бэклог", "В работе", "Готово"]
    assert await repository.get_max_order_index(project_id=project.id) == 2


@pytest.mark.asyncio
async def test_duplicate_stage_name_within_project_raises_domain_error(
    db_session: AsyncSession,
    project: Project,
) -> None:
    repository = ProjectStagesRepository(db_session)
    data = {
        "project_id": project.id,
        "name": "Бэклог",
        "order_index": 0,
        "color": "#7d8793",
        "is_done_stage": False,
    }
    await repository.save(data=data)

    with pytest.raises(ProjectStageNameAlreadyExistsRepositoryError) as exc_info:
        await repository.save(data={**data, "order_index": 1})

    assert exc_info.value.name == "Бэклог"

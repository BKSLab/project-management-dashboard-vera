import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.projects import Project
from src.exceptions.projects import ProjectKeyAlreadyExistsRepositoryError
from src.repositories.projects import ProjectsRepository


@pytest.mark.asyncio
async def test_duplicate_key_raises_domain_error(
    db_session: AsyncSession,
    project: Project,
) -> None:
    repository = ProjectsRepository(db_session)

    with pytest.raises(ProjectKeyAlreadyExistsRepositoryError) as exc_info:
        await repository.save(
            data={
                "key": project.key,
                "name": "Другой проект",
                "status": "PLANNING",
                "color": "#a371f7",
                "order_index": 1,
            }
        )

    assert exc_info.value.key == project.key


@pytest.mark.asyncio
async def test_get_by_key_and_max_order_index(
    db_session: AsyncSession,
    project: Project,
) -> None:
    repository = ProjectsRepository(db_session)

    found = await repository.get_by_key(key=project.key)

    assert found is not None
    assert found.id == project.id
    assert await repository.get_max_order_index() == project.order_index

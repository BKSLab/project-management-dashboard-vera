import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.project_stages import ProjectStage
from src.db.models.projects import Project
from src.repositories.project_stages import ProjectStagesRepository
from src.repositories.projects import ProjectsRepository


@pytest_asyncio.fixture
async def project(db_session: AsyncSession) -> Project:
    """Создаёт проект, от которого зависят остальные сущности трекера."""
    return await ProjectsRepository(db_session).save(
        data={
            "key": "VERA",
            "name": "Агент Вера",
            "status": "PLANNING",
            "color": "#58a6ff",
            "order_index": 0,
        }
    )


@pytest_asyncio.fixture
async def stage(db_session: AsyncSession, project: Project) -> ProjectStage:
    """Создаёт рабочую стадию проекта."""
    return await ProjectStagesRepository(db_session).save(
        data={
            "project_id": project.id,
            "name": "В работе",
            "order_index": 1,
            "color": "#58a6ff",
            "is_done_stage": False,
        }
    )

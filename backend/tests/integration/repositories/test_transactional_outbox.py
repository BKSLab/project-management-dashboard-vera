import pytest
from sqlalchemy import select

from src.db.models.knowledge_index_jobs import (
    KnowledgeEntityType,
    KnowledgeIndexJob,
)
from src.db.models.project_stages import ProjectStage
from src.db.models.projects import Project
from src.db.models.tasks import Task
from src.exceptions.knowledge import KnowledgeIndexJobsRepositoryError
from src.repositories.knowledge_index_jobs import KnowledgeIndexJobsRepository
from src.repositories.tasks import TasksRepository
from src.services.knowledge_events import KnowledgeEvents


def task_data(project: Project, stage: ProjectStage, *, number: int, title: str) -> dict:
    """Возвращает минимальные поля задачи для транзакционных тестов."""
    return {
        "project_id": project.id,
        "stage_id": stage.id,
        "number": number,
        "title": title,
        "priority": "MEDIUM",
        "position": 1000.0,
    }


@pytest.mark.asyncio
async def test_domain_rollback_removes_outbox_job(
    db_session,
    project: Project,
    stage: ProjectStage,
) -> None:
    task = await TasksRepository(db_session).save(
        task_data(project, stage, number=701, title="Откатываемая задача")
    )
    await KnowledgeEvents(repository=KnowledgeIndexJobsRepository(db_session)).upsert(
        project_id=project.id,
        entity_type=KnowledgeEntityType.TASK,
        entity_id=task.id,
    )

    await db_session.rollback()

    assert (
        await db_session.scalar(
            select(KnowledgeIndexJob).where(KnowledgeIndexJob.entity_id == str(task.id))
        )
    ) is None
    assert await db_session.scalar(select(Task).where(Task.title == "Откатываемая задача")) is None


@pytest.mark.asyncio
async def test_outbox_insert_failure_rolls_back_domain_change(
    db_session,
    project: Project,
    stage: ProjectStage,
) -> None:
    await TasksRepository(db_session).save(
        task_data(project, stage, number=702, title="Задача перед ошибкой outbox")
    )

    with pytest.raises(KnowledgeIndexJobsRepositoryError):
        await KnowledgeIndexJobsRepository(db_session).add_many(
            project_id=project.id,
            entity_type=KnowledgeEntityType.TASK,
            operation=None,  # type: ignore[arg-type]
            entity_ids=["999"],
        )

    assert (
        await db_session.scalar(select(Task).where(Task.title == "Задача перед ошибкой outbox"))
    ) is None

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.project_stages import ProjectStage
from src.repositories.task_attachments import TaskAttachmentsRepository
from src.repositories.tasks import TasksRepository


@pytest.mark.asyncio
async def test_save_list_and_cascade_delete_task_attachment(
    db_session: AsyncSession,
    stage: ProjectStage,
) -> None:
    tasks_repository = TasksRepository(db_session)
    task = await tasks_repository.save(
        data={
            "project_id": stage.project_id,
            "stage_id": stage.id,
            "number": 1,
            "title": "Задача с файлом",
            "priority": "MEDIUM",
            "position": 1.0,
        }
    )
    attachments_repository = TaskAttachmentsRepository(db_session)
    attachment = await attachments_repository.save(
        task_id=task.id,
        original_name="report.pdf",
        storage_key=f"tasks/{task.id}/unique.pdf",
        content_type="application/pdf",
        size=3,
    )

    items = await attachments_repository.get_for_task(task_id=task.id)

    assert [item.id for item in items] == [attachment.id]
    assert await attachments_repository.get_count_for_task(task.id) == 1

    await tasks_repository.delete(task=task)

    assert await attachments_repository.get_for_task(task_id=task.id) == []

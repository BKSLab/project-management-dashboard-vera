import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.kanban_stages import KanbanStagesRepository
from src.repositories.kanban_tasks import KanbanTasksRepository
from src.repositories.task_attachments import TaskAttachmentsRepository


@pytest.mark.asyncio
async def test_save_list_and_cascade_delete_task_attachment(db_session: AsyncSession) -> None:
    stage = await KanbanStagesRepository(db_session).save(
        data={
            "name": "В работе",
            "order_index": 1,
            "color": "#6366F1",
            "is_done_stage": False,
        }
    )
    tasks_repository = KanbanTasksRepository(db_session)
    task = await tasks_repository.save(
        data={"stage_id": stage.id, "title": "Задача с файлом", "position": 1.0}
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

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions.document_links import DocumentLinkAlreadyExistsRepositoryError
from src.repositories.document_links import DocumentLinksRepository
from src.repositories.documents import DocumentsRepository
from src.repositories.kanban_stages import KanbanStagesRepository
from src.repositories.kanban_tasks import KanbanTasksRepository


@pytest.mark.asyncio
async def test_create_on_real_postgres_rejects_duplicate_link(
    db_session: AsyncSession,
) -> None:
    documents_repository = DocumentsRepository(db_session)
    stages_repository = KanbanStagesRepository(db_session)
    tasks_repository = KanbanTasksRepository(db_session)
    links_repository = DocumentLinksRepository(db_session)
    document = await documents_repository.create(
        slug="architecture",
        title="Архитектура",
        content_md="Описание.",
    )
    stage = await stages_repository.save(
        data={
            "name": "Бэклог",
            "order_index": 0,
            "color": "#999999",
            "is_done_stage": False,
        }
    )
    task = await tasks_repository.save(
        data={"stage_id": stage.id, "title": "Работа", "position": 0.0}
    )
    link_data = {
        "document_id": document.id,
        "kanban_task_id": task.id,
        "wbs_item_id": None,
    }
    await links_repository.create(data=link_data)

    with pytest.raises(DocumentLinkAlreadyExistsRepositoryError):
        await links_repository.create(data=link_data)

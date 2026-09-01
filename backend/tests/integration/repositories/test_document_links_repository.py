import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.project_stages import ProjectStage
from src.exceptions.document_links import DocumentLinkAlreadyExistsRepositoryError
from src.repositories.document_links import DocumentLinksRepository
from src.repositories.documents import DocumentsRepository
from src.repositories.tasks import TasksRepository


@pytest.mark.asyncio
async def test_duplicate_link_raises_domain_error(
    db_session: AsyncSession,
    stage: ProjectStage,
) -> None:
    document = await DocumentsRepository(db_session).create(
        data={
            "project_id": stage.project_id,
            "slug": "plan",
            "title": "План",
            "content_md": "Текст",
        }
    )
    task = await TasksRepository(db_session).save(
        data={
            "project_id": stage.project_id,
            "stage_id": stage.id,
            "number": 1,
            "title": "Задача",
            "priority": "MEDIUM",
            "position": 1000.0,
        }
    )
    repository = DocumentLinksRepository(db_session)
    link = await repository.create(data={"document_id": document.id, "task_id": task.id})

    with pytest.raises(DocumentLinkAlreadyExistsRepositoryError):
        await repository.create(data={"document_id": document.id, "task_id": task.id})

    for_task = await repository.get_for_task(task_id=task.id)
    for_document = await repository.get_for_document(document_id=document.id)

    assert [item.id for item in for_task] == [link.id]
    assert [item.id for item in for_document] == [link.id]

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

import pytest

from src.db.models.documents import Document
from src.db.models.knowledge_index_jobs import KnowledgeEntityType, KnowledgeIndexOperation
from src.db.models.project_milestones import ProjectMilestone, ProjectMilestoneStatus
from src.db.models.projects import Project
from src.db.models.task_attachments import TaskAttachment
from src.db.models.task_comments import TaskComment
from src.db.models.tasks import Task
from src.knowledge.documents import build_attachment_chunks, build_comment_document
from src.repositories.documents import DocumentsRepository
from src.repositories.milestones import MilestonesRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.task_attachments import TaskAttachmentsRepository
from src.repositories.task_comments import TaskCommentsRepository
from src.repositories.tasks import TasksRepository
from src.repositories.wbs_nodes import WbsNodesRepository
from src.services.knowledge_index import KnowledgeIndexService


def build_service(tmp_path):
    now = datetime.now(UTC)
    project = Project(id=1, owner_id=1, key="PROJ", name="Вера", updated_at=now)
    task = Task(
        id=7,
        project_id=project.id,
        stage_id=1,
        number=12,
        title="Изменяемый заголовок",
        description_md="Описание",
        position=1000,
        created_at=now,
        updated_at=now,
    )

    projects = AsyncMock(spec=ProjectsRepository)
    projects.get_by_id.return_value = project
    tasks = AsyncMock(spec=TasksRepository)
    tasks.get_by_id.return_value = task
    nodes = AsyncMock(spec=WbsNodesRepository)
    nodes.get_by_project.return_value = []
    documents = AsyncMock(spec=DocumentsRepository)
    comments = AsyncMock(spec=TaskCommentsRepository)
    attachments = AsyncMock(spec=TaskAttachmentsRepository)
    storage = Mock()
    storage.resolve.return_value = tmp_path / "attachment.txt"

    embedding = SimpleNamespace(get_embeddings=AsyncMock(return_value=[[1.0, 0.0]]))
    qdrant = SimpleNamespace(
        vector_dim=2,
        delete_task_context=AsyncMock(),
        delete_entity=AsyncMock(),
        upsert_documents=AsyncMock(),
    )
    runtime = SimpleNamespace(embedding_client=embedding, qdrant_client=qdrant)
    service = KnowledgeIndexService(
        projects_repository=projects,
        tasks_repository=tasks,
        wbs_nodes_repository=nodes,
        documents_repository=documents,
        comments_repository=comments,
        attachments_repository=attachments,
        attachment_storage=storage,
        embedding_batch_size=32,
        chunk_target_chars=2200,
        chunk_overlap_chars=300,
        runtime=runtime,
    )
    return service, project, task, runtime, documents, attachments


def make_job(operation: KnowledgeIndexOperation, entity_type: KnowledgeEntityType, entity_id=7):
    return SimpleNamespace(
        operation=operation,
        project_id=1,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
    )


@pytest.mark.asyncio
async def test_upsert_existing_task_replaces_point_without_deleting_task_context(tmp_path) -> None:
    service, _, _, runtime, _, _ = build_service(tmp_path)

    await service.process(make_job(KnowledgeIndexOperation.UPSERT, KnowledgeEntityType.TASK))

    runtime.qdrant_client.delete_task_context.assert_not_awaited()
    runtime.qdrant_client.delete_entity.assert_not_awaited()
    runtime.qdrant_client.upsert_documents.assert_awaited_once()


@pytest.mark.asyncio
async def test_milestone_semantic_document_excludes_operational_dates(tmp_path) -> None:
    service, _, _, runtime, _, _ = build_service(tmp_path)
    milestones = AsyncMock(spec=MilestonesRepository)
    milestones.get_by_id.return_value = ProjectMilestone(
        id=7,
        project_id=1,
        title="MVP",
        description_md="Критерии запуска.",
        due_date=datetime.now(UTC).date(),
        status=ProjectMilestoneStatus.PLANNED,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service.milestones_repository = milestones

    await service.process(make_job(KnowledgeIndexOperation.UPSERT, KnowledgeEntityType.MILESTONE))

    texts = runtime.embedding_client.get_embeddings.await_args.args[0]
    assert len(texts) == 1
    assert "MVP" in texts[0]
    assert "Критерии запуска" in texts[0]
    assert str(datetime.now(UTC).date()) not in texts[0]


@pytest.mark.asyncio
async def test_upsert_missing_task_deletes_entire_task_context(tmp_path) -> None:
    service, _, _, runtime, _, _ = build_service(tmp_path)
    service.tasks_repository.get_by_id.return_value = None

    await service.process(make_job(KnowledgeIndexOperation.UPSERT, KnowledgeEntityType.TASK))

    runtime.qdrant_client.delete_task_context.assert_awaited_once_with(project_id=1, task_id=7)
    runtime.qdrant_client.upsert_documents.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_task_deletes_entire_task_context(tmp_path) -> None:
    service, _, _, runtime, _, _ = build_service(tmp_path)

    await service.process(make_job(KnowledgeIndexOperation.DELETE, KnowledgeEntityType.TASK))

    runtime.qdrant_client.delete_task_context.assert_awaited_once_with(project_id=1, task_id=7)
    runtime.embedding_client.get_embeddings.assert_not_awaited()


@pytest.mark.asyncio
async def test_task_batch_uses_one_bulk_load_and_one_embedding_call(tmp_path) -> None:
    service, project, task, runtime, _, _ = build_service(tmp_path)
    second = Task(
        id=8,
        project_id=project.id,
        stage_id=1,
        number=13,
        title="Вторая задача",
        description_md="Описание",
        position=2000,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service.tasks_repository.get_by_ids.return_value = [task, second]
    runtime.embedding_client.get_embeddings.return_value = [
        [1.0, 0.0],
        [0.0, 1.0],
    ]

    chunks = await service.upsert_tasks(project_id=1, entity_ids=[7, 8])

    assert chunks == {7: 1, 8: 1}
    service.tasks_repository.get_by_ids.assert_awaited_once_with({7, 8})
    service.projects_repository.get_by_id.assert_awaited_once_with(1)
    service.wbs_nodes_repository.get_by_project.assert_awaited_once_with(1)
    runtime.embedding_client.get_embeddings.assert_awaited_once()
    assert len(runtime.embedding_client.get_embeddings.await_args.args[0]) == 2
    runtime.qdrant_client.upsert_documents.assert_awaited_once()


@pytest.mark.asyncio
async def test_task_batch_deletes_context_only_for_missing_tasks(tmp_path) -> None:
    service, _, task, runtime, _, _ = build_service(tmp_path)
    service.tasks_repository.get_by_ids.return_value = [task]

    chunks = await service.upsert_tasks(project_id=1, entity_ids=[7, 404])

    assert chunks == {7: 1, 404: 0}
    runtime.qdrant_client.delete_task_context.assert_awaited_once_with(
        project_id=1,
        task_id=404,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("entity_type", "entity_id"),
    [
        (KnowledgeEntityType.DOCUMENT, 9),
        (KnowledgeEntityType.ATTACHMENT, 11),
    ],
)
async def test_upsert_multichunk_entity_deletes_old_chunks_before_writing(
    tmp_path,
    entity_type: KnowledgeEntityType,
    entity_id: int,
) -> None:
    service, project, task, runtime, documents, attachments = build_service(tmp_path)
    now = datetime.now(UTC)
    documents.get_by_id.return_value = Document(
        id=entity_id,
        project_id=project.id,
        slug="plan",
        title="План",
        content_md="Содержимое документа",
        created_at=now,
        updated_at=now,
    )
    attachments.get_by_id.return_value = TaskAttachment(
        id=entity_id,
        task_id=task.id,
        original_name="attachment.txt",
        storage_key="tasks/7/attachment.txt",
        content_type="text/plain",
        size=10,
        created_at=now,
    )
    (tmp_path / "attachment.txt").write_text("Содержимое вложения", encoding="utf-8")
    manager = Mock()
    manager.attach_mock(runtime.qdrant_client.delete_entity, "delete")
    manager.attach_mock(runtime.qdrant_client.upsert_documents, "upsert")

    await service.process(make_job(KnowledgeIndexOperation.UPSERT, entity_type, entity_id))

    assert manager.mock_calls[0] == call.delete(
        project_id=1,
        entity_type=entity_type.value.lower(),
        entity_id=entity_id,
    )
    assert manager.mock_calls[1].args == ()
    assert manager.mock_calls[1].kwargs["project_id"] == 1


def test_comment_document_does_not_depend_on_mutable_task_title(tmp_path) -> None:
    _, project, task, _, _, _ = build_service(tmp_path)
    comment = TaskComment(
        id=5,
        task_id=task.id,
        author_name="Автор",
        body_md="Комментарий",
        created_at=datetime.now(UTC),
    )

    document = build_comment_document(comment, task=task, project=project)

    assert "Задача: PROJ-12" in document.text
    assert task.title not in document.text


def test_attachment_document_does_not_depend_on_mutable_task_title(tmp_path) -> None:
    _, project, task, _, _, _ = build_service(tmp_path)
    attachment = TaskAttachment(
        id=11,
        task_id=task.id,
        original_name="note.txt",
        storage_key="tasks/7/note.txt",
        content_type="text/plain",
        size=10,
        created_at=datetime.now(UTC),
    )

    documents = build_attachment_chunks(
        attachment,
        extracted_text="Текст файла",
        task=task,
        project=project,
        target_chars=2200,
        overlap_chars=300,
    )

    assert documents
    assert "Задача: PROJ-12" in documents[0].text
    assert task.title not in documents[0].text

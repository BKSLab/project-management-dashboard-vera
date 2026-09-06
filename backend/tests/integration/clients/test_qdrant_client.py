import os
from collections.abc import Generator
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from docker.errors import DockerException
from qdrant_client import AsyncQdrantClient, models
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import HttpWaitStrategy

from src.clients.qdrant import PAYLOAD_INDEX_FIELDS, ProjectQdrantClient
from src.clients.vision import DisabledVisionCapability
from src.db.models.knowledge_index_jobs import KnowledgeEntityType, KnowledgeIndexOperation
from src.db.models.projects import Project
from src.db.models.tasks import Task
from src.knowledge.documents import build_task_document
from src.services.knowledge_index import KnowledgeIndexService, PreparedIndexAction


@pytest.fixture(scope="module")
def qdrant_url() -> Generator[str, None, None]:
    """Поднимает совместимый Qdrant для проверки реального query API."""
    try:
        with (
            DockerContainer("qdrant/qdrant:v1.12.6")
            .with_exposed_ports(6333)
            .waiting_for(HttpWaitStrategy(6333).for_status_code(200).with_startup_timeout(120))
        ) as container:
            host = container.get_container_host_ip()
            port = container.get_exposed_port(6333)
            yield f"http://{host}:{port}"
    except DockerException as error:
        if os.getenv("CI"):
            raise
        pytest.skip(f"Docker недоступен для Qdrant integration-тестов: {error}")


def build_client(qdrant_url: str) -> ProjectQdrantClient:
    """Создаёт тестовый клиент с малой размерностью векторов."""
    return ProjectQdrantClient(
        client=AsyncQdrantClient(url=qdrant_url, api_key=None),
        collection_prefix="project",
        vector_dim=3,
    )


@pytest.mark.asyncio
async def test_payload_index_backfill_updates_existing_collection(qdrant_url: str) -> None:
    client = build_client(qdrant_url)
    collection_name = client.collection_name(101)
    try:
        await client.client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(size=3, distance=models.Distance.COSINE),
        )

        processed = await client.backfill_payload_indexes()
        info = await client.client.get_collection(collection_name)

        assert processed == 1
        assert set(info.payload_schema) == set(PAYLOAD_INDEX_FIELDS)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_grouped_search_keeps_entity_types_separate_and_filters_them(
    qdrant_url: str,
) -> None:
    client = build_client(qdrant_url)
    documents = [
        SimpleNamespace(
            point_id=1,
            payload={
                "source_id": "task:5",
                "entity_type": "task",
                "entity_id": "5",
                "task_id": "5",
                "text": "Первый фрагмент задачи",
            },
        ),
        SimpleNamespace(
            point_id=2,
            payload={
                "source_id": "task:5",
                "entity_type": "task",
                "entity_id": "5",
                "task_id": "5",
                "text": "Второй фрагмент задачи",
            },
        ),
        SimpleNamespace(
            point_id=3,
            payload={
                "source_id": "document:5",
                "entity_type": "document",
                "entity_id": "5",
                "text": "Фрагмент документа",
            },
        ),
    ]
    try:
        await client.upsert_documents(
            project_id=102,
            documents=documents,
            vectors=[[1.0, 0.0, 0.0], [0.99, 0.01, 0.0], [0.9, 0.1, 0.0]],
        )

        all_hits = await client.search(
            project_id=102,
            vector=[1.0, 0.0, 0.0],
            limit=10,
            score_threshold=0.0,
        )
        document_hits = await client.search(
            project_id=102,
            vector=[1.0, 0.0, 0.0],
            limit=10,
            score_threshold=0.0,
            entity_type="document",
        )

        assert [hit.payload["source_id"] for hit in all_hits] == ["task:5", "document:5"]
        assert [hit.payload["source_id"] for hit in document_hits] == ["document:5"]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_task_upsert_preserves_comment_and_attachment_points(qdrant_url: str) -> None:
    client = build_client(qdrant_url)
    now = datetime.now(UTC)
    project = Project(id=103, owner_id=1, key="PROJ", name="Вера", updated_at=now)
    old_task = Task(
        id=5,
        project_id=project.id,
        stage_id=1,
        number=5,
        title="Старый заголовок",
        description_md="Описание",
        position=1000,
        created_at=now,
        updated_at=now,
    )
    new_task = Task(
        id=5,
        project_id=project.id,
        stage_id=1,
        number=5,
        title="Новый заголовок",
        description_md="Описание",
        position=1000,
        created_at=now,
        updated_at=now,
    )
    old_task_document = build_task_document(old_task, project=project, wbs_path=None)
    new_task_document = build_task_document(new_task, project=project, wbs_path=None)
    child_documents = [
        SimpleNamespace(
            point_id=2,
            payload={
                "source_id": "comment:8",
                "entity_type": "comment",
                "entity_id": "8",
                "task_id": "5",
                "text": "Комментарий сохраняется",
            },
        ),
        SimpleNamespace(
            point_id=3,
            payload={
                "source_id": "attachment:9",
                "entity_type": "attachment",
                "entity_id": "9",
                "task_id": "5",
                "text": "Вложение сохраняется",
            },
        ),
    ]
    embedding_client = SimpleNamespace(get_embeddings=AsyncMock(return_value=[[1.0, 0.0, 0.0]]))
    service = KnowledgeIndexService(
        risks_repository=SimpleNamespace(),
        projects_repository=SimpleNamespace(),
        tasks_repository=SimpleNamespace(),
        wbs_nodes_repository=SimpleNamespace(),
        documents_repository=SimpleNamespace(),
        comments_repository=SimpleNamespace(),
        attachments_repository=SimpleNamespace(),
        attachment_storage=SimpleNamespace(),
        milestones_repository=SimpleNamespace(),
        embedding_batch_size=32,
        chunk_target_chars=2200,
        chunk_overlap_chars=300,
        extract_max_chars=350_000,
        embedding_client=embedding_client,
        qdrant_client=client,
        vision=DisabledVisionCapability(),
    )
    try:
        await client.upsert_documents(
            project_id=project.id,
            documents=[old_task_document, *child_documents],
            vectors=[[0.8, 0.2, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        )

        await service.execute_prepared(
            PreparedIndexAction(
                project_id=project.id,
                entity_type=KnowledgeEntityType.TASK,
                operation=KnowledgeIndexOperation.UPSERT,
                entity_id=new_task.id,
                documents=(new_task_document,),
            )
        )
        points, _ = await client.client.scroll(
            collection_name=client.collection_name(project.id),
            limit=10,
            with_payload=True,
        )

        payloads = {point.payload["source_id"]: point.payload for point in points}
        assert set(payloads) == {"task:5", "comment:8", "attachment:9"}
        assert payloads["task:5"]["title"] == "PROJ-5 · Новый заголовок"
        assert payloads["comment:8"]["text"] == "Комментарий сохраняется"
        assert payloads["attachment:9"]["text"] == "Вложение сохраняется"
    finally:
        await client.close()

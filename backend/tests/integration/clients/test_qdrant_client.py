import os
from collections.abc import Generator
from types import SimpleNamespace

import pytest
from docker.errors import DockerException
from qdrant_client import AsyncQdrantClient, models
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import HttpWaitStrategy

from src.clients.qdrant import PAYLOAD_INDEX_FIELDS, ProjectQdrantClient


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

        assert [hit.payload["source_id"] for hit in all_hits] == ["task:5", "task:5", "document:5"]
        assert [hit.payload["source_id"] for hit in document_hits] == ["document:5"]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_project_sync_updates_and_deletes_points_in_real_qdrant(
    qdrant_url: str, tmp_path
) -> None:
    from tests.unit.knowledge.test_knowledge_index import base_rows, build_service, sync

    client = build_client(qdrant_url)
    service = build_service(tmp_path, qdrant=client)
    try:
        await sync(service)
        first = await client.manifest(1)
        service.embedding_client.reset_mock()
        rows = base_rows()
        rows["tasks"][0]["due_date"] = "2026-10-01"
        rows["document_links"] = []
        await sync(service, rows)
        service.embedding_client.get_embeddings.assert_not_awaited()
        updated = await client.manifest(1)
        assert set(first) == set(updated)
        assert (
            next(item for item in updated.values() if item["source_id"] == "task:7")["properties"][
                "due_date"
            ]
            == "2026-10-01"
        )
        rows["task_comments"] = []
        await sync(service, rows)
        assert "comment:8" not in {
            item["source_id"] for item in (await client.manifest(1)).values()
        }
        await sync(service, {})
        assert await client.count(1) is None
    finally:
        await client.close()

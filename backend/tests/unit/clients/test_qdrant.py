from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from qdrant_client import models

from src.clients.qdrant import PAYLOAD_INDEX_FIELDS, ProjectQdrantClient


def build_client(*, collection_exists: bool = True) -> tuple[ProjectQdrantClient, AsyncMock]:
    """Создаёт Qdrant-обёртку с сетевым клиентом-дублёром."""
    qdrant = AsyncMock()
    qdrant.collection_exists.return_value = collection_exists
    client = ProjectQdrantClient(
        client=qdrant,
        collection_prefix="project",
        vector_dim=3,
    )
    return client, qdrant


@pytest.mark.asyncio
async def test_ensure_collection_creates_payload_indexes_for_existing_collection() -> None:
    client, qdrant = build_client(collection_exists=True)

    await client.ensure_collection(project_id=7)

    qdrant.create_collection.assert_not_awaited()
    assert qdrant.create_payload_index.await_count == len(PAYLOAD_INDEX_FIELDS)
    assert [
        call.kwargs["field_name"] for call in qdrant.create_payload_index.await_args_list
    ] == list(PAYLOAD_INDEX_FIELDS)
    assert all(
        call.kwargs["field_schema"] is models.PayloadSchemaType.KEYWORD
        for call in qdrant.create_payload_index.await_args_list
    )


@pytest.mark.asyncio
async def test_ensure_collection_creates_collection_and_payload_indexes() -> None:
    client, qdrant = build_client(collection_exists=False)

    await client.ensure_collection(project_id=8)

    qdrant.create_collection.assert_awaited_once()
    assert qdrant.create_payload_index.await_count == len(PAYLOAD_INDEX_FIELDS)


@pytest.mark.asyncio
async def test_recreate_collection_restores_payload_indexes() -> None:
    client, qdrant = build_client(collection_exists=True)

    await client.recreate_collection(project_id=9)

    qdrant.delete_collection.assert_awaited_once_with("project_9")
    qdrant.create_collection.assert_awaited_once()
    assert qdrant.create_payload_index.await_count == len(PAYLOAD_INDEX_FIELDS)


@pytest.mark.asyncio
async def test_delete_collection_invalidates_payload_index_memo() -> None:
    client, qdrant = build_client(collection_exists=True)
    client._indexed_collections.add("project_7")
    qdrant.collection_exists.side_effect = [True, False]

    await client.delete_collection(project_id=7)
    await client.ensure_collection(project_id=7)

    qdrant.delete_collection.assert_awaited_once_with("project_7")
    qdrant.create_collection.assert_awaited_once()
    assert qdrant.create_payload_index.await_count == len(PAYLOAD_INDEX_FIELDS)


@pytest.mark.asyncio
async def test_backfill_indexes_only_project_collections() -> None:
    client, qdrant = build_client()
    qdrant.get_collections.return_value = SimpleNamespace(
        collections=[
            SimpleNamespace(name="project_1"),
            SimpleNamespace(name="project_42"),
            SimpleNamespace(name="project_backup"),
            SimpleNamespace(name="foreign_3"),
        ]
    )

    count = await client.backfill_payload_indexes()

    assert count == 2
    assert qdrant.create_payload_index.await_count == 2 * len(PAYLOAD_INDEX_FIELDS)
    assert {
        call.kwargs["collection_name"] for call in qdrant.create_payload_index.await_args_list
    } == {"project_1", "project_42"}


@pytest.mark.asyncio
async def test_payload_indexes_are_checked_once_per_runtime() -> None:
    client, qdrant = build_client(collection_exists=True)

    await client.ensure_collection(project_id=7)
    await client.ensure_collection(project_id=7)

    assert qdrant.create_payload_index.await_count == len(PAYLOAD_INDEX_FIELDS)


@pytest.mark.asyncio
async def test_search_uses_query_api_and_groups_by_source_id() -> None:
    client, qdrant = build_client(collection_exists=True)
    task = SimpleNamespace(score=0.9, payload={"source_id": "task:5"})
    document = SimpleNamespace(score=0.8, payload={"source_id": "document:5"})
    qdrant.query_points_groups.return_value = SimpleNamespace(
        groups=[SimpleNamespace(hits=[task]), SimpleNamespace(hits=[document])]
    )

    hits = await client.search(
        project_id=7,
        vector=[1.0, 0.0, 0.0],
        limit=10,
        score_threshold=0.35,
    )

    assert [hit.payload["source_id"] for hit in hits] == ["task:5", "document:5"]
    qdrant.query_points_groups.assert_awaited_once()
    call = qdrant.query_points_groups.await_args
    assert call.kwargs["group_by"] == "source_id"
    assert call.kwargs["group_size"] == 1
    assert call.kwargs["query"] == [1.0, 0.0, 0.0]
    qdrant.search.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_passes_entity_type_filter_to_query_api() -> None:
    client, qdrant = build_client(collection_exists=True)
    qdrant.query_points_groups.return_value = SimpleNamespace(groups=[])

    await client.search(
        project_id=7,
        vector=[1.0, 0.0, 0.0],
        limit=10,
        score_threshold=0.35,
        entity_type="document",
    )

    query_filter = qdrant.query_points_groups.await_args.kwargs["query_filter"]
    assert query_filter.must[0].key == "entity_type"
    assert query_filter.must[0].match.value == "document"


@pytest.mark.asyncio
async def test_search_without_entity_type_omits_filter() -> None:
    client, qdrant = build_client(collection_exists=True)
    qdrant.query_points_groups.return_value = SimpleNamespace(groups=[])

    await client.search(
        project_id=7,
        vector=[1.0, 0.0, 0.0],
        limit=10,
        score_threshold=0.35,
    )

    assert qdrant.query_points_groups.await_args.kwargs["query_filter"] is None

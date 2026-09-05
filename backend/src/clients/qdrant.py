import logging
from dataclasses import dataclass
from typing import Any

from qdrant_client import AsyncQdrantClient, models

from src.exceptions.knowledge import KnowledgeProviderError

logger = logging.getLogger(__name__)

PAYLOAD_INDEX_FIELDS = ("entity_type", "entity_id", "task_id")


@dataclass(frozen=True, slots=True)
class KnowledgeSearchHit:
    """Найденный Qdrant point с нормализованным payload."""

    score: float
    payload: dict[str, Any]


class ProjectQdrantClient:
    """Qdrant client с отдельной collection на каждый проект.

    Transport передаётся готовым: создание и закрытие SDK принадлежат
    lifespan приложения, поэтому у сетевого ресурса один видимый владелец,
    а в тестах его можно подменить без обращения к сети.
    """

    def __init__(
        self,
        *,
        client: AsyncQdrantClient,
        collection_prefix: str,
        vector_dim: int,
    ) -> None:
        self.client = client
        self.collection_prefix = collection_prefix.strip().lower().replace("-", "_")
        self.vector_dim = vector_dim
        self._indexed_collections: set[str] = set()

    def collection_name(self, project_id: int) -> str:
        """Возвращает серверное имя collection, недоступное для выбора клиентом."""
        return f"{self.collection_prefix}_{project_id}"

    async def ensure_collection(self, project_id: int) -> None:
        """Создаёт collection проекта, если она отсутствует."""
        name = self.collection_name(project_id)
        try:
            if not await self.client.collection_exists(name):
                await self.client.create_collection(
                    collection_name=name,
                    vectors_config=models.VectorParams(
                        size=self.vector_dim,
                        distance=models.Distance.COSINE,
                    ),
                )
                logger.info("✅ Создана Qdrant collection %s.", name)
            await self._ensure_payload_indexes(name)
        except Exception as error:
            raise KnowledgeProviderError(str(error)) from error

    async def recreate_collection(self, project_id: int) -> None:
        """Пересоздаёт производный индекс проекта для полного reindex."""
        name = self.collection_name(project_id)
        try:
            if await self.client.collection_exists(name):
                await self.client.delete_collection(name)
            await self.client.create_collection(
                collection_name=name,
                vectors_config=models.VectorParams(
                    size=self.vector_dim,
                    distance=models.Distance.COSINE,
                ),
            )
            self._indexed_collections.discard(name)
            await self._ensure_payload_indexes(name)
        except Exception as error:
            raise KnowledgeProviderError(str(error)) from error

    async def backfill_payload_indexes(self) -> int:
        """Создаёт payload-индексы во всех существующих project collections."""
        try:
            response = await self.client.get_collections()
            prefix = f"{self.collection_prefix}_"
            names = [
                collection.name
                for collection in response.collections
                if collection.name.startswith(prefix)
                and collection.name.removeprefix(prefix).isdigit()
            ]
            for name in names:
                await self._ensure_payload_indexes(name)
            if names:
                logger.info("✅ Payload-индексы проверены для %s Qdrant collections.", len(names))
            return len(names)
        except KnowledgeProviderError:
            raise
        except Exception as error:
            raise KnowledgeProviderError(str(error)) from error

    async def delete_collection(self, project_id: int) -> None:
        """Удаляет collection проекта, если она существует."""
        name = self.collection_name(project_id)
        try:
            if await self.client.collection_exists(name):
                await self.client.delete_collection(name)
                logger.info("✅ Удалена Qdrant collection %s.", name)
            self._indexed_collections.discard(name)
        except Exception as error:
            raise KnowledgeProviderError(str(error)) from error

    async def upsert_documents(
        self,
        *,
        project_id: int,
        documents: list[Any],
        vectors: list[list[float]],
    ) -> None:
        """Идемпотентно записывает документы с детерминированными point IDs."""
        if not documents:
            return
        if len(documents) != len(vectors):
            raise KnowledgeProviderError("Число документов не совпало с числом embeddings.")
        if any(len(vector) != self.vector_dim for vector in vectors):
            raise KnowledgeProviderError(
                f"Embedding dimension не совпадает с Qdrant: ожидается {self.vector_dim}."
            )
        try:
            await self.ensure_collection(project_id)
            await self.client.upsert(
                collection_name=self.collection_name(project_id),
                points=[
                    models.PointStruct(
                        id=document.point_id,
                        vector=vector,
                        payload=document.payload,
                    )
                    for document, vector in zip(documents, vectors, strict=True)
                ],
                wait=True,
            )
        except KnowledgeProviderError:
            raise
        except Exception as error:
            raise KnowledgeProviderError(str(error)) from error

    async def delete_entity(
        self,
        *,
        project_id: int,
        entity_type: str,
        entity_id: int | str,
    ) -> None:
        """Удаляет все chunks одной исходной сущности."""
        await self._delete_by_filter(
            project_id=project_id,
            conditions=[
                models.FieldCondition(
                    key="entity_type",
                    match=models.MatchValue(value=entity_type),
                ),
                models.FieldCondition(
                    key="entity_id",
                    match=models.MatchValue(value=str(entity_id)),
                ),
            ],
        )

    async def delete_task_context(self, *, project_id: int, task_id: int) -> None:
        """Удаляет задачу и дочерние comments/attachments из индекса."""
        await self._delete_by_filter(
            project_id=project_id,
            conditions=[
                models.FieldCondition(
                    key="task_id",
                    match=models.MatchValue(value=str(task_id)),
                )
            ],
        )

    async def search(
        self,
        *,
        project_id: int,
        vector: list[float],
        limit: int,
        score_threshold: float,
        entity_type: str | None = None,
    ) -> list[KnowledgeSearchHit]:
        """Ищет по одному лучшему chunk каждого source_id внутри проекта."""
        name = self.collection_name(project_id)
        try:
            if not await self.client.collection_exists(name):
                return []
            query_filter = (
                models.Filter(
                    must=[
                        models.FieldCondition(
                            key="entity_type",
                            match=models.MatchValue(value=entity_type),
                        )
                    ]
                )
                if entity_type is not None
                else None
            )
            groups = await self.client.query_points_groups(
                collection_name=name,
                query=vector,
                group_by="source_id",
                group_size=1,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True,
                query_filter=query_filter,
            )
            return [
                KnowledgeSearchHit(score=float(point.score), payload=dict(point.payload or {}))
                for group in groups.groups
                for point in group.hits[:1]
            ]
        except Exception as error:
            raise KnowledgeProviderError(str(error)) from error

    async def count(self, project_id: int) -> int | None:
        """Возвращает точное число points либо ``None`` без collection."""
        name = self.collection_name(project_id)
        try:
            if not await self.client.collection_exists(name):
                return None
            result = await self.client.count(collection_name=name, exact=True)
            return int(result.count)
        except Exception as error:
            raise KnowledgeProviderError(str(error)) from error

    async def close(self) -> None:
        """Закрывает сетевой клиент Qdrant."""
        await self.client.close()

    async def _ensure_payload_indexes(self, collection_name: str) -> None:
        """Создаёт keyword-индексы полей, используемых в Qdrant-фильтрах."""
        if collection_name in self._indexed_collections:
            return
        for field_name in PAYLOAD_INDEX_FIELDS:
            await self.client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=models.PayloadSchemaType.KEYWORD,
                wait=True,
            )
        self._indexed_collections.add(collection_name)

    async def _delete_by_filter(
        self,
        *,
        project_id: int,
        conditions: list[models.Condition],
    ) -> None:
        name = self.collection_name(project_id)
        try:
            if not await self.client.collection_exists(name):
                return
            await self.client.delete(
                collection_name=name,
                points_selector=models.Filter(must=conditions),
                wait=True,
            )
        except Exception as error:
            raise KnowledgeProviderError(str(error)) from error

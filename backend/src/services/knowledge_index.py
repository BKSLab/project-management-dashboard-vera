"""Один алгоритм синхронизации всех источников коллекции проекта."""

import asyncio
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from src.clients.embedding import EmbeddingClient
from src.clients.qdrant import ProjectQdrantClient
from src.clients.vision import VisionCapability
from src.db.models.knowledge_index_jobs import KnowledgeIndexJob
from src.exceptions.clients import ClientError
from src.exceptions.knowledge import KnowledgeProviderError
from src.knowledge.catalog import ProjectCatalog, build_catalog, digest
from src.knowledge.documents import KnowledgeDocument
from src.knowledge.extract import IMAGE_EXTENSIONS, INDEXABLE_EXTENSIONS, extract_indexable_text
from src.repositories.knowledge_sources import KnowledgeSourcesRepository
from src.repositories.unit_of_work import UnitOfWork
from src.storage.task_attachments import TaskAttachmentStorage


@dataclass(slots=True)
class PreparedIndexAction:
    """Снимок без сессии; внешняя фаза дополняет тексты файлов."""

    project_id: int
    catalog: ProjectCatalog
    extractions: list[dict] = field(default_factory=list)
    extraction_errors: list[str] = field(default_factory=list)


class KnowledgeIndexService:
    def __init__(
        self,
        *,
        sources_repository: KnowledgeSourcesRepository,
        unit_of_work: UnitOfWork,
        attachment_storage: TaskAttachmentStorage,
        embedding_batch_size: int,
        chunk_target_chars: int,
        chunk_overlap_chars: int,
        embedding_client: EmbeddingClient,
        qdrant_client: ProjectQdrantClient,
        vision: VisionCapability,
    ):
        self.sources_repository = sources_repository
        self.unit_of_work = unit_of_work
        self.attachment_storage = attachment_storage
        self.embedding_batch_size = embedding_batch_size
        self.chunk_target_chars = chunk_target_chars
        self.chunk_overlap_chars = chunk_overlap_chars
        self.embedding_client = embedding_client
        self.qdrant_client = qdrant_client
        self.vision = vision

    async def prepare(self, job: KnowledgeIndexJob) -> PreparedIndexAction:
        """Обычная мутация и полная пересборка читают один и тот же каталог."""
        rows = await self.sources_repository.get_project_rows(job.project_id)
        return PreparedIndexAction(job.project_id, build_catalog(job.project_id, rows))

    async def extract(self, action: PreparedIndexAction) -> None:
        """Читает файлы и vision после закрытия DB-области."""
        rows = action.catalog.rows
        cached = {row["attachment_id"]: row for row in rows.get("knowledge_attachment_texts", [])}
        for attachment in rows.get("task_attachments", []):
            previous = cached.get(attachment["id"])
            if previous and previous["status"] in {"ready", "unsupported"}:
                continue
            result = await self._extract_attachment(attachment)
            action.extractions.append(result)
            cached[attachment["id"]] = result
            if result["status"] == "failed":
                action.extraction_errors.append(f"Файл {attachment['id']}: {result['detail']}")
        rows["knowledge_attachment_texts"] = list(cached.values())
        action.catalog = build_catalog(action.project_id, rows)

    async def persist_extractions(self, action: PreparedIndexAction) -> None:
        """Сохраняет извлечение для FTS до обращения к embeddings/Qdrant."""
        if not action.extractions:
            return
        try:
            for result in action.extractions:
                await self.sources_repository.save_extraction(result)
            await self.unit_of_work.commit()
        except Exception:
            await self.unit_of_work.rollback()
            raise

    async def execute_prepared(self, action: PreparedIndexAction) -> int:
        """Текст → embedding, свойства → payload, удалённое → delete."""
        if not action.catalog.sources:
            await self.qdrant_client.delete_collection(action.project_id)
            return 0
        documents = [
            chunk
            for source in action.catalog.sources.values()
            for chunk in source.chunks(self.chunk_target_chars, self.chunk_overlap_chars)
        ]
        existing = await self.qdrant_client.manifest(action.project_id)
        signature = digest([self.embedding_client.model, self.qdrant_client.vector_dim])
        for document in documents:
            document.payload["embedding_signature"] = signature
        changed = [
            doc
            for doc in documents
            if existing.get(doc.point_id, {}).get("text_hash") != doc.payload["text_hash"]
            or existing.get(doc.point_id, {}).get("embedding_signature") != signature
        ]
        vectors = await self._embed(changed)
        await self.qdrant_client.ensure_collection(action.project_id)
        for start in range(0, len(changed), self.embedding_batch_size):
            await self.qdrant_client.upsert_documents(
                project_id=action.project_id,
                documents=changed[start : start + self.embedding_batch_size],
                vectors=vectors[start : start + self.embedding_batch_size],
            )
        unchanged_text = [
            doc
            for doc in documents
            if doc.point_id in existing
            and existing[doc.point_id].get("text_hash") == doc.payload["text_hash"]
            and existing[doc.point_id].get("embedding_signature") == signature
            and existing[doc.point_id] != doc.payload
        ]
        await self.qdrant_client.update_payloads(action.project_id, unchanged_text)
        expected = {doc.point_id for doc in documents}
        await self.qdrant_client.delete_points(action.project_id, sorted(set(existing) - expected))
        if action.extraction_errors:
            raise KnowledgeProviderError("; ".join(action.extraction_errors))
        return len(documents)

    async def _extract_attachment(self, attachment: dict) -> dict:
        result = {
            "attachment_id": attachment["id"],
            "text": "",
            "status": "pending",
            "detail": None,
            "original_chars": 0,
            "content_hash": "",
        }
        suffix = Path(attachment["original_name"]).suffix.lower()
        if suffix not in INDEXABLE_EXTENSIONS:
            return {
                **result,
                "status": "unsupported",
                "detail": "Формат не поддерживает извлечение текста; метаданные файла доступны.",
            }
        try:
            content = await asyncio.to_thread(
                self.attachment_storage.resolve(attachment["storage_key"]).read_bytes
            )
            result["content_hash"] = hashlib.sha256(content).hexdigest()
            extracted = await extract_indexable_text(
                attachment["original_name"], content, vision=self.vision
            )
            if not extracted:
                return {
                    **result,
                    "status": "empty",
                    "detail": "Распознавание изображения не дало текста."
                    if suffix in IMAGE_EXTENSIONS
                    else "Текст не найден; для PDF проверяется текстовый слой, OCR страниц не выполняется.",
                }
            result.update(text=extracted, original_chars=len(extracted), status="ready")
            return result
        except ClientError:
            return {
                **result,
                "status": "failed",
                "detail": "Сервис распознавания временно недоступен; запланирован повтор.",
            }
        except Exception:
            return {
                **result,
                "status": "failed",
                "detail": "Не удалось прочитать или разобрать файл; запланирован повтор.",
            }

    async def _embed(self, documents: list[KnowledgeDocument]) -> list[list[float]]:
        vectors = []
        for start in range(0, len(documents), self.embedding_batch_size):
            vectors.extend(
                await self.embedding_client.get_embeddings(
                    [doc.text for doc in documents[start : start + self.embedding_batch_size]]
                )
            )
        if len(vectors) != len(documents) or any(
            len(vector) != self.qdrant_client.vector_dim for vector in vectors
        ):
            raise ValueError(
                "Количество или размерность embeddings не совпадает с документами коллекции."
            )
        return vectors

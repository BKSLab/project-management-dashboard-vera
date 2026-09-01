from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from src.db.models.knowledge_index_jobs import (
    KnowledgeEntityType,
    KnowledgeIndexJob,
    KnowledgeIndexOperation,
)
from src.knowledge.documents import (
    KnowledgeDocument,
    build_attachment_chunks,
    build_comment_document,
    build_document_chunks,
    build_project_document,
    build_task_document,
    build_wbs_paths,
)
from src.knowledge.extract import extract_indexable_text
from src.knowledge.runtime import KnowledgeRuntime, get_knowledge_runtime
from src.repositories.documents import DocumentsRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.task_attachments import TaskAttachmentsRepository
from src.repositories.task_comments import TaskCommentsRepository
from src.repositories.tasks import TasksRepository
from src.repositories.wbs_nodes import WbsNodesRepository
from src.storage.task_attachments import TaskAttachmentStorage

logger = logging.getLogger(__name__)


class KnowledgeIndexService:
    """Строит производный Qdrant-индекс из актуальных данных PostgreSQL."""

    def __init__(
        self,
        *,
        projects_repository: ProjectsRepository,
        tasks_repository: TasksRepository,
        wbs_nodes_repository: WbsNodesRepository,
        documents_repository: DocumentsRepository,
        comments_repository: TaskCommentsRepository,
        attachments_repository: TaskAttachmentsRepository,
        attachment_storage: TaskAttachmentStorage,
        embedding_batch_size: int,
        chunk_target_chars: int,
        chunk_overlap_chars: int,
        runtime: KnowledgeRuntime | None = None,
    ) -> None:
        self.projects_repository = projects_repository
        self.tasks_repository = tasks_repository
        self.wbs_nodes_repository = wbs_nodes_repository
        self.documents_repository = documents_repository
        self.comments_repository = comments_repository
        self.attachments_repository = attachments_repository
        self.attachment_storage = attachment_storage
        self.embedding_batch_size = embedding_batch_size
        self.chunk_target_chars = chunk_target_chars
        self.chunk_overlap_chars = chunk_overlap_chars
        self.runtime = runtime or get_knowledge_runtime()

    async def process(self, job: KnowledgeIndexJob) -> None:
        """Выполняет одно идемпотентное задание очереди."""
        if job.operation is KnowledgeIndexOperation.DELETE_COLLECTION:
            await self.runtime.qdrant_client.delete_collection(job.project_id)
            return
        if job.operation is KnowledgeIndexOperation.REINDEX_PROJECT:
            await self.reindex_project(job.project_id)
            return
        if job.entity_id is None:
            raise ValueError("Для операции над сущностью отсутствует entity_id.")

        entity_id = int(job.entity_id)
        if job.operation is KnowledgeIndexOperation.DELETE:
            await self._delete(job.project_id, job.entity_type, entity_id)
            return
        await self._upsert(job.project_id, job.entity_type, entity_id)

    async def reindex_project(self, project_id: int) -> int:
        """Полностью пересобирает collection проекта и возвращает число chunks."""
        project = await self.projects_repository.get_by_id(project_id)
        if project is None:
            await self.runtime.qdrant_client.delete_collection(project_id)
            return 0

        tasks = await self.tasks_repository.get_by_project(project_id)
        task_ids = {task.id for task in tasks}
        nodes = await self.wbs_nodes_repository.get_by_project(project_id)
        documents = await self.documents_repository.get_by_project(project_id)
        comments = await self.comments_repository.get_for_tasks(task_ids)
        attachments = await self.attachments_repository.get_for_tasks(task_ids)

        task_by_id = {task.id: task for task in tasks}
        wbs_paths = build_wbs_paths(nodes)
        chunks: list[KnowledgeDocument] = [build_project_document(project)]
        chunks.extend(
            build_task_document(
                task,
                project=project,
                wbs_path=wbs_paths.get(task.wbs_node_id) if task.wbs_node_id else None,
            )
            for task in tasks
        )
        for document in documents:
            chunks.extend(self._document_chunks(document))
        for comment in comments:
            task = task_by_id.get(comment.task_id)
            if task is not None:
                chunks.append(build_comment_document(comment, task=task, project=project))
        for attachment in attachments:
            task = task_by_id.get(attachment.task_id)
            if task is not None:
                chunks.extend(await self._attachment_chunks(attachment, task, project))

        # Сначала получаем и валидируем все embeddings. Если внешний API упал,
        # рабочая collection остаётся нетронутой.
        vectors = await self._embed(chunks)
        await self.runtime.qdrant_client.recreate_collection(project_id)
        await self._write_batches(project_id, chunks, vectors)
        logger.info("✅ Индекс проекта id=%s пересобран: %s chunks.", project_id, len(chunks))
        return len(chunks)

    async def _upsert(
        self,
        project_id: int,
        entity_type: KnowledgeEntityType,
        entity_id: int,
    ) -> None:
        builders: dict[
            KnowledgeEntityType, Callable[[int, int], Awaitable[list[KnowledgeDocument]]]
        ] = {
            KnowledgeEntityType.PROJECT: self._project_documents,
            KnowledgeEntityType.TASK: self._task_documents,
            KnowledgeEntityType.DOCUMENT: self._wiki_documents,
            KnowledgeEntityType.COMMENT: self._comment_documents,
            KnowledgeEntityType.ATTACHMENT: self._attachment_documents,
        }
        chunks = await builders[entity_type](project_id, entity_id)
        if not chunks:
            await self._delete(project_id, entity_type, entity_id)
            return
        vectors = await self._embed(chunks)
        await self._delete(project_id, entity_type, entity_id)
        await self._write_batches(project_id, chunks, vectors)

    async def _delete(
        self,
        project_id: int,
        entity_type: KnowledgeEntityType,
        entity_id: int,
    ) -> None:
        if entity_type is KnowledgeEntityType.TASK:
            await self.runtime.qdrant_client.delete_task_context(
                project_id=project_id,
                task_id=entity_id,
            )
            return
        await self.runtime.qdrant_client.delete_entity(
            project_id=project_id,
            entity_type=entity_type.value.lower(),
            entity_id=entity_id,
        )

    async def _project_documents(self, project_id: int, entity_id: int) -> list[KnowledgeDocument]:
        if project_id != entity_id:
            return []
        project = await self.projects_repository.get_by_id(project_id)
        return [build_project_document(project)] if project is not None else []

    async def _task_documents(self, project_id: int, entity_id: int) -> list[KnowledgeDocument]:
        task = await self.tasks_repository.get_by_id(entity_id)
        project = await self.projects_repository.get_by_id(project_id)
        if task is None or project is None or task.project_id != project_id:
            return []
        nodes = await self.wbs_nodes_repository.get_by_project(project_id)
        return [
            build_task_document(
                task,
                project=project,
                wbs_path=(
                    build_wbs_paths(nodes).get(task.wbs_node_id) if task.wbs_node_id else None
                ),
            )
        ]

    async def _wiki_documents(self, project_id: int, entity_id: int) -> list[KnowledgeDocument]:
        document = await self.documents_repository.get_by_id(entity_id)
        if document is None or document.project_id != project_id:
            return []
        return self._document_chunks(document)

    async def _comment_documents(self, project_id: int, entity_id: int) -> list[KnowledgeDocument]:
        comment = await self.comments_repository.get_by_id(entity_id)
        if comment is None:
            return []
        task = await self.tasks_repository.get_by_id(comment.task_id)
        project = await self.projects_repository.get_by_id(project_id)
        if task is None or project is None or task.project_id != project_id:
            return []
        return [build_comment_document(comment, task=task, project=project)]

    async def _attachment_documents(
        self,
        project_id: int,
        entity_id: int,
    ) -> list[KnowledgeDocument]:
        attachment = await self.attachments_repository.get_by_id(entity_id)
        if attachment is None:
            return []
        task = await self.tasks_repository.get_by_id(attachment.task_id)
        project = await self.projects_repository.get_by_id(project_id)
        if task is None or project is None or task.project_id != project_id:
            return []
        return await self._attachment_chunks(attachment, task, project)

    def _document_chunks(self, document) -> list[KnowledgeDocument]:
        return build_document_chunks(
            document,
            target_chars=self.chunk_target_chars,
            overlap_chars=self.chunk_overlap_chars,
        )

    async def _attachment_chunks(self, attachment, task, project) -> list[KnowledgeDocument]:
        try:
            path = self.attachment_storage.resolve(attachment.storage_key)
            content = await asyncio.to_thread(path.read_bytes)
            extracted = await asyncio.to_thread(
                extract_indexable_text,
                attachment.original_name,
                content,
            )
        except Exception:
            logger.warning(
                "⚠️ Вложение id=%s не удалось извлечь, оно пропущено при индексации.",
                attachment.id,
                exc_info=True,
            )
            return []
        if not extracted:
            return []
        return build_attachment_chunks(
            attachment,
            extracted_text=extracted,
            task=task,
            project=project,
            target_chars=self.chunk_target_chars,
            overlap_chars=self.chunk_overlap_chars,
        )

    async def _embed(self, documents: list[KnowledgeDocument]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for index in range(0, len(documents), self.embedding_batch_size):
            batch = documents[index : index + self.embedding_batch_size]
            vectors.extend(
                await self.runtime.embedding_client.get_embeddings(
                    [document.text for document in batch]
                )
            )
        if any(len(vector) != self.runtime.qdrant_client.vector_dim for vector in vectors):
            raise ValueError(
                "Размерность embedding API не совпадает с EMBEDDING_DIM: "
                f"ожидается {self.runtime.qdrant_client.vector_dim}."
            )
        return vectors

    async def _write_batches(
        self,
        project_id: int,
        documents: list[KnowledgeDocument],
        vectors: list[list[float]],
    ) -> None:
        for index in range(0, len(documents), self.embedding_batch_size):
            await self.runtime.qdrant_client.upsert_documents(
                project_id=project_id,
                documents=documents[index : index + self.embedding_batch_size],
                vectors=vectors[index : index + self.embedding_batch_size],
            )

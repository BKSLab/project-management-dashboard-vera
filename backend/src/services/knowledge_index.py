from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from src.clients.embedding import EmbeddingClient
from src.clients.qdrant import ProjectQdrantClient
from src.clients.vision import VisionCapability
from src.db.models.knowledge_index_jobs import (
    KnowledgeEntityType,
    KnowledgeIndexJob,
    KnowledgeIndexOperation,
)
from src.exceptions.knowledge import KnowledgeProviderError
from src.knowledge.documents import (
    KnowledgeDocument,
    build_attachment_chunks,
    build_comment_document,
    build_document_chunks,
    build_milestone_document,
    build_project_document,
    build_task_document,
    build_wbs_paths,
)
from src.knowledge.extract import extract_indexable_text
from src.repositories.documents import DocumentsRepository
from src.repositories.milestones import MilestonesRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.task_attachments import TaskAttachmentsRepository
from src.repositories.task_comments import TaskCommentsRepository
from src.repositories.tasks import TasksRepository
from src.repositories.wbs_nodes import WbsNodesRepository
from src.storage.task_attachments import TaskAttachmentStorage

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PreparedIndexAction:
    """Подготовленное по PostgreSQL действие без открытой DB-сессии."""

    project_id: int
    entity_type: KnowledgeEntityType
    operation: KnowledgeIndexOperation
    entity_id: int | None
    documents: tuple[KnowledgeDocument, ...] = ()


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
        milestones_repository: MilestonesRepository,
        embedding_batch_size: int,
        chunk_target_chars: int,
        chunk_overlap_chars: int,
        extract_max_chars: int,
        embedding_client: EmbeddingClient,
        qdrant_client: ProjectQdrantClient,
        vision: VisionCapability,
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
        self.extract_max_chars = extract_max_chars
        self.milestones_repository = milestones_repository
        self.embedding_client = embedding_client
        self.qdrant_client = qdrant_client
        self.vision = vision

    async def process(self, job: KnowledgeIndexJob) -> int:
        """Готовит и выполняет одно идемпотентное задание очереди."""
        return await self.execute_prepared(await self.prepare(job))

    async def prepare(self, job: KnowledgeIndexJob) -> PreparedIndexAction:
        """Читает PostgreSQL и готовит действие до внешних вызовов."""
        if job.operation is KnowledgeIndexOperation.DELETE_COLLECTION:
            return PreparedIndexAction(
                project_id=job.project_id,
                entity_type=job.entity_type,
                operation=job.operation,
                entity_id=None,
            )
        if job.operation is KnowledgeIndexOperation.REINDEX_PROJECT:
            return PreparedIndexAction(
                project_id=job.project_id,
                entity_type=job.entity_type,
                operation=job.operation,
                entity_id=None,
                documents=tuple(await self._reindex_documents(job.project_id)),
            )
        if job.entity_id is None:
            raise ValueError("Для операции над сущностью отсутствует entity_id.")

        entity_id = int(job.entity_id)
        documents: tuple[KnowledgeDocument, ...] = ()
        if job.operation is KnowledgeIndexOperation.UPSERT:
            builders: dict[
                KnowledgeEntityType, Callable[[int, int], Awaitable[list[KnowledgeDocument]]]
            ] = {
                KnowledgeEntityType.PROJECT: self._project_documents,
                KnowledgeEntityType.TASK: self._task_documents,
                KnowledgeEntityType.DOCUMENT: self._wiki_documents,
                KnowledgeEntityType.COMMENT: self._comment_documents,
                KnowledgeEntityType.ATTACHMENT: self._attachment_documents,
                KnowledgeEntityType.MILESTONE: self._milestone_documents,
            }
            documents = tuple(await builders[job.entity_type](job.project_id, entity_id))
        return PreparedIndexAction(
            project_id=job.project_id,
            entity_type=job.entity_type,
            operation=job.operation,
            entity_id=entity_id,
            documents=documents,
        )

    async def execute_prepared(self, action: PreparedIndexAction) -> int:
        """Выполняет embeddings/Qdrant без обращения к PostgreSQL."""
        if action.operation is KnowledgeIndexOperation.DELETE_COLLECTION:
            await self.qdrant_client.delete_collection(action.project_id)
            return 0
        if action.operation is KnowledgeIndexOperation.REINDEX_PROJECT:
            if not action.documents:
                await self.qdrant_client.delete_collection(action.project_id)
                return 0
            documents = list(action.documents)
            vectors = await self._embed(documents)
            await self.qdrant_client.recreate_collection(action.project_id)
            await self._write_batches(action.project_id, documents, vectors)
            logger.info(
                "✅ Индекс проекта id=%s пересобран: %s chunks.",
                action.project_id,
                len(documents),
            )
            return len(documents)
        if action.entity_id is None:
            raise ValueError("Для операции над сущностью отсутствует entity_id.")
        if action.operation is KnowledgeIndexOperation.DELETE:
            await self._delete(action.project_id, action.entity_type, action.entity_id)
            return 0

        documents = list(action.documents)
        if not documents:
            await self._delete(action.project_id, action.entity_type, action.entity_id)
            return 0
        vectors = await self._embed(documents)
        if action.entity_type is not KnowledgeEntityType.TASK:
            await self._delete(action.project_id, action.entity_type, action.entity_id)
        await self._write_batches(action.project_id, documents, vectors)
        return len(documents)

    async def reindex_project(self, project_id: int) -> int:
        """Полностью пересобирает collection проекта и возвращает число chunks."""
        action = PreparedIndexAction(
            project_id=project_id,
            entity_type=KnowledgeEntityType.PROJECT,
            operation=KnowledgeIndexOperation.REINDEX_PROJECT,
            entity_id=None,
            documents=tuple(await self._reindex_documents(project_id)),
        )
        return await self.execute_prepared(action)

    async def _reindex_documents(self, project_id: int) -> list[KnowledgeDocument]:
        """Загружает и строит все документы проекта без сетевых вызовов."""
        project = await self.projects_repository.get_by_id(project_id)
        if project is None:
            return []

        tasks = await self.tasks_repository.get_by_project(project_id)
        task_ids = {task.id for task in tasks}
        nodes = await self.wbs_nodes_repository.get_by_project(project_id)
        documents = await self.documents_repository.get_by_project(project_id)
        comments = await self.comments_repository.get_for_tasks(task_ids)
        attachments = await self.attachments_repository.get_for_tasks(task_ids)
        milestones = await self.milestones_repository.get_by_project(project_id)

        task_by_id = {task.id: task for task in tasks}
        wbs_paths = build_wbs_paths(nodes)
        chunks: list[KnowledgeDocument] = [build_project_document(project)]
        chunks.extend(build_milestone_document(milestone) for milestone in milestones)
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

        return chunks

    async def upsert_tasks(self, project_id: int, entity_ids: list[int]) -> dict[int, int]:
        """Индексирует несколько задач одним чтением данных и одним embedding-батчем."""
        actions = await self.prepare_task_upserts(project_id, entity_ids)
        return await self.execute_task_upserts(actions)

    async def prepare_task_upserts(
        self,
        project_id: int,
        entity_ids: list[int],
    ) -> list[PreparedIndexAction]:
        """Одним набором запросов готовит TASK UPSERT без сетевых вызовов."""
        unique_ids = list(dict.fromkeys(entity_ids))
        if not unique_ids:
            return []
        project = await self.projects_repository.get_by_id(project_id)
        tasks = await self.tasks_repository.get_by_ids(set(unique_ids))
        nodes = await self.wbs_nodes_repository.get_by_project(project_id)
        paths = build_wbs_paths(nodes)
        tasks_by_id = {
            task.id: task for task in tasks if project is not None and task.project_id == project_id
        }
        return [
            PreparedIndexAction(
                project_id=project_id,
                entity_type=KnowledgeEntityType.TASK,
                operation=KnowledgeIndexOperation.UPSERT,
                entity_id=entity_id,
                documents=(
                    build_task_document(
                        tasks_by_id[entity_id],
                        project=project,
                        wbs_path=(
                            paths.get(tasks_by_id[entity_id].wbs_node_id)
                            if tasks_by_id[entity_id].wbs_node_id
                            else None
                        ),
                    ),
                )
                if entity_id in tasks_by_id
                else (),
            )
            for entity_id in unique_ids
        ]

    async def execute_task_upserts(
        self,
        actions: list[PreparedIndexAction],
    ) -> dict[int, int]:
        """Выполняет подготовленную TASK-пачку одним embedding-вызовом."""
        if not actions:
            return {}
        project_id = actions[0].project_id
        if any(
            action.project_id != project_id
            or action.entity_type is not KnowledgeEntityType.TASK
            or action.operation is not KnowledgeIndexOperation.UPSERT
            or action.entity_id is None
            for action in actions
        ):
            raise ValueError("TASK-пачка содержит несовместимые действия.")
        for action in actions:
            if not action.documents:
                await self.qdrant_client.delete_task_context(
                    project_id=project_id,
                    task_id=action.entity_id,
                )
        documents = [document for action in actions for document in action.documents]
        if documents:
            vectors = await self._embed(documents)
            await self._write_batches(project_id, documents, vectors)
        return {
            action.entity_id: len(action.documents)
            for action in actions
            if action.entity_id is not None
        }

    async def _delete(
        self,
        project_id: int,
        entity_type: KnowledgeEntityType,
        entity_id: int,
    ) -> None:
        if entity_type is KnowledgeEntityType.TASK:
            await self.qdrant_client.delete_task_context(
                project_id=project_id,
                task_id=entity_id,
            )
            return
        await self.qdrant_client.delete_entity(
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

    async def _milestone_documents(
        self,
        project_id: int,
        entity_id: int,
    ) -> list[KnowledgeDocument]:
        milestone = await self.milestones_repository.get_by_id(entity_id)
        if milestone is None or milestone.project_id != project_id:
            return []
        return [build_milestone_document(milestone)]

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
            extracted = await extract_indexable_text(
                attachment.original_name,
                content,
                vision=self.vision,
                max_chars=self.extract_max_chars,
            )
        except KnowledgeProviderError:
            # Недоступность vision-модели — временная: файл разобрать можно,
            # просто не сейчас. Пропустить его здесь значило бы навсегда
            # потерять содержимое, поэтому job уходит на повторную попытку.
            raise
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
                await self.embedding_client.get_embeddings(
                    [document.text for document in batch]
                )
            )
        if any(len(vector) != self.qdrant_client.vector_dim for vector in vectors):
            raise ValueError(
                "Размерность embedding API не совпадает с EMBEDDING_DIM: "
                f"ожидается {self.qdrant_client.vector_dim}."
            )
        return vectors

    async def _write_batches(
        self,
        project_id: int,
        documents: list[KnowledgeDocument],
        vectors: list[list[float]],
    ) -> None:
        for index in range(0, len(documents), self.embedding_batch_size):
            await self.qdrant_client.upsert_documents(
                project_id=project_id,
                documents=documents[index : index + self.embedding_batch_size],
                vectors=vectors[index : index + self.embedding_batch_size],
            )

import logging

from src.db.models.knowledge_index_jobs import (
    KnowledgeEntityType,
    KnowledgeIndexOperation,
)
from src.exceptions.knowledge import KnowledgeIndexJobsRepositoryError
from src.repositories.knowledge_index_jobs import KnowledgeIndexJobsRepository

logger = logging.getLogger(__name__)


class KnowledgeEvents:
    """Best-effort постановка доменных изменений в очередь индексации."""

    def __init__(self, repository: KnowledgeIndexJobsRepository, enabled: bool = True) -> None:
        self.repository = repository
        self.enabled = enabled

    async def upsert(
        self,
        *,
        project_id: int,
        entity_type: KnowledgeEntityType,
        entity_id: int,
    ) -> None:
        await self._enqueue(
            project_id=project_id,
            entity_type=entity_type,
            entity_id=entity_id,
            operation=KnowledgeIndexOperation.UPSERT,
        )

    async def delete(
        self,
        *,
        project_id: int,
        entity_type: KnowledgeEntityType,
        entity_id: int,
    ) -> None:
        await self._enqueue(
            project_id=project_id,
            entity_type=entity_type,
            entity_id=entity_id,
            operation=KnowledgeIndexOperation.DELETE,
        )

    async def reindex_project(self, project_id: int) -> None:
        await self._enqueue(
            project_id=project_id,
            entity_type=KnowledgeEntityType.PROJECT,
            entity_id=None,
            operation=KnowledgeIndexOperation.REINDEX_PROJECT,
        )

    async def delete_collection(self, project_id: int) -> None:
        await self._enqueue(
            project_id=project_id,
            entity_type=KnowledgeEntityType.PROJECT,
            entity_id=None,
            operation=KnowledgeIndexOperation.DELETE_COLLECTION,
        )

    async def _enqueue(
        self,
        *,
        project_id: int,
        entity_type: KnowledgeEntityType,
        entity_id: int | None,
        operation: KnowledgeIndexOperation,
    ) -> None:
        if not self.enabled:
            return
        try:
            await self.repository.enqueue(
                project_id=project_id,
                entity_type=entity_type,
                entity_id=entity_id,
                operation=operation,
            )
        except KnowledgeIndexJobsRepositoryError:
            # Пользовательская операция уже сохранена в PostgreSQL. Недоступность
            # производного AI-контура не должна откатывать основной CRUD.
            logger.warning(
                "⚠️ Изменение сохранено, но не поставлено в очередь знаний: project=%s, "
                "entity=%s:%s, operation=%s.",
                project_id,
                entity_type.value,
                entity_id,
                operation.value,
                exc_info=True,
            )

import logging

from src.db.models.knowledge_index_jobs import (
    KnowledgeEntityType,
    KnowledgeIndexOperation,
)
from src.exceptions.knowledge import (
    KnowledgeEventsServiceError,
    KnowledgeIndexJobsRepositoryError,
)
from src.repositories.knowledge_index_jobs import KnowledgeIndexJobsRepository

logger = logging.getLogger(__name__)


class KnowledgeEvents:
    """Атомарная постановка доменных изменений в outbox индексации."""

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

    async def upsert_many(
        self,
        *,
        project_id: int,
        entity_type: KnowledgeEntityType,
        entity_ids: list[int],
    ) -> None:
        """Добавляет набор UPSERT-заданий в текущую транзакцию."""
        if not self.enabled or not entity_ids:
            return
        try:
            await self.repository.enqueue_many(
                project_id=project_id,
                entity_type=entity_type,
                entity_ids=entity_ids,
                operation=KnowledgeIndexOperation.UPSERT,
            )
        except KnowledgeIndexJobsRepositoryError as error:
            logger.error(
                "❌ Не удалось поставить пакет изменений в очередь знаний: "
                "project=%s, entity=%s, count=%s.",
                project_id,
                entity_type.value,
                len(entity_ids),
                exc_info=True,
            )
            raise KnowledgeEventsServiceError(str(error)) from error

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
        except KnowledgeIndexJobsRepositoryError as error:
            logger.error(
                "❌ Не удалось поставить изменение в очередь знаний: project=%s, "
                "entity=%s:%s, operation=%s.",
                project_id,
                entity_type.value,
                entity_id,
                operation.value,
                exc_info=True,
            )
            raise KnowledgeEventsServiceError(str(error)) from error

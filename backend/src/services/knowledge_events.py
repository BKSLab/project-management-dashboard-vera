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
            await self._enqueue_missing(
                project_id=project_id,
                entity_type=entity_type,
                operation=KnowledgeIndexOperation.UPSERT,
                entity_ids=[str(entity_id) for entity_id in dict.fromkeys(entity_ids)],
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
            await self._enqueue_missing(
                project_id=project_id,
                entity_type=entity_type,
                operation=operation,
                entity_ids=[str(entity_id) if entity_id is not None else None],
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

    async def _enqueue_missing(
        self,
        *,
        project_id: int,
        entity_type: KnowledgeEntityType,
        operation: KnowledgeIndexOperation,
        entity_ids: list[str | None],
    ) -> None:
        """Ставит в очередь только те изменения, которых в ней ещё нет.

        Дедупликация — это оркестрация двух запросов, поэтому она живёт
        здесь, а не внутри репозитория: чтение очереди и запись новых
        заданий остаются отдельными однозапросными операциями.

        Задания не фиксируются отдельным commit: outbox обязан попасть в
        базу той же транзакцией, что и сам бизнес-факт.
        """
        pending = await self.repository.get_pending(
            project_id=project_id,
            entity_type=entity_type,
            operation=operation,
            entity_ids=entity_ids,
        )
        already_queued = {job.entity_id for job in pending}
        missing = [entity_id for entity_id in entity_ids if entity_id not in already_queued]
        if not missing:
            return
        await self.repository.add_many(
            project_id=project_id,
            entity_type=entity_type,
            operation=operation,
            entity_ids=missing,
        )

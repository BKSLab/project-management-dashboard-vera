"""Явные запросы синхронизации поверх общего транзакционного outbox."""

from src.db.models.knowledge_index_jobs import KnowledgeEntityType
from src.exceptions.knowledge import KnowledgeEventsServiceError, KnowledgeIndexJobsRepositoryError
from src.repositories.knowledge_index_jobs import KnowledgeIndexJobsRepository


class KnowledgeEvents:
    """Смысловое изменение и ручная пересборка используют один проектный алгоритм.

    Полноту доменных событий гарантируют триггеры из реестра. Явные вызовы
    сервисов дедуплицируются с ними в той же транзакции.
    """

    def __init__(self, repository: KnowledgeIndexJobsRepository, enabled: bool = True):
        self.repository = repository
        self.enabled = enabled

    async def reindex_project(self, project_id: int) -> None:
        if not self.enabled:
            return
        try:
            await self.repository.add_project_change(project_id)
        except KnowledgeIndexJobsRepositoryError as error:
            raise KnowledgeEventsServiceError(str(error)) from error

    async def upsert(
        self, *, project_id: int, entity_type: KnowledgeEntityType, entity_id: int
    ) -> None:
        await self.reindex_project(project_id)

    async def delete(
        self, *, project_id: int, entity_type: KnowledgeEntityType, entity_id: int
    ) -> None:
        await self.reindex_project(project_id)

    async def delete_collection(self, project_id: int) -> None:
        await self.reindex_project(project_id)

    async def upsert_many(
        self, *, project_id: int, entity_type: KnowledgeEntityType, entity_ids: list[int]
    ) -> None:
        if entity_ids:
            await self.reindex_project(project_id)

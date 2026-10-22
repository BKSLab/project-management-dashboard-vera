"""Смысловой поиск по базе знаний проекта — один сценарий для REST и MCP.

Вектор запроса и поиск в Qdrant — внешние вызовы, поэтому они делаются
вне области базы; сверка найденного с текущим состоянием проекта и
лексический поиск — в короткой области ``ProjectQueryService``. Векторный
поиск недоступен — ответ собирается одним FTS, а не падает.
"""

import logging

from src.exceptions.clients import ClientError
from src.knowledge.catalog import SourceType
from src.services.project_query import ProjectQueryService

logger = logging.getLogger(__name__)


class KnowledgeSearchService:
    """Гибридный поиск по знаниям проекта."""

    def __init__(
        self,
        *,
        query: ProjectQueryService,
        embedding_client,
        qdrant_client,
        enabled: bool,
        score_threshold: float,
        target_chars: int,
        overlap_chars: int,
    ) -> None:
        """Создаёт сервис.

        Args:
            query: Сервис чтения проекта.
            embedding_client: Клиент векторизации запроса.
            qdrant_client: Клиент векторной базы.
            enabled: Включена ли база знаний.
            score_threshold: Порог близости векторного поиска.
            target_chars: Целевой размер фрагмента.
            overlap_chars: Перекрытие фрагментов.
        """
        self.query = query
        self.embedding_client = embedding_client
        self.qdrant_client = qdrant_client
        self.enabled = enabled
        self.score_threshold = score_threshold
        self.target_chars = target_chars
        self.overlap_chars = overlap_chars

    async def search(
        self,
        *,
        project_id: int,
        query: str,
        entity_type: SourceType | None,
        limit: int,
    ) -> list[dict]:
        """Ищет фрагменты по смыслу и по словам.

        Raises:
            ProjectsServiceError: Если прочитать источники проекта не удалось.
        """
        text = query.strip()
        hits: list = []
        if self.enabled:
            try:
                vector = await self.embedding_client.get_embedding(text)
                hits = await self.qdrant_client.search(
                    project_id=project_id,
                    vector=vector,
                    limit=limit,
                    score_threshold=self.score_threshold,
                    entity_type=entity_type,
                )
            except ClientError:
                logger.warning("Семантический поиск недоступен, используется FTS.", exc_info=True)
        return await self.query.search_knowledge(
            project_id=project_id,
            query=text,
            semantic_hits=hits,
            entity_type=entity_type,
            limit=limit,
            target_chars=self.target_chars,
            overlap_chars=self.overlap_chars,
        )

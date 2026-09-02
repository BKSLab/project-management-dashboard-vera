from dataclasses import dataclass

import httpx

from src.clients.embedding import EmbeddingClient
from src.clients.llm import LlmClient
from src.clients.qdrant import ProjectQdrantClient
from src.core.settings import get_settings


@dataclass(slots=True)
class KnowledgeRuntime:
    """Долгоживущие сетевые клиенты AI-контура."""

    http_client: httpx.AsyncClient
    embedding_client: EmbeddingClient
    llm_client: LlmClient
    qdrant_client: ProjectQdrantClient
    payload_indexes_backfill_pending: bool = False


_runtime: KnowledgeRuntime | None = None


def get_knowledge_runtime() -> KnowledgeRuntime:
    """Лениво создаёт общий runtime для HTTP-запросов и worker-а."""
    global _runtime
    if _runtime is None:
        settings = get_settings()
        http_client = httpx.AsyncClient(timeout=float(settings.llm.llm_timeout))
        _runtime = KnowledgeRuntime(
            http_client=http_client,
            embedding_client=EmbeddingClient(
                http_client=http_client,
                url=settings.embedding.embedding_api_url,
                api_key=settings.embedding.embedding_api_key.get_secret_value(),
                model=settings.embedding.embedding_model,
                timeout=settings.embedding.embedding_timeout,
            ),
            llm_client=LlmClient(
                http_client=http_client,
                url=settings.llm.llm_api_url,
                headers=settings.llm.headers,
                model=settings.llm.agent_model,
                timeout=settings.llm.llm_timeout,
                retries=settings.llm.llm_retries,
            ),
            qdrant_client=ProjectQdrantClient(
                url=settings.knowledge.qdrant_url,
                api_key=settings.knowledge.qdrant_api_key.get_secret_value() or None,
                collection_prefix=settings.knowledge.qdrant_collection_prefix,
                vector_dim=settings.embedding.embedding_dim,
            ),
        )
    return _runtime


async def close_knowledge_runtime() -> None:
    """Закрывает внешние клиенты при остановке приложения."""
    global _runtime
    if _runtime is None:
        return
    await _runtime.qdrant_client.close()
    await _runtime.http_client.aclose()
    _runtime = None

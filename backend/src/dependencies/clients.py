"""Фабрики клиентов внешних систем для графа зависимостей запроса.

Каждая фабрика только извлекает уже созданный lifespan ресурс. Здесь
намеренно нет ни одного конструктора сетевого клиента: клиент, созданный
на запрос, обошёл бы общий пул соединений и общий lifecycle.

Сервису передаётся конкретный клиент, а не весь контейнер: зависимость
должна показывать, что именно сервису нужно.
"""

from typing import Annotated

from fastapi import Depends

from src.clients.embedding import EmbeddingClient
from src.clients.llm import LlmClient
from src.clients.qdrant import ProjectQdrantClient
from src.clients.vision import VisionCapability
from src.dependencies.http_client import KnowledgeRuntimeDep


def get_llm_client(runtime: KnowledgeRuntimeDep) -> LlmClient:
    """Возвращает клиент chat completions."""
    return runtime.llm_client


LlmClientDep = Annotated[LlmClient, Depends(get_llm_client)]


def get_embedding_client(runtime: KnowledgeRuntimeDep) -> EmbeddingClient:
    """Возвращает клиент API эмбеддингов."""
    return runtime.embedding_client


EmbeddingClientDep = Annotated[EmbeddingClient, Depends(get_embedding_client)]


def get_qdrant_client(runtime: KnowledgeRuntimeDep) -> ProjectQdrantClient:
    """Возвращает клиент векторного индекса проектов."""
    return runtime.qdrant_client


QdrantClientDep = Annotated[ProjectQdrantClient, Depends(get_qdrant_client)]


def get_vision_capability(runtime: KnowledgeRuntimeDep) -> VisionCapability:
    """Возвращает распознавание изображений либо его выключенную реализацию.

    Возвращается всегда объект: выключенный feature flag выражен no-op
    реализацией того же protocol, а не отсутствием зависимости.
    """
    return runtime.vision


VisionCapabilityDep = Annotated[VisionCapability, Depends(get_vision_capability)]

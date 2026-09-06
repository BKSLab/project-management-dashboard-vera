"""Сборка зависимостей фонового индексатора знаний.

Единственное место, где для worker-а создаются конкретные репозитории и
`KnowledgeIndexService`. Сам worker их не знает: он получает конфигурацию,
сервис очереди, фабрику индексатора и клиентов конструктором, поэтому в
тестах подменяется без monkeypatch модульных globals.

Фабрика индексатора отдаёт сервис вместе с областью сессии: подготовка
идёт внутри области, а внешний вызов — уже после её закрытия. Так
соединение с PostgreSQL не удерживается на время обращения к эмбеддингам
и Qdrant.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.settings import Settings
from src.knowledge.runtime import KnowledgeRuntime
from src.knowledge.worker import IndexServiceFactory, KnowledgeWorker, WorkerConfig
from src.repositories.documents import DocumentsRepository
from src.repositories.knowledge_index_jobs import KnowledgeIndexJobsRepository
from src.repositories.milestones import MilestonesRepository
from src.repositories.project_risks import ProjectRiskRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.task_attachments import TaskAttachmentsRepository
from src.repositories.task_comments import TaskCommentsRepository
from src.repositories.tasks import TasksRepository
from src.repositories.wbs_nodes import WbsNodesRepository
from src.services.db_scope import KnowledgeQueueScope, KnowledgeQueueScopeFactory
from src.services.knowledge_index import KnowledgeIndexService
from src.services.knowledge_queue import KnowledgeQueueService
from src.storage.task_attachments import TaskAttachmentStorage


def build_knowledge_queue_scope(session_factory: async_sessionmaker) -> KnowledgeQueueScopeFactory:
    """Создаёт фабрику коротких областей очереди индексации."""

    @asynccontextmanager
    async def scope() -> AsyncIterator[KnowledgeQueueScope]:
        async with session_factory() as session:
            yield KnowledgeQueueScope(jobs=KnowledgeIndexJobsRepository(session))

    return scope


def build_index_service_factory(
    *,
    session_factory: async_sessionmaker,
    settings: Settings,
    runtime: KnowledgeRuntime,
) -> IndexServiceFactory:
    """Создаёт фабрику индексатора на короткоживущей сессии.

    Сервис остаётся годным и после закрытия области: обращение к БД он
    делает только в фазе подготовки, а внешние вызовы выполняет по уже
    собранному снимку.
    """

    @asynccontextmanager
    async def factory() -> AsyncIterator[KnowledgeIndexService]:
        async with session_factory() as session:
            yield KnowledgeIndexService(
                projects_repository=ProjectsRepository(session),
                risks_repository=ProjectRiskRepository(session),
                tasks_repository=TasksRepository(session),
                wbs_nodes_repository=WbsNodesRepository(session),
                documents_repository=DocumentsRepository(session),
                comments_repository=TaskCommentsRepository(session),
                attachments_repository=TaskAttachmentsRepository(session),
                attachment_storage=TaskAttachmentStorage(settings.app.uploads_path),
                embedding_batch_size=settings.knowledge.knowledge_embedding_batch_size,
                chunk_target_chars=settings.knowledge.knowledge_chunk_target_chars,
                chunk_overlap_chars=settings.knowledge.knowledge_chunk_overlap_chars,
                extract_max_chars=settings.knowledge.knowledge_extract_max_chars,
                milestones_repository=MilestonesRepository(session),
                embedding_client=runtime.embedding_client,
                qdrant_client=runtime.qdrant_client,
                vision=runtime.vision,
            )

    return factory


def build_knowledge_worker(
    *,
    session_factory: async_sessionmaker,
    settings: Settings,
    runtime: KnowledgeRuntime,
) -> KnowledgeWorker:
    """Собирает фоновый индексатор со всеми его зависимостями.

    Args:
        session_factory: Фабрика сессий приложения.
        settings: Настройки приложения.
        runtime: Клиенты AI-контура, созданные lifespan.

    Returns:
        Готовый к запуску worker.
    """
    return KnowledgeWorker(
        config=WorkerConfig.from_settings(settings),
        queue=KnowledgeQueueService(scope=build_knowledge_queue_scope(session_factory)),
        index_service=build_index_service_factory(
            session_factory=session_factory,
            settings=settings,
            runtime=runtime,
        ),
        runtime=runtime,
    )

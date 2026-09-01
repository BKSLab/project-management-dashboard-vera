import asyncio
import logging

from src.core.settings import get_settings
from src.db.session import async_session_factory
from src.knowledge.runtime import get_knowledge_runtime
from src.repositories.documents import DocumentsRepository
from src.repositories.knowledge_index_jobs import KnowledgeIndexJobsRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.task_attachments import TaskAttachmentsRepository
from src.repositories.task_comments import TaskCommentsRepository
from src.repositories.tasks import TasksRepository
from src.repositories.wbs_nodes import WbsNodesRepository
from src.services.knowledge_index import KnowledgeIndexService
from src.storage.task_attachments import TaskAttachmentStorage

logger = logging.getLogger(__name__)


async def run_knowledge_worker(stop_event: asyncio.Event) -> None:
    """Последовательно обрабатывает постоянную очередь до остановки приложения."""
    settings = get_settings()
    async with async_session_factory() as session:
        reset = await KnowledgeIndexJobsRepository(session).reset_processing()
        if reset:
            logger.info("ℹ️ Возвращено в очередь прерванных AI-заданий: %s.", reset)

    while not stop_event.is_set():
        try:
            processed = await _process_next()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.error("❌ Ошибка цикла индексатора знаний.", exc_info=True)
            processed = False
        if not processed:
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=settings.knowledge.knowledge_index_poll_seconds,
                )
            except TimeoutError:
                pass


async def _process_next() -> bool:
    settings = get_settings()
    async with async_session_factory() as session:
        jobs_repository = KnowledgeIndexJobsRepository(session)
        job = await jobs_repository.claim_next()
        if job is None:
            return False

        service = KnowledgeIndexService(
            projects_repository=ProjectsRepository(session),
            tasks_repository=TasksRepository(session),
            wbs_nodes_repository=WbsNodesRepository(session),
            documents_repository=DocumentsRepository(session),
            comments_repository=TaskCommentsRepository(session),
            attachments_repository=TaskAttachmentsRepository(session),
            attachment_storage=TaskAttachmentStorage(settings.app.uploads_path),
            embedding_batch_size=settings.knowledge.knowledge_embedding_batch_size,
            chunk_target_chars=settings.knowledge.knowledge_chunk_target_chars,
            chunk_overlap_chars=settings.knowledge.knowledge_chunk_overlap_chars,
            runtime=get_knowledge_runtime(),
        )
        try:
            await service.process(job)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            logger.warning(
                "⚠️ AI-задание id=%s завершилось ошибкой (попытка %s): %s",
                job.id,
                job.attempts,
                error,
                exc_info=True,
            )
            await jobs_repository.mark_failed(
                job.id,
                str(error),
                settings.knowledge.knowledge_index_max_attempts,
            )
        else:
            await jobs_repository.mark_succeeded(job.id)
        return True

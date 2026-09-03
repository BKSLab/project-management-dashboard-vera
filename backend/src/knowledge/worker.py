import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.settings import Settings, get_settings
from src.db.models.knowledge_index_jobs import (
    KnowledgeEntityType,
    KnowledgeIndexJob,
    KnowledgeIndexOperation,
)
from src.db.session import async_session_factory
from src.exceptions.knowledge import KnowledgeProviderError
from src.knowledge.runtime import KnowledgeRuntime, get_knowledge_runtime
from src.repositories.documents import DocumentsRepository
from src.repositories.knowledge_index_jobs import KnowledgeIndexJobsRepository
from src.repositories.milestones import MilestonesRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.task_attachments import TaskAttachmentsRepository
from src.repositories.task_comments import TaskCommentsRepository
from src.repositories.tasks import TasksRepository
from src.repositories.wbs_nodes import WbsNodesRepository
from src.services.knowledge_index import KnowledgeIndexService, PreparedIndexAction
from src.storage.task_attachments import TaskAttachmentStorage

logger = logging.getLogger(__name__)

RETENTION_CLEANUP_INTERVAL_SECONDS = 60 * 60


@dataclass(frozen=True, slots=True)
class JobExecutionResult:
    """Результат внешней обработки одного задания."""

    job: KnowledgeIndexJob
    chunks_count: int = 0
    error: Exception | None = None


async def run_knowledge_worker(stop_event: asyncio.Event) -> None:
    """Последовательно обрабатывает постоянную очередь до остановки приложения."""
    settings = get_settings()
    runtime = get_knowledge_runtime()
    await _maintain_queue(settings=settings, reset_processing=True)
    loop = asyncio.get_running_loop()
    next_cleanup_at = loop.time() + RETENTION_CLEANUP_INTERVAL_SECONDS

    while not stop_event.is_set():
        try:
            await _backfill_payload_indexes_if_pending(runtime)
            processed = await _process_next()
            if loop.time() >= next_cleanup_at:
                await _maintain_queue(settings=settings, reset_processing=False)
                next_cleanup_at = loop.time() + RETENTION_CLEANUP_INTERVAL_SECONDS
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


async def _backfill_payload_indexes_if_pending(runtime: KnowledgeRuntime) -> None:
    """Повторяет отложенный startup-backfill до первого успешного обращения."""
    if not runtime.payload_indexes_backfill_pending:
        return
    try:
        await runtime.qdrant_client.backfill_payload_indexes()
    except KnowledgeProviderError:
        logger.warning(
            "⚠️ Qdrant недоступен; отложенный backfill payload-индексов будет повторён.",
            exc_info=True,
        )
        return
    runtime.payload_indexes_backfill_pending = False
    logger.info("✅ Отложенный backfill payload-индексов выполнен.")


async def _maintain_queue(*, settings: Settings, reset_processing: bool) -> None:
    """Возвращает прерванные jobs и удаляет старые успешные записи."""
    async with async_session_factory() as session:
        repository = KnowledgeIndexJobsRepository(session)
        if reset_processing:
            reset = await repository.reset_processing()
            if reset:
                logger.info("ℹ️ Возвращено в очередь прерванных AI-заданий: %s.", reset)
        cutoff = datetime.now(UTC) - timedelta(days=settings.knowledge.knowledge_job_retention_days)
        deleted = await repository.delete_succeeded_before(cutoff)
        if deleted:
            logger.info("ℹ️ Удалено старых успешных AI-заданий: %s.", deleted)


async def _process_next() -> bool:
    """Обрабатывает следующую job или совместимую TASK-пачку короткими сессиями."""
    settings = get_settings()
    async with async_session_factory() as session:
        jobs = await KnowledgeIndexJobsRepository(session).claim_next_batch(
            limit=settings.knowledge.knowledge_embedding_batch_size
        )
    if not jobs:
        return False

    first = jobs[0]
    if (
        first.entity_type is KnowledgeEntityType.TASK
        and first.operation is KnowledgeIndexOperation.UPSERT
    ):
        results = await _prepare_and_execute_task_jobs(jobs=jobs, settings=settings)
    else:
        results = [await _prepare_and_execute_job(job=first, settings=settings)]
    await _persist_results(
        results=results,
        max_attempts=settings.knowledge.knowledge_index_max_attempts,
    )
    return True


async def _prepare_and_execute_job(
    *,
    job: KnowledgeIndexJob,
    settings: Settings,
) -> JobExecutionResult:
    """Готовит job в DB-сессии, затем выполняет её после закрытия сессии."""
    try:
        async with async_session_factory() as session:
            service = _build_index_service(session=session, settings=settings)
            action = await service.prepare(job)
        chunks_count = await service.execute_prepared(action)
        return JobExecutionResult(job=job, chunks_count=chunks_count)
    except asyncio.CancelledError:
        raise
    except Exception as error:
        return JobExecutionResult(job=job, error=error)


async def _prepare_and_execute_task_jobs(
    *,
    jobs: list[KnowledgeIndexJob],
    settings: Settings,
) -> list[JobExecutionResult]:
    """Готовит TASK-пачку одним DB-срезом и выполняет её без открытой сессии."""
    try:
        async with async_session_factory() as session:
            service = _build_index_service(session=session, settings=settings)
            actions = await service.prepare_task_upserts(
                project_id=jobs[0].project_id,
                entity_ids=[int(job.entity_id) for job in jobs if job.entity_id is not None],
            )
        if len(actions) != len(jobs):
            raise ValueError("Число подготовленных TASK-действий не совпало с jobs.")
        return await _execute_task_jobs(service=service, jobs=jobs, actions=actions)
    except asyncio.CancelledError:
        raise
    except Exception as error:
        return [JobExecutionResult(job=job, error=error) for job in jobs]


async def _execute_task_jobs(
    *,
    service: KnowledgeIndexService,
    jobs: list[KnowledgeIndexJob],
    actions: list[PreparedIndexAction],
) -> list[JobExecutionResult]:
    """Выполняет TASK-пачку и делит её до одной job при ошибке."""
    try:
        chunks_by_entity = await service.execute_task_upserts(actions)
    except asyncio.CancelledError:
        raise
    except Exception as error:
        if len(jobs) == 1:
            return [JobExecutionResult(job=jobs[0], error=error)]
        middle = len(jobs) // 2
        first_half = await _execute_task_jobs(
            service=service,
            jobs=jobs[:middle],
            actions=actions[:middle],
        )
        second_half = await _execute_task_jobs(
            service=service,
            jobs=jobs[middle:],
            actions=actions[middle:],
        )
        return first_half + second_half

    return [
        JobExecutionResult(
            job=job,
            chunks_count=chunks_by_entity.get(int(job.entity_id), 0),
        )
        for job in jobs
        if job.entity_id is not None
    ]


async def _persist_results(*, results: list[JobExecutionResult], max_attempts: int) -> None:
    """Короткой DB-сессией сохраняет статусы и диагностику выполненных jobs."""
    async with async_session_factory() as session:
        repository = KnowledgeIndexJobsRepository(session)
        for result in results:
            if result.error is None:
                await repository.mark_succeeded(result.job.id, result.chunks_count)
                continue
            logger.warning(
                "⚠️ AI-задание id=%s завершилось ошибкой (попытка %s): %s",
                result.job.id,
                result.job.attempts,
                result.error,
                exc_info=(type(result.error), result.error, result.error.__traceback__),
            )
            await repository.mark_failed(
                result.job.id,
                str(result.error),
                max_attempts,
            )


def _build_index_service(*, session: AsyncSession, settings: Settings) -> KnowledgeIndexService:
    """Собирает индексатор на короткоживущей DB-сессии."""
    return KnowledgeIndexService(
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
        extract_max_chars=settings.knowledge.knowledge_extract_max_chars,
        milestones_repository=MilestonesRepository(session),
        runtime=get_knowledge_runtime(),
    )

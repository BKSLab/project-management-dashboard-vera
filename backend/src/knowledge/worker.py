"""Фоновый индексатор базы знаний.

Worker получает всё нужное конструктором: неизменяемую конфигурацию,
сервис очереди, фабрику индексатора и клиентов AI-контура. Он не читает
глобальные настройки, не ищет клиентов и не знает ни репозиториев, ни
фабрики сессий — их собирает `knowledge/composition.py` из lifespan.

Ключевой инвариант цикла: соединение с PostgreSQL занято только на время
работы с очередью и подготовки задания. Эмбеддинги и Qdrant вызываются
после закрытия области — иначе один медленный внешний вызов удерживал бы
соединение сотни секунд.
"""

import asyncio
import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import timedelta

from src.core.settings import Settings
from src.db.models.knowledge_index_jobs import (
    KnowledgeEntityType,
    KnowledgeIndexJob,
    KnowledgeIndexOperation,
)
from src.exceptions.clients import VectorStoreClientError
from src.knowledge.runtime import KnowledgeRuntime
from src.services.knowledge_index import KnowledgeIndexService, PreparedIndexAction
from src.services.knowledge_queue import JobOutcome, KnowledgeQueueService

logger = logging.getLogger(__name__)

RETENTION_CLEANUP_INTERVAL_SECONDS = 60 * 60

# Фабрика индексатора отдаёт сервис вместе с областью сессии: подготовка
# идёт внутри области, внешний вызов — после её закрытия.
IndexServiceFactory = Callable[[], AbstractAsyncContextManager[KnowledgeIndexService]]


@dataclass(frozen=True, slots=True)
class WorkerConfig:
    """Неизменяемая конфигурация цикла индексации.

    Значения снимаются с настроек один раз при сборке: цикл не должен
    менять поведение на ходу от перечитанной конфигурации.
    """

    poll_seconds: float
    batch_size: int
    max_attempts: int
    retention: timedelta
    cleanup_interval_seconds: float = RETENTION_CLEANUP_INTERVAL_SECONDS

    @classmethod
    def from_settings(cls, settings: Settings) -> "WorkerConfig":
        """Собирает конфигурацию цикла из настроек приложения."""
        knowledge = settings.knowledge
        return cls(
            poll_seconds=knowledge.knowledge_index_poll_seconds,
            batch_size=knowledge.knowledge_embedding_batch_size,
            max_attempts=knowledge.knowledge_index_max_attempts,
            retention=timedelta(days=knowledge.knowledge_job_retention_days),
        )


@dataclass(frozen=True, slots=True)
class JobExecutionResult:
    """Результат внешней обработки одного задания."""

    job: KnowledgeIndexJob
    chunks_count: int = 0
    error: Exception | None = None


class KnowledgeWorker:
    """Последовательно обрабатывает постоянную очередь индексации знаний."""

    def __init__(
        self,
        *,
        config: WorkerConfig,
        queue: KnowledgeQueueService,
        index_service: IndexServiceFactory,
        runtime: KnowledgeRuntime,
    ) -> None:
        self.config = config
        self.queue = queue
        self.index_service = index_service
        self.runtime = runtime

    async def run(self, stop_event: asyncio.Event) -> None:
        """Обрабатывает очередь до остановки приложения.

        Args:
            stop_event: Признак остановки приложения.
        """
        await self.queue.reset_interrupted()
        await self.queue.purge_succeeded(retention=self.config.retention)
        loop = asyncio.get_running_loop()
        next_cleanup_at = loop.time() + self.config.cleanup_interval_seconds

        while not stop_event.is_set():
            try:
                await self._backfill_payload_indexes_if_pending()
                processed = await self._process_next()
                if loop.time() >= next_cleanup_at:
                    await self.queue.purge_succeeded(retention=self.config.retention)
                    next_cleanup_at = loop.time() + self.config.cleanup_interval_seconds
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.error("❌ Ошибка цикла индексатора знаний.", exc_info=True)
                processed = False
            if not processed:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=self.config.poll_seconds)
                except TimeoutError:
                    pass

    async def _backfill_payload_indexes_if_pending(self) -> None:
        """Повторяет отложенный startup-backfill до первого успешного обращения."""
        if not self.runtime.payload_indexes_backfill_pending:
            return
        try:
            await self.runtime.qdrant_client.backfill_payload_indexes()
        except VectorStoreClientError:
            logger.warning(
                "⚠️ Qdrant недоступен; отложенный backfill payload-индексов будет повторён.",
                exc_info=True,
            )
            return
        self.runtime.payload_indexes_backfill_pending = False
        logger.info("✅ Отложенный backfill payload-индексов выполнен.")

    async def _process_next(self) -> bool:
        """Обрабатывает следующую job или совместимую TASK-пачку.

        Returns:
            Была ли обработана хотя бы одна job.
        """
        jobs = await self.queue.claim_next_batch(limit=self.config.batch_size)
        if not jobs:
            return False

        first = jobs[0]
        if (
            first.entity_type is KnowledgeEntityType.TASK
            and first.operation is KnowledgeIndexOperation.UPSERT
        ):
            results = await self._prepare_and_execute_task_jobs(jobs)
        else:
            results = [await self._prepare_and_execute_job(first)]
        await self._persist_results(results)
        return True

    async def _prepare_and_execute_job(self, job: KnowledgeIndexJob) -> JobExecutionResult:
        """Готовит job в DB-области, затем выполняет её после её закрытия."""
        try:
            async with self.index_service() as service:
                action = await service.prepare(job)
            chunks_count = await service.execute_prepared(action)
            return JobExecutionResult(job=job, chunks_count=chunks_count)
        except asyncio.CancelledError:
            # Остановка приложения — не отказ задания: иначе каждый рестарт
            # тратил бы попытку и в итоге переводил job в FAILED.
            raise
        except Exception as error:
            return JobExecutionResult(job=job, error=error)

    async def _prepare_and_execute_task_jobs(
        self,
        jobs: list[KnowledgeIndexJob],
    ) -> list[JobExecutionResult]:
        """Готовит TASK-пачку одним DB-срезом и выполняет её без открытой области."""
        try:
            async with self.index_service() as service:
                actions = await service.prepare_task_upserts(
                    project_id=jobs[0].project_id,
                    entity_ids=[int(job.entity_id) for job in jobs if job.entity_id is not None],
                )
            if len(actions) != len(jobs):
                raise ValueError("Число подготовленных TASK-действий не совпало с jobs.")
            return await self._execute_task_jobs(service=service, jobs=jobs, actions=actions)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            return [JobExecutionResult(job=job, error=error) for job in jobs]

    async def _execute_task_jobs(
        self,
        *,
        service: KnowledgeIndexService,
        jobs: list[KnowledgeIndexJob],
        actions: list[PreparedIndexAction],
    ) -> list[JobExecutionResult]:
        """Выполняет TASK-пачку и делит её до одной job при ошибке.

        Одна плохая задача не должна лишать индексации остальные: пачка
        делится пополам, пока виновник не останется в одиночестве.
        """
        try:
            chunks_by_entity = await service.execute_task_upserts(actions)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if len(jobs) == 1:
                return [JobExecutionResult(job=jobs[0], error=error)]
            middle = len(jobs) // 2
            first_half = await self._execute_task_jobs(
                service=service,
                jobs=jobs[:middle],
                actions=actions[:middle],
            )
            second_half = await self._execute_task_jobs(
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

    async def _persist_results(self, results: list[JobExecutionResult]) -> None:
        """Сохраняет статусы и диагностику выполненных jobs через очередь."""
        outcomes: list[JobOutcome] = []
        for result in results:
            if result.error is None:
                outcomes.append(
                    JobOutcome(job_id=result.job.id, chunks_count=result.chunks_count)
                )
                continue
            logger.warning(
                "⚠️ AI-задание id=%s завершилось ошибкой (попытка %s): %s",
                result.job.id,
                result.job.attempts,
                result.error,
                exc_info=(type(result.error), result.error, result.error.__traceback__),
            )
            outcomes.append(JobOutcome(job_id=result.job.id, error=str(result.error)))
        await self.queue.finish(outcomes, max_attempts=self.config.max_attempts)

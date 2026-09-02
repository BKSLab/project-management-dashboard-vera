import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import Result, and_, delete, exists, func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.db.models.knowledge_index_jobs import (
    KnowledgeEntityType,
    KnowledgeIndexJob,
    KnowledgeIndexOperation,
    KnowledgeIndexStatus,
)
from src.exceptions.knowledge import KnowledgeIndexJobsRepositoryError

logger = logging.getLogger(__name__)

BARRIER_OPERATIONS = (
    KnowledgeIndexOperation.REINDEX_PROJECT,
    KnowledgeIndexOperation.DELETE_COLLECTION,
)


class KnowledgeIndexJobsRepository:
    """Репозиторий постоянной очереди индексации знаний."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def enqueue(
        self,
        *,
        project_id: int,
        entity_type: KnowledgeEntityType,
        operation: KnowledgeIndexOperation,
        entity_id: int | str | None = None,
    ) -> KnowledgeIndexJob:
        """Добавляет задание, не дублируя идентичное ожидающее задание."""
        normalized_entity_id = str(entity_id) if entity_id is not None else None
        try:
            conditions = [
                KnowledgeIndexJob.project_id == project_id,
                KnowledgeIndexJob.entity_type == entity_type,
                KnowledgeIndexJob.operation == operation,
                KnowledgeIndexJob.status == KnowledgeIndexStatus.PENDING,
            ]
            if normalized_entity_id is None:
                conditions.append(KnowledgeIndexJob.entity_id.is_(None))
            else:
                conditions.append(KnowledgeIndexJob.entity_id == normalized_entity_id)
            existing = (
                (
                    await self.db_session.execute(
                        select(KnowledgeIndexJob).where(*conditions).order_by(KnowledgeIndexJob.id)
                    )
                )
                .scalars()
                .first()
            )
            if existing is not None:
                return existing

            job = KnowledgeIndexJob(
                project_id=project_id,
                entity_type=entity_type,
                entity_id=normalized_entity_id,
                operation=operation,
                status=KnowledgeIndexStatus.PENDING,
                available_at=datetime.now(UTC),
            )
            self.db_session.add(job)
            await self.db_session.flush()
            await self.db_session.refresh(job)
            return job
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось поставить задание индексации.", exc_info=True)
            raise KnowledgeIndexJobsRepositoryError(str(error)) from error

    async def enqueue_many(
        self,
        *,
        project_id: int,
        entity_type: KnowledgeEntityType,
        operation: KnowledgeIndexOperation,
        entity_ids: list[int | str],
    ) -> list[KnowledgeIndexJob]:
        """Добавляет набор заданий в текущую транзакцию без отдельного commit."""
        jobs: list[KnowledgeIndexJob] = []
        for entity_id in dict.fromkeys(entity_ids):
            jobs.append(
                await self.enqueue(
                    project_id=project_id,
                    entity_type=entity_type,
                    operation=operation,
                    entity_id=entity_id,
                )
            )
        return jobs

    async def claim_next(self) -> KnowledgeIndexJob | None:
        """Атомарно забирает следующее готовое задание одним worker-ом."""
        jobs = await self.claim_next_batch(limit=1)
        return jobs[0] if jobs else None

    async def claim_next_batch(self, *, limit: int) -> list[KnowledgeIndexJob]:
        """Забирает совместимую пачку TASK UPSERT, соблюдая барьеры проекта."""
        if limit < 1:
            raise ValueError("Размер пачки заданий должен быть положительным.")
        try:
            now = datetime.now(UTC)
            candidate = aliased(KnowledgeIndexJob)
            earlier_barrier = aliased(KnowledgeIndexJob)
            blocked_task = and_(
                candidate.entity_type == KnowledgeEntityType.TASK,
                candidate.operation == KnowledgeIndexOperation.UPSERT,
                exists(
                    select(1).where(
                        earlier_barrier.project_id == candidate.project_id,
                        earlier_barrier.id < candidate.id,
                        earlier_barrier.status.in_(
                            (KnowledgeIndexStatus.PENDING, KnowledgeIndexStatus.PROCESSING)
                        ),
                        earlier_barrier.operation.in_(BARRIER_OPERATIONS),
                    )
                ),
            )
            result: Result = await self.db_session.execute(
                select(candidate)
                .where(
                    candidate.status == KnowledgeIndexStatus.PENDING,
                    candidate.available_at <= now,
                    ~blocked_task,
                )
                .order_by(candidate.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            first = result.scalar_one_or_none()
            if first is None:
                await self.db_session.rollback()
                return []

            jobs = [first]
            if (
                limit > 1
                and first.entity_type is KnowledgeEntityType.TASK
                and first.operation is KnowledgeIndexOperation.UPSERT
            ):
                next_barrier_id = await self.db_session.scalar(
                    select(func.min(KnowledgeIndexJob.id)).where(
                        KnowledgeIndexJob.project_id == first.project_id,
                        KnowledgeIndexJob.id > first.id,
                        KnowledgeIndexJob.status.in_(
                            (KnowledgeIndexStatus.PENDING, KnowledgeIndexStatus.PROCESSING)
                        ),
                        KnowledgeIndexJob.operation.in_(BARRIER_OPERATIONS),
                    )
                )
                conditions = [
                    KnowledgeIndexJob.project_id == first.project_id,
                    KnowledgeIndexJob.entity_type == KnowledgeEntityType.TASK,
                    KnowledgeIndexJob.operation == KnowledgeIndexOperation.UPSERT,
                    KnowledgeIndexJob.status == KnowledgeIndexStatus.PENDING,
                    KnowledgeIndexJob.available_at <= now,
                    KnowledgeIndexJob.id >= first.id,
                ]
                if next_barrier_id is not None:
                    conditions.append(KnowledgeIndexJob.id < next_barrier_id)
                jobs = list(
                    (
                        await self.db_session.execute(
                            select(KnowledgeIndexJob)
                            .where(*conditions)
                            .order_by(KnowledgeIndexJob.id)
                            .with_for_update(skip_locked=True)
                            .limit(limit)
                        )
                    )
                    .scalars()
                    .all()
                )

            for job in jobs:
                job.status = KnowledgeIndexStatus.PROCESSING
                job.attempts += 1
                job.last_error = None
                job.started_at = now
                job.finished_at = None
                job.chunks_count = None
            await self.db_session.commit()
            return jobs
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            raise KnowledgeIndexJobsRepositoryError(str(error)) from error

    async def mark_succeeded(self, job_id: int, chunks_count: int = 0) -> None:
        """Отмечает задание успешно выполненным."""
        await self._set_terminal_state(
            job_id=job_id,
            status=KnowledgeIndexStatus.SUCCEEDED,
            last_error=None,
            chunks_count=chunks_count,
        )

    async def mark_failed(self, job_id: int, error: str, max_attempts: int) -> None:
        """Планирует retry либо переводит исчерпанное задание в FAILED."""
        try:
            job = await self.db_session.get(KnowledgeIndexJob, job_id)
            if job is None:
                return
            job.last_error = error[:4000]
            job.finished_at = datetime.now(UTC)
            job.chunks_count = 0
            if job.attempts >= max_attempts:
                job.status = KnowledgeIndexStatus.FAILED
            else:
                job.status = KnowledgeIndexStatus.PENDING
                delay_seconds = min(2 ** max(job.attempts, 1), 300)
                job.available_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
            await self.db_session.commit()
        except SQLAlchemyError as repository_error:
            await self.db_session.rollback()
            raise KnowledgeIndexJobsRepositoryError(str(repository_error)) from repository_error

    async def reset_processing(self) -> int:
        """Возвращает прерванные при прошлом shutdown задания в очередь."""
        try:
            result = await self.db_session.execute(
                update(KnowledgeIndexJob)
                .where(KnowledgeIndexJob.status == KnowledgeIndexStatus.PROCESSING)
                .values(
                    status=KnowledgeIndexStatus.PENDING,
                    available_at=datetime.now(UTC),
                    started_at=None,
                    finished_at=None,
                    chunks_count=None,
                )
            )
            await self.db_session.commit()
            return int(result.rowcount or 0)
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            raise KnowledgeIndexJobsRepositoryError(str(error)) from error

    async def delete_succeeded_before(self, cutoff: datetime) -> int:
        """Удаляет завершённые успешные задания старше указанной даты."""
        try:
            result = await self.db_session.execute(
                delete(KnowledgeIndexJob).where(
                    KnowledgeIndexJob.status == KnowledgeIndexStatus.SUCCEEDED,
                    func.coalesce(
                        KnowledgeIndexJob.finished_at,
                        KnowledgeIndexJob.updated_at,
                    )
                    < cutoff,
                )
            )
            await self.db_session.commit()
            return int(result.rowcount or 0)
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            raise KnowledgeIndexJobsRepositoryError(str(error)) from error

    async def get_status_counts(self, project_id: int) -> dict[KnowledgeIndexStatus, int]:
        """Возвращает количество заданий проекта по состояниям."""
        try:
            rows = (
                await self.db_session.execute(
                    select(KnowledgeIndexJob.status, func.count(KnowledgeIndexJob.id))
                    .where(KnowledgeIndexJob.project_id == project_id)
                    .group_by(KnowledgeIndexJob.status)
                )
            ).all()
            return {status: int(count) for status, count in rows}
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            raise KnowledgeIndexJobsRepositoryError(str(error)) from error

    async def get_last_error(self, project_id: int) -> str | None:
        """Возвращает последнюю окончательную ошибку индексации проекта."""
        try:
            return (
                await self.db_session.execute(
                    select(KnowledgeIndexJob.last_error)
                    .where(
                        KnowledgeIndexJob.project_id == project_id,
                        KnowledgeIndexJob.status == KnowledgeIndexStatus.FAILED,
                    )
                    .order_by(KnowledgeIndexJob.updated_at.desc(), KnowledgeIndexJob.id.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            raise KnowledgeIndexJobsRepositoryError(str(error)) from error

    async def _set_terminal_state(
        self,
        *,
        job_id: int,
        status: KnowledgeIndexStatus,
        last_error: str | None,
        chunks_count: int,
    ) -> None:
        try:
            job = await self.db_session.get(KnowledgeIndexJob, job_id)
            if job is None:
                return
            job.status = status
            job.last_error = last_error
            job.finished_at = datetime.now(UTC)
            job.chunks_count = chunks_count
            await self.db_session.commit()
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            raise KnowledgeIndexJobsRepositoryError(str(error)) from error

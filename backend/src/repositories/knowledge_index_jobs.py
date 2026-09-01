import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import Result, func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.knowledge_index_jobs import (
    KnowledgeEntityType,
    KnowledgeIndexJob,
    KnowledgeIndexOperation,
    KnowledgeIndexStatus,
)
from src.exceptions.knowledge import KnowledgeIndexJobsRepositoryError

logger = logging.getLogger(__name__)


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
            await self.db_session.commit()
            await self.db_session.refresh(job)
            return job
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось поставить задание индексации.", exc_info=True)
            raise KnowledgeIndexJobsRepositoryError(str(error)) from error

    async def claim_next(self) -> KnowledgeIndexJob | None:
        """Атомарно забирает следующее готовое задание одним worker-ом."""
        try:
            result: Result = await self.db_session.execute(
                select(KnowledgeIndexJob)
                .where(
                    KnowledgeIndexJob.status == KnowledgeIndexStatus.PENDING,
                    KnowledgeIndexJob.available_at <= datetime.now(UTC),
                )
                .order_by(KnowledgeIndexJob.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            job = result.scalar_one_or_none()
            if job is None:
                await self.db_session.rollback()
                return None
            job.status = KnowledgeIndexStatus.PROCESSING
            job.attempts += 1
            job.last_error = None
            await self.db_session.commit()
            await self.db_session.refresh(job)
            return job
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            raise KnowledgeIndexJobsRepositoryError(str(error)) from error

    async def mark_succeeded(self, job_id: int) -> None:
        """Отмечает задание успешно выполненным."""
        await self._set_terminal_state(
            job_id=job_id,
            status=KnowledgeIndexStatus.SUCCEEDED,
            last_error=None,
        )

    async def mark_failed(self, job_id: int, error: str, max_attempts: int) -> None:
        """Планирует retry либо переводит исчерпанное задание в FAILED."""
        try:
            job = await self.db_session.get(KnowledgeIndexJob, job_id)
            if job is None:
                return
            job.last_error = error[:4000]
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
    ) -> None:
        try:
            job = await self.db_session.get(KnowledgeIndexJob, job_id)
            if job is None:
                return
            job.status = status
            job.last_error = last_error
            await self.db_session.commit()
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            raise KnowledgeIndexJobsRepositoryError(str(error)) from error

import logging
from datetime import UTC, datetime

from sqlalchemy import (
    Result,
    and_,
    case,
    delete,
    exists,
    func,
    literal,
    or_,
    select,
    update,
)
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

LAST_ERROR_LIMIT = 4000
MAX_RETRY_DELAY_SECONDS = 300
STATUS_TYPE = KnowledgeIndexJob.__table__.c.status.type

BARRIER_OPERATIONS = (
    KnowledgeIndexOperation.REINDEX_PROJECT,
    KnowledgeIndexOperation.DELETE_COLLECTION,
)


class KnowledgeIndexJobsRepository:
    """Репозиторий постоянной очереди индексации знаний."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def get_pending(
        self,
        *,
        project_id: int,
        entity_type: KnowledgeEntityType,
        operation: KnowledgeIndexOperation,
        entity_ids: list[str | None],
    ) -> list[KnowledgeIndexJob]:
        """Возвращает уже ожидающие задания для перечисленных сущностей.

        Один запрос на весь набор: дедупликация пачки не должна
        превращаться в отдельный SELECT на каждый элемент.

        Args:
            project_id: Проект заданий.
            entity_type: Тип индексируемой сущности.
            operation: Операция индексации.
            entity_ids: Идентификаторы сущностей; ``None`` — задание уровня проекта.

        Returns:
            Ожидающие задания, найденные среди перечисленных сущностей.

        Raises:
            KnowledgeIndexJobsRepositoryError: Если запрос к БД завершился ошибкой.
        """
        if not entity_ids:
            return []
        concrete = [item for item in entity_ids if item is not None]
        matches_entity = []
        if concrete:
            matches_entity.append(KnowledgeIndexJob.entity_id.in_(concrete))
        if any(item is None for item in entity_ids):
            matches_entity.append(KnowledgeIndexJob.entity_id.is_(None))
        try:
            result: Result = await self.db_session.execute(
                select(KnowledgeIndexJob)
                .where(
                    KnowledgeIndexJob.project_id == project_id,
                    KnowledgeIndexJob.entity_type == entity_type,
                    KnowledgeIndexJob.operation == operation,
                    KnowledgeIndexJob.status == KnowledgeIndexStatus.PENDING,
                    or_(*matches_entity),
                )
                .order_by(KnowledgeIndexJob.id)
            )
            return list(result.scalars().all())
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось прочитать очередь индексации.", exc_info=True)
            raise KnowledgeIndexJobsRepositoryError(str(error)) from error

    async def add_many(
        self,
        *,
        project_id: int,
        entity_type: KnowledgeEntityType,
        operation: KnowledgeIndexOperation,
        entity_ids: list[str | None],
        commit: bool = False,
    ) -> list[KnowledgeIndexJob]:
        """Добавляет задания одной вставкой.

        Args:
            project_id: Проект заданий.
            entity_type: Тип индексируемой сущности.
            operation: Операция индексации.
            entity_ids: Идентификаторы сущностей; ``None`` — задание уровня проекта.
            commit: Завершить ли запись самостоятельно. По умолчанию задания
                фиксируются вместе с бизнес-изменением: outbox и сам факт
                должны попасть в базу одной транзакцией.

        Returns:
            Созданные задания.

        Raises:
            KnowledgeIndexJobsRepositoryError: Если запрос к БД завершился ошибкой.
        """
        if not entity_ids:
            return []
        now = datetime.now(UTC)
        jobs = [
            KnowledgeIndexJob(
                project_id=project_id,
                entity_type=entity_type,
                entity_id=entity_id,
                operation=operation,
                status=KnowledgeIndexStatus.PENDING,
                available_at=now,
            )
            for entity_id in entity_ids
        ]
        try:
            self.db_session.add_all(jobs)
            await self.db_session.flush()
            if commit:
                await self.db_session.commit()
            return jobs
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            logger.error("❌ Не удалось поставить задание индексации.", exc_info=True)
            raise KnowledgeIndexJobsRepositoryError(str(error)) from error

    async def claim_next_batch(
        self,
        *,
        limit: int,
        commit: bool = True,
    ) -> list[KnowledgeIndexJob]:
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
            if commit:
                await self.db_session.commit()
            return jobs
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            raise KnowledgeIndexJobsRepositoryError(str(error)) from error

    async def mark_succeeded(
        self,
        job_id: int,
        chunks_count: int = 0,
        *,
        commit: bool = True,
    ) -> None:
        """Отмечает задание успешно выполненным."""
        await self._set_terminal_state(
            job_id=job_id,
            status=KnowledgeIndexStatus.SUCCEEDED,
            last_error=None,
            chunks_count=chunks_count,
            commit=commit,
        )

    async def mark_failed(
        self,
        job_id: int,
        error: str,
        max_attempts: int,
        *,
        commit: bool = True,
    ) -> None:
        """Планирует retry либо переводит исчерпанное задание в FAILED.

        Решение выражено одним UPDATE: отдельное чтение перед записью
        оставляло бы окно, в котором число попыток успевало измениться.

        Args:
            job_id: Идентификатор задания.
            error: Текст ошибки выполнения.
            max_attempts: Предел попыток, после которого задание считается
                окончательно неуспешным.
            commit: Завершить ли запись самостоятельно.

        Raises:
            KnowledgeIndexJobsRepositoryError: Если запрос к БД завершился ошибкой.
        """
        exhausted = KnowledgeIndexJob.attempts >= max_attempts
        # Задержка растёт вдвое с каждой попыткой и упирается в потолок.
        backoff_seconds = func.least(
            func.power(2, func.greatest(KnowledgeIndexJob.attempts, 1)),
            MAX_RETRY_DELAY_SECONDS,
        )
        try:
            await self.db_session.execute(
                update(KnowledgeIndexJob)
                .where(KnowledgeIndexJob.id == job_id)
                .values(
                    last_error=error[:LAST_ERROR_LIMIT],
                    finished_at=datetime.now(UTC),
                    chunks_count=0,
                    # Тип литералов задаётся явно: без него PostgreSQL
                    # получил бы text там, где объявлен enum-столбец.
                    status=case(
                        (exhausted, literal(KnowledgeIndexStatus.FAILED, STATUS_TYPE)),
                        else_=literal(KnowledgeIndexStatus.PENDING, STATUS_TYPE),
                    ),
                    available_at=case(
                        (exhausted, KnowledgeIndexJob.available_at),
                        else_=func.now() + func.make_interval(0, 0, 0, 0, 0, 0, backoff_seconds),
                    ),
                )
                .execution_options(synchronize_session=False)
            )
            if commit:
                await self.db_session.commit()
        except SQLAlchemyError as repository_error:
            await self.db_session.rollback()
            raise KnowledgeIndexJobsRepositoryError(str(repository_error)) from repository_error

    async def reset_processing(self, *, commit: bool = True) -> int:
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
            if commit:
                await self.db_session.commit()
            return int(result.rowcount or 0)
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            raise KnowledgeIndexJobsRepositoryError(str(error)) from error

    async def delete_succeeded_before(self, cutoff: datetime, *, commit: bool = True) -> int:
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
            if commit:
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
        commit: bool = True,
    ) -> None:
        """Переводит задание в конечное состояние одним UPDATE."""
        try:
            await self.db_session.execute(
                update(KnowledgeIndexJob)
                .where(KnowledgeIndexJob.id == job_id)
                .values(
                    status=status,
                    last_error=last_error,
                    finished_at=datetime.now(UTC),
                    chunks_count=chunks_count,
                )
                .execution_options(synchronize_session=False)
            )
            if commit:
                await self.db_session.commit()
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            raise KnowledgeIndexJobsRepositoryError(str(error)) from error

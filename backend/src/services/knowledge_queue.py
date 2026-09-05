"""Очередь заданий индексации знаний как отдельный use case.

Worker раньше сам открывал сессии и создавал репозиторий на каждый шаг
цикла: правило «одна операция очереди — одна короткая транзакция» жило
внутри цикла и повторялось в четырёх местах. Здесь оно описано один раз,
а worker получает готовый сервис конструктором.

Каждый метод открывает свою короткую область: между вызовами очереди
worker обращается к эмбеддингам и Qdrant, и соединение с PostgreSQL всё
это время должно быть свободно.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from src.db.models.knowledge_index_jobs import KnowledgeIndexJob
from src.services.db_scope import KnowledgeQueueScopeFactory

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class JobOutcome:
    """Итог одного задания очереди.

    Ошибка приходит текстом: сервис очереди сохраняет диагностику, но не
    разбирает исключения вызывающего.
    """

    job_id: int
    chunks_count: int = 0
    error: str | None = None


class KnowledgeQueueService:
    """Обслуживает постоянную очередь заданий индексации знаний."""

    def __init__(self, *, scope: KnowledgeQueueScopeFactory) -> None:
        self.scope = scope

    async def reset_interrupted(self) -> int:
        """Возвращает в очередь задания, прерванные прошлой остановкой.

        Returns:
            Число возвращённых заданий.

        Raises:
            KnowledgeIndexJobsRepositoryError: Если запрос к БД не удался.
        """
        async with self.scope() as db:
            reset = await db.jobs.reset_processing()
        if reset:
            logger.info("ℹ️ Возвращено в очередь прерванных AI-заданий: %s.", reset)
        return reset

    async def purge_succeeded(self, *, retention: timedelta) -> int:
        """Удаляет успешные задания старше срока хранения.

        Args:
            retention: Срок, в течение которого выполненные задания хранятся.

        Returns:
            Число удалённых заданий.

        Raises:
            KnowledgeIndexJobsRepositoryError: Если запрос к БД не удался.
        """
        cutoff = datetime.now(UTC) - retention
        async with self.scope() as db:
            deleted = await db.jobs.delete_succeeded_before(cutoff)
        if deleted:
            logger.info("ℹ️ Удалено старых успешных AI-заданий: %s.", deleted)
        return deleted

    async def claim_next_batch(self, *, limit: int) -> list[KnowledgeIndexJob]:
        """Забирает следующее задание или совместимую с ним пачку.

        Args:
            limit: Предельный размер пачки.

        Returns:
            Захваченные задания; пустой список, если очередь пуста.

        Raises:
            KnowledgeIndexJobsRepositoryError: Если запрос к БД не удался.
        """
        async with self.scope() as db:
            return await db.jobs.claim_next_batch(limit=limit)

    async def finish(self, outcomes: Sequence[JobOutcome], *, max_attempts: int) -> None:
        """Сохраняет итоги выполненной пачки одной короткой транзакцией.

        Пачка сохраняется целиком: отдельная сессия на каждое задание
        превратила бы один результат в десятки коротких транзакций.

        Args:
            outcomes: Итоги заданий пачки.
            max_attempts: Предел попыток для неуспешных заданий.

        Raises:
            KnowledgeIndexJobsRepositoryError: Если запрос к БД не удался.
        """
        if not outcomes:
            return
        async with self.scope() as db:
            for outcome in outcomes:
                if outcome.error is None:
                    await db.jobs.mark_succeeded(outcome.job_id, outcome.chunks_count)
                else:
                    await db.jobs.mark_failed(outcome.job_id, outcome.error, max_attempts)

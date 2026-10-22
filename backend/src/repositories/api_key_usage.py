"""Запись и статистика журнала обращений по сервисному ключу .

Статистика считается запросами к сырым строкам по индексу
``(api_key_id, at)``: второй агрегатной таблицы и джоба к ней не заводим.
"""

import logging
import uuid
from datetime import datetime

from sqlalchemy import Result, case, delete, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.api_key_usage import ApiKeyUsage
from src.exceptions.api_keys import ApiKeysRepositoryError

logger = logging.getLogger(__name__)

# Ошибкой считается всё, что не 2xx/3xx: и промах клиента, и сбой сервиса.
_IS_ERROR = case((ApiKeyUsage.status_code >= 400, 1), else_=0)


class ApiKeyUsageRepository:
    """Репозиторий журнала обращений по API-ключу."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def add(self, *, data: dict, commit: bool = True) -> None:
        """Записывает одно обращение.

        Args:
            data: Поля строки журнала.
            commit: Зафиксировать транзакцию сразу.

        Raises:
            ApiKeysRepositoryError: Если запрос к БД завершился ошибкой.
        """
        try:
            self.db_session.add(ApiKeyUsage(**data))
            await self.db_session.flush()
            if commit:
                await self.db_session.commit()
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            raise ApiKeysRepositoryError(str(error)) from error

    async def totals(self, api_key_id: uuid.UUID, *, since: datetime) -> dict:
        """Итоги по ключу за период: запросы, ошибки, объём, средняя длительность."""
        try:
            result: Result = await self.db_session.execute(
                select(
                    func.count().label("requests"),
                    func.coalesce(func.sum(_IS_ERROR), 0).label("errors"),
                    func.coalesce(func.sum(ApiKeyUsage.response_bytes), 0).label("response_bytes"),
                    func.coalesce(func.avg(ApiKeyUsage.duration_ms), 0).label("avg_duration_ms"),
                    func.max(ApiKeyUsage.at).label("last_at"),
                ).where(ApiKeyUsage.api_key_id == api_key_id, ApiKeyUsage.at >= since)
            )
            row = result.one()
            return {
                "requests": int(row.requests or 0),
                "errors": int(row.errors or 0),
                "response_bytes": int(row.response_bytes or 0),
                "avg_duration_ms": int(row.avg_duration_ms or 0),
                "last_at": row.last_at,
            }
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            raise ApiKeysRepositoryError(str(error)) from error

    async def by_day(
        self, api_key_id: uuid.UUID, *, since: datetime, timezone_name: str
    ) -> list[dict]:
        """Разбивка обращений по дням в указанном часовом поясе."""
        day = func.date(func.timezone(timezone_name, ApiKeyUsage.at))
        try:
            result: Result = await self.db_session.execute(
                select(
                    day.label("day"),
                    func.count().label("requests"),
                    func.coalesce(func.sum(_IS_ERROR), 0).label("errors"),
                    func.coalesce(func.sum(ApiKeyUsage.response_bytes), 0).label("response_bytes"),
                )
                .where(ApiKeyUsage.api_key_id == api_key_id, ApiKeyUsage.at >= since)
                .group_by(day)
                .order_by(day)
            )
            return [
                {
                    "day": row.day.isoformat(),
                    "requests": int(row.requests or 0),
                    "errors": int(row.errors or 0),
                    "response_bytes": int(row.response_bytes or 0),
                }
                for row in result.all()
            ]
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            raise ApiKeysRepositoryError(str(error)) from error

    async def by_route(
        self, api_key_id: uuid.UUID, *, since: datetime, limit: int = 30
    ) -> list[dict]:
        """Разбивка по методам REST и инструментам MCP, от частых к редким."""
        try:
            result: Result = await self.db_session.execute(
                select(
                    ApiKeyUsage.channel,
                    ApiKeyUsage.method,
                    ApiKeyUsage.route,
                    func.count().label("requests"),
                    func.coalesce(func.sum(_IS_ERROR), 0).label("errors"),
                    func.coalesce(func.avg(ApiKeyUsage.duration_ms), 0).label("avg_duration_ms"),
                    func.max(ApiKeyUsage.at).label("last_at"),
                )
                .where(ApiKeyUsage.api_key_id == api_key_id, ApiKeyUsage.at >= since)
                .group_by(ApiKeyUsage.channel, ApiKeyUsage.method, ApiKeyUsage.route)
                .order_by(func.count().desc())
                .limit(limit)
            )
            return [
                {
                    "channel": row.channel,
                    "method": row.method,
                    "route": row.route,
                    "requests": int(row.requests or 0),
                    "errors": int(row.errors or 0),
                    "avg_duration_ms": int(row.avg_duration_ms or 0),
                    "last_at": row.last_at,
                }
                for row in result.all()
            ]
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            raise ApiKeysRepositoryError(str(error)) from error

    async def recent(self, api_key_id: uuid.UUID, *, limit: int = 50) -> list[ApiKeyUsage]:
        """Последние обращения ключа."""
        try:
            result: Result = await self.db_session.execute(
                select(ApiKeyUsage)
                .where(ApiKeyUsage.api_key_id == api_key_id)
                .order_by(ApiKeyUsage.at.desc(), ApiKeyUsage.id.desc())
                .limit(limit)
            )
            return list(result.scalars().all())
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            raise ApiKeysRepositoryError(str(error)) from error

    async def delete_older_than(self, *, before: datetime, commit: bool = True) -> int:
        """Удаляет записи журнала старше момента ``before``.

        Returns:
            Сколько строк удалено.
        """
        try:
            result = await self.db_session.execute(
                delete(ApiKeyUsage).where(ApiKeyUsage.at < before)
            )
            if commit:
                await self.db_session.commit()
            return int(result.rowcount or 0)
        except SQLAlchemyError as error:
            await self.db_session.rollback()
            raise ApiKeysRepositoryError(str(error)) from error

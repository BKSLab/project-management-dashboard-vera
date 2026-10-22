"""Журнал обращений по сервисному ключу и статистика .

Сервис пишет строку на каждый запрос REST и вызов инструмента MCP по ключу
и собирает статистику для страницы ключей. Параметры запроса усечены, а
секреты заменены звёздочками: журнал нужен для разбора, а не как копия.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from src.repositories.api_key_usage import ApiKeyUsageRepository
from src.schemas.api_keys import (
    ApiKeyUsageDaySchema,
    ApiKeyUsageRequestSchema,
    ApiKeyUsageRouteSchema,
    ApiKeyUsageSchema,
)

logger = logging.getLogger(__name__)

MAX_QUERY_VALUE_LENGTH = 120
MAX_QUERY_PARAMS = 25
SENSITIVE_PARAMS = frozenset({"api_key", "key", "token", "secret", "password"})


class ApiKeyUsageService:
    """Запись обращений и статистика по ним."""

    def __init__(self, usage_repository: ApiKeyUsageRepository):
        self.usage_repository = usage_repository

    async def record(
        self,
        *,
        api_key_id: uuid.UUID,
        key_prefix: str,
        at: datetime,
        channel: str,
        method: str,
        route: str,
        path: str,
        query: dict,
        actor_login: str | None,
        status_code: int,
        duration_ms: int,
        response_bytes: int | None,
        client_ip: str | None,
    ) -> None:
        """Сохраняет одно обращение.

        Raises:
            ApiKeysRepositoryError: Если запись не удалась (гасит вызывающий).
        """
        await self.usage_repository.add(
            data={
                "api_key_id": api_key_id,
                "key_prefix": key_prefix[:16],
                "at": at,
                "channel": channel[:8],
                "method": method[:8],
                "route": route[:255],
                "path": path[:512],
                "query": sanitize_query(query),
                "actor_login": (actor_login or None) and actor_login[:255],
                "status_code": status_code,
                "duration_ms": duration_ms,
                "response_bytes": response_bytes,
                "client_ip": (client_ip or None) and client_ip[:64],
            }
        )

    async def get_usage(
        self,
        api_key_id: uuid.UUID,
        *,
        days: int = 30,
        recent_limit: int = 50,
        timezone_name: str = "Europe/Moscow",
    ) -> ApiKeyUsageSchema:
        """Собирает статистику по ключу за период."""
        since = datetime.now(UTC) - timedelta(days=days)
        totals = await self.usage_repository.totals(api_key_id, since=since)
        daily = await self.usage_repository.by_day(
            api_key_id, since=since, timezone_name=timezone_name
        )
        routes = await self.usage_repository.by_route(api_key_id, since=since)
        recent = await self.usage_repository.recent(api_key_id, limit=recent_limit)
        return ApiKeyUsageSchema(
            api_key_id=api_key_id,
            days=days,
            **totals,
            daily=[ApiKeyUsageDaySchema(**row) for row in daily],
            routes=[ApiKeyUsageRouteSchema(**row) for row in routes],
            recent=[ApiKeyUsageRequestSchema.model_validate(item) for item in recent],
        )

    async def purge(self, *, retention_days: int) -> int:
        """Удаляет записи журнала старше срока хранения."""
        before = datetime.now(UTC) - timedelta(days=retention_days)
        removed = await self.usage_repository.delete_older_than(before=before)
        if removed:
            logger.info("🧹 Журнал API-ключей: удалено %s строк старше %s.", removed, before.date())
        return removed


def sanitize_query(query: dict) -> dict:
    """Готовит параметры к записи: без секретов, с усечением длинных значений."""
    cleaned: dict[str, str] = {}
    for name, value in list(query.items())[:MAX_QUERY_PARAMS]:
        if str(name).lower() in SENSITIVE_PARAMS:
            cleaned[str(name)] = "***"
            continue
        text = str(value)
        cleaned[str(name)] = (
            text if len(text) <= MAX_QUERY_VALUE_LENGTH else text[:MAX_QUERY_VALUE_LENGTH] + "…"
        )
    return cleaned

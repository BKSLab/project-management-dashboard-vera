"""Redis Pub/Sub, TTL-состояния и распределённые пределы частоты."""

import json
import time
from collections import Counter
from time import monotonic

from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.exceptions.project_chats import ChatRateLimitError, ChatUnavailableError

PRESENCE_SCRIPT = """
local now = tonumber(ARGV[1])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
if ARGV[2] ~= '' then
    if ARGV[3] == 'remove' then redis.call('ZREM', KEYS[1], ARGV[2])
    else redis.call('ZADD', KEYS[1], now + tonumber(ARGV[4]), ARGV[2]) end
end
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[4]) * 2)
local members = redis.call('ZRANGE', KEYS[1], 0, -1)
local users = {}; local seen = {}
for _, member in ipairs(members) do
    local user = string.match(member, '^([^:]+):')
    if user and not seen[user] then table.insert(users, tonumber(user)); seen[user] = true end
end
table.sort(users)
local state = cjson.encode(users)
local previous = redis.call('GET', KEYS[2])
redis.call('SET', KEYS[2], state, 'EX', tonumber(ARGV[4]) * 2)
if previous ~= state then return state end
return false
"""
RATE_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return count
"""


class ChatRedisClient:
    """Получает готовый transport; владельцем соединений является lifespan."""

    def __init__(self, redis: Redis, *, presence_ttl: int, typing_ttl: int):
        self.redis = redis
        self.presence_ttl = presence_ttl
        self.typing_ttl = typing_ttl
        self.metrics = Counter()

    async def publish(self, project_id: int, event: dict) -> None:
        """Публикует уже зафиксированное долговечное либо временное событие."""
        started = monotonic()
        try:
            await self.redis.publish(
                f"project_chat:{project_id}", json.dumps(event, ensure_ascii=False)
            )
            self.metrics["redis_publish_total"] += 1
        except RedisError as error:
            self.metrics["redis_publish_errors_total"] += 1
            raise ChatUnavailableError("Redis publish недоступен.") from error
        finally:
            self.metrics["redis_publish_ms_sum"] += (monotonic() - started) * 1000

    async def rate_limit(
        self, project_id: int, user_id: int, kind: str, *, limit: int, seconds: int = 60
    ):
        """Один лимит на пользователя независимо от числа вкладок и экземпляров."""
        try:
            count = await self.redis.eval(
                RATE_SCRIPT, 1, f"chat_rate:{project_id}:{user_id}:{kind}", seconds
            )
        except RedisError as error:
            raise ChatUnavailableError("Redis rate limiter недоступен.") from error
        if count > limit:
            raise ChatRateLimitError("Превышен лимит действий.")

    async def state(
        self,
        project_id: int,
        user_id: int = 0,
        connection_id: str = "",
        *,
        kind: str = "presence",
        remove: bool = False,
    ):
        """TTL учитывает каждую вкладку отдельно; закрытие одной не скрывает остальные."""
        ttl = self.presence_ttl if kind == "presence" else self.typing_ttl
        key = f"chat_{kind}:{project_id}"
        try:
            changed = await self.redis.eval(
                PRESENCE_SCRIPT,
                2,
                key,
                f"{key}:snapshot",
                time.time(),
                f"{user_id}:{connection_id}" if connection_id else "",
                "remove" if remove else "add",
                ttl,
            )
            if changed is not None:
                ids = json.loads(changed)
                # Lua кодирует пустую таблицу как {}, API всегда возвращает список.
                await self.publish(
                    project_id,
                    {
                        "type": f"{kind}.updated",
                        "project_id": project_id,
                        "data": {"user_ids": ids if isinstance(ids, list) else []},
                    },
                )
        except RedisError as error:
            raise ChatUnavailableError("Redis presence недоступен.") from error

    async def snapshot(self, project_id: int) -> dict:
        """Начальное временное состояние для только что подключившейся вкладки."""
        try:
            values = await self.redis.mget(
                f"chat_presence:{project_id}:snapshot", f"chat_typing:{project_id}:snapshot"
            )
            return {
                kind: (json.loads(value) or []) if value else []
                for kind, value in zip(("presence", "typing"), values, strict=True)
            }
        except RedisError as error:
            raise ChatUnavailableError("Redis snapshot недоступен.") from error

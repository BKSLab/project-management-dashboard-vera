"""Проверенные команды WebSocket используют те же сценарии, что HTTP."""

import logging
from collections import Counter
from time import monotonic

from src.clients.chat_redis import ChatRedisClient
from src.exceptions.project_chats import ChatForbiddenError, ChatValidationError
from src.schemas.project_chats import (
    ChatMessageCreate,
    ChatMessageDelete,
    ChatMessageEdit,
    ChatReactionChange,
    ChatReadUpdate,
)
from src.services.project_chats import ProjectChatService

logger = logging.getLogger(__name__)


class ChatCommandsService:
    """Транспорт только разбирает конверт и доставляет ack/error."""

    def __init__(
        self,
        chat: ProjectChatService,
        redis: ChatRedisClient,
        *,
        send_limit: int,
        action_limit: int,
    ):
        self.chat = chat
        self.redis = redis
        self.send_limit = send_limit
        self.action_limit = action_limit
        self.metrics = Counter()

    async def execute(self, project_id, principal, connection_id, command):
        """Применяет одну команду с ограничениями частоты на всех экземплярах."""
        started = monotonic()
        result = {}
        try:
            result = await self._execute(project_id, principal, connection_id, command)
            self.metrics[f"{command.type}_total"] += 1
            return result
        except Exception:
            self.metrics[f"{command.type}_errors_total"] += 1
            raise
        finally:
            duration = (monotonic() - started) * 1000
            self.metrics[f"{command.type}_ms_sum"] += duration
            if command.type not in {"ping", "typing.started", "typing.stopped"}:
                logger.info(
                    "chat.command project_id=%s actor_id=%s type=%s request_id=%s client_message_id=%s duration_ms=%.1f",
                    project_id,
                    principal.user_id,
                    command.type,
                    command.request_id,
                    result.get("client_message_id"),
                    duration,
                )

    async def _execute(self, project_id, principal, connection_id, command):
        """Общие для HTTP/WS правила команды после транспортной авторизации."""
        user_id = principal.user_id
        if command.type == "ping":
            await self.redis.state(project_id, user_id, connection_id)
            return {"pong": True}
        if not principal.can_write:
            raise ChatForbiddenError("Токен разрешает только чтение.")
        if command.type in {"typing.started", "typing.stopped"}:
            await self.redis.rate_limit(project_id, user_id, "typing", limit=2, seconds=2)
            await self.redis.state(
                project_id,
                user_id,
                connection_id,
                kind="typing",
                remove=command.type == "typing.stopped",
            )
            return {}
        await self.redis.rate_limit(project_id, user_id, "actions", limit=self.action_limit)
        if command.type == "message.send":
            await self.redis.rate_limit(project_id, user_id, "send", limit=self.send_limit)
            result = await self.chat.send(
                project_id, user_id, ChatMessageCreate.model_validate(command.data)
            )
            return {
                "message": result.model_dump(mode="json"),
                "client_message_id": str(result.client_message_id),
            }
        if command.type == "read.set":
            data = ChatReadUpdate.model_validate(command.data)
            return await self.chat.mark_read(project_id, user_id, data.message_id)
        if command.message_id is None:
            raise ChatValidationError("Нужен ID сообщения.")
        if command.type == "message.edit":
            result = await self.chat.edit(
                project_id,
                user_id,
                command.message_id,
                ChatMessageEdit.model_validate(command.data),
            )
        elif command.type == "message.delete":
            data = ChatMessageDelete.model_validate(command.data)
            result = await self.chat.delete(
                project_id, user_id, command.message_id, data.expected_revision
            )
        elif command.type == "reaction.set":
            data = ChatReactionChange.model_validate(command.data)
            result = await self.chat.react(
                project_id, user_id, command.message_id, data.reaction, data.active
            )
        else:
            raise ChatValidationError("Неизвестная команда.")
        return {"message": result.model_dump(mode="json")}

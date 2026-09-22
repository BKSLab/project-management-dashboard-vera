"""Тонкий WebSocket-адаптер без request-scoped авторизации или сессии БД."""

import asyncio
import json
import logging
from contextlib import suppress
from time import monotonic

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from src.dependencies.chat import ChatRuntimeDep
from src.dependencies.settings import SettingsDep
from src.exceptions.auth import AuthServiceError
from src.exceptions.project_chats import ChatServiceError
from src.schemas.project_chats import ChatCommand
from src.utils.api_tokens import extract_bearer_secret

logger = logging.getLogger(__name__)
router = APIRouter()


async def _sender(websocket, connection, send_budget):
    """Единственный writer сокета; очередь не блокирует общий fan-out."""
    while not connection.closed.is_set():
        event = await connection.queue.get()
        if connection.closed.is_set():
            break
        await asyncio.wait_for(websocket.send_json(event), timeout=send_budget)


async def _receive(websocket, connection, runtime, principal, credentials):
    """Разбирает конверт, вызывает сервис и формирует ack/error."""
    hub, config = runtime.hub, runtime.settings
    while not connection.closed.is_set():
        raw = await asyncio.wait_for(
            websocket.receive_text(), timeout=config.chat_heartbeat_seconds * 3
        )
        if len(raw.encode("utf-8")) > config.chat_max_frame_bytes:
            connection.close(1009)
            break
        request_id = None
        started = monotonic()
        try:
            payload = json.loads(raw)
            command = ChatCommand.model_validate(payload)
            request_id = str(command.request_id)
            if command.type not in {"typing.started", "typing.stopped"}:
                principal = await runtime.chat.authenticate(connection.project_id, **credentials)
                if principal.user_id != connection.user_id:
                    connection.close(4401)
                    break
            result = await runtime.commands.execute(
                connection.project_id, principal, connection.id, command
            )
            hub.enqueue(connection, {"type": "ack", "request_id": request_id, "data": result})
            hub.metrics["commands_total"] += 1
            logger.debug(
                "chat.command project=%s user=%s type=%s request=%s duration_ms=%.1f",
                connection.project_id,
                connection.user_id,
                command.type,
                request_id,
                (monotonic() - started) * 1000,
            )
        except (ValueError, ValidationError):
            hub.enqueue(
                connection,
                {
                    "type": "error",
                    "request_id": request_id,
                    "status": 422,
                    "detail": "Проверьте поля команды чата.",
                },
            )
        except (ChatServiceError, AuthServiceError) as error:
            hub.metrics["command_errors_total"] += 1
            hub.enqueue(
                connection,
                {
                    "type": "error",
                    "request_id": request_id,
                    "status": error.status_code,
                    "detail": error.detail,
                },
            )
            if (
                isinstance(error, AuthServiceError)
                or error.status_code == 404
                and command.type == "ping"
            ):
                connection.close(4403)


@router.websocket("/projects/{project_id}/chat/ws", name="projectChatWebSocket")
async def project_chat_socket(
    websocket: WebSocket, project_id: int, runtime: ChatRuntimeDep, settings: SettingsDep
):
    """Подключает текущего участника; PostgreSQL освобождается до accept/receive."""
    origin = websocket.headers.get("origin")
    bearer = extract_bearer_secret(websocket.headers.get("authorization"))
    host = websocket.headers.get("host", "")
    allowed = {*settings.app.cors_origins, f"http://{host}", f"https://{host}"}
    if (origin is not None and origin not in allowed) or (origin is None and not bearer):
        await websocket.close(code=4403)
        return
    credentials = dict(
        session_token=websocket.cookies.get(settings.auth.session_cookie_name), bearer_secret=bearer
    )
    try:
        principal = await runtime.chat.authenticate(project_id, **credentials)
    except (AuthServiceError, ChatServiceError):
        await websocket.close(code=4403)
        return
    if not runtime.ready.is_set():
        await websocket.close(code=1013)
        return
    try:
        connection = runtime.hub.connect(project_id, principal.user_id)
    except ChatServiceError:
        await websocket.close(code=1013)
        return
    tasks = []
    try:
        await websocket.accept()
        await runtime.redis.state(project_id, principal.user_id, connection.id)
        snapshot = await runtime.redis.snapshot(project_id)
        runtime.hub.enqueue(
            connection,
            {
                "type": "ready",
                "project_id": project_id,
                "data": {
                    "heartbeat_seconds": runtime.settings.chat_heartbeat_seconds,
                    "can_write": principal.can_write,
                    **snapshot,
                },
            },
        )
        tasks = [
            asyncio.create_task(
                _sender(websocket, connection, runtime.settings.chat_socket_send_timeout)
            ),
            asyncio.create_task(_receive(websocket, connection, runtime, principal, credentials)),
            asyncio.create_task(connection.closed.wait()),
        ]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            if not task.cancelled():
                task.result()
    except (WebSocketDisconnect, TimeoutError, OSError, ChatServiceError):
        connection.close(1013)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        runtime.hub.disconnect(connection)
        with suppress(ChatServiceError):
            await runtime.redis.state(project_id, principal.user_id, connection.id, remove=True)
            await runtime.redis.state(
                project_id, principal.user_id, connection.id, kind="typing", remove=True
            )
        with suppress(RuntimeError, OSError, WebSocketDisconnect):
            await websocket.close(code=connection.close_code)

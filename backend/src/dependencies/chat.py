"""Адаптер HTTP/WS к ресурсу lifespan; не открывает сессии БД."""

from typing import Annotated

from fastapi import Depends, HTTPException
from starlette.requests import HTTPConnection

from src.dependencies.access import ProjectIdPath
from src.dependencies.auth import AuthorizationHeaderDep, SessionCookieDep, require_write_scope
from src.exceptions.auth import AuthServiceError
from src.exceptions.project_chats import ChatServiceError
from src.realtime.runtime import CHAT_RUNTIME_KEY, ChatRuntime
from src.services.auth import Principal
from src.services.chat_attachments import ChatAttachmentsService
from src.services.chat_commands import ChatCommandsService
from src.services.project_chats import ProjectChatService
from src.utils.api_tokens import extract_bearer_secret


def get_chat_runtime(connection: HTTPConnection) -> ChatRuntime:
    """HTTPConnection подходит и Request, и WebSocket."""
    return getattr(connection.state, CHAT_RUNTIME_KEY)


ChatRuntimeDep = Annotated[ChatRuntime, Depends(get_chat_runtime)]


def get_chat_service(runtime: ChatRuntimeDep) -> ProjectChatService:
    """Возвращает сервис с фабрикой коротких областей."""
    return runtime.chat


def get_chat_files_service(runtime: ChatRuntimeDep) -> ChatAttachmentsService:
    """Файловая выдача не удерживает авторизационные зависимости с БД."""
    return runtime.files


ChatServiceDep = Annotated[ProjectChatService, Depends(get_chat_service)]
ChatFilesServiceDep = Annotated[ChatAttachmentsService, Depends(get_chat_files_service)]


def get_chat_commands_service(runtime: ChatRuntimeDep) -> ChatCommandsService:
    """Общие ограничения частоты и диспетчер операций обоих транспортов."""
    return runtime.commands


ChatCommandsServiceDep = Annotated[ChatCommandsService, Depends(get_chat_commands_service)]


async def require_chat_access(
    project_id: ProjectIdPath,
    service: ChatServiceDep,
    session_cookie: SessionCookieDep = None,
    authorization: AuthorizationHeaderDep = None,
) -> Principal:
    """Проверяет сессию и membership, освобождая БД до HTTP-сценария.

    Guard с request-scoped сессией занял бы второе соединение одновременно
    с коротким scope сервиса. Конкурентные запросы могли бы исчерпать пул.
    """
    try:
        return await service.authenticate(
            project_id,
            session_token=session_cookie,
            bearer_secret=extract_bearer_secret(authorization),
        )
    except (ChatServiceError, AuthServiceError) as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


ChatPrincipalDep = Annotated[Principal, Depends(require_chat_access)]


async def require_chat_write_scope(principal: ChatPrincipalDep) -> Principal:
    """Переиспользует общее правило write scope после короткой авторизации."""
    return await require_write_scope(principal)


ChatWriteScopeDep = Annotated[Principal, Depends(require_chat_write_scope)]

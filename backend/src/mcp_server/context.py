"""Аутентификация и разрешение сущностей для MCP-инструментов.

MCP-слой намеренно не имеет собственной логики доступа: он вызывает ту же
функцию аутентификации, что и HTTP-эндпоинты, и ту же проверку участия в
проекте. Иначе две реализации прав рано или поздно разъедутся, и разойдутся
молча.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import HTTPException
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.api_tokens import ApiTokenScope
from src.db.models.project_members import ProjectMember
from src.db.models.projects import Project
from src.db.models.tasks import Task
from src.db.models.users import User
from src.db.session import async_session_factory
from src.dependencies.auth import AuthenticatedPrincipal, get_principal
from src.exceptions.base import ApplicationError
from src.repositories.api_tokens import ApiTokensRepository
from src.repositories.project_members import ProjectMembersRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.tasks import TasksRepository
from src.repositories.users import UsersRepository

logger = logging.getLogger(__name__)

NOT_AUTHENTICATED = "Требуется действующий токен доступа."
PROJECT_NOT_AVAILABLE = "Проект недоступен."
TASK_NOT_AVAILABLE = "Задача недоступна."
READ_ONLY_TOKEN = "Токен выдан только на чтение."


@dataclass(slots=True)
class ToolContext:
    """Всё, что нужно инструменту: кто спрашивает и через какую сессию."""

    principal: AuthenticatedPrincipal
    session: AsyncSession

    @property
    def user(self) -> User:
        """Возвращает пользователя, от имени которого работает инструмент."""
        return self.principal.user


@asynccontextmanager
async def tool_context(
    context: Context, *, require_write: bool = False
) -> AsyncIterator[ToolContext]:
    """Открывает сессию и определяет пользователя вызова инструмента.

    Args:
        context: Контекст вызова MCP с заголовками транспорта.
        require_write: Требуется ли право изменять данные.

    Yields:
        Пользователь запроса и сессия базы данных.

    Raises:
        ToolError: Если токен не предъявлен, недействителен или недостаточен.
    """
    authorization = _authorization_header(context)
    async with async_session_factory() as session:
        try:
            principal = await get_principal(
                session_cookie=None,
                authorization=authorization,
                users_repository=UsersRepository(session),
                tokens_repository=ApiTokensRepository(session),
            )
        except HTTPException as error:
            # Клиенту не сообщается, чем именно плох токен: отозванный,
            # истёкший и выдуманный неотличимы.
            logger.info("ℹ️ MCP-вызов отклонён на аутентификации: %s.", error.status_code)
            raise ToolError(NOT_AUTHENTICATED) from error

        if require_write and principal.scope is not ApiTokenScope.WRITE:
            raise ToolError(READ_ONLY_TOKEN)
        yield ToolContext(principal=principal, session=session)


async def resolve_project(tools: ToolContext, project_key: str) -> Project:
    """Находит проект по ключу и проверяет доступ пользователя.

    Args:
        tools: Контекст вызова инструмента.
        project_key: Отображаемый ключ проекта, например ``VERA``.

    Returns:
        Проект, доступный пользователю.

    Raises:
        ToolError: Если проект не найден или недоступен.
    """
    normalized = (project_key or "").strip().upper()
    if not normalized:
        raise ToolError(PROJECT_NOT_AVAILABLE)
    try:
        project = await ProjectsRepository(tools.session).get_by_key(normalized)
    except ApplicationError as error:
        raise ToolError("Не удалось получить проект.") from error
    if project is None:
        raise ToolError(PROJECT_NOT_AVAILABLE)
    await _ensure_member(tools, project.id)
    return project


async def resolve_task(tools: ToolContext, task_key: str) -> tuple[Task, Project]:
    """Находит задачу по отображаемому ключу и проверяет доступ.

    Args:
        tools: Контекст вызова инструмента.
        task_key: Ключ задачи вида ``VERA-142``.

    Returns:
        Задача и её проект.

    Raises:
        ToolError: Если ключ некорректен, задача не найдена или недоступна.
    """
    project_key, _, number_text = (task_key or "").strip().rpartition("-")
    if not project_key or not number_text.isdigit():
        raise ToolError("Ключ задачи должен иметь вид VERA-142.")

    project = await resolve_project(tools, project_key)
    try:
        tasks = await TasksRepository(tools.session).get_by_project(project_id=project.id)
    except ApplicationError as error:
        raise ToolError("Не удалось получить задачи проекта.") from error

    number = int(number_text)
    task = next((item for item in tasks if item.number == number), None)
    if task is None:
        raise ToolError(TASK_NOT_AVAILABLE)
    return task, project


async def _ensure_member(tools: ToolContext, project_id: int) -> ProjectMember:
    """Проверяет участие пользователя в проекте тем же правилом, что и HTTP-слой."""
    try:
        membership = await ProjectMembersRepository(tools.session).get(
            project_id=project_id,
            user_id=tools.user.id,
        )
    except ApplicationError as error:
        raise ToolError("Не удалось проверить доступ к проекту.") from error
    if membership is None:
        # Отсутствие доступа и отсутствие проекта неразличимы: иначе перебором
        # выяснялось бы существование чужих проектов.
        raise ToolError(PROJECT_NOT_AVAILABLE)
    return membership


def _authorization_header(context: Context) -> str | None:
    """Достаёт заголовок ``Authorization`` из транспорта MCP."""
    headers = context.headers
    if not headers:
        return None
    for name, value in headers.items():
        if name.lower() == "authorization":
            return value
    return None

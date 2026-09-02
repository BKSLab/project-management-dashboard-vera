"""MCP-сервер трекера: инструменты поверх существующих сервисов.

Собственной бизнес-логики здесь нет. Каждый инструмент проходит ту же
аутентификацию и ту же проверку участия в проекте, что и HTTP-эндпоинты,
и вызывает те же репозитории.
"""

import logging
from collections import Counter
from typing import Annotated

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field
from starlette.applications import Starlette

from src.core.settings import get_settings
from src.exceptions.base import ApplicationError
from src.exceptions.knowledge import KnowledgeProviderError
from src.knowledge.documents import build_wbs_paths
from src.knowledge.runtime import get_knowledge_runtime
from src.mcp_server.context import resolve_project, resolve_task, tool_context
from src.mcp_server.presenters import (
    comment_item,
    project_detail,
    project_summary,
    shorten,
    task_detail,
    task_summary,
)
from src.repositories.project_members import ProjectMembersRepository
from src.repositories.project_stages import ProjectStagesRepository
from src.repositories.projects import ProjectsRepository
from src.repositories.task_comments import TaskCommentsRepository
from src.repositories.tasks import TasksRepository
from src.repositories.wbs_nodes import WbsNodesRepository
from src.services.tasks import build_task_key

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 50
MAX_LIMIT = 200

INSTRUCTIONS = """Трекер задач Vera. Проекты обозначаются ключом вида VERA,
задачи — ключом вида VERA-142. Числовых идентификаторов в контракте нет.
Токен видит только те проекты, в которых состоит его владелец.
Списки всегда ограничены: увеличивайте limit осознанно."""

mcp_server = MCPServer(
    name="vera-tracker",
    title="Трекер задач Vera",
    instructions=INSTRUCTIONS,
    version="1.0.0",
)


@mcp_server.tool(
    name="list_projects",
    title="Список проектов",
    description="Возвращает проекты, доступные владельцу токена, с ключом, названием и статусом.",
)
async def list_projects(context: Context) -> list[dict]:
    """Возвращает доступные пользователю проекты."""
    async with tool_context(context) as tools:
        try:
            allowed = await ProjectMembersRepository(tools.session).get_project_ids_for_user(
                user_id=tools.user.id
            )
            projects = await ProjectsRepository(tools.session).get_all()
        except ApplicationError as error:
            raise ToolError("Не удалось получить список проектов.") from error
        return [project_summary(item) for item in projects if item.id in allowed]


@mcp_server.tool(
    name="get_project",
    title="Карточка проекта",
    description=(
        "Возвращает описание проекта, его стадии и число задач в каждой стадии. "
        "Проект задаётся ключом, например VERA."
    ),
)
async def get_project(
    context: Context,
    project_key: Annotated[str, Field(description="Ключ проекта, например VERA.")],
) -> dict:
    """Возвращает подробную карточку проекта."""
    async with tool_context(context) as tools:
        project = await resolve_project(tools, project_key)
        try:
            stages = await ProjectStagesRepository(tools.session).get_by_project(project.id)
            tasks = await TasksRepository(tools.session).get_by_project(project_id=project.id)
        except ApplicationError as error:
            raise ToolError("Не удалось получить состав проекта.") from error
        counts = Counter(task.stage_id for task in tasks)
        return project_detail(
            project,
            stages=stages,
            task_counts=counts,
            total_tasks=len(tasks),
        )


@mcp_server.tool(
    name="list_tasks",
    title="Список задач проекта",
    description=(
        "Возвращает задачи проекта. Можно отфильтровать по названию стадии, "
        "по исполнителю и оставить только незавершённые."
    ),
)
async def list_tasks(
    context: Context,
    project_key: Annotated[str, Field(description="Ключ проекта, например VERA.")],
    stage: Annotated[str | None, Field(description="Название стадии, например «В работе».")] = None,
    assignee: Annotated[str | None, Field(description="Имя исполнителя целиком.")] = None,
    only_open: Annotated[bool, Field(description="Оставить только незавершённые задачи.")] = False,
    limit: Annotated[int, Field(description="Максимум задач в ответе.", ge=1, le=MAX_LIMIT)] = (
        DEFAULT_LIMIT
    ),
) -> list[dict]:
    """Возвращает задачи проекта с фильтрами."""
    async with tool_context(context) as tools:
        project = await resolve_project(tools, project_key)
        try:
            stages = await ProjectStagesRepository(tools.session).get_by_project(project.id)
            tasks = await TasksRepository(tools.session).get_by_project(project_id=project.id)
        except ApplicationError as error:
            raise ToolError("Не удалось получить задачи проекта.") from error

        stage_by_id = {item.id: item for item in stages}
        if stage is not None:
            wanted = stage.strip().casefold()
            matched = {item.id for item in stages if item.name.casefold() == wanted}
            if not matched:
                known = ", ".join(item.name for item in stages)
                raise ToolError(f"Стадия не найдена. Доступные стадии: {known}.")
            tasks = [task for task in tasks if task.stage_id in matched]
        if assignee is not None:
            wanted_assignee = assignee.strip().casefold()
            tasks = [task for task in tasks if (task.assignee or "").casefold() == wanted_assignee]
        if only_open:
            tasks = [
                task
                for task in tasks
                if not (task.stage_id in stage_by_id and stage_by_id[task.stage_id].is_done_stage)
            ]
        return [
            task_summary(task, project=project, stage=stage_by_id.get(task.stage_id))
            for task in tasks[:limit]
        ]


@mcp_server.tool(
    name="get_task",
    title="Карточка задачи",
    description=(
        "Возвращает задачу целиком: описание, стадию, приоритет, исполнителя, "
        "срок и раздел ИСР. Задача задаётся ключом, например VERA-142."
    ),
)
async def get_task(
    context: Context,
    task_key: Annotated[str, Field(description="Ключ задачи, например VERA-142.")],
) -> dict:
    """Возвращает подробную карточку задачи."""
    async with tool_context(context) as tools:
        task, project = await resolve_task(tools, task_key)
        try:
            stages = await ProjectStagesRepository(tools.session).get_by_project(project.id)
            comments = await TaskCommentsRepository(tools.session).get_for_task(task.id)
            wbs_path = None
            if task.wbs_node_id is not None:
                nodes = await WbsNodesRepository(tools.session).get_by_project(project.id)
                wbs_path = build_wbs_paths(nodes).get(task.wbs_node_id)
        except ApplicationError as error:
            raise ToolError("Не удалось получить задачу.") from error

        stage_by_id = {item.id: item for item in stages}
        return task_detail(
            task,
            project=project,
            stage=stage_by_id.get(task.stage_id),
            wbs_path=wbs_path,
            comment_count=len(comments),
        )


@mcp_server.tool(
    name="list_comments",
    title="Комментарии задачи",
    description="Возвращает комментарии задачи в порядке добавления.",
)
async def list_comments(
    context: Context,
    task_key: Annotated[str, Field(description="Ключ задачи, например VERA-142.")],
    limit: Annotated[
        int,
        Field(description="Максимум комментариев в ответе.", ge=1, le=MAX_LIMIT),
    ] = DEFAULT_LIMIT,
) -> list[dict]:
    """Возвращает комментарии задачи."""
    async with tool_context(context) as tools:
        task, project = await resolve_task(tools, task_key)
        try:
            comments = await TaskCommentsRepository(tools.session).get_for_task(task.id)
        except ApplicationError as error:
            raise ToolError("Не удалось получить комментарии.") from error
        key = build_task_key(project.key, task.number)
        return [comment_item(comment, task_key=key) for comment in comments[:limit]]


@mcp_server.tool(
    name="search_tasks",
    title="Поиск задач по тексту",
    description=(
        "Ищет задачи проекта по названию, описанию, тексту комментариев и номеру. "
        "Это лексический поиск: он точен по словам и номерам задач."
    ),
)
async def search_tasks(
    context: Context,
    project_key: Annotated[str, Field(description="Ключ проекта, например VERA.")],
    query: Annotated[str, Field(description="Поисковый запрос.", min_length=1)],
    limit: Annotated[
        int,
        Field(description="Максимум задач в ответе.", ge=1, le=MAX_LIMIT),
    ] = DEFAULT_LIMIT,
) -> list[dict]:
    """Ищет задачи проекта лексическим поиском PostgreSQL."""
    async with tool_context(context) as tools:
        project = await resolve_project(tools, project_key)
        tasks_repository = TasksRepository(tools.session)
        try:
            matching_ids = await tasks_repository.search_ids(
                project_id=project.id,
                search=query.strip(),
            )
            if not matching_ids:
                return []
            stages = await ProjectStagesRepository(tools.session).get_by_project(project.id)
            tasks = await tasks_repository.get_by_project(
                project_id=project.id,
                task_ids=matching_ids,
            )
        except ApplicationError as error:
            raise ToolError("Не удалось выполнить поиск задач.") from error

        stage_by_id = {item.id: item for item in stages}
        return [
            task_summary(task, project=project, stage=stage_by_id.get(task.stage_id))
            for task in tasks[:limit]
        ]


@mcp_server.tool(
    name="search_project_knowledge",
    title="Смысловой поиск по базе знаний проекта",
    description=(
        "Ищет по смыслу в задачах, документах, комментариях и вложениях проекта "
        "и возвращает фрагменты с указанием источника. Подходит для вопросов "
        "«что решили по…», когда точные слова неизвестны."
    ),
)
async def search_project_knowledge(
    context: Context,
    project_key: Annotated[str, Field(description="Ключ проекта, например VERA.")],
    query: Annotated[str, Field(description="Смысловой запрос.", min_length=2)],
    entity_type: Annotated[
        str | None,
        Field(description="Ограничить тип: project, task, document, comment или attachment."),
    ] = None,
    limit: Annotated[
        int,
        Field(description="Максимум фрагментов в ответе.", ge=1, le=50),
    ] = 10,
) -> list[dict]:
    """Возвращает смысловые фрагменты базы знаний проекта."""
    settings = get_settings()
    if not settings.knowledge.knowledge_enabled:
        raise ToolError("Семантический поиск отключён в конфигурации сервера.")

    async with tool_context(context) as tools:
        project = await resolve_project(tools, project_key)
        runtime = get_knowledge_runtime()
        try:
            vector = await runtime.embedding_client.get_embedding(query.strip())
            hits = await runtime.qdrant_client.search(
                project_id=project.id,
                vector=vector,
                limit=limit,
                score_threshold=settings.knowledge.qdrant_score_threshold,
            )
        except KnowledgeProviderError as error:
            raise ToolError("Семантический поиск временно недоступен.") from error

        wanted = entity_type.strip().lower() if entity_type else None
        results: list[dict] = []
        for hit in hits:
            payload = hit.payload
            hit_type = str(payload.get("entity_type") or "")
            if wanted and hit_type != wanted:
                continue
            results.append(
                {
                    "source": str(payload.get("source_id") or ""),
                    "entity_type": hit_type,
                    "task_key": payload.get("task_key"),
                    "title": payload.get("title"),
                    "score": round(float(hit.score), 3),
                    "excerpt": shorten(str(payload.get("text") or "")),
                }
            )
        return results


def build_mcp_app() -> Starlette:
    """Собирает ASGI-приложение MCP для монтирования в основное приложение.

    Returns:
        Starlette-приложение транспорта Streamable HTTP.
    """
    return mcp_server.streamable_http_app(streamable_http_path="/")


# Инструменты записи регистрируются импортом: декоратор привязывает их к
# тому же серверу. Импорт в конце файла, потому что модуль записи опирается
# на уже созданный ``mcp_server``.
from src.mcp_server import write_tools  # noqa: E402,F401  isort:skip

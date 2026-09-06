"""MCP-сервер трекера: инструменты поверх существующих сервисов.

Собственной бизнес-логики здесь нет. Каждый инструмент проходит ту же
аутентификацию и ту же проверку участия в проекте, что и HTTP-эндпоинты,
и вызывает те же репозитории.
"""

import logging
from datetime import date
from typing import Annotated

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field
from starlette.applications import Starlette

from src.core.settings import Settings
from src.exceptions.base import ApplicationError
from src.exceptions.clients import ClientError
from src.mcp_server.context import resolve_project, resolve_task, tool_context
from src.mcp_server.presenters import (
    comment_item,
    project_detail,
    project_summary,
    shorten,
    task_detail,
    task_summary,
)
from src.services.project_query import UnknownStageError

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 50
MAX_LIMIT = 200

INSTRUCTIONS = """Трекер задач. Проекты обозначаются ключом вида PROJ,
задачи — ключом вида PROJ-142. Числовых идентификаторов в контракте нет.
Токен видит только те проекты, в которых состоит его владелец.
Списки всегда ограничены: увеличивайте limit осознанно."""

mcp_server = MCPServer(
    name="task-tracker",
    title="Трекер задач",
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
            projects = await tools.services.query.list_accessible_projects(
                user_id=tools.principal.user_id
            )
        except ApplicationError as error:
            raise ToolError("Не удалось получить список проектов.") from error
        return [project_summary(item) for item in projects]


@mcp_server.tool(
    name="get_project",
    title="Карточка проекта",
    description=(
        "Возвращает описание проекта, его стадии и число задач в каждой стадии. "
        "Проект задаётся ключом, например PROJ."
    ),
)
async def get_project(
    context: Context,
    project_key: Annotated[str, Field(description="Ключ проекта, например PROJ.")],
) -> dict:
    """Возвращает подробную карточку проекта."""
    async with tool_context(context) as tools:
        project_id = await resolve_project(tools, project_key)
        try:
            overview = await tools.services.query.get_project_overview(project_id=project_id)
        except ApplicationError as error:
            raise ToolError("Не удалось получить состав проекта.") from error
        return project_detail(overview)


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
    project_key: Annotated[str, Field(description="Ключ проекта, например PROJ.")],
    stage: Annotated[str | None, Field(description="Название стадии, например «В работе».")] = None,
    assignee: Annotated[str | None, Field(description="Имя исполнителя целиком.")] = None,
    only_open: Annotated[bool, Field(description="Оставить только незавершённые задачи.")] = False,
    limit: Annotated[int, Field(description="Максимум задач в ответе.", ge=1, le=MAX_LIMIT)] = (
        DEFAULT_LIMIT
    ),
) -> list[dict]:
    """Возвращает задачи проекта с фильтрами."""
    async with tool_context(context) as tools:
        project_id = await resolve_project(tools, project_key)
        try:
            tasks = await tools.services.query.list_tasks(
                project_id=project_id,
                stage_name=stage,
                assignee=assignee,
                only_open=only_open,
                limit=limit,
            )
        except UnknownStageError as error:
            raise ToolError(error.detail) from error
        except ApplicationError as error:
            raise ToolError("Не удалось получить задачи проекта.") from error
        return [task_summary(item) for item in tasks]


@mcp_server.tool(
    name="get_task",
    title="Карточка задачи",
    description=(
        "Возвращает задачу целиком: описание, стадию, приоритет, исполнителя, "
        "срок и раздел ИСР. Задача задаётся ключом, например PROJ-142."
    ),
)
async def get_task(
    context: Context,
    task_key: Annotated[str, Field(description="Ключ задачи, например PROJ-142.")],
) -> dict:
    """Возвращает подробную карточку задачи."""
    async with tool_context(context) as tools:
        resolved = await resolve_task(tools, task_key)
        try:
            details = await tools.services.query.get_task_details(task_id=resolved.task_id)
        except ApplicationError as error:
            raise ToolError("Не удалось получить задачу.") from error
        return task_detail(details)


@mcp_server.tool(
    name="list_comments",
    title="Комментарии задачи",
    description="Возвращает комментарии задачи в порядке добавления.",
)
async def list_comments(
    context: Context,
    task_key: Annotated[str, Field(description="Ключ задачи, например PROJ-142.")],
    limit: Annotated[
        int,
        Field(description="Максимум комментариев в ответе.", ge=1, le=MAX_LIMIT),
    ] = DEFAULT_LIMIT,
) -> list[dict]:
    """Возвращает комментарии задачи."""
    async with tool_context(context) as tools:
        resolved = await resolve_task(tools, task_key)
        try:
            comments = await tools.services.query.list_comments(
                task_id=resolved.task_id,
                task_key=resolved.task_key,
                limit=limit,
            )
        except ApplicationError as error:
            raise ToolError("Не удалось получить комментарии.") from error
        return [comment_item(item) for item in comments]


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
    project_key: Annotated[str, Field(description="Ключ проекта, например PROJ.")],
    query: Annotated[str, Field(description="Поисковый запрос.", min_length=1)],
    limit: Annotated[
        int,
        Field(description="Максимум задач в ответе.", ge=1, le=MAX_LIMIT),
    ] = DEFAULT_LIMIT,
) -> list[dict]:
    """Ищет задачи проекта лексическим поиском PostgreSQL."""
    async with tool_context(context) as tools:
        project_id = await resolve_project(tools, project_key)
        try:
            tasks = await tools.services.query.search_tasks(
                project_id=project_id,
                query=query,
                limit=limit,
            )
        except ApplicationError as error:
            raise ToolError("Не удалось выполнить поиск задач.") from error
        return [task_summary(item) for item in tasks]


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
    project_key: Annotated[str, Field(description="Ключ проекта, например PROJ.")],
    query: Annotated[str, Field(description="Смысловой запрос.", min_length=2)],
    entity_type: Annotated[
        str | None,
        Field(
            description=(
                "Ограничить тип: project, task, document, comment, attachment, milestone или risk. "
                "Текущие оценки и планы риска проверяйте через get_project_risk."
            )
        ),
    ] = None,
    limit: Annotated[
        int,
        Field(description="Максимум фрагментов в ответе.", ge=1, le=50),
    ] = 10,
) -> list[dict]:
    """Возвращает смысловые фрагменты базы знаний проекта."""
    # Аутентификация и проверка доступа выполняются в короткой DB-области,
    # и она закрывается до обращения к эмбеддингам и Qdrant: иначе
    # соединение с PostgreSQL удерживалось бы всё время внешнего вызова.
    async with tool_context(context) as tools:
        if not tools.settings.knowledge.knowledge_enabled:
            raise ToolError("Семантический поиск отключён в конфигурации сервера.")
        project_id = await resolve_project(tools, project_key)
        runtime = tools.runtime
        score_threshold = tools.settings.knowledge.qdrant_score_threshold

    try:
        vector = await runtime.embedding_client.get_embedding(query.strip())
        hits = await runtime.qdrant_client.search(
            project_id=project_id,
            vector=vector,
            limit=limit,
            score_threshold=score_threshold,
        )
    except ClientError as error:
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


@mcp_server.tool(
    name="get_calendar_range",
    title="Временной диапазон проекта",
    description=(
        "Возвращает ограниченный диапазон временной карты: даты задач, вехи, "
        "baseline, drift и рассчитанные backend-причины риска."
    ),
)
async def get_calendar_range(
    context: Context,
    project_key: Annotated[str, Field(description="Ключ проекта, например PROJ.")],
    date_from: Annotated[str, Field(description="Первый день диапазона, ГГГГ-ММ-ДД.")],
    date_to: Annotated[str, Field(description="Последний день диапазона, ГГГГ-ММ-ДД.")],
    today: Annotated[
        str | None,
        Field(description="Текущая локальная дата пользователя, ГГГГ-ММ-ДД."),
    ] = None,
    limit: Annotated[
        int,
        Field(description="Максимум задач в ответе.", ge=1, le=MAX_LIMIT),
    ] = DEFAULT_LIMIT,
) -> dict:
    """Возвращает календарные факты по отображаемому ключу проекта."""
    first = _calendar_date(date_from, "date_from")
    last = _calendar_date(date_to, "date_to")
    current = _calendar_date(today, "today") if today else date.today()
    async with tool_context(context) as tools:
        project_id = await resolve_project(tools, project_key)
        try:
            calendar = await tools.services.calendar.get_range(
                project_id=project_id,
                date_from=first,
                date_to=last,
                today=current,
            )
        except ApplicationError as error:
            raise ToolError(
                _application_message(error, "Не удалось получить календарь.")
            ) from error
        visible_tasks = calendar.tasks[:limit]
        return {
            "project_key": project_key.strip().upper(),
            "range": {
                "date_from": calendar.range.date_from.isoformat(),
                "date_to": calendar.range.date_to.isoformat(),
            },
            "tasks": [
                {
                    "task_key": item.key,
                    "title": item.title,
                    "start_date": item.start_date.isoformat() if item.start_date else None,
                    "due_date": item.due_date.isoformat() if item.due_date else None,
                    "baseline_start_date": (
                        item.baseline_start_date.isoformat() if item.baseline_start_date else None
                    ),
                    "baseline_due_date": (
                        item.baseline_due_date.isoformat() if item.baseline_due_date else None
                    ),
                    "drift_days": item.drift_days,
                    "assignee": item.assignee,
                    "is_done": item.is_done,
                    "risk_level": item.risk_level,
                    "risk_reasons": [
                        reason.model_dump(mode="json", exclude_none=True)
                        for reason in item.risk_reasons
                    ],
                }
                for item in visible_tasks
            ],
            "milestones": [
                {
                    "title": item.title,
                    "due_date": item.due_date.isoformat(),
                    "status": item.status.value,
                    "is_system": item.is_system,
                }
                for item in calendar.milestones
            ],
            "summary": calendar.summary.model_dump(mode="json"),
            "truncated": len(calendar.tasks) > limit,
        }


@mcp_server.tool(
    name="list_tasks_without_due_date",
    title="Задачи проекта без срока",
    description=(
        "Возвращает ограниченный пул задач без due_date, чтобы их можно было "
        "явно запланировать, не загружая весь backlog проекта."
    ),
)
async def list_tasks_without_due_date(
    context: Context,
    project_key: Annotated[str, Field(description="Ключ проекта, например PROJ.")],
    limit: Annotated[
        int,
        Field(description="Максимум задач в ответе.", ge=1, le=MAX_LIMIT),
    ] = DEFAULT_LIMIT,
) -> list[dict]:
    """Возвращает задачи без срока с отображаемыми ключами."""
    async with tool_context(context) as tools:
        project_id = await resolve_project(tools, project_key)
        try:
            page = await tools.services.calendar.get_unscheduled(
                project_id=project_id,
                today=date.today(),
                cursor=None,
                limit=limit,
            )
        except ApplicationError as error:
            raise ToolError(
                _application_message(error, "Не удалось получить задачи без срока.")
            ) from error
        return [
            {
                "task_key": item.key,
                "title": item.title,
                "assignee": item.assignee,
                "priority": item.priority.value,
                "risk_reasons": [
                    reason.model_dump(mode="json", exclude_none=True)
                    for reason in item.risk_reasons
                ],
            }
            for item in page.items
        ]


@mcp_server.tool(
    name="list_milestones",
    title="Вехи проекта",
    description=(
        "Возвращает пользовательские вехи проекта и системную веху дедлайна "
        "проекта без внутренних числовых идентификаторов."
    ),
)
async def list_milestones(
    context: Context,
    project_key: Annotated[str, Field(description="Ключ проекта, например PROJ.")],
    limit: Annotated[
        int,
        Field(description="Максимум пользовательских вех.", ge=1, le=MAX_LIMIT),
    ] = DEFAULT_LIMIT,
) -> list[dict]:
    """Возвращает простые вехи доступного проекта."""
    async with tool_context(context) as tools:
        project_id = await resolve_project(tools, project_key)
        try:
            milestones = await tools.services.query.list_milestones(
                project_id=project_id,
                limit=limit,
            )
        except ApplicationError as error:
            raise ToolError("Не удалось получить вехи проекта.") from error
        return [
            {
                "title": item.title,
                "due_date": item.due_date.isoformat(),
                "status": item.status,
                "description": shorten(item.description),
                "is_system": item.is_system,
            }
            for item in milestones
        ]


def _calendar_date(value: str, field_name: str) -> date:
    """Разбирает date-only аргумент календарного MCP-инструмента."""
    try:
        return date.fromisoformat(value.strip())
    except ValueError as error:
        raise ToolError(f"{field_name} должен быть в формате ГГГГ-ММ-ДД.") from error


def _application_message(error: ApplicationError, fallback: str) -> str:
    """Возвращает безопасное доменное сообщение календарного инструмента."""
    detail = getattr(error, "detail", None)
    return str(detail) if detail else fallback


def build_mcp_app(*, settings: Settings) -> Starlette:
    """Собирает ASGI-приложение MCP для монтирования в основное приложение.

    Настройки приходят из composition root: транспортный модуль не читает
    конфигурацию приложения сам.

    Args:
        settings: Настройки приложения.

    Returns:
        Starlette-приложение транспорта Streamable HTTP.
    """
    app_settings = settings.app
    # Настройки передаются явно: иначе SDK сам включает защиту с allowlist
    # только под localhost, и доступ по адресу сервера отвечает 421.
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=list(app_settings.mcp_allowed_hosts),
        allowed_origins=list(app_settings.mcp_allowed_origins),
    )
    return mcp_server.streamable_http_app(
        streamable_http_path="/",
        transport_security=security,
    )


# Инструменты записи регистрируются импортом: декоратор привязывает их к
# тому же серверу. Импорт в конце файла, потому что модуль записи опирается
# на уже созданный ``mcp_server``.
from src.mcp_server import write_tools  # noqa: E402,F401  isort:skip
from src.mcp_server import risk_tools  # noqa: E402,F401  isort:skip

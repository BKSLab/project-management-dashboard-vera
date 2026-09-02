"""Инструменты MCP, изменяющие данные трекера.

Каждый требует токена с правом записи и вызывает те же сервисы, что и
HTTP-эндпоинты: история задачи, сквозная нумерация и постановка в очередь
индексации знаний работают одинаково независимо от канала.
"""

import logging
from datetime import date
from typing import Annotated

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from src.db.models.project_milestones import ProjectMilestoneStatus
from src.db.models.project_stages import ProjectStage
from src.db.models.tasks import TaskPriority
from src.exceptions.base import ApplicationError
from src.mcp_server.context import ToolContext, resolve_project, resolve_task, tool_context
from src.mcp_server.server import mcp_server
from src.mcp_server.services import (
    build_comments_service,
    build_milestones_service,
    build_tasks_service,
)
from src.repositories.project_stages import ProjectStagesRepository
from src.services.tasks import build_task_key

logger = logging.getLogger(__name__)


@mcp_server.tool(
    name="create_task",
    title="Создать задачу",
    description=(
        "Создаёт задачу в проекте. Без указания стадии задача попадает в первую "
        "стадию доски. Требует токена с правом записи."
    ),
)
async def create_task(
    context: Context,
    project_key: Annotated[str, Field(description="Ключ проекта, например PROJ.")],
    title: Annotated[str, Field(description="Заголовок задачи.", min_length=1, max_length=255)],
    description: Annotated[str | None, Field(description="Описание задачи в Markdown.")] = None,
    stage: Annotated[
        str | None,
        Field(description="Название стадии; по умолчанию первая стадия доски."),
    ] = None,
    priority: Annotated[
        str | None,
        Field(description="Приоритет: LOW, MEDIUM, HIGH или URGENT."),
    ] = None,
    assignee: Annotated[str | None, Field(description="Имя исполнителя.")] = None,
    due_date: Annotated[str | None, Field(description="Срок в формате ГГГГ-ММ-ДД.")] = None,
) -> dict:
    """Создаёт задачу в доступном проекте."""
    async with tool_context(context, require_write=True) as tools:
        project = await resolve_project(tools, project_key)
        payload: dict = {"title": title.strip()}
        if description is not None:
            payload["description_md"] = description
        if stage is not None:
            stages = await _project_stages(tools, project.id)
            payload["stage_id"] = _stage_by_name(stages, stage).id
        if priority is not None:
            payload["priority"] = _parse_priority(priority)
        if assignee is not None:
            payload["assignee"] = assignee.strip() or None
        if due_date is not None:
            payload["due_date"] = _parse_date(due_date)

        try:
            created = await build_tasks_service(tools.session).create_task(
                project_id=project.id,
                data=payload,
            )
        except ApplicationError as error:
            raise ToolError(_domain_message(error, "Не удалось создать задачу.")) from error
        return {"task_key": created.key, "title": created.title, "created": True}


@mcp_server.tool(
    name="update_task",
    title="Изменить задачу",
    description=(
        "Изменяет переданные поля задачи и не трогает остальные. Требует токена с правом записи."
    ),
)
async def update_task(
    context: Context,
    task_key: Annotated[str, Field(description="Ключ задачи, например PROJ-142.")],
    title: Annotated[str | None, Field(description="Новый заголовок.", max_length=255)] = None,
    description: Annotated[str | None, Field(description="Новое описание в Markdown.")] = None,
    priority: Annotated[
        str | None,
        Field(description="Приоритет: LOW, MEDIUM, HIGH или URGENT."),
    ] = None,
    assignee: Annotated[
        str | None,
        Field(description="Имя исполнителя; пустая строка снимает исполнителя."),
    ] = None,
    due_date: Annotated[
        str | None,
        Field(description="Срок в формате ГГГГ-ММ-ДД; пустая строка снимает срок."),
    ] = None,
) -> dict:
    """Изменяет переданные поля задачи."""
    async with tool_context(context, require_write=True) as tools:
        task, _ = await resolve_task(tools, task_key)
        payload: dict = {}
        if title is not None:
            payload["title"] = title.strip()
        if description is not None:
            payload["description_md"] = description
        if priority is not None:
            payload["priority"] = _parse_priority(priority)
        if assignee is not None:
            payload["assignee"] = assignee.strip() or None
        if due_date is not None:
            payload["due_date"] = _parse_date(due_date) if due_date.strip() else None
        if not payload:
            raise ToolError("Не передано ни одного поля для изменения.")

        try:
            updated = await build_tasks_service(tools.session).update_task(
                task_id=task.id,
                data=payload,
            )
        except ApplicationError as error:
            raise ToolError(_domain_message(error, "Не удалось изменить задачу.")) from error
        return {"task_key": updated.key, "updated_fields": sorted(payload)}


@mcp_server.tool(
    name="move_task",
    title="Перевести задачу в другую стадию",
    description=(
        "Переводит задачу в стадию с указанным названием и ставит её в конец стадии. "
        "Требует токена с правом записи."
    ),
)
async def move_task(
    context: Context,
    task_key: Annotated[str, Field(description="Ключ задачи, например PROJ-142.")],
    stage: Annotated[str, Field(description="Название целевой стадии.", min_length=1)],
) -> dict:
    """Переводит задачу в другую стадию доски."""
    async with tool_context(context, require_write=True) as tools:
        task, project = await resolve_task(tools, task_key)
        stages = await _project_stages(tools, project.id)
        target = _stage_by_name(stages, stage)

        try:
            moved = await build_tasks_service(tools.session).move_task(
                task_id=task.id,
                stage_id=target.id,
            )
        except ApplicationError as error:
            raise ToolError(_domain_message(error, "Не удалось переместить задачу.")) from error
        return {"task_key": moved.key, "stage": target.name, "is_done": target.is_done_stage}


@mcp_server.tool(
    name="delete_task",
    title="Удалить задачу",
    description=(
        "Безвозвратно удаляет задачу вместе с её комментариями и файлами. "
        "Требует токена с правом записи и явного подтверждения confirm=true."
    ),
)
async def delete_task(
    context: Context,
    task_key: Annotated[str, Field(description="Ключ задачи, например PROJ-142.")],
    confirm: Annotated[
        bool,
        Field(description="Подтверждение удаления; без него задача не удаляется."),
    ] = False,
) -> dict:
    """Удаляет задачу после явного подтверждения."""
    if not confirm:
        # Удаление необратимо. Отдельное поле подтверждения заставляет модель
        # выразить намерение явно, а не «дотянуться» до инструмента случайно.
        raise ToolError("Удаление требует confirm=true: действие необратимо.")

    async with tool_context(context, require_write=True) as tools:
        task, project = await resolve_task(tools, task_key)
        key = build_task_key(project.key, task.number)

        try:
            await build_tasks_service(tools.session).delete_task(task_id=task.id)
        except ApplicationError as error:
            raise ToolError(_domain_message(error, "Не удалось удалить задачу.")) from error
        return {"task_key": key, "deleted": True}


@mcp_server.tool(
    name="add_comment",
    title="Добавить комментарий к задаче",
    description=(
        "Добавляет комментарий к задаче и фиксирует событие в её истории. "
        "Требует токена с правом записи."
    ),
)
async def add_comment(
    context: Context,
    task_key: Annotated[str, Field(description="Ключ задачи, например PROJ-142.")],
    body: Annotated[str, Field(description="Текст комментария в Markdown.", min_length=1)],
    author: Annotated[
        str | None,
        Field(description="Подпись автора; по умолчанию имя владельца токена."),
    ] = None,
) -> dict:
    """Добавляет комментарий к задаче."""
    async with tool_context(context, require_write=True) as tools:
        task, project = await resolve_task(tools, task_key)
        author_name = (author or "").strip() or _default_author(tools)

        try:
            comment = await build_comments_service(tools.session).add_comment(
                task_id=task.id,
                author_name=author_name,
                body_md=body,
            )
        except ApplicationError as error:
            raise ToolError(_domain_message(error, "Не удалось добавить комментарий.")) from error
        return {
            "task_key": build_task_key(project.key, task.number),
            "author": comment.author_name,
            "created_at": comment.created_at.isoformat(),
        }


@mcp_server.tool(
    name="set_task_dates",
    title="Изменить плановые даты задачи",
    description=(
        "Изменяет start_date и/или due_date задачи через доменный сервис и историю. "
        "Требует токена с правом записи."
    ),
)
async def set_task_dates(
    context: Context,
    task_key: Annotated[str, Field(description="Ключ задачи, например PROJ-142.")],
    start_date: Annotated[
        str | None,
        Field(description="Начало ГГГГ-ММ-ДД; пустая строка снимает начало."),
    ] = None,
    due_date: Annotated[
        str | None,
        Field(description="Завершение ГГГГ-ММ-ДД; пустая строка снимает срок."),
    ] = None,
) -> dict:
    """Меняет только явно переданные календарные поля задачи."""
    async with tool_context(context, require_write=True) as tools:
        task, _ = await resolve_task(tools, task_key)
        payload: dict = {}
        if start_date is not None:
            payload["start_date"] = _parse_date(start_date) if start_date.strip() else None
        if due_date is not None:
            payload["due_date"] = _parse_date(due_date) if due_date.strip() else None
        if not payload:
            raise ToolError("Не передано ни одной даты для изменения.")
        try:
            updated = await build_tasks_service(tools.session).update_task(
                task_id=task.id,
                data=payload,
            )
        except ApplicationError as error:
            raise ToolError(_domain_message(error, "Не удалось изменить даты задачи.")) from error
        return {
            "task_key": updated.key,
            "start_date": updated.start_date.isoformat() if updated.start_date else None,
            "due_date": updated.due_date.isoformat() if updated.due_date else None,
            "updated_fields": sorted(payload),
        }


@mcp_server.tool(
    name="create_milestone",
    title="Создать проектную веху",
    description=(
        "Создаёт простую календарную веху проекта без отдельного workflow. "
        "Требует токена с правом записи."
    ),
)
async def create_milestone(
    context: Context,
    project_key: Annotated[str, Field(description="Ключ проекта, например PROJ.")],
    title: Annotated[str, Field(description="Название вехи.", min_length=1, max_length=255)],
    due_date: Annotated[str, Field(description="Дата вехи в формате ГГГГ-ММ-ДД.")],
    description: Annotated[str | None, Field(description="Описание вехи в Markdown.")] = None,
    status: Annotated[
        str,
        Field(description="Статус PLANNED или ACHIEVED."),
    ] = "PLANNED",
) -> dict:
    """Создаёт пользовательскую веху в доступном проекте."""
    async with tool_context(context, require_write=True) as tools:
        project = await resolve_project(tools, project_key)
        try:
            milestone_status = ProjectMilestoneStatus(status.strip().upper())
        except ValueError as error:
            raise ToolError("Статус вехи должен быть PLANNED или ACHIEVED.") from error
        try:
            created = await build_milestones_service(tools.session).create_milestone(
                project.id,
                {
                    "title": title.strip(),
                    "due_date": _parse_date(due_date),
                    "status": milestone_status,
                    "description_md": description,
                    "wbs_node_id": None,
                },
            )
        except ApplicationError as error:
            raise ToolError(_domain_message(error, "Не удалось создать веху.")) from error
        return {
            "project_key": project.key,
            "title": created.title,
            "due_date": created.due_date.isoformat(),
            "status": created.status.value,
            "created": True,
        }


async def _project_stages(tools: ToolContext, project_id: int) -> list[ProjectStage]:
    """Загружает стадии проекта с единым текстом ошибки."""
    try:
        return await ProjectStagesRepository(tools.session).get_by_project(project_id)
    except ApplicationError as error:
        raise ToolError("Не удалось получить стадии проекта.") from error


def _stage_by_name(stages: list[ProjectStage], name: str) -> ProjectStage:
    """Находит стадию по названию без учёта регистра."""
    wanted = name.strip().casefold()
    for stage in stages:
        if stage.name.casefold() == wanted:
            return stage
    known = ", ".join(item.name for item in stages)
    raise ToolError(f"Стадия не найдена. Доступные стадии: {known}.")


def _parse_priority(value: str) -> TaskPriority:
    """Разбирает приоритет и подсказывает допустимые значения."""
    try:
        return TaskPriority(value.strip().upper())
    except ValueError as error:
        allowed = ", ".join(item.value for item in TaskPriority)
        raise ToolError(f"Приоритет должен быть одним из: {allowed}.") from error


def _parse_date(value: str) -> date:
    """Разбирает дату в формате ISO."""
    try:
        return date.fromisoformat(value.strip())
    except ValueError as error:
        raise ToolError("Дата должна быть в формате ГГГГ-ММ-ДД.") from error


def _default_author(tools: ToolContext) -> str:
    """Возвращает подпись автора по имени владельца токена."""
    user = tools.user
    parts = [user.last_name, user.first_name]
    return " ".join(part for part in parts if part) or user.username


def _domain_message(error: ApplicationError, fallback: str) -> str:
    """Отдаёт доменное сообщение об ошибке, не раскрывая внутренних деталей."""
    detail = getattr(error, "detail", None)
    return str(detail) if detail else fallback

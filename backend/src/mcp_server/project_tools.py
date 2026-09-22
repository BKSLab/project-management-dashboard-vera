"""Полный каталог действий через общие сценарии проектного чата."""

import json
from typing import Annotated, Any
from uuid import UUID

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp.shared.exceptions import MCPError
from pydantic import BaseModel, Field

from src.agent.action_catalog import PROJECT_ACTIONS
from src.agent.tools import AgentToolContext
from src.exceptions.agent_tools import AgentToolsServiceError
from src.mcp_server.context import resolve_project, tool_context
from src.mcp_server.server import mcp_server


class ActionApproval(BaseModel):
    """Отдельный ответ участника в интерфейсе MCP-клиента."""

    approve: bool = Field(description="Выполнить указанное действие с показанными параметрами?")


@mcp_server.tool(
    name="list_project_tools",
    title="Каталог действий проекта",
    description="Все операции проектного агента. Без names возвращает краткий каталог; names раскрывает до 8 точных схем. Числовые ID берутся из ответов этих инструментов.",
)
async def list_project_tools(
    context: Context,
    project_key: Annotated[str, Field(description="Ключ текущего проекта.")],
    names: Annotated[
        list[str] | None, Field(max_length=8, description="Имена для получения схем аргументов.")
    ] = None,
) -> dict:
    """Возвращает общий реестр с учётом прав токена."""
    async with tool_context(context) as tools:
        await resolve_project(tools, project_key)
        definitions = {item.name: item for item in PROJECT_ACTIONS}
        if names and any(name not in definitions for name in names):
            raise ToolError("Неизвестное имя инструмента.")
        return {
            "tools": [
                {
                    "name": item.name,
                    "title": item.title,
                    "description": item.description,
                    "mutating": item.mutating,
                    "requires_confirmation": item.requires_confirmation,
                    "owner_only": item.owner_only,
                    **({"parameters": item.parameters.model_json_schema()} if names else {}),
                }
                for item in PROJECT_ACTIONS
                if (not names or item.name in names)
                and (tools.principal.can_write or not item.mutating)
            ]
        }


@mcp_server.tool(
    name="execute_project_tool",
    title="Выполнить действие проекта",
    description="Исполняет операцию из list_project_tools с общей проверкой проекта и прав. Для записи передавайте стабильный UUID request_id и повторяйте его при сетевом сбое. Удаления и массовые действия запрашивают решение участника через MCP elicitation; параметра самоподтверждения нет.",
)
async def execute_project_tool(
    context: Context,
    project_key: Annotated[str, Field(description="Ключ текущего проекта.")],
    name: Annotated[str, Field(max_length=64, description="Имя из каталога проектных действий.")],
    arguments: Annotated[
        dict[str, Any], Field(description="Параметры по точной схеме инструмента.")
    ],
    request_id: Annotated[
        UUID | None,
        Field(description="Стабильный ключ повторной записи; обязателен для изменений."),
    ] = None,
) -> dict:
    """Применяет то же атомарное действие, что проектный чат."""
    definition = next((item for item in PROJECT_ACTIONS if item.name == name), None)
    if definition is None:
        raise ToolError("Неизвестное имя инструмента.")
    # Закрываем область аутентификации до ожидания решения человека.
    async with tool_context(context, require_write=definition.mutating) as tools:
        project_id = await resolve_project(tools, project_key)
        actor = AgentToolContext(
            project_id=project_id,
            user_id=tools.principal.user_id,
            can_write=tools.principal.can_write,
            request_id=request_id,
        )
        actions = tools.services.actions
    try:
        response = await actions.execute(context=actor, name=name, arguments=arguments)
        action = response.get("action")
        if action is not None and action["status"] == "pending":
            review = {
                "project_key": project_key,
                "title": action["title"],
                "arguments": action["arguments"],
                "preview": action["result"].get("preview"),
            }
            try:
                answer = await context.elicit(
                    message=json.dumps(review, ensure_ascii=False), schema=ActionApproval
                )
            except MCPError:
                return {
                    **response,
                    "message": "Действие не выполнено. Для решения участника нужен MCP-клиент с поддержкой form elicitation. Повторите тот же request_id в таком клиенте.",
                }
            if answer.action == "cancel":
                return response
            decision = "approve" if answer.action == "accept" and answer.data.approve else "reject"
            # Повторно проверяем токен после ожидания, включая отзыв и срок действия.
            async with tool_context(context, require_write=True) as current:
                await resolve_project(current, project_key)
                if current.principal.user_id != actor.user_id:
                    raise ToolError("Пользователь вызова изменился.")
            decided = await actions.decide(
                context=actor, action_id=UUID(action["id"]), decision=decision
            )
            return {"action": decided.model_dump(mode="json")}
        return response
    except AgentToolsServiceError as error:
        raise ToolError(error.detail) from error

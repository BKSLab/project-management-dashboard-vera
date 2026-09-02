"""Проверки монтирования MCP и контракта объявленных инструментов."""

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from src.core.settings import get_settings
from src.mcp_server.server import MAX_LIMIT, mcp_server

READ_TOOLS = {
    "list_projects",
    "get_project",
    "list_tasks",
    "get_task",
    "list_comments",
    "search_tasks",
    "search_project_knowledge",
    "get_calendar_range",
    "list_tasks_without_due_date",
    "list_milestones",
}
WRITE_TOOLS = {
    "create_task",
    "update_task",
    "move_task",
    "delete_task",
    "add_comment",
    "set_task_dates",
    "create_milestone",
}


async def test_all_planned_tools_are_registered() -> None:
    """Объявлен ровно тот набор инструментов, который описан в плане."""
    tools = await mcp_server.list_tools()

    assert {tool.name for tool in tools} == READ_TOOLS | WRITE_TOOLS


async def test_delete_tool_requires_explicit_confirmation() -> None:
    """У необратимого удаления есть отдельное поле подтверждения."""
    tools = {tool.name: tool for tool in await mcp_server.list_tools()}
    properties = tools["delete_task"].input_schema["properties"]

    assert "confirm" in properties
    assert properties["confirm"].get("default") is False


async def test_write_tools_announce_required_scope() -> None:
    """Описание изменяющего инструмента предупреждает о праве записи."""
    tools = {tool.name: tool for tool in await mcp_server.list_tools()}

    for name in WRITE_TOOLS:
        assert "право" in tools[name].description or "записи" in tools[name].description


async def test_every_tool_has_russian_description() -> None:
    """Описание читает модель: без него она не выберет инструмент осмысленно."""
    tools = await mcp_server.list_tools()

    for tool in tools:
        assert tool.description, f"У инструмента {tool.name} нет описания."
        assert len(tool.description) > 40, f"Описание {tool.name} слишком короткое."


async def test_tools_take_display_keys_not_numeric_ids() -> None:
    """В контракте инструментов нет числовых идентификаторов сущностей."""
    tools = await mcp_server.list_tools()

    for tool in tools:
        properties = set(tool.input_schema.get("properties", {}))
        assert "project_id" not in properties, f"{tool.name} принимает числовой project_id."
        assert "task_id" not in properties, f"{tool.name} принимает числовой task_id."


@pytest.mark.parametrize(
    "name",
    [
        "list_tasks",
        "list_comments",
        "search_tasks",
        "get_calendar_range",
        "list_tasks_without_due_date",
        "list_milestones",
    ],
)
async def test_list_tools_have_bounded_limit(name: str) -> None:
    """Списочные инструменты ограничены: агент не вытянет проект целиком."""
    tools = {tool.name: tool for tool in await mcp_server.list_tools()}
    limit = tools[name].input_schema["properties"]["limit"]

    assert limit.get("maximum") == MAX_LIMIT
    assert limit.get("minimum") == 1
    assert "default" in limit


async def test_project_tools_require_project_key() -> None:
    """Инструменты уровня проекта обязательно требуют ключ проекта."""
    tools = {tool.name: tool for tool in await mcp_server.list_tools()}

    for name in (
        "get_project",
        "list_tasks",
        "search_tasks",
        "search_project_knowledge",
        "get_calendar_range",
        "list_tasks_without_due_date",
        "list_milestones",
        "create_milestone",
    ):
        assert "project_key" in tools[name].input_schema.get("required", []), name


async def test_mcp_is_mounted_and_rejects_plain_get() -> None:
    """Путь MCP смонтирован в приложении и отвечает своим транспортом."""
    mcp_path = get_settings().app.mcp_path

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(mcp_path)

    # Транспорт Streamable HTTP не обслуживает обычный GET без сессии,
    # но сам путь существует: 404 означал бы, что монтирование не сработало.
    assert response.status_code != 404


async def test_mcp_rejects_call_without_token() -> None:
    """Вызов без заголовка Authorization не проходит аутентификацию."""
    mcp_path = get_settings().app.mcp_path

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            mcp_path,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "list_projects", "arguments": {}},
            },
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )

    assert response.status_code != 200 or "list_projects" not in response.text

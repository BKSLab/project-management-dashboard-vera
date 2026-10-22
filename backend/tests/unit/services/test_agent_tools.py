from unittest.mock import AsyncMock

from src.agent.tools import AgentToolContext, AgentToolRequest
from src.dependencies.services import build_knowledge_tool_executor
from src.services.project_query import ProjectQueryService


async def test_tool_registry_validates_arguments_and_keeps_project_scope_on_server():
    query = AsyncMock(spec=ProjectQueryService)
    query.read_knowledge.return_value = {"items": [], "total": 0}
    tools = build_knowledge_tool_executor(query)
    context = AgentToolContext(project_id=5, user_id=8)
    assert {item["name"] for item in tools.describe()} == {
        "list_sources",
        "read_source",
        "related_sources",
        "search_sources",
    }
    for name, arguments in (
        ("create_task", {"title": "Подмена"}),
        ("search_sources", {"query": "тест", "project_id": 99}),
        ("read_source", {"source_id": "task:1", "max_chars": 1000000}),
    ):
        assert "error" in await tools.execute(
            context, AgentToolRequest(name=name, arguments=arguments)
        )
    query.read_knowledge.assert_not_awaited()
    assert await tools.execute(
        context, AgentToolRequest(name="search_sources", arguments={"query": "тест"})
    ) == {"items": [], "total": 0}
    assert query.read_knowledge.await_args.kwargs["project_id"] == 5
    assert query.read_knowledge.await_args.kwargs["request"].query == "тест"


async def test_refusals_name_the_field_and_format_and_respect_key_scopes(monkeypatch):
    """#40793: модель по «не соответствует схеме» не может исправить вызов."""
    from datetime import date

    from pydantic import BaseModel, ConfigDict, Field

    from src.agent.tools import AgentTool, AgentToolExecutor

    class DatesInput(BaseModel):
        model_config = ConfigDict(extra="forbid")
        task_id: int = Field(description="ID задачи из list_tasks.")
        due_date: date | None = None

    handler = AsyncMock(return_value={"ok": True})
    tools = AgentToolExecutor([AgentTool("set_dates", "Сроки", DatesInput, handler, mutating=True)])
    writer = AgentToolContext(project_id=5, user_id=8, can_write=True)
    result = await tools.execute(
        writer,
        AgentToolRequest(name="set_dates", arguments={"due_date": "пятница", "task_key": "P-1"}),
    )
    error = result["error"]
    assert "task_id: обязательное поле не передано" in error
    assert "целое число (ID задачи из list_tasks.)" in error
    assert "due_date:" in error and "дата ГГГГ-ММ-ДД" in error
    assert "task_key: такого поля нет; допустимые поля: due_date, task_id" in error
    # Изменение, не открытое правами ключа, отклоняется и пишется в журнал.
    limited = AgentToolContext(
        project_id=5, user_id=8, can_write=True, allowed_tools=frozenset({"add_comment"})
    )
    from unittest.mock import Mock

    from src.agent import tools as tools_module

    journal = Mock()
    monkeypatch.setattr(tools_module.logger, "warning", journal)
    refused = await tools.execute(
        limited, AgentToolRequest(name="set_dates", arguments={"task_id": 1})
    )
    assert "правами ключа" in refused["error"]
    assert journal.call_args.args[1] == "set_dates"
    assert "правами ключа" in journal.call_args.args[-1]
    handler.assert_not_awaited()
    assert await tools.execute(
        writer, AgentToolRequest(name="set_dates", arguments={"task_id": 1})
    ) == {"ok": True}

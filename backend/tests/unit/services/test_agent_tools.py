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

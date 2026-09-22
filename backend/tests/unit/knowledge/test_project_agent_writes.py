"""Поручение пользователя проверяется до чтения документов и отдельно от прав канала."""

import json
from unittest.mock import AsyncMock

import pytest

from src.agent.tools import AgentTool, AgentToolContext, AgentToolExecutor, AgentToolRequest
from src.schemas.project_tool_inputs import TaskCreateInput, TaskInput
from src.services.project_agent import AgentOutput, AgentToolPlan
from tests.unit.knowledge.test_project_agent import build_service


@pytest.mark.parametrize(
    ("write_intent", "transport_write"), [(False, True), (True, False), (True, True)]
)
async def test_write_requires_intent_before_retrieval_and_trusted_transport(
    write_intent, transport_write
):
    service, project, runtime, _ = build_service()
    handler = AsyncMock(
        return_value={
            "action": {
                "id": "saved",
                "tool_name": "create_task",
                "title": "Создать задачу",
                "status": "completed",
            }
        }
    )
    service.tools = AgentToolExecutor(
        [AgentTool("create_task", "Создать задачу", TaskCreateInput, handler, mutating=True)]
    )
    prompts = []

    async def respond(*, schema, content, **kwargs):
        payload = json.loads(content)
        if schema is AgentToolPlan:
            assert "retrieval_context" not in payload
            return AgentToolPlan(write_intent=write_intent)
        prompts.append(payload)
        if len(prompts) == 1:
            return AgentOutput(
                answer="",
                source_ids=[],
                tool_calls=[
                    AgentToolRequest(name="create_task", arguments={"title": "Проверка окна"})
                ],
            )
        return AgentOutput(answer="Результат проверен.", source_ids=[])

    runtime.llm_client.get_structured_response.side_effect = respond
    await service.ask(
        project_id=project.id,
        question="Проверь сведения из документа",
        history=[],
        execution=AgentToolContext(project_id=project.id, user_id=1, can_write=transport_write),
    )
    assert prompts[0]["writes_allowed"] is (write_intent and transport_write)
    assert handler.await_count == int(write_intent and transport_write)
    if write_intent and transport_write:
        assert handler.await_args.args[0].user_id == 1
    else:
        assert prompts[1]["read_results"][0]["result"].get("error")


async def test_domain_tool_result_receives_verified_source_handle():
    service, project, runtime, _ = build_service()
    service.tools = AgentToolExecutor(
        [
            AgentTool(
                "get_task",
                "Прочитать задачу",
                TaskInput,
                AsyncMock(
                    return_value={"source_id": "task:7", "task": {"id": 7, "title": "Проверка"}}
                ),
            )
        ]
    )
    prompts = []

    async def respond(*, schema, content, **kwargs):
        if schema is AgentToolPlan:
            return AgentToolPlan()
        payload = json.loads(content)
        prompts.append(payload)
        if len(prompts) == 1:
            return AgentOutput(
                tool_calls=[AgentToolRequest(name="get_task", arguments={"task_id": 7})]
            )
        handle = payload["read_results"][0]["result"]["source_handle"]
        return AgentOutput(answer="Задача найдена.", source_ids=[handle])

    runtime.llm_client.get_structured_response.side_effect = respond
    answer = await service.ask(project_id=project.id, question="Найди задачу", history=[])
    assert [item.source_id for item in answer.sources] == ["task:7"]

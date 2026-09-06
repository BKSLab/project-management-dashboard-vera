from types import SimpleNamespace

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from src.db.models.api_tokens import ApiTokenScope
from src.exceptions.project_risks import ProjectRiskNotFoundError, ProjectRiskServiceError
from src.mcp_server import risk_tools as rt
from src.schemas.project_risks import ProjectRiskPageSchema, ProjectRiskSchema
from src.services.project_query import ResolvedTask
from tests.unit.mcp_server.conftest import PROJECT_ID, FakeContext
from tests.unit.services.test_project_risks_service import risk


def creation(**changes):
    return {
        "project_key": "PROJ",
        "confirmed_by_user": True,
        "title": "Риск",
        "description": "Описание",
        "probability": "HIGH",
        "impact": "MEDIUM",
        "response_strategy": "MITIGATE",
        **changes,
    }


async def test_risk_reads_use_project_scope_and_batch_public_links(tools):
    services = tools(ApiTokenScope.READ)
    saved = ProjectRiskSchema.model_validate(risk(owner_user_id=42, task_id=7))
    services.risks.list_risks.return_value = ProjectRiskPageSchema(
        items=[saved], total=1, page=2, page_size=5
    )
    services.risks.get_risk.return_value = saved
    services.query.get_task_keys.return_value = {7: "PROJ-142"}
    services.members.get_member_list.return_value = [
        SimpleNamespace(user=SimpleNamespace(id=42, username="boris"))
    ]
    result = await rt.list_project_risks(
        FakeContext(), project_key="PROJ", status="OPEN", page=2, page_size=5
    )
    assert result["page"] == 2
    assert result["items"][0]["owner"] == "boris"
    assert result["items"][0]["task_key"] == "PROJ-142"
    assert not {"id", "project_id", "task_id", "owner_user_id"} & result["items"][0].keys()
    detail = await rt.get_project_risk(FakeContext(), project_key="PROJ", risk_key="RISK-12")
    assert "mitigation_plan" in detail and "response_plan" in detail
    services.risks.get_risk.assert_awaited_once_with(project_id=PROJECT_ID, risk_id=12, user_id=1)


async def test_risk_creation_requires_scope_confirmation_and_uses_same_service(tools):
    services = tools(ApiTokenScope.READ)
    with pytest.raises(ToolError):
        await rt.create_project_risk(FakeContext(), **creation())
    services.risks.create_risk.assert_not_awaited()
    services = tools(ApiTokenScope.WRITE)
    with pytest.raises(ToolError, match="подтверждение"):
        await rt.create_project_risk(FakeContext(), **creation(confirmed_by_user=False))
    services.risks.create_risk.assert_not_awaited()
    services.risks.create_risk.return_value = ProjectRiskSchema.model_validate(risk())
    services.query.resolve_task.return_value = ResolvedTask(
        task_id=7, project_id=PROJECT_ID, task_key="PROJ-142"
    )
    services.members.resolve_member_user_id.return_value = 42
    result = await rt.create_project_risk(
        FakeContext(), **creation(source="AI_SUGGESTED", task_key="PROJ-142", owner="boris")
    )
    data = services.risks.create_risk.await_args.kwargs["data"]
    assert data.task_id == 7 and data.owner_user_id == 42
    assert data.source == "AI_SUGGESTED"
    assert "risk_level" not in data.model_dump()
    assert result["created"]


async def test_risk_patch_clears_links_and_preserves_omitted_fields(tools):
    services = tools(ApiTokenScope.WRITE)
    services.risks.update_risk.return_value = ProjectRiskSchema.model_validate(risk())
    await rt.update_project_risk(
        FakeContext(),
        project_key="PROJ",
        risk_key="RISK-12",
        confirmed_by_user=True,
        impact="LOW",
        owner="",
        task_key="",
        review_date="",
    )
    assert services.risks.update_risk.await_args.kwargs["data"].model_dump(exclude_unset=True) == {
        "impact": "LOW",
        "owner_user_id": None,
        "task_id": None,
        "review_date": None,
    }


async def test_risk_tools_hide_foreign_risks_and_internal_errors(tools):
    services = tools(ApiTokenScope.READ)
    for error, expected in [
        (ProjectRiskNotFoundError(12), "Риск не найден"),
        (ProjectRiskServiceError("private SQL"), "Не удалось выполнить"),
    ]:
        services.risks.get_risk.side_effect = error
        with pytest.raises(ToolError, match=expected) as raised:
            await rt.get_project_risk(FakeContext(), project_key="PROJ", risk_key="RISK-12")
        assert "private SQL" not in str(raised.value)


async def test_foreign_task_and_invalid_patch_do_not_reach_mutations(tools):
    services = tools(ApiTokenScope.WRITE)
    services.query.resolve_task.return_value = ResolvedTask(
        task_id=7, project_id=PROJECT_ID + 1, task_key="OTHER-7"
    )
    with pytest.raises(ToolError, match="проекту риска"):
        await rt.create_project_risk(FakeContext(), **creation(task_key="OTHER-7"))
    services.risks.create_risk.assert_not_awaited()
    with pytest.raises(ToolError):
        await rt.update_project_risk(
            FakeContext(), project_key="PROJ", risk_key="RISK-12", confirmed_by_user=True
        )
    services.risks.update_risk.assert_not_awaited()

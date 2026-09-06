import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.schemas.enums import RiskRating, RiskResponseStrategy, RiskStatus
from src.schemas.risk_formulation import (
    RiskFormulationField,
    RiskFormulationRequest,
    RiskFormulationResponse,
)
from src.services.risk_formulation import RiskFormulationService


@pytest.mark.asyncio
async def test_formulation_uses_all_current_risk_fields_and_keeps_db_closed_for_llm():
    db = SimpleNamespace(
        auth=SimpleNamespace(resolve_principal=AsyncMock(return_value=SimpleNamespace(user_id=4))),
        access=SimpleNamespace(ensure_project_access=AsyncMock()),
        projects=SimpleNamespace(get_by_id=AsyncMock(return_value=SimpleNamespace(id=1))),
    )
    opened = False

    @asynccontextmanager
    async def scope():
        nonlocal opened
        opened = True
        try:
            yield db
        finally:
            opened = False

    llm = AsyncMock()

    async def response(**kwargs):
        assert not opened
        payload = json.loads(kwargs["content"])
        assert payload["probability"] == "HIGH"
        assert payload["response_strategy"] == "MITIGATE"
        return RiskFormulationResponse(
            field=RiskFormulationField.MITIGATION_PLAN, text="Согласовать API"
        )

    llm.get_structured_response.side_effect = response
    service = RiskFormulationService(scope=scope, llm_client=llm)
    data = RiskFormulationRequest(
        field=RiskFormulationField.MITIGATION_PLAN,
        title="Задержка поставки",
        description="Поставщик может опоздать",
        probability=RiskRating.HIGH,
        impact=RiskRating.MEDIUM,
        response_strategy=RiskResponseStrategy.MITIGATE,
        status=RiskStatus.OPEN,
    )
    result = await service.suggest(project_id=1, data=data, session_token="s", bearer_secret=None)
    assert result.field == RiskFormulationField.MITIGATION_PLAN
    assert result.text == "Согласовать API"
    db.access.ensure_project_access.assert_awaited_once_with(project_id=1, user_id=4)

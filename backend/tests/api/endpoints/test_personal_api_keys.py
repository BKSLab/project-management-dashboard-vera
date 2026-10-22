"""Новые ключи не открывают управление ключами и чужие scopes."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from main import app
from src.db.models.api_tokens import ApiTokenScope
from src.dependencies.auth import get_principal
from src.dependencies.services import get_api_keys_service
from src.services.api_keys import ApiKeysService
from src.services.auth import ApiKeyGrant
from src.utils.request_actor import reset_request_actor, set_request_actor


def key_principal(principal, scopes):
    return replace(principal, via_api_token=True, scope=ApiTokenScope.WRITE,
        api_key=ApiKeyGrant(key_id=uuid4(), label="Мой клиент", key_prefix="ttk_example",
            owner_user_id=principal.user_id, scopes=frozenset(scopes)))


@pytest.mark.parametrize("new_key", [False, True])
@pytest.mark.parametrize("method,suffix", [("get", ""), ("get", "/scopes"), ("post", ""), ("patch", "/00000000-0000-4000-8000-000000000001")])
async def test_both_token_formats_cannot_manage_keys(api_client, current_principal, method, suffix, new_key):
    service = AsyncMock(spec=ApiKeysService)
    principal = key_principal(current_principal, {"projects:write", "tasks:write"}) if new_key else replace(current_principal, via_api_token=True)
    app.dependency_overrides[get_principal] = lambda: principal
    app.dependency_overrides[get_api_keys_service] = lambda: service
    response = await getattr(api_client, method)("/api/v1/users/me/api-keys" + suffix,
        **({"json": {"label": "Ключ", "is_active": False}} if method in {"post", "patch"} else {}))
    assert response.status_code == 403
    service.list_personal_keys.assert_not_awaited()
    service.create_personal_key.assert_not_awaited()
    service.update_personal_key.assert_not_awaited()


@pytest.mark.parametrize("scopes,allowed", [({"boards:write"}, False), ({"projects:write"}, False), ({"boards:write", "projects:write"}, True)])
async def test_promoting_board_requires_both_board_and_project_permissions(current_principal, scopes, allowed):
    principal = key_principal(current_principal, scopes)
    auth = AsyncMock()
    auth.resolve_principal.return_value = principal
    path = "/api/v1/boards/{board_id}/create-project"
    request = Request({"type": "http", "method": "POST", "path": "/api/v1/boards/1/create-project",
        "headers": [], "route": SimpleNamespace(path=path)})
    token = set_request_actor(None)
    try:
        if allowed:
            assert await get_principal(auth, authorization="Bearer ttk_example", request=request) is principal
        else:
            with pytest.raises(HTTPException) as error:
                await get_principal(auth, authorization="Bearer ttk_example", request=request)
            assert error.value.status_code == 403
    finally:
        reset_request_actor(token)

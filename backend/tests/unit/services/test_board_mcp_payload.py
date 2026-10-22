"""Execute the real MCP handlers with a fake transport, retaining nested field presence."""

import ast
from pathlib import Path
from typing import Annotated, Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from pydantic import Field

from src.schemas.board_diagrams import BoardShapeUpdatesInput

SRC = Path(__file__).resolve().parents[3] / "src"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data",
    [
        {"label": "after"},
        {"x": 32, "y": 64},
        {"start_ref": None},
    ],
)
async def test_mcp_update_handler_preserves_unset_and_explicit_null(data):
    # No MCP server, credentials or app lifespan is needed for a serialization
    # boundary test. The function body is loaded unchanged from the real module.
    tree = ast.parse((SRC / "mcp_server/board_tools.py").read_text())
    handler = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "update_board_shapes"
    )
    handler.decorator_list = []

    async def execute(context, **kwargs):
        validated = BoardShapeUpdatesInput.model_validate(kwargs["arguments"])
        assert validated.updates[0].data.model_dump(exclude_unset=True) == data
        return {"validated": True}

    namespace = {
        "Context": Any,
        "Annotated": Annotated,
        "Field": Field,
        "BoardShapeUpdatesInput": BoardShapeUpdatesInput,
        "UUID": UUID,
        "_execute": AsyncMock(side_effect=execute),
    }
    exec(compile(ast.Module(body=[handler], type_ignores=[]), "board_tools.py", "exec"), namespace)
    args = BoardShapeUpdatesInput(
        board_id=4,
        updates=[{"id": 2, "revision": 3, "data": data}],
    )
    request_id = uuid4()
    result = await namespace["update_board_shapes"](object(), args, request_id, project_key="DEMO")
    assert result == {"validated": True}
    call = namespace["_execute"].await_args.kwargs
    assert call["request_id"] == request_id and call["write"] is True
    assert call["project_key"] == "DEMO"

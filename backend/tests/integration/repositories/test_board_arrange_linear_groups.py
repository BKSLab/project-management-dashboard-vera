"""Real scene -> arrange regression for complete mixed groups with linear members."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import update

from src.db.models.board_shapes import BoardShape, BoardShapeKind
from src.exceptions.agent_tools import AgentToolArgumentsError
from src.exceptions.board_shapes import BoardBatchConflictError, BoardShapeInvalidError
from src.schemas.board_diagrams import BoardArrangeInput, BoardSceneInput
from src.schemas.board_shapes import default_style
from src.services.agent_board_actions import arrange_board_objects, get_board_scene
from src.services.board_arrange import compile_arrangement
from tests.integration.repositories.test_board_arrange_agent_batch import (
    context,
    seed,
    services,
    snapshot,
    without,
)


async def mixed_group(session, *, linear_kind="arrow"):
    env = await seed(session)
    db = services(session)
    second = BoardShape(
        board_id=env.board_id,
        kind=BoardShapeKind.RECT,
        x=150,
        y=450,
        w=190,
        h=120,
        label="Second manual node",
        style=default_style(BoardShapeKind.RECT),
        revision=2,
        z_index=19,
        created_by_user_id=env.owner_id,
    )
    session.add(second)
    await session.flush()
    env.second_id = second.id
    if linear_kind == "line":
        await session.execute(
            update(BoardShape)
            .where(BoardShape.id == env.internal_id)
            .values(
                kind=BoardShapeKind.LINE,
                style=default_style(BoardShapeKind.LINE),
            )
        )
    board = await db.board_shapes.editor_repository.get_board(env.board_id)
    metadata = deepcopy(board.editor_metadata)
    metadata["groups"][0]["members"] += [
        {"type": "shape", "id": env.second_id},
        {"type": "shape", "id": env.internal_id},
    ]
    metadata["locked"] = [{"type": "shape", "id": env.outside_id}]
    board.editor_metadata = metadata
    await session.commit()
    return db, env


async def scene_arguments(db, env, *, mode="align", direction="TB", include_detached=False):
    scene = await get_board_scene(
        db, context(env), BoardSceneInput(board_id=env.board_id, limit=200)
    )
    objects = {(item["type"], item["id"]): item for item in scene["objects"]}
    members = list(scene["editor_metadata"]["groups"][0]["members"])
    if include_detached:
        members.append({"type": "shape", "id": env.detached_id})
    args = BoardArrangeInput(
        board_id=env.board_id,
        expected_revision=scene["revision"],
        objects=[
            {**ref, "revision": objects[(ref["type"], ref["id"])]["revision"]} for ref in members
        ],
        mode=mode,
        direction=direction,
        alignment="left" if mode == "align" else None,
    )
    return scene, args


@pytest.mark.parametrize("linear_kind", ["arrow", "line"])
@pytest.mark.parametrize(
    ("mode", "direction"), [("align", "TB"), ("layout", "TB"), ("layout", "LR")]
)
async def test_scene_complete_mixed_group_arranges_once_preserving_ids_fields_metadata_locks(
    db_session, linear_kind, mode, direction
):
    db, env = await mixed_group(db_session, linear_kind=linear_kind)
    before = await snapshot(db_session, db, env)
    scene, args = await scene_arguments(db, env, mode=mode, direction=direction)
    assert {ref.type for ref in args.objects} == {"shape", "sticker"}
    assert any(item["kind"] == linear_kind for item in scene["objects"] if item["type"] == "shape")
    service = db.board_shapes
    with (
        patch.object(service, "apply_batch", AsyncMock(wraps=service.apply_batch)) as batch_spy,
        patch.object(
            service.unit_of_work, "commit", AsyncMock(wraps=service.unit_of_work.commit)
        ) as commit_spy,
    ):
        result = await arrange_board_objects(db, context(env), args)
    batch_spy.assert_awaited_once()
    commit_spy.assert_awaited_once()
    batch = batch_spy.await_args.kwargs["data"]
    keys = [("sticker" if op.op == "move_sticker" else "shape", op.id) for op in batch.ops]
    assert len(keys) == len(set(keys)) == 5
    assert keys.count(("shape", env.internal_id)) == 1
    assert {op.op for op in batch.ops} == {"update_shape", "move_sticker"}
    assert all(op.revision is not None for op in batch.ops)
    assert result.keys() == {"board_change"}
    assert result["board_change"]["operation_count"] == 5
    assert result["board_change"]["batch"]["id_map"] == {}
    after = await snapshot(db_session, db, env)
    assert after["metadata"] == before["metadata"]
    assert after["revision"] == before["revision"] + 1
    old_shapes = {item["id"]: item for item in before["scene"]["shapes"]}
    new_shapes = {item["id"]: item for item in after["scene"]["shapes"]}
    assert new_shapes.keys() == old_shapes.keys()
    for shape_id, original in old_shapes.items():
        changed = new_shapes[shape_id]
        if shape_id in {env.outside_id, env.detached_id}:
            assert changed == original
            continue
        mutable = {"x", "y", "revision", "updated_at"}
        if original["kind"] in {"arrow", "line"}:
            mutable |= {"w", "h", "points"}
            if mode == "layout" and shape_id == env.internal_id:
                mutable |= {"start_ref", "end_ref"}
        assert without(changed, mutable) == without(original, mutable)
        assert changed["revision"] == original["revision"] + 1
    original, changed = before["scene"]["stickers"][0], after["scene"]["stickers"][0]
    assert changed["id"] == original["id"]
    assert without(changed, {"canvas_x", "canvas_y", "revision", "updated_at"}) == without(
        original, {"canvas_x", "canvas_y", "revision", "updated_at"}
    )
    if mode == "align":
        assert {
            new_shapes[env.shape_id]["x"],
            new_shapes[env.second_id]["x"],
            changed["canvas_x"],
        } == {150}
        assert (
            new_shapes[env.internal_id]["points"][1:-1]
            == old_shapes[env.internal_id]["points"][1:-1]
        )
    assert new_shapes[env.external_id]["points"][1:] == old_shapes[env.external_id]["points"][1:]


async def test_selected_detached_arrow_is_revision_checked_without_moving_its_geometry(db_session):
    db, env = await mixed_group(db_session)
    before = await snapshot(db_session, db, env)
    _, args = await scene_arguments(db, env, include_detached=True)
    result = await arrange_board_objects(db, context(env), args)
    assert result["board_change"]["operation_count"] == 6
    after = await snapshot(db_session, db, env)
    original = next(item for item in before["scene"]["shapes"] if item["id"] == env.detached_id)
    changed = next(item for item in after["scene"]["shapes"] if item["id"] == env.detached_id)
    assert without(changed, {"revision", "updated_at"}) == without(
        original, {"revision", "updated_at"}
    )
    assert changed["revision"] == original["revision"] + 1


@pytest.mark.parametrize("missing_member", ["internal_id", "second_id"])
async def test_complete_group_still_required_when_arrow_or_node_omitted(db_session, missing_member):
    db, env = await mixed_group(db_session)
    _, args = await scene_arguments(db, env)
    args.objects = [
        ref
        for ref in args.objects
        if not (ref.type == "shape" and ref.id == getattr(env, missing_member))
    ]
    before = await snapshot(db_session, db, env)
    with pytest.raises(AgentToolArgumentsError, match="Review process"):
        await arrange_board_objects(db, context(env), args)
    assert await snapshot(db_session, db, env) == before


@pytest.mark.parametrize("target", ["internal_id", "detached_id"])
async def test_real_batch_rechecks_selected_linear_revision_and_rolls_back_every_node(
    db_session, target
):
    db, env = await mixed_group(db_session)
    scene, args = await scene_arguments(db, env, include_detached=True)
    batch = compile_arrangement(args, objects=scene["objects"], metadata=scene["editor_metadata"])
    await db_session.execute(
        update(BoardShape)
        .where(BoardShape.id == getattr(env, target))
        .values(
            revision=BoardShape.revision + 1,
            label="Concurrent manual label",
        )
    )
    await db_session.commit()
    before = await snapshot(db_session, db, env)
    with pytest.raises(BoardBatchConflictError):
        await db.board_shapes.apply_batch(
            project_id=None,
            board_id=env.board_id,
            author_id=env.owner_id,
            data=batch,
        )
    assert await snapshot(db_session, db, env) == before


@pytest.mark.parametrize("target", ["internal_id", "external_id", "detached_id"])
async def test_group_selected_and_indirect_locked_arrows_are_never_bypassed(db_session, target):
    db, env = await mixed_group(db_session)
    board = await db.board_shapes.editor_repository.get_board(env.board_id)
    metadata = deepcopy(board.editor_metadata)
    metadata["locked"].append({"type": "shape", "id": getattr(env, target)})
    board.editor_metadata = metadata
    await db_session.commit()
    _, args = await scene_arguments(db, env, include_detached=True)
    before = await snapshot(db_session, db, env)
    with pytest.raises(BoardShapeInvalidError):
        await arrange_board_objects(db, context(env), args)
    assert await snapshot(db_session, db, env) == before

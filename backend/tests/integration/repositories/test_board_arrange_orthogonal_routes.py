"""Saved UI orthogonal routes remain orthogonal through real atomic arrange writes."""

from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError
from sqlalchemy import update

from src.db.models.board_shapes import BoardShape, BoardShapeKind
from src.exceptions.board_shapes import BoardShapeInvalidError
from src.schemas.board_diagrams import BoardArrangeInput, BoardSceneInput
from src.schemas.board_shapes import BoardBatchSchema, default_style
from src.services.agent_board_actions import arrange_board_objects, get_board_scene
from src.services.board_arrange import compile_arrangement
from tests.integration.repositories.test_board_arrange_agent_batch import (
    context,
    seed,
    services,
    snapshot,
    without,
)


def axis_segments(points):
    assert len(points) <= 50
    assert all(a[0] == b[0] or a[1] == b[1] for a, b in zip(points, points[1:], strict=False))


def line_box(points):
    xs, ys = zip(*points, strict=False)
    return dict(points=points, x=min(xs), y=min(ys), w=max(xs) - min(xs), h=max(ys) - min(ys))


async def saved_ui_group(session, *, center=False, fifty=False, collinear=False):
    env = await seed(session)
    db = services(session)
    await session.execute(
        update(BoardShape).where(BoardShape.id == env.shape_id).values(x=200, y=400, w=100, h=100)
    )
    await session.execute(
        update(BoardShape)
        .where(BoardShape.id == env.outside_id)
        .values(x=550, y=400 if collinear else 420, w=100, h=100)
    )
    points = [[300, 450], [430, 450], [430, 470], [550, 470]]
    if center:
        points = [[300, 452.9], [430, 452.9], [430, 467.1], [550.1, 467.1]]
    elif collinear:
        points = [[300 + i * 250 / 49, 450] for i in range(50)]
    elif fifty:
        points = [[300, 450]]
        points += [[300 + ((i + 1) // 2) * 5, 450 + (i // 2) * 20 / 24] for i in range(1, 49)]
        points += [[550, 470]]
    axis_segments(points)
    await session.execute(
        update(BoardShape)
        .where(BoardShape.id == env.internal_id)
        .values(
            **line_box(points),
            start_ref={
                "type": "shape",
                "id": env.shape_id,
                "anchor": "center" if center else "right",
            },
            end_ref={
                "type": "shape",
                "id": env.outside_id,
                "anchor": "center" if center else "left",
            },
        )
    )
    external = [
        [960, 310],
        [1000, 310],
        [1000, 450 if collinear else 470],
        [550, 450 if collinear else 470],
    ]
    await session.execute(
        update(BoardShape)
        .where(BoardShape.id == env.external_id)
        .values(
            **line_box(external),
            style={**default_style(BoardShapeKind.ARROW), "route": "orthogonal"},
            end_ref={"type": "shape", "id": env.outside_id, "anchor": "left"},
        )
    )
    board = await db.board_shapes.editor_repository.get_board(env.board_id)
    metadata = deepcopy(board.editor_metadata)
    metadata["groups"][0]["members"] = [
        {"type": "shape", "id": object_id}
        for object_id in (env.shape_id, env.outside_id, env.internal_id)
    ]
    metadata["locked"] = [{"type": "shape", "id": env.detached_id}]
    board.editor_metadata = metadata
    await session.commit()
    return db, env


async def selected_args(db, env, refs=None):
    scene = await get_board_scene(
        db, context(env), BoardSceneInput(board_id=env.board_id, limit=200)
    )
    objects = {(item["type"], item["id"]): item for item in scene["objects"]}
    refs = refs if refs is not None else scene["editor_metadata"]["groups"][0]["members"]
    args = BoardArrangeInput(
        board_id=env.board_id,
        expected_revision=scene["revision"],
        mode="align",
        alignment="top",
        objects=[
            {**ref, "revision": objects[(ref["type"], ref["id"])]["revision"]} for ref in refs
        ],
    )
    return scene, args


@pytest.mark.parametrize(("center", "fifty"), [(False, False), (True, False), (False, True)])
async def test_full_group_top_align_preserves_manual_route_fields_ids_and_single_common_cas(
    db_session, center, fifty
):
    db, env = await saved_ui_group(db_session, center=center, fifty=fifty)
    before = await snapshot(db_session, db, env)
    _, args = await selected_args(db, env)
    service = db.board_shapes
    with (
        patch.object(service, "apply_batch", AsyncMock(wraps=service.apply_batch)) as batch,
        patch.object(
            service.unit_of_work, "commit", AsyncMock(wraps=service.unit_of_work.commit)
        ) as commit,
    ):
        result = await arrange_board_objects(db, context(env), args)
    batch.assert_awaited_once()
    commit.assert_awaited_once()
    after = await snapshot(db_session, db, env)
    assert after["metadata"] == before["metadata"]
    assert after["revision"] == before["revision"] + 1
    old = {item["id"]: item for item in before["scene"]["shapes"]}
    new = {item["id"]: item for item in after["scene"]["shapes"]}
    assert new.keys() == old.keys()
    for object_id in (env.shape_id, env.outside_id):
        assert new[object_id]["y"] == 400
        assert without(new[object_id], {"x", "y", "revision", "updated_at"}) == without(
            old[object_id], {"x", "y", "revision", "updated_at"}
        )
    for object_id in (env.internal_id, env.external_id):
        axis_segments(new[object_id]["points"])
        assert without(
            new[object_id], {"x", "y", "w", "h", "points", "revision", "updated_at"}
        ) == without(old[object_id], {"x", "y", "w", "h", "points", "revision", "updated_at"})
        assert new[object_id]["revision"] == old[object_id]["revision"] + 1
    points = new[env.internal_id]["points"]
    if fifty:
        assert len(points) == 50
        assert points[2:-2] == old[env.internal_id]["points"][2:-2]
    else:
        assert points == [[300, 450], [430, 450], [430, 450], [550, 450]]
    assert new[env.external_id]["points"] == [[960, 310], [1000, 310], [1000, 450], [550, 450]]
    assert new[env.detached_id] == old[env.detached_id]
    assert after["scene"]["stickers"] == before["scene"]["stickers"]
    assert result["board_change"]["operation_count"] == 4


@pytest.mark.parametrize("collinear", [False, True])
async def test_external_route_tracks_moved_node_without_diagonals_or_unselected_node_writes(
    db_session, collinear
):
    db, env = await saved_ui_group(db_session, collinear=collinear)
    marker = BoardShape(
        board_id=env.board_id,
        kind=BoardShapeKind.RECT,
        x=800,
        y=200,
        w=100,
        h=100,
        label="Alignment target",
        style=default_style(BoardShapeKind.RECT),
    )
    db_session.add(marker)
    await db_session.flush()
    marker_id = marker.id
    board = await db.board_shapes.editor_repository.get_board(env.board_id)
    metadata = deepcopy(board.editor_metadata)
    metadata["groups"] = []
    board.editor_metadata = metadata
    await db_session.commit()
    _, args = await selected_args(
        db, env, [{"type": "shape", "id": env.outside_id}, {"type": "shape", "id": marker_id}]
    )
    before = await snapshot(db_session, db, env)
    await arrange_board_objects(db, context(env), args)
    after = await snapshot(db_session, db, env)
    old = {item["id"]: item for item in before["scene"]["shapes"]}
    new = {item["id"]: item for item in after["scene"]["shapes"]}
    assert new[env.shape_id] == old[env.shape_id]
    assert after["scene"]["stickers"] == before["scene"]["stickers"]
    assert after["metadata"] == before["metadata"]
    assert new[env.outside_id]["y"] == 200
    for object_id in (env.internal_id, env.external_id):
        axis_segments(new[object_id]["points"])
        assert new[object_id]["points"][0] == old[object_id]["points"][0]
        assert new[object_id]["points"][-1] == [550, 250]
        assert new[object_id]["start_ref"] == old[object_id]["start_ref"]
        assert new[object_id]["end_ref"] == old[object_id]["end_ref"]
        assert new[object_id]["style"] == old[object_id]["style"]
        assert new[object_id]["label"] == old[object_id]["label"]
    if collinear:
        assert len(new[env.internal_id]["points"]) == 4
        assert new[env.internal_id]["points"] == [[300, 450], [425, 450], [425, 250], [550, 250]]
    else:
        assert new[env.internal_id]["points"][1:] == [[430, 450], [430, 250], [550, 250]]
    assert after["revision"] == before["revision"] + 1


async def test_late_batch_error_rolls_back_adjusted_route_nodes_revisions_and_metadata(db_session):
    db, env = await saved_ui_group(db_session, fifty=True)
    scene, args = await selected_args(db, env)
    batch = compile_arrangement(args, objects=scene["objects"], metadata=scene["editor_metadata"])
    raw = batch.model_dump(mode="json", exclude_unset=True)
    raw["ops"].append(
        {
            "op": "update_shape",
            "id": env.detached_id,
            "revision": 13,
            "data": {"end_ref": {"type": "shape", "id": 999999999, "anchor": "left"}},
        }
    )
    # The last target is unlocked so the failure occurs after real earlier writes.
    board = await db.board_shapes.editor_repository.get_board(env.board_id)
    metadata = deepcopy(board.editor_metadata)
    metadata["locked"] = []
    board.editor_metadata = metadata
    await db_session.commit()
    before = await snapshot(db_session, db, env)
    with pytest.raises(BoardShapeInvalidError, match="Привязка"):
        await db.board_shapes.apply_batch(
            project_id=None,
            board_id=env.board_id,
            author_id=env.owner_id,
            data=BoardBatchSchema.model_validate(raw),
        )
    assert await snapshot(db_session, db, env) == before


async def test_external_center_contact_matches_ui_without_mutating_its_node(db_session):
    db, env = await saved_ui_group(db_session, center=True)
    marker = BoardShape(
        board_id=env.board_id,
        kind=BoardShapeKind.RECT,
        x=800,
        y=200,
        w=100,
        h=100,
        label="Alignment target",
        style=default_style(BoardShapeKind.RECT),
    )
    db_session.add(marker)
    await db_session.flush()
    marker_id = marker.id
    board = await db.board_shapes.editor_repository.get_board(env.board_id)
    metadata = deepcopy(board.editor_metadata)
    metadata["groups"] = []
    board.editor_metadata = metadata
    await db_session.commit()
    _, args = await selected_args(
        db,
        env,
        [
            {"type": "shape", "id": env.outside_id},
            {"type": "shape", "id": marker_id},
        ],
    )
    before = await snapshot(db_session, db, env)
    await arrange_board_objects(db, context(env), args)
    after = await snapshot(db_session, db, env)
    old = {item["id"]: item for item in before["scene"]["shapes"]}
    new = {item["id"]: item for item in after["scene"]["shapes"]}
    assert new[env.shape_id] == old[env.shape_id]
    arrow = new[env.internal_id]
    assert arrow["points"] == [[300, 421.4], [430, 421.4], [430, 274.8], [556.6, 274.8]]
    axis_segments(arrow["points"])
    assert arrow["start_ref"] == old[env.internal_id]["start_ref"]
    assert arrow["end_ref"] == old[env.internal_id]["end_ref"]
    assert arrow["style"] == old[env.internal_id]["style"]
    assert after["metadata"] == before["metadata"]
    assert after["revision"] == before["revision"] + 1


async def test_fifty_one_points_remain_rejected_before_any_write(db_session):
    db, env = await saved_ui_group(db_session)
    before = await snapshot(db_session, db, env)
    with pytest.raises(ValidationError):
        BoardBatchSchema.model_validate(
            {
                "ops": [
                    {
                        "op": "update_shape",
                        "id": env.internal_id,
                        "revision": 7,
                        "data": {"points": [[i, 450] for i in range(51)]},
                    },
                ]
            }
        )
    assert await snapshot(db_session, db, env) == before

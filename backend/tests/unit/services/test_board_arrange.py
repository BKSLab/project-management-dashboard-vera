"""Geometry contracts of explicit rearrangement, independent of persistence."""

from copy import deepcopy
from itertools import combinations

import pytest
from pydantic import ValidationError

from src.schemas.board_diagrams import BoardArrangeInput
from src.schemas.board_shapes import BoardBatchSchema
from src.services.board_arrange import compile_arrangement
from src.services.board_layout import DiagramLayoutError


def node(object_id, *, type="shape", x=300, y=200, w=120, h=80, revision=3):
    return {
        "type": type,
        "id": object_id,
        "kind": "rect" if type == "shape" else None,
        "x": x,
        "y": y,
        "w": w,
        "h": h,
        "revision": revision,
        "label": f"Node {object_id}",
        "body": "Keep this note",
        "task_ids": [17, 29],
        "style": {"fill": "yellow", "dash": "dashed"},
        "z_index": 9,
    }


def ref(item, *, anchor=None):
    value = {"type": item["type"], "id": item["id"]}
    if anchor is not None:
        value["anchor"] = anchor
    return value


def edge(object_id, start, end, *, points=None, revision=7):
    return {
        "type": "shape",
        "id": object_id,
        "kind": "arrow",
        "revision": revision,
        "points": points or [[420, 240], [500, 240], [500, 540], [700, 540]],
        "start_ref": ref(start, anchor="right"),
        "end_ref": ref(end, anchor="left"),
        "style": {"route": "orthogonal", "dash": "dashed"},
        "label": "Keep edge text",
        "z_index": 6,
    }


def arguments(selected, **kwargs):
    return BoardArrangeInput(
        board_id=4,
        expected_revision=12,
        objects=[{**ref(item), "revision": item["revision"]} for item in selected],
        mode="layout",
        **kwargs,
    )


def compile_for(selected, objects=None, metadata=None, **kwargs):
    return compile_arrangement(
        arguments(selected, **kwargs),
        objects=objects if objects is not None else selected,
        metadata=metadata or {},
    )


def resulting_boxes(selected, batch):
    boxes = {(item["type"], item["id"]): deepcopy(item) for item in selected}
    for op in batch.ops:
        key = ("sticker" if op.op == "move_sticker" else "shape", op.id)
        if key not in boxes:
            continue
        data = op.data.model_dump(exclude_unset=True)
        if op.op == "move_sticker":
            data = {"x": data["canvas_x"], "y": data["canvas_y"]}
        boxes[key].update(data)
    return boxes


def assert_position_only(batch, selected, objects):
    originals = {(item["type"], item["id"]): item for item in objects}
    selected_keys = {(item["type"], item["id"]) for item in selected}
    seen = set()
    for op in batch.ops:
        assert op.op in {"update_shape", "move_sticker"}
        key = ("sticker" if op.op == "move_sticker" else "shape", op.id)
        assert key in originals and key not in seen
        seen.add(key)
        assert op.revision == originals[key]["revision"]
        fields = op.data.model_fields_set
        if originals[key].get("kind") in {"arrow", "line"}:
            assert "points" in fields
            assert fields <= {"points", "start_ref", "end_ref"}
            for name in ("start_ref", "end_ref"):
                if name in fields:
                    updated_ref = getattr(op.data, name)
                    assert (updated_ref.type, updated_ref.id) == (
                        originals[key][name]["type"],
                        originals[key][name]["id"],
                    )
        elif op.op == "move_sticker":
            assert fields == {"canvas_x", "canvas_y"}
        else:
            assert fields == {"x", "y"}
    assert selected_keys <= seen
    assert batch.expected_revision == 12
    assert batch.editor_state is None and batch.editor_insert is None


@pytest.mark.parametrize("direction", ["TB", "LR"])
def test_layout_keeps_sizes_fields_and_ids_with_overlapping_shape_sticker_ids(direction):
    a = node(1, x=700, y=500, w=170, h=90)
    b = node(1, type="sticker", x=300, y=100, w=260, h=180, revision=5)
    c = node(2, x=100, y=300, w=95, h=210)
    selected = [a, b, c]
    objects = [*selected, edge(20, a, b), edge(21, b, c)]
    untouched = deepcopy(objects)

    batch = compile_for(selected, objects, direction=direction)
    boxes = resulting_boxes(selected, batch)
    axis, size = ("y", "h") if direction == "TB" else ("x", "w")
    ordered = [boxes[(item["type"], item["id"])] for item in selected]

    assert ordered[0][axis] + ordered[0][size] < ordered[1][axis]
    assert ordered[1][axis] + ordered[1][size] < ordered[2][axis]
    for item in selected:
        updated = boxes[(item["type"], item["id"])]
        assert {k: v for k, v in updated.items() if k not in {"x", "y"}} == {
            k: v for k, v in item.items() if k not in {"x", "y"}
        }
    assert objects == untouched
    assert_position_only(batch, selected, objects)


@pytest.mark.parametrize("direction", ["TB", "LR"])
def test_cycles_self_loop_and_disconnected_nodes_remain_distinct_and_nonoverlapping(direction):
    selected = [
        node(1, x=100, y=100, w=120, h=80),
        node(2, x=100, y=100, w=300, h=240),
        node(3, type="sticker", x=100, y=100, w=220, h=180),
        node(4, x=100, y=100, w=60, h=310),
    ]
    a, b, c, _ = selected
    objects = [*selected, edge(10, a, b), edge(11, b, c), edge(12, c, a), edge(13, a, a)]

    batch = compile_for(selected, objects, direction=direction)
    boxes = list(resulting_boxes(selected, batch).values())

    for first, second in combinations(boxes, 2):
        assert (
            first["x"] + first["w"] <= second["x"]
            or second["x"] + second["w"] <= first["x"]
            or first["y"] + first["h"] <= second["y"]
            or second["y"] + second["h"] <= first["y"]
        )
    arrows = [op for op in batch.ops if op.id in {10, 11, 12, 13}]
    assert len(arrows) == 4
    assert all(len(set(op.data.points)) >= 2 for op in arrows)
    assert_position_only(batch, selected, objects)


@pytest.mark.parametrize(
    ("alignment", "axis", "size", "fraction"),
    [
        ("left", "x", "w", 0),
        ("center", "x", "w", 0.5),
        ("right", "x", "w", 1),
        ("top", "y", "h", 0),
        ("middle", "y", "h", 0.5),
        ("bottom", "y", "h", 1),
    ],
)
def test_all_alignments_use_selection_bounds_and_keep_other_axis_and_bendpoints(
    alignment, axis, size, fraction
):
    a = node(1, x=-100, y=50, w=120, h=90)
    b = node(2, type="sticker", x=700, y=400, w=260, h=180)
    arrow = edge(9, a, b, points=[[20, 95], [200, 95], [200, 490], [700, 490]])
    selected = [a, b]
    args = arguments(selected).model_copy(update={"mode": "align", "alignment": alignment})
    originals = deepcopy([*selected, arrow])

    batch = compile_arrangement(args, objects=[*selected, arrow], metadata={})
    boxes = resulting_boxes(selected, batch)
    lower = min(item[axis] for item in selected)
    upper = max(item[axis] + item[size] for item in selected)
    target = lower + (upper - lower) * fraction

    for item in selected:
        updated = boxes[(item["type"], item["id"])]
        assert updated[axis] + updated[size] * fraction == pytest.approx(target)
        other_axis = "y" if axis == "x" else "x"
        assert updated[other_axis] == item[other_axis]
    arrow_op = next(op for op in batch.ops if op.id == 9)
    points = [list(point) for point in arrow_op.data.points]
    assert points[1:-1] == [[200, points[0][1]], [200, points[-1][1]]]
    assert all(a[0] == b[0] or a[1] == b[1] for a, b in zip(points, points[1:], strict=False))
    assert arrow_op.data.model_fields_set == {"points"}
    assert arrow_op.data.points[0] == (
        boxes[("shape", 1)]["x"] + a["w"],
        boxes[("shape", 1)]["y"] + a["h"] / 2,
    )
    assert arrow_op.data.points[-1] == (
        boxes[("sticker", 2)]["x"],
        boxes[("sticker", 2)]["y"] + b["h"] / 2,
    )
    assert [*selected, arrow] == originals
    assert_position_only(batch, selected, [*selected, arrow])


@pytest.mark.parametrize("mode", ["layout", "align"])
@pytest.mark.parametrize("selected_endpoint", ["start", "end"])
def test_external_arrow_retains_interiors_unselected_endpoint_and_detached_arrow(
    mode, selected_endpoint
):
    a = node(1, x=500, y=200)
    b = node(2, type="sticker", x=100, y=500, w=260, h=180)
    outside = node(3, x=1000, y=900)
    arrow = edge(10, a, outside) if selected_endpoint == "start" else edge(10, outside, a)
    detached = {**edge(11, outside, outside), "start_ref": None, "end_ref": None}
    objects = [a, b, outside, arrow, detached]
    args = arguments([a, b]).model_copy(update={"mode": mode, "alignment": "left"})

    batch = compile_arrangement(args, objects=objects, metadata={})
    op = next(op for op in batch.ops if op.id == 10)
    points = [list(point) for point in op.data.points]
    endpoint = 0 if selected_endpoint == "start" else -1

    assert points[1:-1] == [[500, points[0][1]], [500, points[-1][1]]]
    assert all(a[0] == b[0] or a[1] == b[1] for a, b in zip(points, points[1:], strict=False))
    assert points[-1 if endpoint == 0 else 0] == arrow["points"][-1 if endpoint == 0 else 0]
    assert points[endpoint] != arrow["points"][endpoint]
    assert op.data.model_fields_set == {"points"}
    assert not any(op.id in {3, 11} and op.op == "update_shape" for op in batch.ops)


def test_partial_group_alignment_is_rejected_without_expanding_selection():
    a, b, outside = node(1), node(2, type="sticker"), node(3)
    metadata = {"groups": [{"id": "group", "name": "Review process", "members": [ref(a), ref(b)]}]}
    original = deepcopy(metadata)
    args = arguments([a, outside]).model_copy(update={"mode": "align", "alignment": "left"})

    with pytest.raises(DiagramLayoutError, match="Review process"):
        compile_arrangement(args, objects=[a, b, outside], metadata=metadata)
    assert metadata == original

    batch = compile_arrangement(
        arguments([a, b]).model_copy(update={"mode": "align", "alignment": "left"}),
        objects=[a, b, outside],
        metadata=metadata,
    )
    assert_position_only(batch, [a, b], [a, b, outside])


@pytest.mark.parametrize("kind", ["arrow", "line"])
def test_linear_only_selection_requires_a_block_or_sticker(kind):
    a, b = node(1), node(2)
    arrow = {**edge(3, a, b), "kind": kind}
    with pytest.raises(DiagramLayoutError, match="хотя бы один блок"):
        compile_for([arrow], [a, b, arrow])


@pytest.mark.parametrize("kind", ["arrow", "line"])
@pytest.mark.parametrize("mode", ["align", "layout"])
def test_mixed_group_linear_refs_assert_revisions_without_packing_or_duplicate_updates(kind, mode):
    a, b = node(1, x=300), node(2, type="sticker", x=700, y=500)
    arrow = {**edge(3, a, b), "kind": kind}
    detached = {
        **edge(4, a, b),
        "kind": kind,
        "start_ref": None,
        "end_ref": None,
        "points": [[-9000, -8000], [-9500, -8500]],
    }
    selected = [a, b, arrow, detached]
    metadata = {
        "groups": [
            {
                "id": "mixed",
                "name": "Mixed group",
                "members": [ref(item) for item in selected],
            }
        ]
    }
    args = arguments(selected).model_copy(update={"mode": mode, "alignment": "left"})

    batch = compile_arrangement(args, objects=selected, metadata=metadata)

    assert_position_only(batch, selected, selected)
    assert len(batch.ops) == 4
    boxes = resulting_boxes([a, b], batch)
    assert boxes[("shape", 1)]["x"] >= 300
    assert boxes[("sticker", 2)]["x"] >= 300
    arrow_op = next(op for op in batch.ops if op.op == "update_shape" and op.id == 3)
    assert arrow_op.revision == arrow["revision"]
    if mode == "align":
        assert boxes[("shape", 1)]["x"] == boxes[("sticker", 2)]["x"] == 300
        assert [list(point) for point in arrow_op.data.points[1:-1]] == arrow["points"][1:-1]
    detached_op = next(op for op in batch.ops if op.op == "update_shape" and op.id == 4)
    assert [list(point) for point in detached_op.data.points] == detached["points"]
    assert detached_op.data.model_fields_set == {"points"}


def test_omitting_selected_group_arrow_still_denies_partial_alignment():
    a, b = node(1), node(2, type="sticker")
    arrow = edge(3, a, b)
    metadata = {
        "groups": [
            {
                "id": "mixed",
                "name": "Mixed group",
                "members": [ref(item) for item in [a, b, arrow]],
            }
        ]
    }
    args = arguments([a, b]).model_copy(update={"mode": "align", "alignment": "left"})
    with pytest.raises(DiagramLayoutError, match="Mixed group"):
        compile_arrangement(args, objects=[a, b, arrow], metadata=metadata)


def test_explicit_group_arrow_revision_is_not_ignored():
    a, b = node(1), node(2, type="sticker")
    arrow = edge(3, a, b)
    args = arguments([a, b, arrow])
    with pytest.raises(DiagramLayoutError, match="изменился"):
        compile_arrangement(args, objects=[a, b, {**arrow, "revision": 8}], metadata={})


@pytest.mark.parametrize("change", ["missing", "stale"])
def test_missing_or_stale_object_fails_before_batch(change):
    a = node(1)
    objects = [] if change == "missing" else [{**a, "revision": a["revision"] + 1}]
    with pytest.raises(DiagramLayoutError):
        compile_for([a], objects)


@pytest.mark.parametrize("count", [0, 201])
def test_selection_requires_one_to_two_hundred_explicit_objects(count):
    with pytest.raises(ValidationError):
        arguments([node(i + 1) for i in range(count)])


def test_duplicate_selection_rejected_but_shape_sticker_namespace_is_independent():
    a, b = node(1), node(1, type="sticker")
    with pytest.raises(ValidationError):
        arguments([a, a])
    assert len(arguments([a, b]).objects) == 2


@pytest.mark.parametrize("arrow_count", [300, 301])
def test_batch_limit_counts_indirect_arrows_as_well_as_two_hundred_nodes(arrow_count):
    selected = [node(i + 1, x=100 if i else 500, y=i * 10) for i in range(200)]
    outside = node(999, x=5000, y=5000)
    arrows = [edge(1000 + i, selected[0], outside) for i in range(arrow_count)]
    args = arguments(selected).model_copy(update={"mode": "align", "alignment": "left"})

    if arrow_count == 301:
        with pytest.raises(DiagramLayoutError, match="500"):
            compile_arrangement(args, objects=[*selected, outside, *arrows], metadata={})
    else:
        batch = compile_arrangement(args, objects=[*selected, outside, *arrows], metadata={})
        assert len(batch.ops) == 500


@pytest.mark.parametrize("extra_arrow_count", [300, 301])
def test_limits_count_selected_linear_refs_once_alongside_indirect_arrows(extra_arrow_count):
    a = node(1, x=500, y=100)
    b = node(1, type="sticker", x=100, y=500)
    selected_arrows = [
        {**edge(10 + i, a, b), "kind": "arrow" if i % 2 else "line"} for i in range(198)
    ]
    outside = node(999, x=5000, y=5000)
    indirect_arrows = [edge(1000 + i, a, outside) for i in range(extra_arrow_count)]
    selected = [a, b, *selected_arrows]
    args = arguments(selected).model_copy(update={"mode": "align", "alignment": "left"})
    objects = [*selected, outside, *indirect_arrows]
    if extra_arrow_count == 301:
        with pytest.raises(DiagramLayoutError, match="500"):
            compile_arrangement(args, objects=objects, metadata={})
    else:
        batch = compile_arrangement(args, objects=objects, metadata={})
        assert len(batch.ops) == 500
        assert_position_only(batch, selected, objects)
    with pytest.raises(ValidationError):
        arguments([*selected, indirect_arrows[0]])


def test_general_move_schema_remains_backwards_compatible_without_revision():
    batch = BoardBatchSchema(
        ops=[
            {"op": "move_sticker", "id": 1, "data": {"canvas_x": 10, "canvas_y": 20}},
        ]
    )
    assert batch.ops[0].revision is None

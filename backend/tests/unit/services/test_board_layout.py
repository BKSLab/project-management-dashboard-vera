import itertools

import pytest
from pydantic import ValidationError

from src.schemas.board_diagrams import BoardDiagramInput, BoardShapeUpdatesInput
from src.services.board_layout import DiagramLayoutError, compile_diagram


def graph(nodes, links=(), **kwargs):
    return BoardDiagramInput(
        board_id=4,
        nodes=[{"key": key, "label": key} for key in nodes],
        edges=[
            {
                "source": {"type": "node", "key": a},
                "target": {"type": "node", "key": b},
                "label": label,
            }
            for a, b, label in links
        ],
        **kwargs,
    )


@pytest.mark.parametrize("direction", ["TB", "LR"])
def test_branch_merge_is_order_independent_nonoverlapping_and_bound(direction):
    data = graph(
        ["start", "decision", "yes", "no", "end"],
        [
            ("start", "decision", ""),
            ("decision", "yes", "Да"),
            ("decision", "no", "Нет"),
            ("yes", "end", ""),
            ("no", "end", ""),
        ],
        direction=direction,
    )
    batch = compile_diagram(data)
    shuffled = data.model_copy(
        update={
            "nodes": list(reversed(data.nodes)),
            "edges": list(reversed(data.edges)),
        }
    )

    assert compile_diagram(shuffled).model_dump(mode="json") == batch.model_dump(mode="json")
    boxes = [op.data for op in batch.ops if op.data.kind != "arrow"]
    for a, b in itertools.combinations(boxes, 2):
        assert a.x + a.w <= b.x or b.x + b.w <= a.x or a.y + a.h <= b.y or b.y + b.h <= a.y
    known = set()
    labels = []
    for op in batch.ops:
        for ref in (op.data.start_ref, op.data.end_ref):
            if ref:
                assert ref.client_id in known
        known.add(op.client_id)
        if op.data.kind == "arrow":
            assert op.data.style.route == "orthogonal"
            labels.append(op.data.label)
    assert "Да" in labels and "Нет" in labels
    assert len(batch.ops) == 10


@pytest.mark.parametrize("direction", ["TB", "LR"])
def test_cycles_disconnected_nodes_and_self_loop_do_not_collapse(direction):
    batch = compile_diagram(
        graph(
            ["a", "b", "c", "alone"],
            [
                ("a", "b", ""),
                ("b", "c", ""),
                ("c", "a", ""),
                ("a", "a", ""),
            ],
            direction=direction,
        )
    )
    arrows = [op.data for op in batch.ops if op.data.kind == "arrow"]
    assert len(batch.ops) == 8
    assert all(len(set(arrow.points)) >= 3 for arrow in arrows)


def test_append_avoids_existing_scene_and_can_link_existing_sticker():
    occupied = [
        {"type": "sticker", "id": 8, "x": 30, "y": 800, "w": 200, "h": 150},
        {
            "type": "shape",
            "kind": "arrow",
            "id": 9,
            "x": 10,
            "y": 1200,
            "w": 30,
            "h": 20,
        },
    ]
    data = BoardDiagramInput.model_validate(
        {
            **graph(["next"]).model_dump(),
            "edges": [
                {
                    "source": {"type": "sticker", "id": 8},
                    "target": {"type": "node", "key": "next"},
                }
            ],
        }
    )
    batch = compile_diagram(data, occupied=occupied)
    assert batch.ops[0].data.y > 1220
    arrow = batch.ops[1].data
    assert arrow.start_ref.id == 8 and arrow.start_ref.type == "sticker"
    assert arrow.end_ref.client_id == "node_next"


@pytest.mark.parametrize("ref", [{"type": "shape", "id": 777}, {"type": "sticker", "id": 777}])
def test_foreign_board_reference_is_rejected(ref):
    data = BoardDiagramInput(
        board_id=4,
        nodes=[{"key": "n", "label": "n"}],
        edges=[{"source": ref, "target": {"type": "node", "key": "n"}}],
    )
    with pytest.raises(DiagramLayoutError):
        compile_diagram(data)


def test_line_cannot_be_arrow_target():
    data = BoardDiagramInput(
        board_id=4,
        edges=[
            {
                "source": {"type": "shape", "id": 8},
                "target": {"type": "sticker", "id": 9},
            }
        ],
    )
    with pytest.raises(DiagramLayoutError):
        compile_diagram(
            data,
            occupied=[
                {
                    "type": "shape",
                    "kind": "arrow",
                    "id": 8,
                    "x": 0,
                    "y": 0,
                    "w": 50,
                    "h": 50,
                },
                {"type": "sticker", "id": 9, "x": 0, "y": 0, "w": 50, "h": 50},
            ],
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"nodes": [{"key": "a", "label": "a"}, {"key": "a", "label": "b"}]},
        {
            "nodes": [{"key": "a", "label": "a"}],
            "edges": [
                {
                    "source": {"type": "node", "key": "missing"},
                    "target": {"type": "node", "key": "a"},
                }
            ],
        },
        {"nodes": [{"key": "a", "label": " "}]},
        {"nodes": [{"key": "a", "label": "x\x00"}]},
        {"nodes": [{"key": "a", "label": "a"}], "author_id": 77},
        {"nodes": [{"key": "a", "label": "a"}], "project_id": 99},
        {"nodes": []},
    ],
)
def test_invalid_graph_and_principal_override_rejected(payload):
    with pytest.raises(ValidationError):
        BoardDiagramInput.model_validate({"board_id": 4, **payload})


@pytest.mark.parametrize(
    "updates",
    [
        [{"id": 1, "data": {"label": "x"}}],
        [{"id": 1, "revision": 1, "data": {"kind": "text"}}],
        [
            {"id": 1, "revision": 1, "data": {"label": "x"}},
            {"id": 1, "revision": 1, "data": {"label": "y"}},
        ],
        [
            {
                "id": 1,
                "revision": 1,
                "data": {"start_ref": {"type": "shape", "client_id": "new"}},
            }
        ],
        [{"id": 1, "revision": 1, "data": {"label": "x"}, "op": "delete_shape"}],
    ],
)
def test_agent_updates_require_revision_and_cannot_delete_or_create(updates):
    with pytest.raises(ValidationError):
        BoardShapeUpdatesInput(board_id=4, updates=updates)


def test_coordinate_overflow_is_rejected_before_batch():
    data = graph(["a"])
    with pytest.raises(ValidationError):
        compile_diagram(
            data,
            occupied=[
                {"type": "sticker", "id": 1, "x": 0, "y": 999999, "w": 100, "h": 100},
            ],
        )


def test_unequal_label_heights_use_clear_branch_corridor():
    data = graph(["source", "tall", "target"], [("source", "target", "")])
    data.nodes[1].label = "long " * 200
    batch = compile_diagram(data)
    boxes = {op.client_id: op.data for op in batch.ops if op.data.kind != "arrow"}
    lane_y = batch.ops[-1].data.points[1][1]
    assert lane_y > boxes["node_tall"].y + boxes["node_tall"].h


def test_json_schema_exposes_discriminated_refs_and_required_revision():
    schema = BoardDiagramInput.model_json_schema()
    assert schema["additionalProperties"] is False
    assert "discriminator" in schema["$defs"]["DiagramEdge"]["properties"]["source"]
    updates = BoardShapeUpdatesInput.model_json_schema()
    assert "revision" in updates["$defs"]["AgentShapeUpdate"]["required"]


@pytest.mark.parametrize("direction", ["TB", "LR"])
def test_back_edges_self_loops_and_skips_do_not_cut_new_blocks(direction):
    data = graph(
        ["a", "b", "c", "d", "e", "f"],
        [
            ("a", "b", ""),
            ("a", "c", ""),
            ("b", "d", ""),
            ("c", "d", ""),
            ("a", "d", "skip"),
            ("d", "e", ""),
            ("e", "f", ""),
            ("f", "e", "cycle"),
            ("a", "a", "loop"),
        ],
        direction=direction,
    )
    batch = compile_diagram(data)
    boxes = [op.data for op in batch.ops if op.data.kind != "arrow"]
    for op in batch.ops:
        if op.data.kind != "arrow":
            continue
        for a, b in zip(op.data.points, op.data.points[1:], strict=False):
            for box in boxes:
                if a[0] == b[0]:
                    crosses = (
                        box.x < a[0] < box.x + box.w
                        and max(a[1], b[1]) > box.y
                        and min(a[1], b[1]) < box.y + box.h
                    )
                else:
                    assert a[1] == b[1]
                    crosses = (
                        box.y < a[1] < box.y + box.h
                        and max(a[0], b[0]) > box.x
                        and min(a[0], b[0]) < box.x + box.w
                    )
                assert not crosses, (op.client_id, a, b, box.label)

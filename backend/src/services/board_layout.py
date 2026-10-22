"""Deterministic graph layout compiled to one ordinary editable shapes batch."""

from collections import defaultdict
from collections.abc import Sequence
from math import ceil
from typing import Any

from src.schemas.board_diagrams import BoardDiagramInput, DiagramRef
from src.schemas.board_shapes import BoardBatchSchema

NODE_WIDTH = 240.0
NODE_GAP = 80.0
LAYER_GAP = 120.0
MARGIN = 80.0


class DiagramLayoutError(ValueError):
    """Graph cannot be placed or references an unavailable scene object."""


def _ref_key(ref: DiagramRef) -> str:
    return f"node:{ref.key}" if ref.type == "node" else f"{ref.type}:{ref.id}"


def _layers(graph: BoardDiagramInput) -> dict[str, int]:
    """Condense strongly connected components; longest-path layers of their DAG."""
    adjacency: dict[str, set[str]] = {node.key: set() for node in graph.nodes}
    for edge in graph.edges:
        if edge.source.type == edge.target.type == "node":
            adjacency[edge.source.key].add(edge.target.key)
    return graph_layers(adjacency)


def graph_layers(adjacency: dict[str, set[str]]) -> dict[str, int]:
    """Condense cycles, then assign longest-path layers in a deterministic DAG."""
    index = 0
    indexes: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    active: set[str] = set()
    components: list[tuple[str, ...]] = []

    def visit(key: str) -> None:
        nonlocal index
        indexes[key] = low[key] = index
        index += 1
        stack.append(key)
        active.add(key)
        for target in sorted(adjacency[key]):
            if target not in indexes:
                visit(target)
                low[key] = min(low[key], low[target])
            elif target in active:
                low[key] = min(low[key], indexes[target])
        if low[key] == indexes[key]:
            members = []
            while True:
                member = stack.pop()
                active.remove(member)
                members.append(member)
                if member == key:
                    break
            components.append(tuple(sorted(members)))

    for key in sorted(adjacency):
        if key not in indexes:
            visit(key)
    components.sort()
    owner = {key: i for i, members in enumerate(components) for key in members}
    outgoing: dict[int, set[int]] = {i: set() for i in range(len(components))}
    indegree = dict.fromkeys(outgoing, 0)
    for key, targets in adjacency.items():
        for target in targets:
            start, end = owner[key], owner[target]
            if start != end and end not in outgoing[start]:
                outgoing[start].add(end)
                indegree[end] += 1
    levels = dict.fromkeys(outgoing, 0)
    ready = sorted(i for i in indegree if not indegree[i])
    while ready:
        current = ready.pop(0)
        for target in sorted(outgoing[current]):
            levels[target] = max(levels[target], levels[current] + 1)
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
                ready.sort()
    return {key: levels[owner[key]] for key in adjacency}


def _anchor(box: dict[str, float], name: str) -> list[float]:
    x, y, w, h = (box[key] for key in ("x", "y", "w", "h"))
    return {
        "top": [x + w / 2, y],
        "bottom": [x + w / 2, y + h],
        "left": [x, y + h / 2],
        "right": [x + w, y + h / 2],
    }[name]


def compile_diagram(
    graph: BoardDiagramInput, *, occupied: Sequence[dict[str, Any]] = ()
) -> BoardBatchSchema:
    """Append new nodes below the scene; existing nodes stay where the user put them.

    occupied entries have type=shape/sticker and the usual scene fields. References
    are resolved only against this board's scene. Shapes are created before arrows,
    allowing apply_batch to resolve client_id inside the same transaction.
    """
    boxes: dict[str, dict[str, float]] = {}
    refs: dict[str, dict[str, Any]] = {}
    for item in occupied:
        if item["type"] == "shape" and item.get("kind") in {"line", "arrow"}:
            continue
        key = f"{item['type']}:{item['id']}"
        boxes[key] = {name: float(item[name]) for name in ("x", "y", "w", "h")}
        refs[key] = {"type": item["type"], "id": item["id"]}
    for edge in graph.edges:
        for ref in (edge.source, edge.target):
            if ref.type != "node" and _ref_key(ref) not in boxes:
                raise DiagramLayoutError("Arrow target is not a block on this board.")
    levels = _layers(graph)
    rows: dict[int, list[str]] = defaultdict(list)
    nodes = {node.key: node for node in graph.nodes}
    heights = {
        key: max(
            100.0,
            32.0 + 22.0 * sum(max(1, ceil(len(line) / 22)) for line in node.label.split("\n")),
        )
        for key, node in nodes.items()
    }
    for key in sorted(nodes):
        rows[levels[key]].append(key)
    origin_y = max((float(item["y"]) + float(item["h"]) for item in occupied), default=0) + MARGIN
    cursor = origin_y if graph.direction == "TB" else MARGIN
    max_row_size = max((len(row) for row in rows.values()), default=1)
    ops = []
    for level in sorted(rows):
        row = rows[level]
        cross = MARGIN + (max_row_size - len(row)) * (NODE_WIDTH + NODE_GAP) / 2
        cross_y = origin_y
        for key in row:
            node = nodes[key]
            if graph.direction == "TB":
                box = {"x": cross, "y": cursor, "w": NODE_WIDTH, "h": heights[key]}
                cross += NODE_WIDTH + NODE_GAP
            else:
                box = {"x": cursor, "y": cross_y, "w": NODE_WIDTH, "h": heights[key]}
                cross_y += heights[key] + NODE_GAP
            ref_key = "node:" + key
            boxes[ref_key] = box
            refs[ref_key] = {"type": "shape", "client_id": "node_" + key}
            ops.append(
                {
                    "op": "create_shape",
                    "client_id": "node_" + key,
                    "data": {
                        "kind": node.kind,
                        **box,
                        "label": node.label,
                        "style": {"fill": node.color},
                        "z_index": 1,
                    },
                }
            )
        cursor += (
            max(heights[key] for key in row) if graph.direction == "TB" else NODE_WIDTH
        ) + LAYER_GAP
    right = max((b["x"] + b["w"] for b in boxes.values()), default=MARGIN)
    bottom = max((b["y"] + b["h"] for b in boxes.values()), default=origin_y)
    edges = sorted(graph.edges, key=lambda e: (_ref_key(e.source), _ref_key(e.target), e.label))
    for index, edge in enumerate(edges):
        start_key, end_key = _ref_key(edge.source), _ref_key(edge.target)
        start, end = boxes[start_key], boxes[end_key]
        # Only adjacent layers use the inter-layer corridor. Skips, back edges,
        # self-loops and links to existing objects use an exterior lane.
        adjacent = (
            edge.source.type == edge.target.type == "node"
            and levels[edge.target.key] == levels[edge.source.key] + 1
        )
        if graph.direction == "TB":
            start_anchor, end_anchor = "bottom", "top"
            a, b = _anchor(start, start_anchor), _anchor(end, end_anchor)
            source_bottom = (
                max(
                    boxes["node:" + key]["y"] + heights[key]
                    for key in rows[levels[edge.source.key]]
                )
                if edge.source.type == "node"
                else start["y"] + start["h"]
            )
            if adjacent:
                lane = source_bottom + LAYER_GAP / 2
                points = [a, [a[0], lane], [b[0], lane], b]
            else:
                # Leave the source below its whole row, travel outside all
                # columns, then enter the target from the corridor above it.
                out_y, in_y = source_bottom + LAYER_GAP / 4, end["y"] - LAYER_GAP / 4
                lane = right + MARGIN + index * 12
                points = [a, [a[0], out_y], [lane, out_y], [lane, in_y], [b[0], in_y], b]
        else:
            start_anchor, end_anchor = "right", "left"
            a, b = _anchor(start, start_anchor), _anchor(end, end_anchor)
            if adjacent:
                lane = (a[0] + b[0]) / 2
                points = [a, [lane, a[1]], [lane, b[1]], b]
            else:
                out_x, in_x = start["x"] + start["w"] + LAYER_GAP / 4, end["x"] - LAYER_GAP / 4
                lane = bottom + MARGIN + index * 12
                points = [a, [out_x, a[1]], [out_x, lane], [in_x, lane], [in_x, b[1]], b]
        ops.append(
            {
                "op": "create_shape",
                "client_id": f"edge_{index:03d}",
                "data": {
                    "kind": "arrow",
                    "points": points,
                    "label": edge.label,
                    "z_index": 0,
                    "start_ref": {**refs[start_key], "anchor": start_anchor},
                    "end_ref": {**refs[end_key], "anchor": end_anchor},
                    "style": {"route": "orthogonal", "end_head": "arrow"},
                },
            }
        )
    # The shared schema also checks finite coordinates and canvas limits.
    return BoardBatchSchema.model_validate({"ops": ops})

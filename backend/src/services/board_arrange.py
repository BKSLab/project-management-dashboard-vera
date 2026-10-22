"""Compile explicit rearrangement into position-only updates of existing objects."""

from copy import deepcopy
from typing import Any

from src.schemas.board_diagrams import BoardArrangeInput
from src.schemas.board_shapes import MAX_BATCH_OPS, BoardBatchSchema
from src.services.board_connector_geometry import (
    adjust_connector_points,
    connector_endpoints,
)
from src.services.board_connector_geometry import (
    anchor_point as _anchor,
)
from src.services.board_layout import LAYER_GAP, NODE_GAP, DiagramLayoutError, graph_layers


def _key(item: dict) -> tuple[str, int]:
    return item["type"], item["id"]


def _layout(selected: dict, arrows: list[dict], direction: str) -> dict:
    names = {key: f"{key[0]}:{key[1]}" for key in selected}
    graph = {name: set() for name in names.values()}
    for arrow in arrows:
        start, end = arrow.get("start_ref"), arrow.get("end_ref")
        if start and end and _key(start) in names and _key(end) in names:
            graph[names[_key(start)]].add(names[_key(end)])
    layers = graph_layers(graph)
    rows: dict[int, list] = {}
    # Spatial ordering preserves the user's order within disconnected layers.
    for key in sorted(
        selected,
        key=lambda key: (selected[key]["x"] if direction == "TB" else selected[key]["y"], key),
    ):
        rows.setdefault(layers[names[key]], []).append(key)
    origin_x = min(item["x"] for item in selected.values())
    origin_y = min(item["y"] for item in selected.values())
    cursor = origin_y if direction == "TB" else origin_x
    boxes = {}
    for level in sorted(rows):
        cross = origin_x if direction == "TB" else origin_y
        row = rows[level]
        for key in row:
            item = selected[key]
            x, y = (cross, cursor) if direction == "TB" else (cursor, cross)
            boxes[key] = {**item, "x": x, "y": y}
            cross += (item["w"] if direction == "TB" else item["h"]) + NODE_GAP
        cursor += max(selected[key]["h" if direction == "TB" else "w"] for key in row) + LAYER_GAP
    return boxes


def _align(selected: dict, alignment: str) -> dict:
    left = min(item["x"] for item in selected.values())
    top = min(item["y"] for item in selected.values())
    right = max(item["x"] + item["w"] for item in selected.values())
    bottom = max(item["y"] + item["h"] for item in selected.values())
    boxes = {}
    for key, item in selected.items():
        box = dict(item)
        if alignment in {"left", "center", "right"}:
            box["x"] = {
                "left": left,
                "center": (left + right - item["w"]) / 2,
                "right": right - item["w"],
            }[alignment]
        else:
            box["y"] = {
                "top": top,
                "middle": (top + bottom - item["h"]) / 2,
                "bottom": bottom - item["h"],
            }[alignment]
        boxes[key] = box
    return boxes


def compile_arrangement(
    args: BoardArrangeInput, *, objects: list[dict[str, Any]], metadata: dict
) -> BoardBatchSchema:
    """Never recreate nodes, patch labels/styles/sizes or move implicit members."""
    current = {_key(item): item for item in objects}
    selected = {}
    for ref in args.objects:
        key = (ref.type, ref.id)
        item = current.get(key)
        if item is None:
            raise DiagramLayoutError("Выберите существующие объекты этой доски.")
        if item["revision"] != ref.revision:
            raise DiagramLayoutError("Объект изменился; перечитайте свежую сцену.")
        selected[key] = item
    if args.mode == "align":
        for group in metadata.get("groups", []):
            members = {_key(ref) for ref in group["members"]}
            if members & selected.keys() and not members <= selected.keys():
                raise DiagramLayoutError(
                    f"Выберите все объекты группы «{group['name']}» для выравнивания."
                )
    arrows = [
        item
        for item in objects
        if item["type"] == "shape" and item.get("kind") in {"arrow", "line"}
    ]
    nodes = {
        key: item
        for key, item in selected.items()
        if item["type"] != "shape" or item.get("kind") not in {"arrow", "line"}
    }
    if not nodes:
        raise DiagramLayoutError(
            "Для перестройки или выравнивания выберите хотя бы один блок или стикер."
        )
    boxes = (
        _align(nodes, args.alignment)
        if args.mode == "align"
        else _layout(nodes, arrows, args.direction)
    )
    ops = []
    # Include no-op positions as revision assertions for every explicit selection.
    for ref in args.objects:
        if (ref.type, ref.id) not in boxes:
            continue
        box = boxes[(ref.type, ref.id)]
        ops.append(
            {
                "op": "update_shape" if ref.type == "shape" else "move_sticker",
                "id": ref.id,
                "revision": ref.revision,
                "data": {"x": box["x"], "y": box["y"]}
                if ref.type == "shape"
                else {"canvas_x": box["x"], "canvas_y": box["y"]},
            }
        )
    for arrow in arrows:
        start, end = arrow.get("start_ref"), arrow.get("end_ref")
        start_key = _key(start) if start else None
        end_key = _key(end) if end else None
        explicitly_selected = _key(arrow) in selected
        if start_key not in boxes and end_key not in boxes and not explicitly_selected:
            continue
        points = deepcopy(arrow["points"])
        changes = {}
        if args.mode == "layout" and start_key in boxes and end_key in boxes:
            # Explicit layout authorizes internal routing. Align/external routes
            # preserve the manual path with orthogonal attachment adjustments.
            sa, ea = ("bottom", "top") if args.direction == "TB" else ("right", "left")
            a, b = _anchor(boxes[start_key], sa), _anchor(boxes[end_key], ea)
            if args.direction == "TB":
                lane = (a[1] + b[1]) / 2
                points = [a, [a[0], lane], [b[0], lane], b]
            else:
                lane = (a[0] + b[0]) / 2
                points = [a, [lane, a[1]], [lane, b[1]], b]
            changes.update(start_ref={**start, "anchor": sa}, end_ref={**end, "anchor": ea})
        else:
            a, b = connector_endpoints(arrow, current, boxes)
            points = adjust_connector_points(
                arrow["points"], a, b, (arrow.get("style") or {}).get("route", "straight")
            )
        # One operation per arrow, including a points replay when it is selected
        # only for group completeness. This asserts its revision and locks inside
        # the real shared batch without packing the arrow as a block.
        if points != arrow["points"] or changes or explicitly_selected:
            ops.append(
                {
                    "op": "update_shape",
                    "id": arrow["id"],
                    "revision": arrow["revision"],
                    "data": {"points": points, **changes},
                }
            )
    if len(ops) > MAX_BATCH_OPS:
        raise DiagramLayoutError(
            "Перестройка затрагивает больше 500 объектов со стрелками; уменьшите выделение."
        )
    return BoardBatchSchema.model_validate(
        {
            "expected_revision": args.expected_revision,
            "ops": ops,
        }
    )

"""Manual connector routes retain axis runs and use the UI contour anchor formulas."""

from copy import deepcopy

import pytest

from src.services.board_connector_geometry import (
    adjust_connector_points,
    anchor_point,
    connector_endpoints,
)
from src.services.board_layout import DiagramLayoutError


def assert_axis_segments(points):
    assert len(points) <= 50
    assert all(
        a[0] == pytest.approx(b[0]) or a[1] == pytest.approx(b[1])
        for a, b in zip(points, points[1:], strict=False)
    )


def test_hvh_top_align_regression_has_no_diagonal_and_keeps_manual_lane():
    stored = [[300, 450], [430, 450], [430, 470], [550, 470]]
    changed = adjust_connector_points(stored, [300, 450], [550, 450], "orthogonal")
    assert changed == [[300, 450], [430, 450], [430, 450], [550, 450]]
    assert_axis_segments(changed)


@pytest.mark.parametrize("transpose", [False, True])
def test_attachment_propagates_across_entire_collinear_prefix_and_suffix(transpose):
    stored = [[0, 0], [10, 0], [20, 0], [20, 10], [20, 20], [30, 20], [40, 20]]
    expected = [[-10, 5], [10, 5], [20, 5], [20, 10], [20, 30], [30, 30], [60, 30]]
    if transpose:
        stored, expected = ([list(reversed(p)) for p in path] for path in (stored, expected))
    original = deepcopy(stored)
    changed = adjust_connector_points(stored, expected[0], expected[-1], "orthogonal")
    assert changed == expected
    assert changed[3] == stored[3]  # The manual middle subdivision is not rerouted.
    assert stored == original
    assert_axis_segments(changed)


def test_zero_length_subdivisions_join_attachment_chains_without_diagonals():
    stored = [[0, 0], [0, 0], [20, 0], [20, 0], [20, 20], [40, 20], [40, 20]]
    changed = adjust_connector_points(stored, [-10, 5], [60, 30], "orthogonal")
    assert changed == [[-10, 5], [-10, 5], [20, 5], [20, 5], [20, 30], [60, 30], [60, 30]]
    assert_axis_segments(changed)


@pytest.mark.parametrize("route", ["orthogonal", "straight"])
def test_equal_endpoint_displacement_translates_every_manual_point(route):
    stored = [[0, 0], [20, 0], [20, 30], [50, 30], [50, 80], [100, 80]]
    changed = adjust_connector_points(stored, [13, -7], [113, 73], route)
    assert changed == [[x + 13, y - 7] for x, y in stored]


@pytest.mark.parametrize("transpose", [False, True])
def test_fifty_point_collinear_chain_can_become_elbows_when_endpoints_diverge(transpose):
    stored = [[i * 10, 450] for i in range(50)]
    start, end = [300, 450], [550, 470]
    if transpose:
        stored = [list(reversed(point)) for point in stored]
        start, end = list(reversed(start)), list(reversed(end))
    changed = adjust_connector_points(stored, start, end, "orthogonal")
    assert changed[0] == start and changed[-1] == end
    assert len(changed) <= 50
    assert_axis_segments(changed)


def test_fifty_point_bent_route_retains_all_main_bends_without_truncation():
    stored = [[0, 0], [20, 0]]
    for index in range(48):
        x, y = stored[-1]
        stored.append([x + 10, y] if index % 2 else [x, y + 10])
    changed = adjust_connector_points(
        stored, [-10, 5], [stored[-1][0] + 20, stored[-1][1] + 15], "orthogonal"
    )
    assert len(changed) == 50
    assert changed[2:-2] == stored[2:-2]
    assert_axis_segments(changed)


@pytest.mark.parametrize("end", [[10, 0], [0, 10], [10, 10]])
def test_coincident_old_points_keep_both_new_endpoints(end):
    changed = adjust_connector_points([[0, 0], [0, 0], [0, 0]], [0, 0], end, "orthogonal")
    assert changed[0] == [0, 0] and changed[-1] == end
    assert_axis_segments(changed)


@pytest.mark.parametrize(
    "stored",
    [
        [[0, 0], [30, 0]],
        [[0, 0], [10, 0], [20, 0], [30, 0]],
        [[0, 0], [10, 10], [20, -10], [30, 0]],
    ],
)
def test_straight_routes_do_not_normalize_interiors(stored):
    changed = adjust_connector_points(stored, [-5, 8], [50, 20], "straight")
    assert changed == [[-5, 8], *stored[1:-1], [50, 20]]


def test_fifty_one_points_is_a_readable_failure():
    with pytest.raises(DiagramLayoutError, match="50"):
        adjust_connector_points([[i, 0] for i in range(51)], [0, 5], [50, 10], "orthogonal")


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("rect", [300, 200]),
        ("sticker", [300, 200]),
        ("ellipse", [270.71067811865476, 185.35533905932738]),
        ("diamond", [250, 175]),
    ],
)
def test_center_anchors_match_ui_contour_instead_of_bbox_center(kind, expected):
    node = {
        "type": "sticker" if kind == "sticker" else "shape",
        "kind": kind,
        "x": 100,
        "y": 100,
        "w": 200,
        "h": 100,
    }
    assert anchor_point(node, "center", [400, 250]) == pytest.approx(expected)
    assert anchor_point(node, "center") == [200, 150]


def test_resolved_center_anchors_match_connectorpoints_rough_opposite_anchor_and_rounding():
    a = {"type": "shape", "id": 1, "kind": "diamond", "x": 100, "y": 100, "w": 200, "h": 100}
    b = {"type": "sticker", "id": 2, "x": 400, "y": 200, "w": 100, "h": 100}
    arrow = {
        "points": [[200, 150], [400, 250]],
        "start_ref": {"type": "shape", "id": 1, "anchor": "center"},
        "end_ref": {"type": "sticker", "id": 2, "anchor": "left"},
    }
    start, end = connector_endpoints(arrow, {("shape", 1): a, ("sticker", 2): b}, {("shape", 1): a})
    assert start == [250, 175] and end == [400, 250]


@pytest.mark.parametrize(
    ("coordinate", "expected"),
    [
        (0.049999999999999996, 0),
        (0.05, 0.1),
        (-0.05000000000000002, -0.1),
        (-0.05, 0),
    ],
)
def test_rounding_near_positive_and_negative_half_coordinates_matches_javascript(
    coordinate, expected
):
    a = {"type": "shape", "id": 1, "kind": "rect", "x": coordinate, "y": 0, "w": 1, "h": 1}
    arrow = {
        "points": [[coordinate, 0.5], [5, 0.5]],
        "start_ref": {"type": "shape", "id": 1, "anchor": "left"},
    }
    assert connector_endpoints(arrow, {("shape", 1): a}, {("shape", 1): a})[0] == [expected, 0.5]


def test_external_center_contour_tracks_opposite_node_without_moving_external_node():
    a = {"type": "shape", "id": 1, "kind": "diamond", "x": 100, "y": 100, "w": 200, "h": 100}
    b = {"type": "sticker", "id": 2, "x": 400, "y": 200, "w": 100, "h": 100}
    original = deepcopy(a)
    arrow = {
        "points": [[255.6, 172.2], [300, 172.2], [300, 230], [400, 230]],
        "start_ref": {"type": "shape", "id": 1, "anchor": "center"},
        "end_ref": {"type": "sticker", "id": 2, "anchor": "center"},
    }
    start, end = connector_endpoints(
        arrow, {("shape", 1): a, ("sticker", 2): b}, {("sticker", 2): {**b, "y": 0}}
    )
    assert start == [255.6, 127.8] and end == [400, 70]
    assert a == original
    points = adjust_connector_points(arrow["points"], start, end, "orthogonal")
    assert points == [[255.6, 127.8], [300, 127.8], [300, 70], [400, 70]]
    assert_axis_segments(points)


def test_rounding_of_negative_half_coordinate_matches_javascript():
    a = {"type": "shape", "id": 1, "kind": "rect", "x": -1.05, "y": 0, "w": 1, "h": 1}
    arrow = {
        "points": [[-1.05, 0.5], [5, 0.5]],
        "start_ref": {"type": "shape", "id": 1, "anchor": "left"},
    }
    assert connector_endpoints(arrow, {("shape", 1): a}, {("shape", 1): a})[0] == [-1.0, 0.5]

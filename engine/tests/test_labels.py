# FILE: tests/test_labels.py
import pytest
from shapely.geometry import Polygon, box

from engine_params import load_params
from layout.labels import LabelPlacementError, LabelSolver

P = load_params()
CANVAS = box(-10, -10, 40, 40)
EMPTY = Polygon()
LINES = [("시장 홀", "room"), ("162㎡", "sub")]


def test_label_goes_to_open_center_of_region():
    placement = LabelSolver(P, CANVAS).place(box(0, 0, 20, 20), LINES, EMPTY)
    cx, cy = placement.box.centroid.x, placement.box.centroid.y
    assert (cx, cy) == pytest.approx((10, 10), abs=0.6)
    assert placement.leader is None
    assert len(placement.line_centers) == 2
    assert placement.line_centers[0][1] > placement.line_centers[1][1]  # 첫 줄이 위


def test_label_avoids_obstacles():
    obstacle = box(8, 8, 12, 12)
    placement = LabelSolver(P, CANVAS).place(box(0, 0, 20, 20), LINES, obstacle)
    assert not placement.box.intersects(obstacle)
    assert box(0, 0, 20, 20).contains(placement.box)


def test_label_uses_leader_when_region_is_too_small():
    region = box(0, 0, 1.0, 1.0)
    placement = LabelSolver(P, CANVAS).place(region, LINES, EMPTY)
    assert placement.leader is not None
    assert not placement.box.intersects(region)


def test_labels_never_overlap_each_other():
    solver = LabelSolver(P, CANVAS)
    region = box(0, 0, 20, 20)
    first = solver.place(region, LINES, EMPTY)
    second = solver.place(region, [("공공보행통로", "room"), ("420㎡", "sub")], EMPTY)
    assert not first.box.intersects(second.box)


def test_no_space_raises():
    tiny = box(0, 0, 1, 1)
    with pytest.raises(LabelPlacementError):
        LabelSolver(P, tiny).place(tiny, LINES, EMPTY)

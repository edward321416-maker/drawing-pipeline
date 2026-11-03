from shapely.geometry import Polygon, box

from engine_params import load_params
from layout.labels import LabelSolver

P = load_params()


def test_label_finds_a_narrow_free_band_between_obstacles():
    """1:50처럼 라벨이 작은 축척에서 폭이 얇은 빈 띠도 놓치지 않는다(탐색 간격이 라벨 크기에 맞춰진다)."""
    from dataclasses import replace

    sp = replace(P, scale_denominator=50, label_pad_m=0.08, label_gap_m=0.1)
    region = box(0, 0, 3.0, 3.0)
    obstacles = box(-1, -1, 4, 4).difference(box(-1, 1.0, 4, 1.62))   # 높이 0.62 m 띠만 비어 있고 나머지는 모두 막힘
    placement = LabelSolver(sp, box(-2, -2, 5, 5)).place(region, [("장애인 화장실", "room"), ("7.7㎡", "sub")], obstacles)
    assert placement.leader is None
    assert region.contains(placement.box) and not placement.box.intersects(obstacles)

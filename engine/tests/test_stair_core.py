import math
from dataclasses import replace

import pytest
from shapely.geometry import box
from shapely.ops import unary_union

from checks.registry import run_symbol_checks
from checks.symbol_rules import check_g3_door_swings, check_r1_stair_core
from engine_params import load_params
from symbols.stair_core import all_geometry, build_stair_core, core_footprint

P = load_params()
BOUNDS = {"A": (0, 47, 6, 54), "B": (47, 47, 54, 54), "C": (48, 0, 54, 6), "D": (0, 0, 6, 6)}
SIDE = {"A": "S", "B": "S", "C": "W", "D": "E"}


def core(cid="A", p=None):
    return build_stair_core(cid, BOUNDS[cid], SIDE[cid], p or P.stair)


def with_stair(**kw):
    return replace(P.stair, **kw)


def test_core_a_matches_the_midterm_stair_counts():
    c = core("A")
    assert [f.treads for f in c.flights] == [9, 12, 9, 12]   # 6×7 m 코어: 중간발표 stair_capacity와 같은 계산
    assert c.steps_provided == 42 and c.steps_required == 34  # 6.0 m / 0.18 m → 34단
    assert c.vestibule.area == pytest.approx(5.5 * (1.6 - 0.075))
    assert len(c.doors) == 2 and len(c.landings) == 4


def test_break_line_sits_on_the_ninth_tread_of_the_first_flight():
    c = core("A")
    assert c.break_flight == 0
    assert c.break_dist == pytest.approx(8.5 * 0.28)          # 1.5 m 절단 → 9번째 디딤판 한가운데
    solid = [s for _l, s in c.flights[0].tread_lines]
    assert solid.count(True) == 8 and solid.count(False) == 0  # 9번째 디딤판의 앞쪽 선까지 실선
    assert all(not s for f in c.flights[1:] for _l, s in f.tread_lines)  # 이후 갈래는 모두 점선
    assert c.break_line is not None and c.break_line.length > 1.2


@pytest.mark.parametrize("cid", ["A", "B", "C", "D"])
def test_every_core_passes_r1_and_g3(cid):
    c = core(cid)
    assert run_symbol_checks(c, P) == []


@pytest.mark.parametrize("cid, expect", [("A", "S"), ("B", "S"), ("C", "W"), ("D", "E")])
def test_vestibule_is_on_the_hall_side_and_geometry_stays_in_the_core(cid, expect):
    c = core(cid)
    x0, y0, x1, y1 = c.bounds
    vx, vy = c.vestibule.centroid.x, c.vestibule.centroid.y
    side = {"S": vy < (y0 + y1) / 2, "W": vx < (x0 + x1) / 2, "E": vx > (x0 + x1) / 2}[expect]
    assert side
    # 코어 몸체(벽·계단)는 바깥 치수 안에 있다. 문 스윙만 1.2 m 밖(홀 쪽)으로 나간다.
    body = unary_union([c.walls, c.partition, *[f.polygon for f in c.flights], *c.landings])
    assert body.within(core_footprint(c).buffer(1e-6))
    assert all_geometry(c).within(core_footprint(c).buffer(1.2 + 1e-6))


def test_outer_door_opens_toward_the_hall_and_inner_door_into_the_vestibule():
    for cid in "ABCD":
        c = core(cid)
        outer, inner = c.doors
        assert outer.swing.intersection(core_footprint(c)).area < 1e-9
        assert inner.swing.intersection(c.vestibule.buffer(0.1)).area >= 0.99 * inner.swing.area


def test_inner_door_faces_the_main_landing():
    c = core("A")
    inner = c.doors[1]
    main = c.landings[0]
    # 계단실 쪽 문의 개구 폭(문 폭)이 주 계단참 폭과 겹친다
    assert inner.hinge[0] == pytest.approx(main.bounds[0], abs=1e-6)
    assert math.dist(inner.hinge, inner.closed_end) == pytest.approx(main.bounds[2] - main.bounds[0], abs=1e-6)


def test_r1_detects_narrow_flights_short_treads_and_few_steps():
    narrow = core("A", with_stair(flight_w_m=1.1))
    assert any("유효너비" in v.message for v in check_r1_stair_core(narrow, P))
    shallow = core("A", with_stair(tread_m=0.25))
    assert any("디딤판" in v.message for v in check_r1_stair_core(shallow, P))
    low_floor = core("D", with_stair(riser_m=0.12, floor_height_m=6.0))   # 챌면을 낮추면 필요 단수가 늘어 모자란다
    assert any("필요한" in v.message for v in check_r1_stair_core(low_floor, P))


def test_r1_detects_small_vestibule_and_narrow_door():
    small = core("A", with_stair(vestibule_depth_m=0.5))
    assert any("부속실" in v.message for v in check_r1_stair_core(small, P))
    narrow_door = core("A", with_stair(door_w_m=0.9))
    assert any("폭" in v.message for v in check_r1_stair_core(narrow_door, P))


def test_g3_detects_a_door_that_sweeps_through_the_wall():
    wide = core("A", with_stair(door_w_m=2.0))     # 문이 커서 부속실 깊이(1.5 m)를 넘어 바깥 벽을 쓸고 지나간다
    v = check_g3_door_swings(wide, P)
    assert v and all(x.check == "G3" for x in v)


def test_hall_door_offset_moves_the_outer_door_only_and_stays_inside_the_wall():
    centered = core("B")
    moved = build_stair_core("B", BOUNDS["B"], "S", P.stair, hall_door_offset=-2.3)
    assert moved.doors[0].hinge[0] == pytest.approx(centered.doors[0].hinge[0] - 2.3)
    assert moved.doors[1].hinge == pytest.approx(centered.doors[1].hinge)   # 계단실 쪽 문은 주 계단참에 그대로
    assert run_symbol_checks(moved, P) == []
    with pytest.raises(ValueError):
        build_stair_core("B", BOUNDS["B"], "S", P.stair, hall_door_offset=-3.0)  # 벽 모서리를 침범


def test_core_too_small_for_four_flights_is_rejected():
    with pytest.raises(ValueError):
        build_stair_core("X", (0, 0, 3.5, 3.5), "S", P.stair)

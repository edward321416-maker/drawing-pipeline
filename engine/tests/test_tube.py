from dataclasses import replace

from shapely.geometry import Point

from checks.registry import run_tube_checks
from engine_params import load_params
from master.build_master import load_source
from master.tube_sheet import build_world_tubes
from symbols.tube import build_elevator, build_light, build_ramp

P = load_params()


def _ids(vs):
    return {v.check for v in vs}


def test_real_tubes_pass_r3_with_real_columns():
    world = build_world_tubes(load_source(), P)
    assert set(world) == {"T1", "T2", "T3", "T4", "CAP_W"}
    for t in world.values():
        assert run_tube_checks(t, P) == [], t.tube_id
    assert world["T3"].center == (12.0, 42.0) and world["T4"].center == (40.0, 42.0)


def test_ramp_has_double_rim_and_one_smooth_spiral():
    t = build_ramp("T1", "T1", (0, 0), 4.5, P.tube)
    assert len(t.rims) == 2 and t.spiral.is_simple and t.spiral.geom_type == "LineString"
    assert t.band.contains(t.arrow_head) and t.inner_ring is not None


def test_elevator_has_two_square_shafts_inside_and_a_lobby():
    t = build_elevator("T3", "T3", (0, 0), 4.0, P.tube)
    assert len(t.shafts) == 2 and all(len(s.diagonals) == 2 for s in t.shafts)
    assert t.lobby.intersection(t.shafts[0].outer).area < 1e-9
    assert t.lobby.area > 15 and run_tube_checks(t, P) == []


def test_r3_flags_column_in_ramp_and_in_lobby():
    ramp = build_ramp("T1", "T1", (0, 0), 4.5, P.tube, [Point(3.2, 0).buffer(0.45)])
    assert "R3" in _ids(run_tube_checks(ramp, P))
    ev = build_elevator("T3", "T3", (0, 0), 4.0, P.tube, [Point(0, -2.0).buffer(0.45)])
    assert "R3" in _ids(run_tube_checks(ev, P))


def test_r3_flags_shafts_leaving_cylinder_or_overlapping():
    big = build_elevator("T3", "T3", (0, 0), 4.0, replace(P.tube, shaft_to_glass_m=0.0))
    assert "R3" in _ids(run_tube_checks(big, P))        # 이격 0으로 만든 승강로는 검사 기준(0.3 m)을 못 넘는다
    ov = build_elevator("T3", "T3", (0, 0), 4.0, replace(P.tube, shaft_gap_m=-0.4, shaft_to_glass_m=0.3))
    assert any("겹침" in v.message for v in run_tube_checks(ov, P))


def test_r3_flags_wrong_glass_thickness_and_narrow_ramp():
    t = build_light("T2", "T2", (0, 0), 4.5, P.tube)
    assert run_tube_checks(t, P) == []
    assert "R3" in _ids(run_tube_checks(t, replace(P, tube=replace(P.tube, glass_t_m=0.3))))
    narrow = build_ramp("T1", "T1", (0, 0), 4.5, replace(P.tube, ramp_w_m=1.0))
    assert "R3" in _ids(run_tube_checks(narrow, P))
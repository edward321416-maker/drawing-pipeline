from dataclasses import replace

import pytest
from shapely.geometry import Point

from checks.registry import run_restroom_checks
from checks.restroom_rules import check_g3_restroom_doors, check_r2_restroom
from engine_params import load_params
from symbols.restroom import Fixture, all_doors, build_restroom

P = load_params()
# 마스터에 조립된 위치: 이웃 코어에 맞닿게 옮긴 뒤(B 북쪽 +0.225 m, C 남쪽 -0.325 m, design_adjustments.json)
ROOMS = {"B": ((49.5, 41.625, 54.0, 46.925), "unisex", (53.4, 45.0)),
         "C": ((48.5, 6.075, 54.0, 11.875), "split", (53.4, 9.0))}
# 중간발표 원본 위치
ORIGINAL_ROOMS = {"B": ((49.5, 41.4, 54.0, 46.7), "unisex", (53.4, 45.0)),
                  "C": ((48.5, 6.4, 54.0, 12.2), "split", (53.4, 9.0))}


def room(rid, p=None, column=True, rooms=None):
    bounds, program, col = (rooms or ROOMS)[rid]
    cols = [Point(*col).buffer(0.45, quad_segs=12)] if column else []
    return build_restroom(rid, bounds, program, p or P.restroom, cols)


@pytest.mark.parametrize("rid", ["B", "C"])
def test_both_rooms_pass_r2_and_g3(rid):
    assert run_restroom_checks(room(rid), P) == []


@pytest.mark.parametrize("rid", ["B", "C"])
def test_both_rooms_also_pass_at_the_original_midterm_position(rid):
    assert run_restroom_checks(room(rid, rooms=ORIGINAL_ROOMS), P) == []


def test_room_b_is_one_shared_room_with_an_accessible_cubicle():
    rr = room("B")
    assert [u.name for u in rr.units] == ["공용"]
    kinds = [f.kind for f in rr.fixtures]
    assert kinds.count("basin") == 2 and kinds.count("wc") == 2 and kinds.count("urinal") == 0
    assert sorted(c.kind for c in rr.cubicles) == ["accessible", "general"]
    assert any(d.kind == "sliding" for d in all_doors(rr))           # 장애인 큐비클은 슬라이딩 문


def test_room_c_splits_men_women_and_accessible_with_their_own_doors():
    rr = room("C")
    assert [u.name for u in rr.units] == ["남", "여", "장애인"]
    def kinds(prefix):
        return [f.kind for f in rr.fixtures if f.name.startswith(prefix)]

    assert [f.kind for f in rr.fixtures].count("urinal") == 2                      # 소변기는 남자 방에만 있다
    assert kinds("남").count("wc") == 1 and kinds("남").count("basin") == 2
    assert kinds("여").count("wc") == 2 and kinds("여").count("basin") == 2
    assert sorted(kinds("장애인")) == ["basin", "wc"]
    men = next(u for u in rr.units if u.name == "남")
    assert all(men.interior.contains(f.polygon) for f in rr.fixtures if f.kind == "urinal")
    assert [u.door.kind for u in rr.units] == ["swing", "swing", "sliding"]
    assert len({u.door.hinge for u in rr.units}) == 3                 # 문이 각자 따로


@pytest.mark.parametrize("rid", ["B", "C"])
def test_swing_doors_open_toward_the_hall_and_clear_zones_are_inside_the_room(rid):
    rr = room(rid)
    for u in rr.units:
        assert u.clear_zone.difference(u.interior).area < 1e-9
        if u.door.swing is not None:
            assert u.door.swing.intersection(u.interior).area < 1e-9


def test_accessible_turning_circle_fits_inside_and_is_free():
    for rid in ("B", "C"):
        rr = room(rid)
        acc = next(u for u in rr.units if u.turning is not None)
        assert acc.turning.area == pytest.approx(3.14159 * 0.75 ** 2, rel=0.01)
        assert not any(acc.turning.intersects(f.polygon) and acc.turning.intersection(f.polygon).area > 1e-6 for f in rr.fixtures)


def test_r2_detects_an_obstacle_in_front_of_the_door():
    rr = room("B")
    zone = rr.units[0].clear_zone
    rr.fixtures.append(Fixture("막는 물건", "basin", zone.buffer(-0.1)))
    v = check_r2_restroom(rr, P)
    assert any("가로막힘" in x.message and "출입구" in x.message for x in v)


def test_r2_still_detects_an_obstacle_in_the_route_to_the_accessible_door():
    rr = room("B")
    rr.fixtures.append(Fixture("통로 위 물건", "basin", rr.units[0].corridor.centroid.buffer(0.2)))
    assert any("진입 통로" in x.message and "가로막힘" in x.message for x in check_r2_restroom(rr, P))


def test_corridor_ends_at_the_sliding_door_travel_end_plus_margin_and_stays_wide_enough():
    rr = room("B")
    corridor = rr.units[0].corridor
    sliding = next(d for d in all_doors(rr) if d.kind == "sliding")
    assert corridor.bounds[2] == pytest.approx(sliding.travel.bounds[2] + 0.3, abs=1e-6)
    assert corridor.bounds[3] - corridor.bounds[1] >= P.restroom.corridor_min_w_m   # 폭 1.71 m >= 1.2 m


def test_r2_detects_an_undersized_accessible_cubicle():
    small = replace(P.restroom, accessible_depth_m=1.9)
    rr = room("B", small)
    assert any("장애인 큐비클" in x.message for x in check_r2_restroom(rr, P))


def test_r2_detects_a_blocked_turning_circle():
    rr = room("C")
    acc = next(u for u in rr.units if u.turning is not None)
    rr.fixtures.append(Fixture("회전 원 위 기물", "basin", acc.turning.centroid.buffer(0.2)))
    assert any("회전 원" in x.message for x in check_r2_restroom(rr, P))


def test_r2_detects_a_column_through_a_fixture():
    bounds, program, _col = ROOMS["B"]
    basin_center = (bounds[2] - 0.075 - 0.25, bounds[1] + 0.6)
    rr = build_restroom("B", bounds, program, P.restroom, [Point(*basin_center).buffer(0.45, quad_segs=12)])
    assert any("기둥" in x.message for x in check_r2_restroom(rr, P))


def test_g3_detects_a_door_swinging_into_a_column_in_the_hall():
    bounds, program, col = ROOMS["B"]
    hall_column = Point(bounds[0] + 1.0, bounds[1] - 0.6).buffer(0.45, quad_segs=12)  # 출입문 바로 앞 기둥
    rr = build_restroom("B", bounds, program, P.restroom, [Point(*col).buffer(0.45, quad_segs=12), hall_column])
    assert any(x.check == "G3" for x in check_g3_restroom_doors(rr, P))


def test_layout_rejects_rooms_that_are_too_small():
    with pytest.raises(ValueError):
        build_restroom("B", (0, 0, 3.0, 3.0), "unisex", P.restroom)
    with pytest.raises(ValueError):
        build_restroom("C", (0, 0, 4.0, 4.0), "split", P.restroom)

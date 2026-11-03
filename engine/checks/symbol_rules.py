"""심볼 수준 검사: R1(법규·인체치수), G3(문 스윙). 심볼 단독 시트에서 먼저 확인하고, 조립 후에도 같은 함수를 쓴다."""
from __future__ import annotations

import math
from itertools import combinations

from shapely.ops import unary_union

from checks.base import Violation
from symbols.stair_core import StairCore, core_footprint

EPS = 1e-6


def _where(geom):
    c = geom.centroid
    return (round(c.x, 2), round(c.y, 2))


def check_r1_stair_core(core: StairCore, params) -> list[Violation]:
    """특별피난계단 규격: 유효너비·디딤판·챌면·단수·부속실 면적·문 폭·계단참. 기하에서 측정한 값으로 검사한다."""
    p, cid, out = params.stair, core.core_id, []
    key = f"core:{cid}"
    for f in core.flights:
        minx, miny, maxx, maxy = f.polygon.bounds
        w = min(maxx - minx, maxy - miny)
        if w < p.min_flight_w_m - EPS:
            out.append(Violation("R1", f"코어 {cid} {f.index}번째 갈래 유효너비 {w:.2f} m < {p.min_flight_w_m} m",
                                 _where(f.polygon), (key, f"flight{f.index}")))
        lines = [ln for ln, _solid in f.tread_lines]
        pitches = [a.distance(b) for a, b in zip(lines[:-1], lines[1:])]
        if pitches and min(pitches) < p.min_tread_m - EPS:
            out.append(Violation("R1", f"코어 {cid} {f.index}번째 갈래 디딤판 {min(pitches):.3f} m < {p.min_tread_m} m",
                                 _where(f.polygon), (key, f"tread{f.index}")))
    steps = core.steps_provided
    if steps < core.steps_required:
        out.append(Violation("R1", f"코어 {cid} 한 바퀴 {steps}단 < 층고 {p.floor_height_m} m에 필요한 {core.steps_required}단",
                             _where(core.well), (key, "steps")))
    riser = p.floor_height_m / steps if steps else float("inf")
    if riser > p.max_riser_m + EPS:
        out.append(Violation("R1", f"코어 {cid} 챌면 {riser:.3f} m > {p.max_riser_m} m", _where(core.well), (key, "riser")))
    if core.vestibule.area < p.min_vestibule_area_m2 - EPS:
        out.append(Violation("R1", f"코어 {cid} 부속실 {core.vestibule.area:.2f} ㎡ < {p.min_vestibule_area_m2} ㎡",
                             _where(core.vestibule), (key, "vestibule")))
    for d in core.doors:
        width = math.dist(d.hinge, d.closed_end)
        if width < p.min_door_w_m - EPS:
            out.append(Violation("R1", f"코어 {cid} '{d.name}' 폭 {width:.2f} m < {p.min_door_w_m} m", d.hinge, (key, d.name)))
    minx, miny, maxx, maxy = core.landings[0].bounds
    if min(maxx - minx, maxy - miny) < p.min_flight_w_m - EPS:
        out.append(Violation("R1", f"코어 {cid} 주 계단참 너비가 계단 유효너비보다 작음", _where(core.landings[0]), (key, "landing")))
    return out


def check_g3_door_swings(core: StairCore, params) -> list[Violation]:
    """문 스윙이 벽·계단·다른 문과 겹치지 않고, 피난 방향(홀 쪽 문은 코어 밖, 계단실 쪽 문은 부속실 안)으로 열려야 한다."""
    cid, key, out = core.core_id, f"core:{core.core_id}", []
    obstacles = unary_union([core.walls, core.partition, *[f.polygon for f in core.flights], *core.landings])
    for d in core.doors:
        inter = d.swing.intersection(obstacles)
        if inter.area > EPS:
            out.append(Violation("G3", f"코어 {cid} '{d.name}' 스윙이 벽·계단과 {inter.area:.2f} ㎡ 겹침",
                                 _where(inter), (key, d.name)))
    for a, b in combinations(core.doors, 2):
        inter = a.swing.intersection(b.swing)
        if inter.area > EPS:
            out.append(Violation("G3", f"코어 {cid} '{a.name}'과 '{b.name}' 스윙이 {inter.area:.2f} ㎡ 겹침",
                                 _where(inter), (key, a.name, b.name)))
    outer, inner = core.doors[0], core.doors[1]
    if outer.swing.intersection(core_footprint(core)).area > EPS:
        out.append(Violation("G3", f"코어 {cid} '{outer.name}'이 피난 방향(홀 쪽)으로 열리지 않음",
                             outer.hinge, (key, outer.name, "egress")))
    if inner.swing.intersection(core.vestibule.buffer(0.1)).area < 0.99 * inner.swing.area:
        out.append(Violation("G3", f"코어 {cid} '{inner.name}'이 피난 방향(부속실 쪽)으로 열리지 않음",
                             inner.hinge, (key, inner.name, "egress")))
    return out

"""화장실 심볼 검사: R2(인체치수·진입 통로·위생도기 배치), G3(문 스윙)."""
from __future__ import annotations

import math
from itertools import combinations

from shapely.ops import unary_union

from checks.base import Violation
from symbols.restroom import Restroom, all_doors

EPS = 1e-6


def _where(g):
    c = g.centroid
    return (round(c.x, 2), round(c.y, 2))


def _dims(poly):
    minx, miny, maxx, maxy = poly.bounds
    return tuple(sorted((maxx - minx, maxy - miny)))


def check_r2_restroom(rr: Restroom, params) -> list[Violation]:
    p, key, out = params.restroom, f"wc:{rr.room_id}", []
    hard = unary_union([f.polygon for f in rr.fixtures] + rr.thin + [rr.inner_walls, *rr.columns])
    interior = unary_union([u.interior for u in rr.units])

    for c in rr.cubicles:  # 큐비클 치수
        short, long_ = _dims(c.clear)
        need = p.cubicle_accessible_m if c.kind == "accessible" else p.cubicle_general_m
        if short < need[0] - EPS or long_ < need[1] - EPS:
            out.append(Violation("R2", f"화장실 {rr.room_id} '{c.name}' {short:.2f}×{long_:.2f} m < {need[0]}×{need[1]} m",
                                 _where(c.clear), (key, c.name)))

    for u in rr.units:
        d = u.door
        if d.width < p.min_door_w_m - EPS:
            out.append(Violation("R2", f"화장실 {rr.room_id} '{u.name}' 출입문 폭 {d.width:.2f} m < {p.min_door_w_m} m",
                                 d.hinge, (key, u.name, "door")))
        if u.clear_depth < p.entry_clear_m - EPS:
            out.append(Violation("R2", f"화장실 {rr.room_id} '{u.name}' 출입구 앞 유효 통로 {u.clear_depth:.2f} m < {p.entry_clear_m} m",
                                 d.hinge, (key, u.name, "entry")))
        blocked = u.clear_zone.intersection(hard)
        if blocked.area > EPS:  # 문 앞을 가로막는 벽·칸막이·위생도기·기둥
            out.append(Violation("R2", f"화장실 {rr.room_id} '{u.name}' 출입구 앞 유효 통로가 {blocked.area:.2f} ㎡ 가로막힘",
                                 _where(blocked), (key, u.name, "entry")))
        if u.corridor is not None:
            short, _long = _dims(u.corridor)
            if short < p.corridor_min_w_m - EPS:
                out.append(Violation("R2", f"화장실 {rr.room_id} '{u.name}' 진입 통로 폭 {short:.2f} m < {p.corridor_min_w_m} m",
                                     _where(u.corridor), (key, u.name, "corridor")))
            blocked = u.corridor.intersection(hard)
            if blocked.area > EPS:
                out.append(Violation("R2", f"화장실 {rr.room_id} '{u.name}' 진입 통로가 {blocked.area:.2f} ㎡ 가로막힘",
                                     _where(blocked), (key, u.name, "corridor")))
        if u.turning is not None:
            diameter = 2 * math.sqrt(u.turning.area / math.pi)
            if diameter < p.turning_circle_d_m - 0.01:
                out.append(Violation("R2", f"화장실 {rr.room_id} '{u.name}' 회전 원 Ø{diameter:.2f} m < Ø{p.turning_circle_d_m} m",
                                     _where(u.turning), (key, u.name, "turning")))
            outside = u.turning.difference(u.interior if u.name != "공용" else interior)
            blocked = u.turning.intersection(hard)
            if outside.area > EPS or blocked.area > EPS:
                out.append(Violation("R2", f"화장실 {rr.room_id} '{u.name}' 회전 원이 벽·위생도기·기둥과 겹침",
                                     _where(u.turning), (key, u.name, "turning")))

    for f in rr.fixtures:
        if f.polygon.difference(interior).area > EPS:
            out.append(Violation("R2", f"화장실 {rr.room_id} '{f.name}'이(가) 방 밖에 있음", _where(f.polygon), (key, f.name)))
        if f.kind == "basin" and _dims(f.polygon)[1] < p.basin_w_m - EPS:
            out.append(Violation("R2", f"화장실 {rr.room_id} '{f.name}' 카운터 폭 < {p.basin_w_m} m", _where(f.polygon), (key, f.name)))
        for other in [*rr.thin, rr.inner_walls, *rr.columns]:
            if f.polygon.intersection(other).area > EPS:
                out.append(Violation("R2", f"화장실 {rr.room_id} '{f.name}'이(가) 칸막이·벽·기둥과 겹침",
                                     _where(f.polygon.intersection(other)), (key, f.name, "overlap")))
                break
    for a, b in combinations(rr.fixtures, 2):
        inter = a.polygon.intersection(b.polygon)
        if inter.area > EPS:
            out.append(Violation("R2", f"화장실 {rr.room_id} '{a.name}'과(와) '{b.name}'이(가) 겹침", _where(inter), (key, a.name, b.name)))
    return out


def check_g3_restroom_doors(rr: Restroom, params) -> list[Violation]:
    """여닫이 문 스윙이 벽·위생도기·기둥·다른 문과 겹치지 않고 방 밖(홀 쪽)으로 열려야 한다."""
    key, out = f"wc:{rr.room_id}", []
    hard = unary_union([rr.walls, rr.inner_walls, *rr.thin, *[f.polygon for f in rr.fixtures], *rr.columns])
    interior = unary_union([u.interior for u in rr.units])
    swings = [(d.name, d.swing) for d in all_doors(rr) if d.swing is not None]
    for name, sw in swings:
        inter = sw.intersection(hard)
        if inter.area > EPS:
            out.append(Violation("G3", f"화장실 {rr.room_id} '{name}' 스윙이 벽·위생도기·기둥과 {inter.area:.2f} ㎡ 겹침",
                                 _where(inter), (key, name)))
        if sw.intersection(interior).area > EPS:
            out.append(Violation("G3", f"화장실 {rr.room_id} '{name}'이(가) 방 안쪽으로 열림(피난 방향은 홀 쪽)",
                                 _where(sw), (key, name, "egress")))
    for (a, sa), (b, sb) in combinations(swings, 2):
        inter = sa.intersection(sb)
        if inter.area > EPS:
            out.append(Violation("G3", f"화장실 {rr.room_id} '{a}'과(와) '{b}' 스윙이 {inter.area:.2f} ㎡ 겹침",
                                 _where(inter), (key, a, b)))
    return out

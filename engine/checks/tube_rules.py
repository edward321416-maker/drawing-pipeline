"""튜브 심볼 검사: R3(AGENTS.md §3 튜브 표준 — 유리 벽 두께, 기둥 간섭, 나선 램프, 승강로 2개, 승강 로비)."""
from __future__ import annotations

from itertools import combinations

from shapely.geometry import LineString
from shapely.ops import unary_union

from checks.base import Violation
from symbols.tube import Tube

EPS = 1e-6
THICK_TOL_M = 0.005
SQUARE_TOL_M = 0.01
POLY_TOL_M = 0.01      # 원을 다각형으로 근사한 오차(반지름 4 m, 128각형에서 약 1 mm)보다 크게


def _where(g):
    c = g.centroid
    return (round(c.x, 2), round(c.y, 2))


def _wall_t(outer, inner) -> float:
    """바깥·안쪽 윤곽 사이 벽 두께 = 면적 / 평균 둘레 (원이면 정확히 R - r)."""
    return (outer.area - inner.area) / ((outer.length + inner.length) / 2)


def _ring_w(poly) -> float:
    return poly.area / ((poly.exterior.length + poly.interiors[0].length) / 2)


def check_r3_tube(t: Tube, params) -> list[Violation]:
    p, key, out = params.tube, f"tube:{t.tube_id}", []
    tag = f"튜브 {t.tube_id}"
    cols = unary_union(t.columns) if t.columns else None

    for name, outer, inner in t.rims:                      # 유리 벽 두께
        w = _wall_t(outer, inner)
        if abs(w - p.glass_t_m) > THICK_TOL_M:
            out.append(Violation("R3", f"{tag} {name} 두께 {w:.3f} m ≠ {p.glass_t_m} m", _where(outer), (key, name)))

    if cols is not None:                                   # 기둥은 튜브 어디에도 걸치지 않는다
        hit = t.outer.intersection(cols)
        if hit.area > EPS:
            out.append(Violation("R3", f"{tag}이(가) 구조 기둥과 {hit.area:.2f} ㎡ 겹침", _where(hit), (key, "column")))
    if t.envelope is not None and t.outer.difference(t.envelope).area > EPS:
        out.append(Violation("R3", f"{tag}이(가) 건물 외곽(외벽) 밖으로 나감", _where(t.outer), (key, "envelope")))

    if t.kind == "ramp":
        if t.inner_ring is None or t.band is None or len(t.rims) != 2:
            out.append(Violation("R3", f"{tag} 나선 램프에 안쪽·바깥 2중 림이 없음", _where(t.outer), (key, "rims")))
        else:
            w = _ring_w(t.band)
            if w < p.min_ramp_w_m - EPS:
                out.append(Violation("R3", f"{tag} 램프 통로 폭 {w:.2f} m < {p.min_ramp_w_m} m", _where(t.band), (key, "ramp_w")))
        if t.spiral is None or t.arrow_head is None or t.spiral.geom_type != "LineString" or not t.spiral.is_simple:
            out.append(Violation("R3", f"{tag} 나선 화살표가 매끄러운 단일 곡선이 아님", _where(t.outer), (key, "spiral")))
        elif t.band is not None:
            room = t.band.buffer(-(p.spiral_margin_m - POLY_TOL_M))
            if not room.contains(t.spiral) or not t.band.contains(t.arrow_head):
                out.append(Violation("R3", f"{tag} 나선 화살표가 램프 통로(림과 {p.spiral_margin_m} m 이격) 밖으로 나감",
                                     _where(t.spiral), (key, "spiral")))
            if cols is not None and (t.spiral.distance(cols) < EPS or t.arrow_head.intersection(cols).area > EPS):
                out.append(Violation("R3", f"{tag} 나선 화살표가 기둥과 닿음", _where(t.spiral), (key, "spiral", "column")))

    if t.kind == "elevator":
        if len(t.shafts) != 2:
            out.append(Violation("R3", f"{tag} 승강로가 {len(t.shafts)}개 (2개 필요)", _where(t.outer), (key, "shafts")))
        safe = t.inner.buffer(-(p.shaft_to_glass_m - POLY_TOL_M))
        for s in t.shafts:
            if not safe.contains(s.outer):
                out.append(Violation("R3", f"{tag} '{s.name}'이(가) 유리 원통 안({p.shaft_to_glass_m} m 이격)에 온전히 들어가지 않음",
                                     _where(s.outer), (key, s.name, "inside")))
            minx, miny, maxx, maxy = s.clear.bounds
            if abs((maxx - minx) - (maxy - miny)) > SQUARE_TOL_M:
                out.append(Violation("R3", f"{tag} '{s.name}'이(가) 정사각형이 아님", _where(s.clear), (key, s.name, "square")))
            if len(s.diagonals) != 2:
                out.append(Violation("R3", f"{tag} '{s.name}'에 X 표시가 없음", _where(s.clear), (key, s.name, "x")))
            if cols is not None and s.outer.intersection(cols).area > EPS:
                out.append(Violation("R3", f"{tag} '{s.name}'이(가) 기둥과 겹침", _where(s.outer), (key, s.name, "column")))
        for a, b in combinations(t.shafts, 2):
            if a.outer.intersection(b.outer).area > EPS:
                out.append(Violation("R3", f"{tag} '{a.name}'과(와) '{b.name}'이(가) 겹침", _where(a.outer), (key, a.name, b.name)))
        if t.lobby is None:
            out.append(Violation("R3", f"{tag}에 승강 로비가 없음", _where(t.outer), (key, "lobby")))
        else:
            if cols is not None and t.lobby.intersection(cols).area > EPS:
                out.append(Violation("R3", f"{tag} 승강 로비에 기둥이 있음", _where(t.lobby), (key, "lobby", "column")))
            for s in t.shafts:
                if t.lobby.intersection(s.outer).area > EPS:
                    out.append(Violation("R3", f"{tag} 승강 로비가 '{s.name}'과(와) 겹침", _where(t.lobby), (key, "lobby", s.name)))
            cx, cy = t.center
            depth = LineString([(cx, t.outer.bounds[1] - 1), (cx, t.outer.bounds[3] + 1)]).intersection(t.lobby).length
            if depth < p.lobby_min_depth_m - EPS:
                out.append(Violation("R3", f"{tag} 승강 로비 깊이 {depth:.2f} m < {p.lobby_min_depth_m} m", _where(t.lobby), (key, "lobby", "depth")))
            for z in t.lobby_zones:
                if z.difference(t.lobby).area > EPS:
                    out.append(Violation("R3", f"{tag} 승강로 문 앞 유효 깊이 {p.lobby_min_depth_m} m가 로비 밖으로 나감",
                                         _where(z), (key, "lobby", "zone")))
        for d in t.doors:
            if d.width < p.min_door_w_m - EPS:
                out.append(Violation("R3", f"{tag} 출입구 폭 {d.width:.2f} m < {p.min_door_w_m} m", _where(d.leaf), (key, d.name)))
        if t.entry_zone is not None and cols is not None and t.entry_zone.intersection(cols).area > EPS:
            out.append(Violation("R3", f"{tag} 출입구 바깥 유효 통로에 기둥이 있음", _where(t.entry_zone), (key, "entry", "column")))
    return out

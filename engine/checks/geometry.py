# FILE: checks/geometry.py
from __future__ import annotations

from shapely.ops import unary_union

from checks.base import Violation, dedupe
from extract.schema import WALL_KINDS
from extract.slicer import filled_shell

AREA_EPS = 1e-6
G1_BLOCKERS = ("void", "tube_wall", "shaft", "stair", "sanitary")
G2_BLOCKERS = ("void", "tube_wall", "shaft")


def _where(geom):
    c = geom.centroid
    return (round(c.x, 2), round(c.y, 2))


def _blocker(kind, geom):
    # 튜브벽은 링이지만 튜브 내부 전체가 기둥·기물 금지 영역이다
    return filled_shell(geom) if kind == "tube_wall" else geom


def check_g1_columns(sections, params) -> list[Violation]:
    """기둥이 보이드·튜브·승강로·계단을 어느 검사 높이에서든 관통하면 위반."""
    out = []
    for h in sections.heights:
        at = sections.at(h)
        columns = {n: g for n, g in at.items() if sections.kind(n) == "column"}
        for n_b, g_b in at.items():
            kind_b = sections.kind(n_b)
            if kind_b not in G1_BLOCKERS:
                continue
            blocker = _blocker(kind_b, g_b)
            for n_c, g_c in columns.items():
                inter = g_c.intersection(blocker)
                if inter.area > AREA_EPS:
                    out.append(Violation(
                        "G1",
                        f"기둥 '{n_c}'이(가) {kind_b} '{n_b}'을(를) 관통 (높이 {h} m, 겹침 {inter.area:.3f} ㎡)",
                        _where(inter), (n_c, n_b)))
    return dedupe(out)


def check_g2_fixtures(sections, params) -> list[Violation]:
    """기물은 기둥과 최소 이격을 지키고 보이드·튜브 내부·승강로에 들어가지 않아야 한다."""
    out = []
    for h in sections.heights:
        at = sections.at(h)
        for n_f, g_f in at.items():
            if sections.kind(n_f) != "fixture":
                continue
            for n_o, g_o in at.items():
                kind_o = sections.kind(n_o)
                if kind_o == "column":
                    d = g_f.distance(g_o)
                    if d < params.furniture_to_column_m:
                        out.append(Violation(
                            "G2",
                            f"기물 '{n_f}'과(와) 기둥 '{n_o}' 이격 {d:.2f} m < {params.furniture_to_column_m} m",
                            _where(g_f), (n_f, n_o)))
                elif kind_o in G2_BLOCKERS:
                    inter = g_f.intersection(_blocker(kind_o, g_o))
                    if inter.area > AREA_EPS:
                        out.append(Violation(
                            "G2",
                            f"기물 '{n_f}'이(가) {kind_o} '{n_o}'에 침범 (겹침 {inter.area:.3f} ㎡)",
                            _where(inter), (n_f, n_o)))
    return dedupe(out)


def check_g4_zones(sections, params) -> list[Violation]:
    out = []
    zones = {o.name: sections.footprint(o.name) for o in sections.model.by_kind("zone")}
    if not zones:
        return out
    names = list(zones)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            inter = zones[a].intersection(zones[b])
            if inter.area > params.zone_overlap_tolerance_m2:
                out.append(Violation("G4", f"구획존 '{a}'와 '{b}' 겹침 {inter.area:.2f} ㎡", _where(inter), (a, b)))
    slabs = [sections.footprint(o.name) for o in sections.model.by_kind("slab")]
    if not slabs:
        out.append(Violation("G4", "구획존이 있으나 바닥 슬래브(kind=slab)가 없음"))
        return out
    slab = unary_union(slabs)
    zone_union = unary_union(list(zones.values()))
    outside = zone_union.difference(slab)
    if outside.area > params.zone_overlap_tolerance_m2:
        out.append(Violation("G4", f"구획존이 바닥 슬래브 밖으로 {outside.area:.2f} ㎡ 벗어남", _where(outside)))
    uncovered = slab.difference(zone_union)
    if uncovered.area > params.zone_coverage_tolerance_ratio * slab.area:
        out.append(Violation(
            "G4",
            f"구획존이 덮지 못한 바닥 {uncovered.area:.2f} ㎡ ({uncovered.area / slab.area:.1%})",
            _where(uncovered)))
    return out


def check_g7_footprints(sections, params) -> list[Violation]:
    """모든 객체의 바닥 윤곽은 면적이 있어야 한다. 닫히지 않은 메시나 반올림으로 윤곽이 사라진 객체는 도면에서 조용히 빠진다."""
    out = []
    for name, geom in sections._footprints.items():
        obj = sections.obj(name)
        if geom.is_empty or geom.area < 1e-6:
            out.append(Violation("G7", f"'{name}'의 바닥 윤곽 면적이 0이다(메시가 닫히지 않았거나 윤곽이 사라짐)", obj.center_xy, (name,)))
            continue
        cap = _prism_cap_area(obj)   # 각기둥이면 아랫면 면적과 윤곽 면적이 같아야 한다(일부만 사라져도 잡는다)
        if cap is not None and abs(geom.area - cap) > 1e-4 * cap:
            out.append(Violation("G7", f"'{name}'의 바닥 윤곽 면적 {geom.area:.2f} ㎡가 아랫면 {cap:.2f} ㎡와 다르다(윤곽 일부 손실)",
                                 obj.center_xy, (name,)))
    return out


def _prism_cap_area(obj):
    """높이 층이 둘뿐인 각기둥 메시의 아랫면 면적. 각기둥이 아니면 None."""
    import numpy as np

    z = np.round(obj.verts[:, 2], 6)
    levels = np.unique(z)
    if len(levels) != 2:
        return None
    tri = obj.verts[obj.tris]
    flat = np.all(np.abs(tri[:, :, 2] - levels[0]) < 1e-6, axis=1)
    a, b, c = tri[flat, 0, :2], tri[flat, 1, :2], tri[flat, 2, :2]
    return float(0.5 * np.abs((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1])).sum())


def check_g5_walls(sections, params) -> list[Violation]:
    """외벽·코어벽·구획벽의 중심선은 기둥 격자선 위에 있어야 한다(grid_exempt 태그로 예외 지정)."""
    out = []
    spacing = params.grid_spacing_m
    for name, geom in sections.at(params.plan_cut_height_m).items():
        obj = sections.obj(name)
        if obj.kind not in WALL_KINDS or obj.props.get("grid_exempt"):
            continue
        minx, miny, maxx, maxy = geom.bounds
        dx, dy = maxx - minx, maxy - miny
        if min(dx, dy) > 1.0:  # 두꺼운 매스형 벽은 중심선 개념이 아니므로 제외
            continue
        axis, center = ("y", (miny + maxy) / 2) if dy < dx else ("x", (minx + maxx) / 2)
        rem = center % spacing
        off = min(rem, spacing - rem)
        if off > params.grid_tolerance_m:
            out.append(Violation(
                "G5",
                f"벽 '{name}' 중심선 {axis}={center:.3f} m가 기둥 격자({spacing} m)에서 {off:.3f} m 벗어남",
                _where(geom), (name,)))
    return out

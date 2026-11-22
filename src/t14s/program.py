"""C-T14T programme completeness (all PROPOSED_DESIGN): sales/dining vs back-of-house split of the tenant units, back-of-house
fit-out, differentiated culture concepts for 11F-14F, and the garden design for the garden floors.

Everything is derived from the unit polygons fitted on the verified slab. Nothing here changes verified geometry.
"""
from __future__ import annotations

import math

import numpy as np
from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import polylabel, substring, unary_union

from . import fitout as FO
from .walknet import WalkNet

CULTURE_CONCEPT = {
    "11F": ("공연·퍼포먼스 층", ["블랙박스 공연장", "리허설 룸", "분장·대기실", "스튜디오 A", "스튜디오 B", "공연 라운지"], "공연 로비·포이어"),
    "12F": ("전시·미디어 층", ["전시 갤러리 1", "미디어아트 룸", "전시 갤러리 2", "작품 준비·큐레이션 룸", "아트 스토어", "큐레이션 라운지"], "전시 로비·보이드 가장자리 홀"),
    "13F": ("창작·공방 층", ["도예 공방", "목공 공방", "디지털 패브 랩", "레지던시 스튜디오", "공유 작업 라운지", "소재 라이브러리"], "공방 로비·쇼케이스 홀"),
    "14F": ("교육·커뮤니티 층", ["세미나실 A", "세미나실 B", "키즈 워크숍", "소형 상영관", "북 라운지", "커뮤니티 룸"], "커뮤니티 로비·라운지"),
}
# use -> (fit-out family understood by fitout._culture, support-room name or None)
USE_FAMILY = {
    "블랙박스 공연장": ("다목적 홀", "무대 지원·분장"), "리허설 룸": ("스튜디오", "악기·장비 보관"), "분장·대기실": ("스튜디오", None),
    "스튜디오 A": ("스튜디오", "장비 보관"), "스튜디오 B": ("스튜디오", "장비 보관"), "공연 라운지": ("라운지", None),
    "전시 갤러리 1": ("전시 갤러리", "수장·작업실"), "전시 갤러리 2": ("전시 갤러리", "수장·작업실"), "미디어아트 룸": ("전시 갤러리", "서버·장비실"),
    "작품 준비·큐레이션 룸": ("스튜디오", None), "아트 스토어": ("전시 갤러리", "재고 창고"), "큐레이션 라운지": ("라운지", None),
    "도예 공방": ("스튜디오", "재료·가마 창고"), "목공 공방": ("스튜디오", "재료 창고"), "디지털 패브 랩": ("스튜디오", "장비 보관"),
    "레지던시 스튜디오": ("스튜디오", "작업 보관"), "공유 작업 라운지": ("라운지", None), "소재 라이브러리": ("전시 갤러리", "수장 창고"),
    "세미나실 A": ("스튜디오", "교구 보관"), "세미나실 B": ("스튜디오", "교구 보관"), "키즈 워크숍": ("스튜디오", "재료 창고"),
    "소형 상영관": ("다목적 홀", "영사실·장비"), "북 라운지": ("라운지", None), "커뮤니티 룸": ("라운지", None),
    "다목적 홀": ("다목적 홀", "무대 지원"), "전시 갤러리": ("전시 갤러리", "수장·작업실"), "스튜디오": ("스튜디오", "장비 보관"),
    "체험 공방": ("스튜디오", "재료 창고"), "라운지": ("라운지", None), "미디어랩": ("스튜디오", "장비 보관"),
}
SALES_NAME = {"retail": "판매 영역", "fnb": "식음 홀(객석)"}
SVC_DOOR_W, INT_DOOR_W = 1.0, 0.9


def _unit_vec(a, b):
    L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
    return ((b[0] - a[0]) / L, (b[1] - a[1]) / L)


class _Local:
    """Door-aligned frame wrapper that converts boxes / lines / door specs back to world coordinates."""

    def __init__(self, door):
        self.fr = FO.Frame(door["center"], (-door["n"][0], -door["n"][1]))

    def poly(self, b):
        return self.fr.to_world(box(*b))

    def line(self, a, b):
        return self.fr.to_world(LineString([a, b]))

    def door(self, c, towards, w, kind):
        """Opening centred at local c; `towards` is the local unit vector the leaf swings into; wall tangent is perpendicular."""
        W = self.fr.to_world
        cw = W(Point(*c))
        tl = (-towards[1], towards[0])
        t = _unit_vec((cw.x, cw.y), (W(Point(c[0] + tl[0], c[1] + tl[1])).x, W(Point(c[0] + tl[0], c[1] + tl[1])).y))
        n = _unit_vec((cw.x, cw.y), (W(Point(c[0] + towards[0], c[1] + towards[1])).x, W(Point(c[0] + towards[0], c[1] + towards[1])).y))
        return {"center": (cw.x, cw.y), "t": t, "n": n, "w": w, "kind": kind}


def _clear(g, cols, d):
    return cols is None or cols.is_empty or g.distance(cols) >= d


def _pick_door_pos(cands, cols, need):
    for c in cands:
        if _clear(Point(*c), cols, need):
            return c
    return None


def plan_unit(poly, door, prog, hall, col_u, rng, use=None):
    """Sub-divide one unit into main (sales / dining / culture space) and back-of-house rooms. Returns None if the unit stays whole."""
    L = _Local(door)
    lp = L.fr.to_local(poly)
    x0, y0, x1, y1 = lp.bounds
    if abs(y0) > 0.35 or lp.area < 0.97 * (x1 - x0) * (y1 - y0):
        return None
    W, D, area = x1 - x0, y1 - y0, lp.area
    cols = L.fr.to_local(col_u.intersection(poly.buffer(1.0))) if col_u is not None and not col_u.is_empty else None
    hall_l = L.fr.to_local(hall.buffer(0.12)) if hall is not None and not hall.is_empty else None
    dw = door["w"]
    keep_out = box(-dw / 2 - 0.55, y0 - 0.01, dw / 2 + 0.55, y0 + 2.6)

    def side_strips(sw0, min_main, min_sw=2.4):
        out = []
        for dsw in (0.0, 0.3, -0.3, 0.6, -0.6, 0.9, -0.9, 1.2, -1.2):
            sw = sw0 + dsw
            if sw < min_sw or W - sw < min_main:
                continue
            for side in (1, -1):
                xs = x1 - sw if side > 0 else x0 + sw
                strip = (xs, y0, x1, y1) if side > 0 else (x0, y0, xs, y1)
                sb = box(*strip)
                if sb.intersects(keep_out):
                    continue
                if not _clear(LineString([(xs, y0), (xs, y1)]), cols, 0.2):
                    continue
                ow = LineString([(x1 if side > 0 else x0, y0), (x1 if side > 0 else x0, y1)])
                hall_pen = 1.0 if hall_l is not None and ow.buffer(0.15).intersection(hall_l).area > 0.3 else 0.0
                ncol = sb.intersection(cols).area if cols is not None and not cols.is_empty else 0.0
                out.append((hall_pen + 0.2 * ncol + 0.05 * abs(dsw) + rng.random() * 0.01, side, xs, strip))
        return sorted(out, key=lambda c: c[0])

    def mk(rooms, parts, doors):
        return {"rooms": rooms, "parts": parts, "doors": doors}

    def service_door(xc, y_in=1.0):
        for dx in (0.0, 0.5, -0.5, 0.9, -0.9):
            c = (xc + dx, y0)
            if _clear(Point(*c), cols, 0.9):
                return L.door(c, (0, 1), SVC_DOOR_W, "service")
        return None

    def back_split():
        """BOH along the back wall (no direct service door: goods come through the main door). For narrow, deep units."""
        bd = 3.0 if prog == "fnb" else 2.4
        if D - bd < 4.5 or W < 4.0:
            return None
        ya = None
        for sh in (0.0, 0.3, -0.3, 0.6, -0.6, 0.9, -0.9):
            if _clear(LineString([(x0, y1 - bd + sh), (x1, y1 - bd + sh)]), cols, 0.2) and 4.2 <= (y1 - bd + sh) - y0:
                ya = y1 - bd + sh
                break
        if ya is None:
            return None
        parts = [L.line((x0, ya), (x1, ya))]
        main = (x0, y0, x1, ya)
        if prog in ("retail", "culture"):
            xd = _pick_door_pos([((x0 + x1) / 2 + dx, ya) for dx in (0.0, 0.6, -0.6, 1.2, -1.2)], cols, 1.0)
            doors = [L.door(xd, (0, 1), INT_DOOR_W, "internal")] if xd else []
            cul = prog == "culture"
            rooms = [{"poly": L.poly(main), "role": "main", "kind": "culture" if cul else "sales", "name": use if cul else "판매 영역"},
                     {"poly": L.poly((x0, ya, x1, y1)), "role": "support", "kind": "culture_support" if cul else "stock", "name": USE_FAMILY.get(use, ("", "지원"))[1] if cul else "창고·지원"}]
            return mk(rooms, parts, doors)
        xs = None
        for sh in (0.0, 0.3, -0.3, 0.6, -0.6, 0.9, -0.9):
            xx = x0 + 0.4 * W + sh
            if _clear(LineString([(xx, ya), (xx, y1)]), cols, 0.2) and xx - x0 >= 2.2 and x1 - xx >= 2.4:
                xs = xx
                break
        if xs is None:
            return None
        parts.append(L.line((xs, ya), (xs, y1)))
        rooms = [{"poly": L.poly(main), "role": "main", "kind": "dining", "name": "식음 홀(객석)"},
                 {"poly": L.poly((x0, ya, xs, y1)), "role": "support", "kind": "wash", "name": "창고·세척"},
                 {"poly": L.poly((xs, ya, x1, y1)), "role": "support", "kind": "kitchen", "name": "주방"}]
        doors = []
        d1 = _pick_door_pos([(xs, (ya + y1) / 2 + dy) for dy in (0.0, 0.4, -0.4)], cols, 0.9)
        if d1:
            doors.append(L.door(d1, (1, 0), INT_DOOR_W, "internal"))
        d2 = _pick_door_pos([((xs + x1) / 2 + dx, ya) for dx in (0.0, 0.5, -0.5, 0.9, -0.9)], cols, 1.0)
        if d2:
            doors.append(L.door(d2, (0, 1), INT_DOOR_W, "pass"))
        d3 = _pick_door_pos([((x0 + xs) / 2 + dx, ya) for dx in (0.0, 0.4, -0.4)], cols, 1.0)
        if d3:
            doors.append(L.door(d3, (0, 1), INT_DOOR_W, "internal"))
        return mk(rooms, parts, doors)

    if prog == "retail" and area >= 38:
        sw = max(1.8, min(3.0, round(0.22 * W / 0.3) * 0.3))
        cs = side_strips(sw, 3.6, 1.8)
        if not cs:
            return back_split()
        _, side, xs, strip = cs[0]
        sd = service_door((strip[0] + strip[2]) / 2)
        yd = _pick_door_pos([(xs, y0 + f) for f in (0.30 * D, 0.42 * D, 0.2 * D, 0.55 * D)], cols, 1.0)
        doors = [d for d in (sd,) if d]
        if yd:
            doors.append(L.door(yd, (side, 0), INT_DOOR_W, "internal"))
        main = (x0, y0, xs, y1) if side > 0 else (xs, y0, x1, y1)
        rooms = [{"poly": L.poly(main), "role": "main", "kind": "sales", "name": "판매 영역"},
                 {"poly": L.poly(strip), "role": "support", "kind": "stock", "name": "창고·지원"}]
        return mk(rooms, [L.line((xs, y0), (xs, y1))], doors)

    if prog == "fnb" and area >= 40:
        bw = min(6.0, max(2.8, round(0.30 * W / 0.3) * 0.3))
        cs = side_strips(bw, 4.2)
        if not cs:
            return back_split()
        _, side, xs, strip = cs[0]
        n_r = 3 if (area >= 70 and D >= 7.5) else 2 if D >= 5.0 else 1
        fr_ = {3: [0.28, 0.27, 0.45], 2: [0.40, 0.60], 1: [1.0]}[n_r]
        names = {3: [("storage", "창고"), ("wash", "세척·준비"), ("kitchen", "주방")], 2: [("wash", "창고·세척"), ("kitchen", "주방")],
                 1: [("kitchen", "주방·창고")]}[n_r]
        ya = [y0]
        for f in fr_[:-1]:
            ya.append(ya[-1] + f * D)
        ya.append(y1)
        # shift horizontal partitions off columns
        sx0, sx1 = (xs, x1) if side > 0 else (x0, xs)
        for k in range(1, len(ya) - 1):
            for sh in (0.0, 0.3, -0.3, 0.6, -0.6, 0.9, -0.9, 1.2, -1.2):
                ln = LineString([(sx0, ya[k] + sh), (sx1, ya[k] + sh)])
                if _clear(ln, cols, 0.2) and (ya[k] + sh) - ya[k - 1] >= 2.3 and ya[k + 1] - (ya[k] + sh) >= 2.3:
                    ya[k] += sh
                    break
        rooms, parts, doors = [], [], []
        main = (x0, y0, xs, y1) if side > 0 else (xs, y0, x1, y1)
        rooms.append({"poly": L.poly(main), "role": "main", "kind": "dining", "name": "식음 홀(객석)"})
        for (kind, nm), a, b in zip(names, ya[:-1], ya[1:]):
            rooms.append({"poly": L.poly((sx0, a, sx1, b)), "role": "support", "kind": kind, "name": nm})
        parts.append(L.line((xs, y0), (xs, y1)))
        for k in range(1, len(ya) - 1):
            parts.append(L.line((sx0, ya[k]), (sx1, ya[k])))
        xc = (sx0 + sx1) / 2
        sd = service_door(xc)
        if sd:
            doors.append(sd)
        for k in range(1, len(ya) - 1):
            c = _pick_door_pos([(xc + dx, ya[k]) for dx in (0.0, 0.4, -0.4, 0.8, -0.8)], cols, 0.9)
            if c:
                doors.append(L.door(c, (0, 1), INT_DOOR_W, "internal"))
        ky = (ya[-2] + ya[-1]) / 2
        pc = _pick_door_pos([(xs, ky + dy) for dy in (0.0, 0.6, -0.6, 1.0, -1.0)], cols, 1.0)
        if pc:
            doors.append(L.door(pc, (side, 0), INT_DOOR_W, "pass"))
        return mk(rooms, parts, doors)

    if prog == "culture" and area >= 70 and use:
        fam, sup = USE_FAMILY.get(use, ("라운지", None))
        if not sup:
            return None
        sw = 2.4 if W < 10 else 3.0
        cs = side_strips(sw, 4.5)
        if not cs:
            return back_split()
        _, side, xs, strip = cs[0]
        sd = service_door((strip[0] + strip[2]) / 2)
        yd = _pick_door_pos([(xs, y0 + f) for f in (0.30 * D, 0.42 * D, 0.2 * D, 0.55 * D)], cols, 1.0)
        doors = [d for d in (sd,) if d]
        if yd:
            doors.append(L.door(yd, (side, 0), INT_DOOR_W, "internal"))
        main = (x0, y0, xs, y1) if side > 0 else (xs, y0, x1, y1)
        rooms = [{"poly": L.poly(main), "role": "main", "kind": "culture", "name": use},
                 {"poly": L.poly(strip), "role": "support", "kind": "culture_support", "name": sup}]
        return mk(rooms, [L.line((xs, y0), (xs, y1))], doors)
    return None


# ------------------------------------------------------------------------------------------------ back-of-house fit-out
def boh_items(room, kind, block, col_u, rng):
    """Schematic equipment for a back-of-house room (axis-aligned box in world coordinates)."""
    inner = room.buffer(-0.12, join_style=2)
    if block is not None and not block.is_empty:
        inner = inner.difference(block)
    if col_u is not None and not col_u.is_empty:
        inner = inner.difference(col_u.buffer(0.3))
    if inner.is_empty:
        return []
    x0, y0, x1, y1 = room.bounds
    bodies, lines = [], []
    horizontal = (x1 - x0) >= (y1 - y0)

    def put(g, k="body"):
        if g.is_empty or not inner.contains(g):
            return False
        (bodies if k == "body" else lines).append(g)
        return True

    def strip(long_axis_start, depth, ofs, a, b):
        # a strip along the room's x (horizontal) or y direction on the wall at offset ofs
        return box(a, long_axis_start + ofs, b, long_axis_start + ofs + depth) if horizontal else box(long_axis_start + ofs, a, long_axis_start + ofs + depth, b)

    lo, hi = (y0, y1) if horizontal else (x0, x1)
    a, b = (x0, x1) if horizontal else (y0, y1)
    if kind in ("kitchen",):
        for ofs in (0.12, (hi - lo) - 0.12 - 0.7):
            seg = strip(lo, 0.7, ofs, a + 0.12, b - 0.12)
            for part in (inner.intersection(seg),):
                for p in getattr(part, "geoms", [part]):
                    if p.geom_type == "Polygon" and p.area > 0.6:
                        put(p)
        # cooking range on the first wall + hood outline
        for i in range(3):
            c = a + 0.9 + i * 1.0
            g = box(c, lo + 0.17, c + 0.8, lo + 0.17 + 0.7) if horizontal else box(lo + 0.17, c, lo + 0.17 + 0.7, c + 0.8)
            if put(g.buffer(0), "body"):
                put(LineString([(g.centroid.x - 0.25, g.centroid.y), (g.centroid.x + 0.25, g.centroid.y)]), "line")
        if (hi - lo) >= 4.4:
            ctr = (a + b) / 2
            isl = box(ctr - 1.2, (lo + hi) / 2 - 0.5, ctr + 1.2, (lo + hi) / 2 + 0.5) if horizontal else box((lo + hi) / 2 - 0.5, ctr - 1.2, (lo + hi) / 2 + 0.5, ctr + 1.2)
            put(isl)
    elif kind in ("wash",):
        for i in range(3):
            c = a + 0.5 + i * 0.9
            g = box(c, lo + 0.14, c + 0.7, lo + 0.14 + 0.6) if horizontal else box(lo + 0.14, c, lo + 0.14 + 0.6, c + 0.7)
            if put(g):
                put(Point(g.centroid).buffer(0.2, quad_segs=8), "line")
        ctr = (a + b) / 2
        tb = box(ctr - 0.9, (lo + hi) / 2 - 0.4, ctr + 0.9, (lo + hi) / 2 + 0.4) if horizontal else box((lo + hi) / 2 - 0.4, ctr - 0.9, (lo + hi) / 2 + 0.4, ctr + 0.9)
        put(tb)
    else:                                                      # storage / stock / equipment rooms: wall shelving + racks
        for s, part in FO.wall_strips(inner, rng, depth=0.45, seg=(1.5, 3.6), gap=(0.6, 1.1)):
            put(s)
            lines.append(substring(part, 0.1, max(part.length - 0.1, 0.2)))
        w = (hi - lo)
        if w >= 3.6 and (b - a) >= 3.0:
            for off in np.arange(lo + 1.4, hi - 1.4, 1.7):
                rack = box(a + 0.9, off, b - 0.9, off + 0.5) if horizontal else box(off, a + 0.9, off + 0.5, b - 0.9)
                put(rack)
    return [(g, "body") for g in bodies] + [(g, "line") for g in lines if not g.is_empty]


# ------------------------------------------------------------------------------------------------ garden
def _poisson(poly, spacing, rng, limit=60):
    if poly.is_empty:
        return []
    x0, y0, x1, y1 = poly.bounds
    pts = []
    for _ in range(900):
        p = Point(rng.uniform(x0, x1), rng.uniform(y0, y1))
        if poly.contains(p) and all(p.distance(q) >= spacing for q in pts):
            pts.append(p)
            if len(pts) >= limit:
                break
    return pts


def garden_design(garden, base_routes, anchors, col_u, rng, keep_out=None):
    """garden: polygon of the garden hall; base_routes: visitor routes already crossing it; anchors: entrances (door aprons,
    cores, landings) that must be joined to the path. Returns paths / beds / trees / benches / shade as shapely geometry."""
    out = {"paths": None, "lines": [], "beds": [], "trees": [], "shrubs": [], "benches": [], "shade": [], "loop_m": 0.0}
    if garden is None or garden.is_empty:
        return out
    region = garden.buffer(-0.7)
    if col_u is not None and not col_u.is_empty:
        region = region.difference(col_u.buffer(1.05))
    net = WalkNet(region, 0.4)
    if not net.n:
        return out
    lines = []
    tree = set()
    for r in base_routes:
        seg = r.intersection(garden.buffer(0.3))
        for g in getattr(seg, "geoms", [seg]):
            if g.geom_type == "LineString" and g.length > 0.5:
                lines.append(g)
                for k in np.arange(0, g.length, 0.4):
                    c, d = net.nearest(g.interpolate(k).coords[0], 0.6)
                    if c is not None:
                        tree.add(c)
    # a perimeter promenade 2.4 m inside the garden edge
    ring = garden.buffer(-2.4)
    loop = []
    if not ring.is_empty:
        for p in getattr(ring, "geoms", [ring]):
            if p.geom_type != "Polygon":
                continue
            for rg in [p.exterior] + list(p.interiors):
                pts = [rg.interpolate(k).coords[0] for k in np.arange(0, rg.length, 0.8)]
                cells = []
                for q in pts:
                    c, d = net.nearest(q, 0.5)
                    cells.append(c)
                run = []
                for q, c in zip(pts, cells):
                    if c is None:
                        if len(run) > 3:
                            loop.append(LineString(run))
                        run = []
                    else:
                        run.append(q)
                if len(run) > 3:
                    loop.append(LineString(run))
    lines += loop
    out["loop_m"] = sum(l.length for l in loop)
    for g in loop:
        for k in np.arange(0, g.length, 0.4):
            c, d = net.nearest(g.interpolate(k).coords[0], 0.6)
            if c is not None:
                tree.add(c)
    # join anchors to the tree
    for pt in anchors:
        c, d = net.nearest((pt[0], pt[1]), 3.0)
        if c is None:
            continue
        if not tree:
            tree.add(c)
            continue
        dist, pred = net.dist_from(sorted(tree))
        if not np.isfinite(dist[c]):
            continue
        pts = net.path(pred, c)
        if len(pts) >= 2:
            ls = net.smooth(pts, 0.3)
            if ls is not None:
                lines.append(ls)
        tree.update(int(net.nearest(q, 0.6)[0]) for q in pts if net.nearest(q, 0.6)[0] is not None)
    out["lines"] = lines
    if not lines:
        return out
    paths = unary_union([l.buffer(1.2, cap_style=1) for l in lines]).intersection(garden.buffer(-0.25))
    if col_u is not None and not col_u.is_empty:
        paths = paths.difference(col_u.buffer(0.05))
    out["paths"] = paths
    bedspace = garden.buffer(-0.6).difference(paths.buffer(0.4))
    if keep_out is not None and not keep_out.is_empty:
        bedspace = bedspace.difference(keep_out)
    if col_u is not None and not col_u.is_empty:
        bedspace = bedspace.difference(col_u.buffer(0.9))
    beds = []
    for p in getattr(bedspace, "geoms", [bedspace]):
        if p.geom_type != "Polygon" or p.area < 10:
            continue
        q = p.buffer(-0.5).buffer(0.5)
        for s in getattr(q, "geoms", [q]):
            if s.geom_type == "Polygon" and s.area >= 8:
                beds.append(s)
    out["beds"] = beds
    for bd in beds:
        for pt in _poisson(bd.buffer(-1.2), 4.4, rng, limit=14):
            out["trees"].append((pt.x, pt.y, rng.choice([0.9, 1.1, 1.3])))
        rg = bd.buffer(-0.55).exterior if not bd.buffer(-0.55).is_empty and bd.buffer(-0.55).geom_type == "Polygon" else None
        if rg is not None:
            for k in np.arange(0.5, rg.length, 2.1):
                p = rg.interpolate(k)
                if all(math.hypot(p.x - t[0], p.y - t[1]) > t[2] + 0.6 for t in out["trees"]):
                    out["shrubs"].append((p.x, p.y, 0.45))
    # benches along the paths
    for ls in lines:
        for k in np.arange(4.0, ls.length - 2.0, 11.0):
            p, q = ls.interpolate(k), ls.interpolate(k + 0.5)
            ux, uy = _unit_vec((p.x, p.y), (q.x, q.y))
            nx, ny = -uy, ux
            for sgn in (1, -1):
                cx, cy = p.x + sgn * nx * 0.78, p.y + sgn * ny * 0.78
                bench = affinity.rotate(box(cx - 0.9, cy - 0.25, cx + 0.9, cy + 0.25), math.degrees(math.atan2(uy, ux)), origin=(cx, cy))
                if paths.buffer(0.02).contains(bench) and (col_u is None or col_u.is_empty or bench.distance(col_u) > 1.0) \
                        and all(bench.distance(b) > 0.8 for b in out["benches"]):
                    out["benches"].append(bench)
                    break
    # shade pergolas in the two largest beds
    for bd in sorted(beds, key=lambda b: -b.area)[:2]:
        if bd.area < 40:
            continue
        c = polylabel(bd, 0.3)
        sq = box(c.x - 2.0, c.y - 2.0, c.x + 2.0, c.y + 2.0)
        if bd.buffer(-0.4).contains(sq):
            out["shade"].append(sq)
    return out

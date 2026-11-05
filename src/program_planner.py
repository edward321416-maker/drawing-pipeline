"""C-T13 1층 프로그램 계획기 — 렌더러와 분리된 Shapely 모듈.

실제 모델(슬라이스·태그 객체)에서 읽은 기하만 입력으로 받는다. 그림 코드에 새 x/y 좌표를 쓰지 않는다.
순서: ① 보행 동선(문·수직 이동 노드 사이 최단 경로) → ② 동선과 대기 영역을 M06/P01 같은 '비가구' 구획으로 확정
     → ③ 남은 바닥을 18개 하위 프로그램(M01~M06, P01~P04, S01~S04, C01~C04)으로 나눈다 → ④ 구획별 가구를 놓는다.

면적은 모두 Shapely polygon.area 로만 계산한다. soft_target_share 는 설계 목표일 뿐 측정값이 아니다.
출입문(시장 커튼월·캡슐)은 모델에 없으므로 PROPOSED_ONLY / ACCESS_PENDING 으로 표시만 한다.
"""
from __future__ import annotations

import heapq
import math
import os
import random
import re
import sys

import numpy as np
import shapely
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import nearest_points, unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import furniture_library as FL  # noqa: E402
import monograph_plan_renderer as mg  # noqa: E402

U = unary_union

# 승인된 프로그램 의도 (docs/decisions/2026-11-03_1f_program_intent_approved.md): id → (이름, 부모, 연성 목표 비율)
PROGRAMS = {
    "M01": ("안내·길찾기", "MARKET", 0.08), "M02": ("상설 판매", "MARKET", 0.34), "M03": ("팝업·시연", "MARKET", 0.10),
    "M04": ("푸드·시식", "MARKET", 0.16), "M05": ("공용 식음·대화", "MARKET", 0.09), "M06": ("순환·수직이동 대기", "MARKET", 0.23),
    "P01": ("공공 통과", "PILOTI", 0.50), "P02": ("만남·대기", "PILOTI", 0.20), "P03": ("숲 연결 쉼터", "PILOTI", 0.15), "P04": ("가변 행사 여백", "PILOTI", 0.15),
    "S01": ("하역", "SERVICE", 0.45), "S02": ("검수·보관", "SERVICE", 0.25), "S03": ("화물 승강기 대기", "SERVICE", 0.15), "S04": ("운영 통행", "SERVICE", 0.15),
    "C01": ("전시 안내", "CAPSULE", 0.15), "C02": ("주 전시", "CAPSULE", 0.50), "C03": ("관람 후 체류", "CAPSULE", 0.20), "C04": ("출입·관람 순환", "CAPSULE", 0.15),
}
MAIN_AISLE, SEC_AISLE = 2.4, 1.8                       # 계획 기준(법규 확정치 아님)


# ── 기하 도우미 ────────────────────────────────────────────────────────────────────────────
def polys(g):
    if g is None or g.is_empty:
        return []
    if g.geom_type == "Polygon":
        return [g]
    return [p for part in getattr(g, "geoms", []) for p in polys(part)]


def largest(g):
    ps = polys(g)
    return max(ps, key=lambda p: p.area) if ps else Polygon()


def lines(g):
    if g is None or g.is_empty:
        return []
    if g.geom_type == "LineString":
        return [g]
    return [l for part in getattr(g, "geoms", []) for l in lines(part)]


def unit(dx, dy):
    n = math.hypot(dx, dy) or 1.0
    return dx / n, dy / n


def _xy(p):
    return (p.x, p.y) if hasattr(p, "x") else (p[0], p[1])


# ── 입력 ────────────────────────────────────────────────────────────────────────────────
def input_from_dump(d):
    """T13_DUMP 로 덤프한 JSON(WKT) → 계획기 입력. 렌더러는 같은 키의 shapely 객체를 직접 넘긴다."""
    from shapely import wkt
    g = lambda k: (wkt.loads(d[k]) if d.get(k) else None)  # noqa: E731
    lifts = {}
    for t in d["tubes"]:
        m = re.search(r"(?<![A-Za-z0-9])(T\d|EV\d|FR|PL|M\d)(?![A-Za-z0-9])", t["name"])
        if "캡슐" in t["name"] or not m:
            continue
        lifts[m.group(1)] = wkt.loads(t["wkt"])
    return {
        "hall": g("hall"), "piloti": g("piloti"), "service": g("service"), "sunken": g("sunken"), "capsule": g("capsule"), "footprint": g("footprint"),
        "walls": g("walls"), "swings": g("swings"), "rooms": g("rooms"), "cols": list(wkt.loads(d["cols_drawn"]).geoms), "lifts": lifts,
        "lawn": g("lawn"), "cdoors": d["door_defs"], "ent_pts": [tuple(p) for p in d["ent_pts"]], "light_c": tuple(d["light_c"]),
        "bounds": d["bounds"], "bays": [wkt.loads(w) for w in d.get("bays", [])],
    }


# ── 보행 동선: 4방향 최단 경로(꺾임에 벌점) → 건축 축에 맞는 직교 복도 ─────────────────────────────────
def _grid(poly, g):
    minx, miny, maxx, maxy = poly.bounds
    xs = np.arange(math.floor(minx / g) * g + g / 2, maxx, g)
    ys = np.arange(math.floor(miny / g) * g + g / 2, maxy, g)
    X, Y = np.meshgrid(xs, ys)
    return xs, ys, shapely.contains_xy(poly, X, Y)


def route(walk, start, goals, g=0.5, turn=6.0, via=()):
    """walk 안에서 start → (via 순서대로) → goals(점 또는 폴리곤) 최단 직교 경로. 반환: LineString."""
    xs, ys, mask = _grid(walk, g)
    ny, nx = mask.shape

    def snap(p):
        x, y = _xy(p)
        best, bd = None, 1e18
        ii, jj = np.nonzero(mask)
        d2 = (xs[jj] - x) ** 2 + (ys[ii] - y) ** 2
        k = int(np.argmin(d2))
        return int(ii[k]), int(jj[k])

    pts = [snap(start)] + [snap(v) for v in via]
    if hasattr(goals, "geom_type") and goals.geom_type not in ("Point",):
        X, Y = np.meshgrid(xs, ys)
        gmask = shapely.contains_xy(goals, X, Y) & mask
        if not gmask.any():
            gmask[snap(goals.representative_point())] = True
    else:
        gmask = np.zeros_like(mask)
        gmask[snap(goals)] = True

    full = []
    cur = pts[0]
    targets = [np.zeros_like(mask) for _ in pts[1:]]
    for t, p in zip(targets, pts[1:]):
        t[p] = True
    targets.append(gmask)
    dirs = ((0, 1), (1, 0), (0, -1), (-1, 0))
    for tmask in targets:
        INF = 1e18
        dist = {}
        prev = {}
        heap = []
        for d in range(4):
            dist[(cur[0], cur[1], d)] = 0.0
            heapq.heappush(heap, (0.0, cur[0], cur[1], d))
        end = None
        while heap:
            dc, r, c, d = heapq.heappop(heap)
            if dc > dist.get((r, c, d), INF):
                continue
            if tmask[r, c]:
                end = (r, c, d)
                break
            for nd, (dr, dc2) in enumerate(dirs):
                rr, cc = r + dr, c + dc2
                if not (0 <= rr < ny and 0 <= cc < nx and mask[rr, cc]):
                    continue
                cost = 1.0 + (turn if nd != d else 0.0)
                nd_ = dc + cost
                key = (rr, cc, nd)
                if nd_ < dist.get(key, INF):
                    dist[key] = nd_
                    prev[key] = (r, c, d)
                    heapq.heappush(heap, (nd_, rr, cc, nd))
        if end is None:
            raise RuntimeError("동선 경로 없음: 시작 %s" % (start,))
        seg = []
        k = end
        while k in prev:
            seg.append((xs[k[1]], ys[k[0]]))
            k = prev[k]
        seg.append((xs[k[1]], ys[k[0]]))
        seg.reverse()
        full += seg if not full else seg[1:]
        cur = (end[0], end[1])
    ls = LineString(full).simplify(0.01)
    return ls


def corridor(path, width, clip):
    return path.buffer(width / 2, cap_style=2, join_style=2).intersection(clip)


# ── 가중 보로노이 분할 ─────────────────────────────────────────────────────────────────────
def partition(region, seeds, targets, g=0.25, iters=150, lo=0.7, hi=1.4, expo=0.5):
    """region 을 시드까지의 가중 거리로 나눈다. targets: id→목표 비율(합 1). 반환: id→Polygon(Multi 가능)."""
    ids = list(seeds)
    xs, ys, mask = _grid(region, g)
    X, Y = np.meshgrid(xs, ys)
    cx, cy = X[mask], Y[mask]
    D = np.stack([np.min(np.stack([np.maximum(np.abs(cx - sx), np.abs(cy - sy)) + 0.15 * np.hypot(cx - sx, cy - sy) for sx, sy in seeds[i]]), axis=0) for i in ids])      # L∞ 거리(+약간의 유클리드): 구획 경계가 축·45°로 정리된다
    w = np.ones(len(ids))
    tgt = np.array([targets[i] for i in ids], dtype=float)
    tgt /= tgt.sum()
    for _ in range(iters):
        lab = np.argmin(D / w[:, None], axis=0)
        share = np.bincount(lab, minlength=len(ids)) / max(len(lab), 1)
        w *= np.clip((tgt / np.maximum(share, 1e-4)) ** expo, lo, hi)
    lab = np.argmin(D / w[:, None], axis=0)
    full = np.full(mask.shape, -1, dtype=int)
    full[mask] = lab
    out = {}
    for k, i in enumerate(ids):
        boxes = []
        for r in range(full.shape[0]):
            row = full[r] == k
            c = 0
            while c < len(row):
                if row[c]:
                    c0 = c
                    while c < len(row) and row[c]:
                        c += 1
                    boxes.append(box(xs[c0] - g / 2, ys[r] - g / 2, xs[c - 1] + g / 2, ys[r] + g / 2))
                else:
                    c += 1
        out[i] = U(boxes).intersection(region) if boxes else Polygon()
    return out


def absorb_slivers(zones, min_area=6.0):
    """조각 폴리곤(min_area ㎡ 미만)은 맞닿은 길이가 가장 긴 이웃 구획에 합친다."""
    changed = True
    while changed:
        changed = False
        for zid in list(zones):
            for part in polys(zones[zid]):
                if part.area >= min_area:
                    continue
                best, bl = None, 0.0
                for oid, og in zones.items():
                    if oid == zid:
                        continue
                    sh = part.buffer(0.05).intersection(og).area
                    if sh > bl:
                        best, bl = oid, sh
                if best is not None:
                    zones[best] = U([zones[best], part.buffer(0.01)]).buffer(0)
                    zones[zid] = zones[zid].difference(part.buffer(0.001))
                    changed = True
    return zones


# ── 가구 배치기 ───────────────────────────────────────────────────────────────────────────
class Placer:
    def __init__(self, hold, walls):
        self.hold = hold                 # 가구가 들어가면 안 되는 고정 영역
        self.walls = walls               # 벽: 일반 가구는 wall_gap 이격, 벽면 진열대는 벽에 붙는다
        self.items = []                  # {"zone","type","parts","fp"}
        self._fps = []

    def free_in(self, zone, inset=0.25, wall_gap=0.4):
        f = zone.buffer(-inset).difference(self.hold)
        return f.difference(self.walls.buffer(wall_gap)) if wall_gap > 0 else f

    def try_add(self, zone_id, typ, parts, free, gap=0.9):
        bodies = [g for g, k in parts if k == "body"]
        if not bodies:
            return False
        fp = U(bodies)
        if not free.buffer(0.001).contains(fp):
            return False
        for o in self._fps:
            if fp.distance(o) < gap:
                return False
        self.items.append({"zone": zone_id, "type": typ, "parts": parts, "fp": fp})
        self._fps.append(fp)
        return True

    def lattice(self, zone_id, typ, zone, builder, pu, pv, frame, gap=0.9, cap=None, phases=((0, 0),), inset=0.25):
        c, u, v = frame
        free = self.free_in(zone, inset)
        if free.is_empty:
            return 0
        pts = [(x, y) for p in polys(free) for x, y in p.exterior.coords]
        aa = [(x - c[0]) * u[0] + (y - c[1]) * u[1] for x, y in pts]
        bb = [(x - c[0]) * v[0] + (y - c[1]) * v[1] for x, y in pts]
        best = None
        for ph in phases:
            trial = []
            a = min(aa) + ph[0] * pu
            while a < max(aa):
                b = min(bb) + ph[1] * pv
                while b < max(bb):
                    parts = builder(c, u, v, a, b)
                    fp = U([g for g, k in parts if k == "body"])
                    if free.buffer(0.001).contains(fp):
                        trial.append((a, b, parts, fp))
                    b += pv
                a += pu
            chosen, fps = [], list(self._fps)
            for a, b, parts, fp in trial:
                if all(fp.distance(o) >= gap for o in fps):
                    chosen.append((a, b, parts, fp))
                    fps.append(fp)
            if best is None or len(chosen) > len(best):
                best = chosen
        n = 0
        # 구획 중심에 가까운 것부터 cap 개 (군집이 한쪽으로 쏠리지 않게)
        cx, cy = zone.centroid.x, zone.centroid.y
        for a, b, parts, fp in sorted(best or [], key=lambda t: math.hypot(t[3].centroid.x - cx, t[3].centroid.y - cy)):
            if cap is not None and n >= cap:
                break
            if self.try_add(zone_id, typ, parts, free, gap):
                n += 1
        return n

    def pack(self, zone_id, typ, zone, builder, frame, gap=1.8, step=0.5, max_ratio=0.45, cap=None, inset=0.25):
        """첫 적합(first-fit) 채움: 건물 축 방향으로 행 단위로 훑으며 gap 만큼 띄워 놓는다. 불규칙한 구획도 촘촘히 채우되 점유율은 max_ratio 이하."""
        c, u, v = frame
        free = self.free_in(zone, inset)
        if free.is_empty:
            return 0
        pts = [(x, y) for p in polys(free) for x, y in p.exterior.coords]
        aa = [(x - c[0]) * u[0] + (y - c[1]) * u[1] for x, y in pts]
        bb = [(x - c[0]) * v[0] + (y - c[1]) * v[1] for x, y in pts]
        area_cap = free.area * max_ratio
        used, n = 0.0, 0
        b = min(bb)
        while b < max(bb):
            a = min(aa)
            while a < max(aa):
                parts = builder(c, u, v, a, b)
                fp = U([g for g, k in parts if k == "body"])
                if free.buffer(0.001).contains(fp) and all(fp.distance(o) >= gap for o in self._fps):
                    if used + fp.area > area_cap or (cap is not None and n >= cap):
                        return n
                    self.items.append({"zone": zone_id, "type": typ, "parts": parts, "fp": fp})
                    self._fps.append(fp)
                    used += fp.area
                    n += 1
                    a += 0.5
                else:
                    a += step
            b += step
        return n

    def place_near(self, zone_id, typ, zone, target, builder, orients, gap=0.6, inset=0.25, step=0.5, max_try=600):
        """target 에 가장 가까운 빈 자리에 builder(c,u,v,0,0) 를 놓는다. orients: 시험할 방향(u) 목록."""
        free = self.free_in(zone, inset)
        if free.is_empty:
            return False
        minx, miny, maxx, maxy = free.bounds
        xs = np.arange(minx, maxx, step)
        ys = np.arange(miny, maxy, step)
        X, Y = np.meshgrid(xs, ys)
        m = shapely.contains_xy(free, X, Y)
        pts = sorted(zip(X[m], Y[m]), key=lambda q: math.hypot(q[0] - target[0], q[1] - target[1]))[:max_try]
        for x, y in pts:
            for u in orients:
                parts = builder((x, y), u, (-u[1], u[0]), 0.0, 0.0)
                if self.try_add(zone_id, typ, parts, free, gap):
                    return True
        return False

    def along(self, zone_id, typ, zone, edges, builder, spacing, off, gap=0.6, cap=None, inset=0.1, wall_gap=0.0):
        """선분 edges 를 따라 spacing 간격으로 놓는다. builder(c,u,v,a,b): u=선분 방향, v=구획 안쪽 법선."""
        free = self.free_in(zone, inset, wall_gap)
        n = 0
        for ln in edges:
            if ln.length < spacing * 0.9:
                continue
            m = int(ln.length // spacing)
            for i in range(m):
                p = ln.interpolate((i + 0.5) * ln.length / m)
                p2 = ln.interpolate(min(ln.length, (i + 0.5) * ln.length / m + 0.1))
                p1 = ln.interpolate(max(0.0, (i + 0.5) * ln.length / m - 0.1))
                u = unit(p2.x - p1.x, p2.y - p1.y)
                v = (-u[1], u[0])
                if not zone.buffer(0.01).contains(Point(p.x + v[0] * (off + 0.2), p.y + v[1] * (off + 0.2))):
                    v = (-v[0], -v[1])
                parts = builder((p.x, p.y), u, v, 0.0, off)
                if self.try_add(zone_id, typ, parts, free, gap):
                    n += 1
                    if cap is not None and n >= cap:
                        return n
        return n


# ── 본 계획 ────────────────────────────────────────────────────────────────────────────────
def plan_program(variant, I, seed=7):
    rng = random.Random(seed)
    hall, piloti, service, capsule = I["hall"], I["piloti"], I["service"], I["capsule"]
    cols, lifts = I["cols"], I["lifts"]
    shell_all = U(list(lifts.values()) + [capsule])
    blockers = U([I["rooms"], shell_all, I["sunken"] if I["sunken"] is not None else Polygon()])
    hall_net = largest(hall.buffer(-0.3).difference(blockers.buffer(0.1)))
    piloti_net = largest(piloti.buffer(-0.3).difference(blockers.buffer(0.1)))
    service_net = largest(service.buffer(-0.3).difference(blockers.buffer(0.1)))
    col_u = U([c.buffer(0.55) for c in cols])
    swings = I["swings"]
    walls = I["walls"]
    foot_ext = I["footprint"].exterior
    hc = hall_net.centroid

    # 문 후보: 필로티 경계에 놓인 것 = 공공(시장 진입 후보), 서비스 경계 = 서비스. 모두 모델에 없는 그래픽 후보(PROPOSED_ONLY)
    pub, svc = [], []
    for dd in I["cdoors"]:
        c = Point(dd["center"])
        n = tuple(dd["n"])
        if not hall_net.buffer(0.5).contains(Point(c.x + n[0], c.y + n[1])):
            n = (-n[0], -n[1])
        rec = {"center": (c.x, c.y), "n": n, "t": tuple(dd["t"])}
        if piloti.exterior.distance(c) < 0.6 and I["footprint"].exterior.distance(c) > 0.6:
            pub.append(rec)
        elif service.exterior.distance(c) < 0.6 or service.distance(c) < 0.6:
            svc.append(rec)
    pub.sort(key=lambda r: (r["center"][1], r["center"][0]))                       # 남→북 순서로 안정 정렬
    assert len(pub) >= 2, "필로티 경계 문 후보 2개 필요"
    d_low, d_high = pub[0], pub[1]
    prim, sec = (d_low, d_high) if variant == "A" else (d_high, d_low)

    # ── ① 동선 ────────────────────────────────────────────────────────────────────────────
    walk_h = hall_net.difference(col_u).difference(swings.buffer(0.3))
    walk_p = piloti_net.difference(col_u).difference(swings.buffer(0.3))
    T3, T4, T2 = lifts["T3"], lifts["T4"], lifts["T2"]
    ring = lambda sh, r: sh.buffer(r).difference(sh)  # noqa: E731
    ring3, ring4, ring2 = ring(T3, 2.6).intersection(hall_net), ring(T4, 2.6).intersection(hall_net), ring(T2, 2.2).intersection(hall_net)
    ringE = ring(lifts["EV2"], 2.2).intersection(hall_net) if "EV2" in lifts else Polygon()
    ent_in = lambda r, k: (r["center"][0] + r["n"][0] * k, r["center"][1] + r["n"][1] * k)  # noqa: E731
    routes = []                                                                       # (종류, 선, 폭)
    if variant == "A":                                                                # 통과축: 두 문에서 시작해 북쪽 가로축으로 T3·T4 를 잇는 트리
        routes.append(("main", route(walk_h, ent_in(d_low, 0.9), ring4), MAIN_AISLE))
        routes.append(("main", route(walk_h, ent_in(d_high, 0.9), ring3), MAIN_AISLE))
        routes.append(("main", route(walk_h, ring3.representative_point(), ring4), MAIN_AISLE))
        routes.append(("secondary", route(walk_h, ent_in(d_low, 0.9), ring2), SEC_AISLE))
    else:                                                                             # 순환: 문 → T3 → T4 → T2 → 문 의 고리
        routes.append(("main", route(walk_h, ent_in(d_high, 0.9), ring3), MAIN_AISLE))
        routes.append(("main", route(walk_h, ring3.representative_point(), ring4), MAIN_AISLE))
        routes.append(("main", route(walk_h, ring4.representative_point(), ring2), MAIN_AISLE))
        routes.append(("main", route(walk_h, ring2.representative_point(), Point(*ent_in(d_low, 0.9))), MAIN_AISLE))
    door_clear = []
    for r in pub:
        n, t = r["n"], r["t"]
        cx, cy = r["center"]
        door_clear.append(Polygon([(cx - t[0] * 2.0, cy - t[1] * 2.0), (cx + t[0] * 2.0, cy + t[1] * 2.0),
                                   (cx + t[0] * 2.0 + n[0] * 2.8, cy + t[1] * 2.0 + n[1] * 2.8), (cx - t[0] * 2.0 + n[0] * 2.8, cy - t[1] * 2.0 + n[1] * 2.8)]))
    corr_main = U([corridor(l, w, hall_net) for k, l, w in routes if k == "main"])
    corr_sec = U([corridor(l, w, hall_net) for k, l, w in routes if k == "secondary"])
    core_fronts = swings.buffer(1.2).intersection(hall_net)
    m06 = U([corr_main, corr_sec, ring3, ring4, ringE, U(door_clear).intersection(hall_net), core_fronts]).intersection(hall_net)
    m06_vector = m06                                                                 # 래스터 잔여 띠를 섞기 전의 순수 벡터 복도·대기 영역(도면 바닥 채움용)
    rest = hall_net.difference(m06)
    rest_open = rest.buffer(-0.9).buffer(0.9).intersection(rest)
    m06 = U([m06, rest.difference(rest_open)]).intersection(hall_net)               # 폭 1.8 m 미만 잔여 띠는 순환으로 편입

    # ── ② 시장 구획 ──────────────────────────────────────────────────────────────────────
    T3c, T4c = lifts["T3"].centroid, lifts["T4"].centroid
    T2c = Point(I["light_c"])
    away = unit(T2c.x - prim["center"][0], T2c.y - prim["center"][1])
    edge_pt = nearest_points(foot_ext, T2c)[0]
    to_in = unit(hc.x - edge_pt.x, hc.y - edge_pt.y)
    seed5 = (edge_pt.x + to_in[0] * 3.2, edge_pt.y + to_in[1] * 3.2)
    mid = ((T3c.x + T4c.x) / 2, (T3c.y + T4c.y) / 2)
    if variant == "A":
        seeds = {"M01": [ent_in(prim, 4.0)], "M02": [mid, (mid[0], mid[1] + 3.0)], "M03": [ent_in(sec, 5.0)],
                 "M04": [(T2c.x + away[0] * 5.0, T2c.y + away[1] * 5.0)], "M05": [seed5]}
    else:
        d34 = unit(T4c.x - T3c.x, T4c.y - T3c.y)
        seeds = {"M01": [ent_in(prim, 6.0), ent_in(prim, 11.0)], "M02": [(T3c.x + d34[0] * 8.5, T3c.y + d34[1] * 8.5), (T4c.x - d34[0] * 8.5, T4c.y - d34[1] * 8.5)],
                 "M03": [ent_in(sec, 5.0), (mid[0] + 3.0, mid[1] - 9.0)], "M04": [(T2c.x + away[0] * 5.0, T2c.y + away[1] * 5.0)], "M05": [seed5]}
    soft = {k: PROGRAMS[k][2] for k in seeds}
    parts = partition(rest_open, seeds, soft)
    zones = absorb_slivers({**parts})
    zones["M06"] = m06

    # ── ③ 필로티 ──────────────────────────────────────────────────────────────────────────
    main_e = I["ent_pts"][0]
    pr = []
    pl_fronts = ring(lifts["PL"], 2.2).intersection(piloti_net) if "PL" in lifts else Polygon()
    for r in pub:
        pr.append(route(walk_p, (main_e[0] + 1.0, main_e[1]), Point(r["center"][0] - r["n"][0] * 1.0, r["center"][1] - r["n"][1] * 1.0)))
    p_corr = U([corridor(l, 4.0, piloti_net) for l in pr] + [pl_fronts])            # 공공 통과: 폭 4 m 복도(주 통로 2.4 m 이상)
    p_rest = piloti_net.difference(p_corr)
    p_rest = p_rest.buffer(-0.9).buffer(0.9).intersection(p_rest)
    lawn_c = I["lawn"].centroid if I.get("lawn") is not None and not I["lawn"].is_empty else Point(hc.x - 40, hc.y)
    p03 = nearest_points(piloti_net, lawn_c)[0]
    open_c = largest(p_rest).representative_point() if not p_rest.is_empty else piloti_net.centroid
    from shapely.ops import polylabel
    try:
        open_c = polylabel(largest(p_rest), tolerance=0.5)
    except Exception:  # noqa: BLE001
        pass
    seeds_p = {"P02": [(main_e[0] + 3.5, main_e[1] + 5.0)], "P03": [(p03.x + 2.0, p03.y - 2.0)], "P04": [(open_c.x, open_c.y)]}
    tp = {"P02": 0.20, "P03": 0.15, "P04": 0.15}
    zp = absorb_slivers(partition(p_rest, seeds_p, tp, iters=200, lo=0.95, hi=1.05, expo=0.2)) if not p_rest.is_empty else {k: Polygon() for k in seeds_p}
    zones.update(zp)
    zones["P01"] = p_corr

    # ── ④ 서비스 ──────────────────────────────────────────────────────────────────────────
    bays = I.get("bays") or []
    fr = lifts.get("FR")
    s01 = U([b.buffer(0.3) for b in bays]).intersection(service_net) if bays else Polygon()
    s03 = ring(fr, 3.0).intersection(service_net) if fr is not None else Polygon()
    ent_s = I["ent_pts"][1] if len(I["ent_pts"]) > 1 else (service.centroid.x, service.bounds[3])
    s04_path = None
    try:
        walk_s = service_net.difference(col_u).difference(s01)
        s04_path = route(walk_s, (ent_s[0], min(ent_s[1], service.bounds[3] - 0.8)), ring(fr, 3.0) if fr is not None else Point(service.centroid))
        s04 = corridor(s04_path, SEC_AISLE, service_net).difference(s01).difference(s03)
    except Exception:  # noqa: BLE001
        s04 = Polygon()
    bay_vs_fr = s01.intersection(s03).area                                         # 하역 베이(모델 기반 렌더러 심볼, 서비스 구역에 1개)가 FR 대기 반경과 겹치는 면적
    s03 = s03.difference(s01)                                                      # 베이가 FR 바로 옆(0.9 m)이라 하역 접안 우선, FR 대기는 나머지 쪽에 둔다
    s02 = service_net.difference(U([s01, s03, s04]))
    zones.update({"S01": s01, "S02": s02, "S03": s03, "S04": s04})

    # ── ⑤ 서측 캡슐 ──────────────────────────────────────────────────────────────────────
    cap_inner = capsule.buffer(-0.35)
    cc, cu, cv_, cL, cW = mg.obb(capsule)
    if cu[1] < 0:
        cu = (-cu[0], -cu[1])
    cv_ = (-cu[1], cu[0])
    base = nearest_points(capsule.exterior, Point(d_high["center"]))[0]                       # 캡슐에 가까운 북쪽 문 후보 기준
    a0 = (base.x - cc[0]) * cu[0] + (base.y - cc[1]) * cu[1]
    shift = -4.0 if variant == "A" else 4.5                                          # A: 필로티 쪽(남), B: 시장 쪽(북) — 모델에 문이 없으므로 후보일 뿐
    a_door = max(-cL / 2 + 3.0, min(cL / 2 - 3.0, a0 + shift))
    side = 1.0 if ((base.x - cc[0]) * cv_[0] + (base.y - cc[1]) * cv_[1]) >= 0 else -1.0         # 시장·필로티 쪽 옆면(문 후보와 같은 쪽)
    door_b = capsule.exterior.interpolate(capsule.exterior.project(Point(cc[0] + cu[0] * a_door + cv_[0] * side * (cW / 2), cc[1] + cu[1] * a_door + cv_[1] * side * (cW / 2))))
    door_pt = (door_b.x, door_b.y)
    inward = unit(cc[0] - door_pt[0], cc[1] - door_pt[1])

    def aproj(g):
        return None

    # 축 위치로 나눈다: C01 = 문 둘레 ±2.6 m 띠, C03 = 문에서 먼 쪽 끝 20 %, C04 = 중앙 통로 1.6 m(문~먼 끝) + 문 앞 현관, C02 = 나머지
    far_sign = -1 if a_door > 0 else 1
    band = lambda a_lo, a_hi: Polygon([(cc[0] + cu[0] * a_lo + cv_[0] * -20, cc[1] + cu[1] * a_lo + cv_[1] * -20), (cc[0] + cu[0] * a_hi + cv_[0] * -20, cc[1] + cu[1] * a_hi + cv_[1] * -20),  # noqa: E731
                                      (cc[0] + cu[0] * a_hi + cv_[0] * 20, cc[1] + cu[1] * a_hi + cv_[1] * 20), (cc[0] + cu[0] * a_lo + cv_[0] * 20, cc[1] + cu[1] * a_lo + cv_[1] * 20)])
    c01 = band(a_door - 2.2, a_door + 2.2).intersection(cap_inner)
    far_lo, far_hi = (-cL / 2, -cL / 2 + 0.2 * cL) if far_sign < 0 else (cL / 2 - 0.2 * cL, cL / 2)
    c03 = band(far_lo, far_hi).intersection(cap_inner).difference(c01)
    aisle = LineString([(cc[0] + cu[0] * (-cL / 2), cc[1] + cu[1] * (-cL / 2)), (cc[0] + cu[0] * (cL / 2), cc[1] + cu[1] * (cL / 2))]).buffer(0.6, cap_style=2)
    vest = Point(door_pt).buffer(2.4).intersection(cap_inner)
    c04 = U([aisle.intersection(cap_inner), vest]).difference(c01).difference(c03)
    c02 = cap_inner.difference(U([c01, c03, c04]))
    zones.update({"C01": c01, "C02": c02, "C03": c03, "C04": c04})

    # ── ⑥ 가구 ────────────────────────────────────────────────────────────────────────────
    hold = U([col_u, walls.buffer(0.03), swings.buffer(0.4), U([s.buffer(0.5) for s in lifts.values()]), I["rooms"].buffer(0.1)])
    P = Placer(hold, walls)
    ax = ((0.0, 0.0), (1.0, 0.0), (0.0, 1.0))                                         # 기준틀: 건물 축(E-W 가 u)
    axN = ((0.0, 0.0), (0.0, 1.0), (-1.0, 0.0))                                       # 회전틀: N-S 가 u
    face_ent = prim["t"]                                                              # 문 접선 방향 (안내대 긴 변)
    wall_edges = [LineString(list(p.exterior.coords)[i:i + 2]) for p in polys(walls) for i in range(len(p.exterior.coords) - 1)]

    # M01 안내·길찾기: 주 진입문 앞 측면에 안내대 + 길찾기 플린스
    n_, t_ = prim["n"], prim["t"]
    P.place_near("M01", "info_counter", zones["M01"], ent_in(prim, 5.5), lambda c, u, v, a, b: FL.info_counter(c, u, v, a, b),
                 [t_, n_, (-t_[0], -t_[1])], gap=0.6, inset=0.4)
    # M02 상설 판매
    z = zones["M02"]
    if variant == "A":                                                                # 통과축 + 군집: 등을 맞댄 쌍 → 낱개 섬 → 단면 매대 순으로 채움
        P.pack("M02", "back_to_back_stall", z, lambda c, u, v, a, b: FL.island_booth(c, u, v, a, b - 1.2) + FL.island_booth(c, u, v, a, b + 1.2), ax, gap=1.8, max_ratio=0.34)
        P.pack("M02", "island_stall", z, lambda c, u, v, a, b: FL.island_booth(c, u, v, a, b), ax, gap=1.8, max_ratio=0.30)
        P.pack("M02", "single_sided_stall", z, lambda c, u, v, a, b: FL.single_stall(c, u, v, a, b), axN, gap=1.8, max_ratio=0.12)
    else:                                                                             # 분산 군집: 남북 방향 단면 매대 열
        P.pack("M02", "single_sided_stall", z, lambda c, u, v, a, b: FL.single_stall(c, u, v, a, b), axN, gap=1.8, max_ratio=0.34)
    P.along("M02", "wall_display", z, [e for e in wall_edges if e.length > 2.6], lambda c, u, v, a, b: FL.wall_display(c, u, v, a, b), 2.8, 0.45 / 2 + 0.03, cap=8)
    n_cash = 0
    for it in list(P.items):
        if it["zone"] == "M02" and it["type"] in ("back_to_back_stall", "single_sided_stall", "island_stall") and n_cash < 3:
            x0, y0, x1, y1 = it["fp"].bounds
            for (px_, py_) in ((x1 + 1.0, (y0 + y1) / 2), (x0 - 1.0, (y0 + y1) / 2), ((x0 + x1) / 2, y1 + 0.8), ((x0 + x1) / 2, y0 - 0.8)):
                if P.try_add("M02", "cash_counter", FL.cash_counter((0, 0), (1, 0), (0, 1), px_, py_), P.free_in(z), gap=0.6):
                    n_cash += 1
                    break
    # M03 팝업·시연
    P.pack("M03", "popup_module", zones["M03"], lambda c, u, v, a, b: FL.popup_module(c, u, v, a, b), ax, gap=1.5, max_ratio=0.40, cap=10)
    # M04 푸드·시식
    P.pack("M04", "food_kiosk", zones["M04"], lambda c, u, v, a, b: FL.food_kiosk(c, u, v, a, b), ax, gap=2.2, max_ratio=0.16, cap=4)
    P.pack("M04", "tasting_counter", zones["M04"], lambda c, u, v, a, b: FL.tasting_counter(c, u, v, a, b), ax, gap=1.8, max_ratio=0.18, cap=4)
    P.along("M04", "pickup_shelf", zones["M04"], [e for e in wall_edges if e.length > 2.4], lambda c, u, v, a, b: FL.pickup_shelf(c, u, v, a, b), 3.0, 0.2 + 0.03, cap=2)
    # M05 공용 식음·대화
    P.along("M05", "banquette", zones["M05"], [l for l in lines(foot_ext.intersection(zones["M05"].buffer(1.0)))], lambda c, u, v, a, b: FL.banquette(c, u, v, a, b), 4.2, 0.3 + 0.4, cap=3)
    P.pack("M05", "communal_table", zones["M05"], lambda c, u, v, a, b: FL.communal_table(c, u, v, a, b), ax, gap=1.3, max_ratio=0.25, cap=4)
    P.pack("M05", "four_top_table", zones["M05"], lambda c, u, v, a, b: FL.four_top(c, u, v, a, b), ax, gap=1.2, max_ratio=0.30, cap=12)
    # P02 만남·대기 / P03 숲 연결 쉼터
    if not zones["P02"].is_empty:
        P.lattice("P02", "long_bench", zones["P02"], lambda c, u, v, a, b: FL.long_bench(c, u, v, a, b), 3.4, 2.6, ax, gap=1.2, cap=4,
                  phases=tuple((i / 3, j / 3) for i in range(3) for j in range(3)))
    if not zones["P03"].is_empty:
        n_pl = P.lattice("P03", "planter_bench", zones["P03"], lambda c, u, v, a, b: FL.planter_bench(*mg.at(c, u, v, a, b), rng), 3.6, 3.6, ax, gap=0.8, cap=3,
                         phases=tuple((i / 4, j / 4) for i in range(4) for j in range(4)), inset=0.3)
        if n_pl == 0:                                                                 # 원형이 안 들어가면 직선 벤치(스펙: 직선/플랜터 벤치)
            P.lattice("P03", "long_bench", zones["P03"], lambda c, u, v, a, b: FL.long_bench(c, u, v, a, b), 3.0, 1.8, ax, gap=0.8, cap=4,
                      phases=tuple((i / 3, j / 3) for i in range(3) for j in range(3)))
    # S02 검수·보관
    if not zones["S02"].is_empty:
        P.lattice("S02", "storage_rack", zones["S02"], lambda c, u, v, a, b: FL.storage_rack(c, u, v, a, b), 3.4, 1.9, ax, gap=1.0, cap=16,
                  phases=tuple((i / 3, j / 3) for i in range(3) for j in range(3)))
    # C 캡슐: 접수 / 전시 / 체류
    cfree = P.free_in(capsule, 0.35)
    frame_c = (cc, cu, cv_)
    ang_in = math.atan2(inward[1], inward[0])
    desk_c = (door_pt[0] + inward[0] * 1.9, door_pt[1] + inward[1] * 1.9)
    P.try_add("C01", "reception_desk", FL.curved_desk(desk_c, ang_in + math.pi, 1.4, 0.9), cfree, gap=0.4) or \
        P.try_add("C01", "reception_desk", FL.curved_desk((door_pt[0] + inward[0] * 2.6, door_pt[1] + inward[1] * 2.6), ang_in + math.pi, 1.4, 0.9), cfree, gap=0.4)
    for k_u in range(4):
        a = a_door + far_sign * (2.2 + 1.7 + 3.4 * k_u)
        for sgn_v in ((-1, 1) if variant == "A" else ((1,) if k_u % 2 == 0 else (-1,))):
            parts = FL.plinth_island(cc, cu, cv_, a, sgn_v * 1.9, rng)
            if zones["C02"].buffer(0.01).contains(U([g for g, k in parts if k == "body"])):
                P.try_add("C02", "plinth_island", parts, cfree, gap=0.8)
    for k_u in range(2):                                                              # 남은 쪽(문 뒤 포켓)에도 전시 한 점
        a = a_door - far_sign * (2.2 + 1.7 + 3.4 * k_u)
        parts = FL.plinth_island(cc, cu, cv_, a, 0.0 if variant == "A" else 1.9, rng)
        if zones["C02"].buffer(0.01).contains(U([g for g, k in parts if k == "body"])):
            P.try_add("C02", "plinth_island", parts, cfree, gap=0.8)
    if variant == "B":                                                                # B: 반대 벽쪽에 갤러리 벤치 줄
        for q in range(3):
            P.try_add("C02", "gallery_bench", FL.gallery_bench(cc, cu, cv_, a_door + far_sign * (3.9 + 3.4 * q), -2.9), cfree, gap=0.6)
    a_c3 = far_sign * (cL / 2 - 2.0)
    for sgn in (-1, 1):                                                               # C03: 축 방향 벤치 둘 + 작은 원탁
        P.try_add("C03", "gallery_bench", FL.gallery_bench(cc, cu, cv_, a_c3, sgn * 1.5), cfree, gap=0.4)

    zones = {k_: (U(polys(v_)) if polys(v_) else Polygon()) for k_, v_ in zones.items()}
    left_h = hall_net.difference(U([zones[k_] for k_ in ("M01", "M02", "M03", "M04", "M05", "M06")]).buffer(0.01))     # 폭 얇은 잔여 띠는 비가구 구획으로 편입
    zones["M06"] = U(polys(U([zones["M06"], left_h])))
    left_p = piloti_net.difference(U([zones[k_] for k_ in ("P01", "P02", "P03", "P04")]).buffer(0.01))
    zones["P01"] = U(polys(U([zones["P01"], left_p])))       # GeometryCollection 정리: 면 구획은 Polygon/MultiPolygon 만

    # ── 흐름 기호 ────────────────────────────────────────────────────────────────────────
    flows = [{"kind": "public", "line": l} for k, l, w in routes if k == "main"] + [{"kind": "secondary", "line": l} for k, l, w in routes if k == "secondary"] \
        + [{"kind": "public", "line": l} for l in pr] + ([{"kind": "service", "line": s04_path}] if s04_path is not None else [])
    entries = [{"id": "ENTRY_MARKET_PRIMARY", "center": prim["center"], "n": prim["n"], "t": prim["t"], "status": "PROPOSED_ONLY / ACCESS_PENDING"},
               {"id": "ENTRY_MARKET_SECONDARY", "center": sec["center"], "n": sec["n"], "t": sec["t"], "status": "PROPOSED_ONLY / ACCESS_PENDING"},
               {"id": "ENTRY_CAPSULE", "center": door_pt, "n": inward, "t": (-inward[1], inward[0]), "status": "PROPOSED_ONLY / ACCESS_PENDING"}]
    notes = {"service_bays_overlap_freight_wait_m2": round(bay_vs_fr, 3),
             "note": "하역 베이는 서비스 구역에서 1개만 들어가며 FR 셸에서 0.9 m. FR 대기 반경 3 m 와 겹친 면적은 S01 우선으로 S03에서 제외했다."}
    return {"variant": variant, "notes": notes, "zones": zones, "m06_vector": m06_vector, "furniture": P.items, "flows": flows, "entries": entries, "door_pt": door_pt,
            "nets": {"hall": hall_net, "piloti": piloti_net, "service": service_net, "capsule": cap_inner}, "hold": hold, "cols_u": col_u,
            "corr_main": corr_main, "corr_sec": corr_sec, "p_corr": p_corr, "door_clear": U(door_clear)}


# ── 검사 ─────────────────────────────────────────────────────────────────────────────────
PARENT_NET = {"MARKET": "hall", "PILOTI": "piloti", "SERVICE": "service", "CAPSULE": "capsule"}


def qa(plan, I):
    """기하 QA: 부모 밖 유출·중첩·구조 침범·가구 중복·면적표."""
    z = plan["zones"]
    rows, res = [], {}
    names = list(z)
    leak = {}
    for zid in names:
        par = PARENT_NET[PROGRAMS[zid][1]]
        leak[zid] = round(z[zid].difference(plan["nets"][par].buffer(0.02)).area, 4)
    res["zone_outside_parent_m2_max"] = max(leak.values())
    ov = 0.0
    pairs = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if PROGRAMS[a][1] != PROGRAMS[b][1]:
                continue
            o = z[a].buffer(-0.01).intersection(z[b].buffer(-0.01)).area
            ov += o
            if o > 1e-6:
                pairs.append((a, b, round(o, 4)))
    res["zone_overlap_m2_total"] = round(ov, 6)
    res["zone_overlap_pairs"] = pairs
    gaps = {}
    for par, net in plan["nets"].items():
        if par == "capsule":
            continue
        union = U([z[k] for k in names if PARENT_NET[PROGRAMS[k][1]] == par])
        gaps[par] = round(net.difference(union.buffer(0.02)).area, 4)
    res["unassigned_net_floor_m2"] = gaps
    cols, lifts = U(I["cols"]), U(list(I["lifts"].values()))
    items = plan["furniture"]
    struct_hit = 0
    zone_out = 0
    cross = 0
    cd = U([r["center"] and Point(r["center"]).buffer(1.8) for r in plan["entries"]])
    door_hit = 0
    for it in items:
        fp = it["fp"]
        if fp.intersects(cols) or fp.intersects(lifts) or fp.intersects(I["rooms"]) or fp.intersects(I["walls"]):
            struct_hit += 1
        par_net = plan["nets"][PARENT_NET[PROGRAMS[it["zone"]][1]]]
        if not par_net.buffer(0.05).contains(fp):
            zone_out += 1
        if not z[it["zone"]].buffer(0.05).contains(fp):
            cross += 1
        if it["type"] not in ("reception_desk", "info_counter") and fp.intersects(cd):
            door_hit += 1
    res["furniture_hits_structure"] = struct_hit
    res["furniture_outside_parent_zone"] = zone_out
    res["furniture_crossing_own_subzone_boundary"] = cross
    res["furniture_in_entry_clearance"] = door_hit
    dup = 0
    md = 1e9
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            d = a["fp"].distance(b["fp"])
            if d < 1e-6:
                dup += 1
            if a["zone"][0] == b["zone"][0]:
                md = min(md, d)
    res["furniture_instance_overlaps"] = dup
    res["min_gap_between_instances_m"] = round(md, 3) if md < 1e8 else None
    res["furniture_instances"] = len(items)
    res["furniture_body_polygons"] = sum(1 for it in items for g, k in it["parts"] if k == "body")
    res["area_table"] = {k: round(z[k].area, 2) for k in names}
    res["service_bays_overlap_freight_wait_m2"] = plan["notes"]["service_bays_overlap_freight_wait_m2"]
    return res

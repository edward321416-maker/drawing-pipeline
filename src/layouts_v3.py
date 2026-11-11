"""상층 프로그램별 가구·동선 계획 V3 (PROPOSED_ONLY).

V2(upper_layouts.py)는 판매층에서 같은 부스 하나를 격자로 복제했다. V3는 프로그램마다 공간 사용 논리가 다르다.

  retail A (2F-5F, B1, B2)  브랜드 셀(크기 4종 + 계산대) 엇갈림 열 · 체험존 · 튜브 둘레 팝업 링 · 승강기 앞 대기 라운지 · 벽 진열
  retail B (그 밖의 판매층)  팝업 스트리트: 세로 거리 2개 · 쌍 섬(길이 3종 + 계산대) · 중앙 대로의 팝업 카트 · 이벤트 광장 · 대기 라운지
  fnb                       외벽 뱅킷 · 2/4/6인 식탁 · 공용 장탁자 · 바(스툴) · 서비스 카운터 + 줄서기 구역 · 운영 동선
  culture                   이벤트 무대(+서는 구역·배경 월) · 전시 패널 격자 · 플린스 줄 · 집합 계단 · 라운지 포드 · 안내 데스크
  garden                    산책로(양쪽 선) · 곡선 화단 · 수목 · 벤치 · 테라스 식탁 세트(구역)

모든 항목은 Item(geometry, kind, ftype)이다. kind: body | counter | line | foliage | zone | route_v | route_o. ftype은 가구 유형(QA가 반복·다양성을 센다).
방문자 동선(route_v)과 운영 동선(route_o)은 비어 있는 격자(0.45 m)에서 최대 여유 경로로 계산하고, 경로의 최소 여유 폭을 meta에 남긴다.
좌표는 구역 폴리곤·장애물·튜브/코어 위치에서 계산하며 숫자 좌표를 직접 쓰지 않는다.
"""
import math

import numpy as np
import shapely
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra, minimum_spanning_tree
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

import upper_layouts as V2

R, RING, STRIPS = V2._rect, V2._ring, V2._perimeter_strips
A_FLOORS = {"2F", "3F", "4F", "5F", "B1", "B2"}


class Item(tuple):
    """(geometry, kind) 두 값으로 풀리는 튜플 + 유형. 기존 렌더러 코드가 `for g, k in items`로 읽어도 그대로 동작한다."""

    def __new__(cls, g, kind, ftype=None):
        o = super().__new__(cls, (g, kind))
        o.ftype = ftype
        return o


class Items(list):
    meta = None


class Packer:
    def __init__(self, region, obst, hard):
        self.region, self.obst, self.hard = region, obst, hard
        self.items, self.taken = [], Polygon()

    def ok(self, g, soft=True, clear=0.0, vs_taken=True):
        if g.is_empty or not self.region.contains(g):
            return False
        if soft and self.obst is not None and not self.obst.is_empty and g.intersects(self.obst):
            return False
        if self.hard is not None and not self.hard.is_empty and g.intersects(self.hard):
            return False
        if vs_taken and not self.taken.is_empty and g.buffer(clear).intersects(self.taken):
            return False
        return True

    def _take(self, g):
        self.taken = unary_union([self.taken, g]) if not self.taken.is_empty else g

    def put(self, g, kind, ftype, soft=True, clear=0.0):
        if not self.ok(g, soft, clear):
            return False
        self.items.append(Item(g, kind, ftype))
        if kind in ("body", "counter", "zone"):
            self._take(g)
        return True

    def put_all(self, parts, soft=True, clear=0.0):
        """parts: [(geom, kind, ftype)]. 몸체·계산대가 모두 들어가면 한꺼번에 놓는다(서로는 겹쳐도 됨)."""
        body = [p for p in parts if p[1] in ("body", "counter")]
        if not all(self.ok(g, soft, clear) for g, _, _ in body):
            return False
        for g, k, t in parts:
            self.items.append(Item(g, k, t))
            if k in ("body", "counter"):
                self._take(g)
        return True

    def line(self, g, ftype):
        self.items.append(Item(g, "line", ftype))


def _pick(rng, options):
    total = sum(w for _, w in options)
    r = rng.uniform(0, total)
    for v, w in options:
        r -= w
        if r <= 0:
            return v
    return options[-1][0]


def _circle(x, y, r, n=14):
    return Point(x, y).buffer(r, n // 4)


def _spots(region, step, order_key):
    x0, y0, x1, y1 = region.bounds
    pts = [(x, y) for x in np.arange(x0 + step, x1 - step, step) for y in np.arange(y0 + step, y1 - step, step)]
    return sorted(pts, key=order_key)


# ── 동선: 비어 있는 격자에서 최대 여유 경로 ───────────────────────────────────────────────────────
def _grid(region, blocked, step=0.45):
    x0, y0, x1, y1 = region.bounds
    xs = np.arange(x0 + step / 2, x1, step)
    ys = np.arange(y0 + step / 2, y1, step)
    X, Y = np.meshgrid(xs, ys)
    inside = shapely.contains_xy(region, X, Y)
    blk = shapely.contains_xy(blocked, X, Y) if blocked is not None and not blocked.is_empty else np.zeros_like(inside)
    free = inside & ~blk
    clear = ndimage.distance_transform_edt(free) * step
    return xs, ys, free, clear, step


def _chaikin(pts, it=2):
    for _ in range(it):
        out = [pts[0]]
        for a, b in zip(pts, pts[1:]):
            out += [(0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]), (0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1])]
        out.append(pts[-1])
        pts = out
    return pts


def circulation(region, blocked, anchors, step=0.45):
    """anchors를 잇는 최소 신장 경로(여유가 큰 칸을 선호). 반환: ([LineString], 경로 최소 여유 폭 m, 연결된 앵커 수)."""
    xs, ys, free, clear, st = _grid(region, blocked, step)
    ny, nx = free.shape
    idx = np.arange(nx * ny).reshape(ny, nx)
    rows, cols, w = [], [], []
    for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):                # 8방향 이웃(중복 없이 4방향만 세우고 무방향 그래프로 쓴다)
        if dx >= 0:
            ia = idx[0:ny - dy, 0:nx - dx]
            ib = idx[dy:ny, dx:nx]
        else:
            ia = idx[0:ny - dy, -dx:nx]
            ib = idx[dy:ny, 0:nx + dx]
        ok = free.ravel()[ia.ravel()] & free.ravel()[ib.ravel()]
        mid = np.minimum(clear.ravel()[ia.ravel()], clear.ravel()[ib.ravel()])
        cost = math.hypot(dx, dy) * st / (0.25 + mid)
        rows += list(ia.ravel()[ok]); cols += list(ib.ravel()[ok]); w += list(cost[ok])
    G = coo_matrix((w, (rows, cols)), shape=(nx * ny, nx * ny)).tocsr()
    snap = []
    for a in anchors:
        i, j = int(np.clip((a[1] - ys[0]) / st, 0, ny - 1)), int(np.clip((a[0] - xs[0]) / st, 0, nx - 1))
        if not free[i, j]:
            fy, fx = np.nonzero(free)
            k = int(np.argmin((fy - i) ** 2 + (fx - j) ** 2))
            i, j = int(fy[k]), int(fx[k])
        snap.append(int(idx[i, j]))
    snap = list(dict.fromkeys(snap))
    if len(snap) < 2:
        return [], None, len(snap)
    D, pred = dijkstra(G, directed=False, indices=snap, return_predecessors=True)
    M = np.array([[D[a][snap[b]] for b in range(len(snap))] for a in range(len(snap))])
    M[~np.isfinite(M)] = 0
    mst = minimum_spanning_tree(coo_matrix(M)).tocoo()
    lines, mins = [], []
    for a, b in zip(mst.row, mst.col):
        path, cur = [], snap[b]
        while cur != snap[a] and cur >= 0:
            path.append(cur)
            cur = pred[a][cur]
        path.append(snap[a])
        if len(path) < 4:
            continue
        pts = [(xs[p % nx], ys[p // nx]) for p in path[::-1]]
        cl = [clear.ravel()[p] for p in path[::-1]]
        k0 = max(1, int(1.2 / st))                                  # 튜브·코어 바로 앞(앵커 근처)은 여유 측정에서 뺀다
        mins.append(min(cl[k0:-k0]) if len(cl) > 2 * k0 + 1 else min(cl))
        s = LineString(pts).simplify(0.25)
        lines.append(LineString(_chaikin(list(s.coords), 2)))
    return lines, (2.0 * min(mins) if mins else None), len(snap)


def _anchors(P, ctx):
    c = P.region.centroid
    out = []
    for t in ctx.get("tubes", []):
        d = math.hypot(c.x - t["c"].x, c.y - t["c"].y) or 1.0
        out.append((t["c"].x + (c.x - t["c"].x) / d * (t["r"] + 1.6), t["c"].y + (c.y - t["c"].y) / d * (t["r"] + 1.6)))
    core = ctx.get("cores")
    if core is not None and not core.is_empty:
        for g in (core.geoms if hasattr(core, "geoms") else [core]):
            if g.area > 4.0:
                p = g.centroid
                d = math.hypot(c.x - p.x, c.y - p.y) or 1.0
                r = math.sqrt(g.area / math.pi)
                out.append((p.x + (c.x - p.x) / d * (r + 2.0), p.y + (c.y - p.y) / d * (r + 2.0)))
    out = [a for a in out if P.region.buffer(0.2).contains(Point(a))]
    return out or [(c.x, c.y)]


def _add_routes(P, ctx, ops_from=None):
    blocked = unary_union([g for g in (P.hard, P.taken.buffer(0.3) if not P.taken.is_empty else None) if g is not None and not g.is_empty])
    lines, width, n = circulation(P.region, blocked, _anchors(P, ctx))
    for ln in lines:
        P.items.append(Item(ln, "route_v", "visitor_route"))
    ops = None
    if ops_from is not None:                                                        # 운영 동선: 서비스 지점 → 가장 가까운 코어
        cores = ctx.get("cores")
        if cores is not None and not cores.is_empty:
            tgt = cores.centroid
            ol, _, _ = circulation(P.region, blocked, [ops_from, (tgt.x, tgt.y)])
            for ln in ol:
                P.items.append(Item(ln, "route_o", "operations_route"))
            ops = len(ol)
    return {"route_min_clear_width_m": width, "route_segments": len(lines), "anchors": n, "ops_route_segments": ops}


# ── 판매 ─────────────────────────────────────────────────────────────────────────────────────────
def _lounge(P, t, rng, count, ang0):
    """승강기 튜브 앞 대기 라운지: 벤치 링 + 바닥 표시."""
    got = 0
    for i in range(count):
        a = ang0 + 360.0 * i / count
        x, y = t["c"].x + (t["r"] + 1.9) * math.cos(math.radians(a)), t["c"].y + (t["r"] + 1.9) * math.sin(math.radians(a))
        if P.put(R(x, y, 1.8, 0.55, a + 90.0), "body", "waiting_bench", soft=False):
            got += 1
    return got


def _retail(P, rng, floor, ctx):
    variant = "A" if floor in A_FLOORS else "B"
    x0, y0, x1, y1 = P.region.bounds
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    plaza = ctx.get("plaza")
    tubes = ctx.get("tubes", [])
    for g in STRIPS(P.region, P.hard, rng, 0.55 if variant == "A" else 0.7, 1.35, seg=(3.0, 6.5), gap=(1.0, 1.8)):
        if P.put(g, "body", "wall_display", soft=False):
            a, b, c2, d = g.bounds
            P.line(LineString([(a + 0.1, (b + d) / 2), (c2 - 0.1, (b + d) / 2)]) if (c2 - a) > (d - b) else LineString([((a + c2) / 2, b + 0.1), ((a + c2) / 2, d - 0.1)]), "wall_display_line")
    for t in tubes:                                                                  # 승강기 튜브(T3/T4 등) 앞 대기 라운지
        nm = t.get("name", "")
        if any(k in nm for k in ("T3", "T4", "승강", "EV")):
            _lounge(P, t, rng, 4 if variant == "A" else 3, 20.0 + 25.0 * rng.random())
    if plaza is not None and variant == "A":                                          # 빛 튜브 둘레 팝업 링(소형 키오스크)
        pc_ = plaza.centroid
        rad = math.sqrt(plaza.area / math.pi) + 3.4
        for i in range(10):
            a = math.radians(18 + 36 * i)
            x, y = pc_.x + rad * math.cos(a), pc_.y + rad * math.sin(a)
            P.put_all([(R(x, y, 1.2, 1.2, math.degrees(a)), "body", "popup_kiosk"), (_circle(x, y, 0.25), "line", "popup_mark")], soft=True, clear=0.8)
    if variant == "A":
        exp = None                                                                    # 체험존: 8×8 바닥 표시 + 체험 테이블 + 안내 카운터
        for (x, y) in _spots(P.region, 2.0, lambda p: math.hypot(p[0] - (cx + 6 * (1 if floor in ("3F", "5F", "B1") else -1)), p[1] - (cy - 3))):
            z = R(x, y, 8.0, 8.0)
            if P.ok(z, soft=True):
                exp = (x, y, z)
                break
        if exp:
            x, y, z = exp
            P.items.append(Item(z, "zone", "experience_zone")); P._take(z)
            for sx, sy in ((-2.0, -1.5), (2.0, -1.5), (0.0, 1.8)):
                P.items.append(Item(_circle(x + sx, y + sy, 0.55), "body", "demo_table"))
            P.items.append(Item(R(x, y + 3.2, 2.4, 0.6), "counter", "experience_counter"))
        SIZES = [((3.0, 1.2), 4), ((3.6, 1.2), 3), ((2.4, 1.2), 2), ((4.2, 1.4), 2)]
        pys = (3.9, 4.4)
        row, y = 0, y0 + 3.4
        while y < y1 - 2.6:
            x = x0 + 3.4 + (2.6 if row % 2 else 0.0)
            while x < x1 - 3.0:
                (w, h) = _pick(rng, SIZES)
                cw = _pick(rng, [((1.0, 0.5), 3), ((0.6, 0.6), 2)])
                body = R(x + w / 2, y, w, h)
                cnt = R(x + w + cw[0] / 2 + 0.05, y, cw[0], cw[1])
                if (plaza is None or body.distance(plaza) > 2.4) and P.put_all([(body, "body", "brand_cell_%.1fx%.1f" % (w, h)), (cnt, "counter", "cashier_%.1fx%.1f" % cw),
                                                                               (LineString([(x + 0.15, y), (x + w - 0.15, y)]), "line", "display_line")], clear=0.55):
                    pass
                x += w + cw[0] + rng.uniform(1.9, 2.6)
            y += pys[row % 2]
            row += 1
    else:
        for (sx, nm) in ((-1, "street_W"), (1, "street_E")):                          # 팝업 스트리트: 중앙 대로 양쪽에 세로 거리
            cxs = cx + sx * 8.8
            lens = [((3.0, 1.4), 3), ((4.0, 1.4), 3), ((5.0, 1.4), 2)]
            for side in (-1, 1):
                y = y0 + 3.0 + (1.8 if side > 0 else 0.0)
                while y < y1 - 3.0:
                    (L, w) = _pick(rng, lens)
                    xx = cxs + side * (w / 2 + 1.0)
                    body = R(xx, y + L / 2, w, L)
                    cnt = R(xx, y + L + 0.35, 0.8, 0.55)
                    P.put_all([(body, "body", "street_island_%.1f" % L), (cnt, "counter", "cashier_street"),
                               (LineString([(xx, y + 0.2), (xx, y + L - 0.2)]), "line", "display_line")], clear=0.6)
                    y += L + 0.9 + rng.uniform(0.8, 1.6)
        for k in range(7):                                                            # 중앙 대로 팝업 카트(엇갈림)
            y = y0 + 4.5 + k * 7.0
            x = cx + (2.2 if k % 2 else -2.2)
            P.put_all([(R(x, y, 1.2, 1.2), "body", "popup_cart"), (_circle(x, y, 0.3), "line", "popup_mark")], clear=0.8)
        for (x, y) in _spots(P.region, 2.0, lambda p: math.hypot(p[0] - cx, p[1] - (cy + 8 if floor in ("8F", "6F") else cy - 8))):
            z = R(x, y, 10.0, 5.0)
            if P.ok(z, soft=True, clear=0.5):
                P.items.append(Item(z, "zone", "event_popup_plaza")); P._take(z)
                for i in range(3):
                    P.items.append(Item(R(x - 3 + i * 3.0, y, 1.0, 1.0), "body", "event_plinth"))
                break
    return None


# ── F&B ──────────────────────────────────────────────────────────────────────────────────────────
def _chairs(P, cx, cy, offs, size=0.36):
    return [(R(cx + dx, cy + dy, size, size), "body", "chair") for dx, dy in offs]


def _fnb(P, rng, floor, ctx):
    x0, y0, x1, y1 = P.region.bounds
    cx0, cy0 = (x0 + x1) / 2, (y0 + y1) / 2
    for g in STRIPS(P.region, P.hard, rng, 0.7, 1.35, seg=(2.4, 3.6), gap=(0.7, 1.2)):
        if not P.put(g, "body", "banquette", soft=False):
            continue
        a0, b0, a1, b1 = g.bounds
        horizontal = (a1 - a0) > (b1 - b0)
        n = max(1, int(((a1 - a0) if horizontal else (b1 - b0)) // 1.3))
        for i in range(n):
            t = (a0 + 0.65 + i * 1.3) if horizontal else (b0 + 0.65 + i * 1.3)
            cx_, cy_ = (t, b1 + 0.55) if (horizontal and (b0 + b1) / 2 < cy0) else (t, b0 - 0.55) if horizontal else ((a1 + 0.55, t) if (a0 + a1) / 2 < cx0 else (a0 - 0.55, t))
            P.put(R(cx_, cy_, 0.7, 0.7), "body", "table_2top", soft=False)
    svc = None                                                                         # 서비스 카운터 + 줄서기 구역(튜브·코어 가까이)
    base = (ctx.get("tubes") or [None])[0]
    cands = _spots(P.region, 1.5, lambda p: math.hypot(p[0] - (base["c"].x if base else cx0), p[1] - (base["c"].y - (base["r"] + 4.0) if base else cy0)))
    for (x, y) in cands:
        cnt, q = R(x, y, 8.0, 0.8), R(x, y - 2.0, 7.0, 2.2)
        if P.ok(cnt, soft=True) and P.ok(q, soft=True):
            P.items.append(Item(cnt, "counter", "service_counter")); P._take(cnt)
            P.items.append(Item(q, "zone", "queue_zone"))
            svc = (x, y + 1.2)
            break
    bars = 0
    for (x, y) in sorted(((cx0 + dx, cy0 + dy) for dx in range(-16, 17, 4) for dy in range(-16, 17, 4)), key=lambda p: math.hypot(p[0] - cx0, p[1] - cy0)):
        if bars >= 2:
            break
        cnt, zone = R(x, y, 9.0, 0.9), R(x, y, 10.5, 3.6)
        if P.ok(zone, soft=True):
            P.items.append(Item(cnt, "counter", "bar_counter")); P._take(zone)
            for i in range(11):
                P.items.append(Item(RING(x - 4.4 + i * 0.88, y + 0.9, 0.22, 10), "line", "stool"))
            bars += 1
    px, py, row, y = 5.4, 4.2, 0, y0 + 4.0
    TOPS = [("table_4top", 4, 3), ("table_2top_free", 2, 3), ("table_6top", 6, 2)]
    while y < y1 - 3.5:
        x = x0 + 4.0 + (px / 2 if row % 2 else 0.0)
        longrow = (row % 4 == 2)
        while x < x1 - 3.5:
            if longrow:
                L = 6.0
                parts = [(R(x + 2.0, y, L, 1.0), "body", "communal_table")] + _chairs(P, x + 2.0, y, [(-2.6 + i * 1.04, s) for i in range(6) for s in (-0.7, 0.7)])
                P.put_all(parts, clear=0.5)
                x += 8.4
            else:
                kind, seats, wt = _pick(rng, [((k, s), w) for k, s, w in TOPS])
                tw, th = {4: (1.0, 0.8), 2: (0.7, 0.7), 6: (1.6, 0.9)}[seats]
                offs = {4: [(-0.7, 0), (0.7, 0), (0, -0.6), (0, 0.6)], 2: [(-0.55, 0), (0.55, 0)], 6: [(-1.0, 0), (1.0, 0), (-0.4, -0.65), (0.4, -0.65), (-0.4, 0.65), (0.4, 0.65)]}[seats]
                P.put_all([(R(x, y, tw, th), "body", kind)] + _chairs(P, x, y, offs), clear=0.5)
                x += px
        y += py
        row += 1
    return svc


# ── 문화·엔터 ────────────────────────────────────────────────────────────────────────────────────
def _culture(P, rng, floor, ctx):
    x0, y0, x1, y1 = P.region.bounds
    cx0, cy0 = (x0 + x1) / 2, (y0 + y1) / 2
    stage = None
    for (x, y) in sorted(((cx0 + dx, cy0 + dy) for dx in range(-20, 21) for dy in range(-20, 21)), key=lambda p: math.hypot(p[0] - cx0, p[1] - cy0)):
        for (w, h) in ((7.5, 4.0), (4.0, 7.5)):
            g = R(x, y, w, h)
            zone = R(x, y - (3.2 if w > h else 0.0), w + 2.4, h + 8.0) if w > h else R(x - 3.2, y, w + 8.0, h + 2.4)     # 무대 + 서는 구역 + 여유
            if P.ok(zone, soft=False):
                stage = (x, y, w, h, g, zone)
                break
        if stage:
            break
    if stage:
        x, y, w, h, g, zone = stage
        P.items.append(Item(g, "body", "stage")); P._take(zone)
        wide = w > h
        for i in range(1, 4):
            P.line(LineString([(x - w / 2, y - h / 2 - i * 0.3), (x + w / 2, y - h / 2 - i * 0.3)]) if wide else LineString([(x - w / 2 - i * 0.3, y - h / 2), (x - w / 2 - i * 0.3, y + h / 2)]), "stage_step")
        P.items.append(Item(R(x, y + h / 2 - 0.35, w - 0.8, 0.22) if wide else R(x + w / 2 - 0.35, y, 0.22, h - 0.8), "body", "media_wall"))
        sz = R(x, y - h / 2 - 2.6, w + 2.0, 4.6) if wide else R(x - w / 2 - 2.6, y, 4.6, h + 2.0)
        P.items.append(Item(sz, "zone", "standing_zone"))
        for i in range(-2, 3):
            pt = (x + i * 1.5, y - h / 2 - 1.9) if wide else (x - w / 2 - 1.9, y + i * 1.5)
            P.line(RING(pt[0], pt[1], 0.32, 12), "standing_mark")
    for side in ("N", "S", "E", "W"):                                                  # 집합 계단
        hz = side in ("S", "N")
        base = (y1 - 4.6) if side == "N" else (y0 + 4.6) if side == "S" else (x1 - 4.6) if side == "E" else (x0 + 4.6)
        sgn = -1 if side in ("N", "E") else 1
        c = cx0 if hz else cy0
        steps = [R(c, base + sgn * i * 0.9, 12.0, 0.9) if hz else R(base + sgn * i * 0.9, c, 0.9, 12.0) for i in range(3)]
        if all(P.ok(s, soft=False) for s in steps):
            for s in steps:
                P.put(s, "body", "assembly_step", soft=False)
            break
    gal = None                                                                         # 전시 구역: 패널 격자 + 바닥 표시
    for (x, y) in sorted(((x, y) for x in range(int(x0) + 6, int(x1) - 6, 3) for y in range(int(y0) + 6, int(y1) - 6, 3)), key=lambda p: -math.hypot(p[0] - cx0, p[1] - cy0)):
        z = R(x, y, 15.0, 10.0)
        if P.ok(z, soft=True):
            gal = (x, y, z)
            break
    if gal:
        x, y, z = gal
        P.items.append(Item(z, "zone", "exhibition_zone")); P._take(z)
        for i in range(3):
            for j in range(2):
                P.items.append(Item(R(x - 5.0 + i * 5.0, y - 2.5 + j * 5.0, 3.0, 0.15) if (i + j) % 2 == 0 else R(x - 5.0 + i * 5.0, y - 2.5 + j * 5.0, 0.15, 3.0), "body", "gallery_panel"))
    best = None
    for side in ("S", "N", "W", "E"):
        hz = side in ("S", "N")
        pos = (y0 + 2.6) if side == "S" else (y1 - 2.6) if side == "N" else (x0 + 2.6) if side == "W" else (x1 - 2.6)
        pl = []
        for i in range(9):
            t = ((x0 + 5 + i * 4.2) if hz else (y0 + 5 + i * 4.2))
            g = R(t, pos, 1.6, 1.6) if hz else R(pos, t, 1.6, 1.6)
            if P.ok(g, soft=False, clear=0.3):
                pl.append(g)
        if best is None or len(pl) > len(best):
            best = pl
    for g in (best or []):
        P.put(g, "body", "plinth", soft=False, clear=0.3)
        P.line(RING(g.centroid.x, g.centroid.y, 0.45, 12), "plinth_mark")
    pods = 0
    for (x, y) in sorted(((x, y) for x in range(int(x0) + 4, int(x1) - 3, 3) for y in range(int(y0) + 4, int(y1) - 3, 3)), key=lambda p: min(p[0] - x0, x1 - p[0], p[1] - y0, y1 - p[1])):
        if pods >= 12:
            break
        zone = R(x, y, 5.6, 4.2)
        if P.ok(zone, soft=True):
            P.items.append(Item(R(x, y - 1.1, 2.4, 0.9), "body", "lounge_sofa"))
            P.items.append(Item(R(x, y + 1.1, 2.4, 0.9, 180), "body", "lounge_sofa"))
            P.items.append(Item(R(x, y, 1.2, 0.7), "body", "lounge_table"))
            P.line(RING(x + 2.2, y, 0.4, 12), "planter")
            P._take(zone)
            pods += 1
    info = None
    for (x, y) in _spots(P.region, 1.5, lambda p: math.hypot(p[0] - cx0, p[1] - y0)):
        c = R(x, y, 3.0, 0.7)
        if P.ok(c.buffer(0.5), soft=True):
            P.items.append(Item(c, "counter", "info_desk")); P._take(c)
            info = (x, y)
            break
    return info


# ── 정원·테라스 ──────────────────────────────────────────────────────────────────────────────────
def _blob(x, y, rx, ry, ang):
    return affinity.rotate(affinity.scale(Point(x, y).buffer(1.0, 16), rx, ry), ang, origin=(x, y))


def _garden(P, rng, floor, ctx):
    x0, y0, x1, y1 = P.region.bounds
    path = None                                                                        # 산책로: 구역 안쪽 4.5 m 둘레의 둥근 고리(폭 2.4)
    inner = P.region.buffer(-4.5, join_style=1)
    if not inner.is_empty:
        ring = max(inner.geoms, key=lambda g: g.area) if hasattr(inner, "geoms") else inner
        path = LineString(list(ring.exterior.coords)).simplify(0.4)
        band = path.buffer(1.2, cap_style=2)
        for edge in (path.parallel_offset(1.2, "left", join_style=1), path.parallel_offset(1.2, "right", join_style=1)):
            ed = edge.difference(P.hard.buffer(0.1)) if P.hard is not None and not P.hard.is_empty else edge
            if not ed.is_empty:
                P.items.append(Item(ed, "line", "promenade_edge"))
        P._take(band.difference(P.hard)) if P.hard is not None and not P.hard.is_empty else P._take(band)
        L, s = path.length, 0.0
        while s < L:                                                                    # 벤치: 산책로를 따라 약 8 m마다
            p, q = path.interpolate(s), path.interpolate(min(L, s + 0.5))
            ang = math.degrees(math.atan2(q.y - p.y, q.x - p.x))
            nrm = math.radians(ang + 90)
            P.put(R(p.x + 1.9 * math.cos(nrm), p.y + 1.9 * math.sin(nrm), 1.6, 0.5, ang), "body", "garden_bench", soft=False)
            s += 8.0 + rng.uniform(-1.0, 2.0)
    tries = 0
    beds = 0
    while beds < 16 and tries < 600:
        tries += 1
        x, y = rng.uniform(x0 + 2, x1 - 2), rng.uniform(y0 + 2, y1 - 2)
        b = _blob(x, y, rng.uniform(1.3, 2.6), rng.uniform(0.8, 1.6), rng.uniform(0, 180))
        if P.put(b, "body", "planting_bed", soft=True, clear=1.0):
            for _ in range(int(b.area // 1.4)):
                px, py = b.centroid.x + rng.uniform(-1, 1) * (b.bounds[2] - b.bounds[0]) / 2.6, b.centroid.y + rng.uniform(-1, 1) * (b.bounds[3] - b.bounds[1]) / 2.6
                if b.buffer(-0.2).contains(Point(px, py)):
                    P.items.append(Item(RING(px, py, rng.uniform(0.25, 0.45), 12), "foliage", "shrub"))
            beds += 1
    trees = 0
    tries = 0
    while trees < 9 and tries < 400:
        tries += 1
        x, y = rng.uniform(x0 + 2, x1 - 2), rng.uniform(y0 + 2, y1 - 2)
        g = _circle(x, y, 1.5)
        if P.put(g, "body", "tree_canopy", soft=True, clear=0.8):
            P.items.append(Item(RING(x, y, 1.4, 18), "foliage", "tree"))
            P.items.append(Item(RING(x, y, 0.9, 14), "foliage", "tree"))
    for (x, y) in _spots(P.region, 2.0, lambda p: math.hypot(p[0] - x1 + 12, p[1] - y0 - 10)):   # 테라스: 식탁 세트 구역
        z = R(x, y, 10.0, 7.0)
        if P.ok(z, soft=True, clear=0.8):
            P.items.append(Item(z, "zone", "terrace_zone")); P._take(z)
            for i in range(2):
                for j in range(2):
                    tx, ty = x - 2.6 + i * 5.2, y - 1.6 + j * 3.2
                    P.items.append(Item(_circle(tx, ty, 0.5), "body", "terrace_table"))
                    for k in range(4):
                        a = math.radians(90 * k + 45)
                        P.items.append(Item(_circle(tx + 1.0 * math.cos(a), ty + 1.0 * math.sin(a), 0.25, 8), "body", "terrace_chair"))
            break
    return None


# ── 진입점 ───────────────────────────────────────────────────────────────────────────────────────
def layout(name, region, obst, hard, rng, floor, ctx):
    n = name or ""
    P = Packer(region, obst, hard)
    if "F&B" in n:
        svc = _fnb(P, rng, floor, ctx)
        kind = "fnb"
    elif "문화" in n or "엔터" in n:
        svc = _culture(P, rng, floor, ctx)
        kind = "culture"
    elif "garden" in n.lower() or "정원" in n:
        svc = _garden(P, rng, floor, ctx)
        kind = "garden"
    elif "판매" in n or "시장" in n or "상업" in n:
        _retail(P, rng, floor, ctx)
        svc, kind = None, "retail_" + ("A" if floor in A_FLOORS else "B")
    else:
        return Items()
    meta = _add_routes(P, ctx, ops_from=svc) if kind != "garden" else {"route_min_clear_width_m": None, "route_segments": 0, "anchors": 0, "ops_route_segments": None}
    types = {}
    for it in P.items:
        if it[1] in ("body", "counter"):
            types[it.ftype] = types.get(it.ftype, 0) + 1
    out = Items(P.items)
    out.meta = dict(meta, program=kind, floor=floor, types=types)
    return out

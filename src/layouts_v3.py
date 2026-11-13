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

C-T14I 확장(슬래브 인식 모드, SLAB_AWARE_FLOORS): V3가 도면집에 실은 다섯 층(3F·8F·10F·13F·15F)은 구역 폴리곤만 보고 배치했다. 층판이 직사각형이 아닌 층(2F L자판, 7F 후퇴)과
층판에 큰 개구가 있는 층(11F·12F 중앙 개구, 에스컬레이터 개구)은 구역 폴리곤이 개구·판 밖까지 덮으므로 가구가 허공에 놓인다. 슬래브 인식 모드는 모델 slice의 층판 투영(개구 포함)을 읽어
(1) 구역을 층판 안쪽 0.5 m로 자르고 (2) 층판이 이어지고 구조물이 없는 구역 구멍(층에 없는 튜브 자리)을 메우고 (3) 윤곽을 따라 띠를 놓고 (4) 가구가 들어갈 자리가 없으면 비운다.
이 모드는 SLAB_AWARE_FLOORS에 든 층에서, configure()로 slice 폴더를 알려 주었거나 환경 변수 T14I_RAW_SLICES가 있을 때만 켜진다. 그 밖의 층(V3 다섯 층 포함)의 출력은 이전과 같다.
"""
import json
import math
import os

import numpy as np
import shapely
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra, minimum_spanning_tree
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import nearest_points, unary_union

import pipeline_common as pc
import upper_layouts as V2

R, RING, STRIPS = V2._rect, V2._ring, V2._perimeter_strips
A_FLOORS = {"2F", "3F", "4F", "5F", "B1", "B2"}

# ── 슬래브 인식 모드 설정 ─────────────────────────────────────────────────────────────────────────
SLAB_AWARE_FLOORS = frozenset({"B2", "B1", "2F", "4F", "5F", "6F", "7F", "11F", "12F"})
SLAB_EDGE_MARGIN = 0.5        # 층판 가장자리·개구 둘레에서 가구가 물러나는 거리(m)
MIN_FREE_M2 = 30.0            # 구조물을 뺀 가구 가능 면적이 이보다 작으면 그 구역은 비운다
_SLICE_DIR = os.environ.get("T14I_RAW_SLICES") or None
_SLAB_CACHE = {}


def configure(raw_slices_dir=None):
    """슬래브 인식 모드에 쓸 raw_slices 폴더를 정한다(None이면 모드를 끈다)."""
    global _SLICE_DIR
    _SLICE_DIR = raw_slices_dir
    _SLAB_CACHE.clear()


def slab_of(floor):
    """층판 투영(개구 포함 도형). 슬래브 인식 층이 아니거나 slice 폴더가 없으면 None."""
    if floor not in SLAB_AWARE_FLOORS or not _SLICE_DIR:
        return None
    key = (floor, _SLICE_DIR)
    if key not in _SLAB_CACHE:
        sl = pc.load_slice(_SLICE_DIR, floor)
        parts = [pc.polygons_from_segments(p["segments"]) for p in sl["projection"]]
        _SLAB_CACHE[key] = unary_union([g for g in parts if not g.is_empty]) if parts else None
    return _SLAB_CACHE[key]


def _polys(g):
    return [] if g is None or g.is_empty else list(pc.iter_polygons(g))


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
        self.items, self.taken, self.solid = [], Polygon(), Polygon()
        self.aware = False                                                           # 슬래브 인식 모드(layout()이 켠다)
        self.atrium = False                                                          # 층판 중앙에 큰 개구(아트리움)가 있다

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

    def _take(self, g, solid=False):
        self.taken = unary_union([self.taken, g]) if not self.taken.is_empty else g
        if solid:
            self.solid = unary_union([self.solid, g]) if not self.solid.is_empty else g

    def zone(self, g, ftype):
        """바닥 표시 구역: 다른 가구가 피하지만 걸어 다닐 수 있다(동선 계산에서 막지 않는다)."""
        self.items.append(Item(g, "zone", ftype))
        self._take(g)

    def put(self, g, kind, ftype, soft=True, clear=0.0):
        if not self.ok(g, soft, clear):
            return False
        self.items.append(Item(g, kind, ftype))
        if kind in ("body", "counter", "zone"):
            self._take(g, solid=kind != "zone")
        return True

    def put_all(self, parts, soft=True, clear=0.0):
        """parts: [(geom, kind, ftype)]. 몸체·계산대가 모두 들어가면 한꺼번에 놓는다(서로는 겹쳐도 됨)."""
        body = [p for p in parts if p[1] in ("body", "counter")]
        if not all(self.ok(g, soft, clear) for g, _, _ in body):
            return False
        for g, k, t in parts:
            self.items.append(Item(g, k, t))
            if k in ("body", "counter"):
                self._take(g, solid=True)
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


def circulation(region, blocked, anchors, step=0.45, hub=None, end_trim=3.0):
    """hub가 있으면 hub에서 각 앵커로 가는 방사형 경로, 없으면 앵커를 잇는 최소 신장 경로(여유가 큰 칸을 선호). 앵커 끝 end_trim m는 폭 측정에서 뺀다. 반환: ([LineString], 경로 최소 여유 폭 m, 연결된 앵커 수)."""
    xs, ys, free, clear, st = _grid(region, blocked, step)
    if not free.any():                                                              # 구조물에 막혀 빈 칸이 없는 구역(예: 코어 안에 걸친 작은 구역): 경로 없음
        return [], None, 0
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
        cost = math.hypot(dx, dy) * st * (1.0 + 5.0 / (1.0 + mid))
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
    if hub is not None:
        hi, hj = int(np.clip((hub[1] - ys[0]) / st, 0, ny - 1)), int(np.clip((hub[0] - xs[0]) / st, 0, nx - 1))
        if not free[hi, hj]:
            fy, fx = np.nonzero(free)
            kk = int(np.argmin((fy - hi) ** 2 + (fx - hj) ** 2))
            hi, hj = int(fy[kk]), int(fx[kk])
        hid = int(idx[hi, hj])
        D, pred = dijkstra(G, directed=False, indices=[hid], return_predecessors=True)
        pairs = [(0, snap[b_]) for b_ in range(len(snap)) if snap[b_] != hid and np.isfinite(D[0][snap[b_]])]
        base = hid
    else:
        D, pred = dijkstra(G, directed=False, indices=snap, return_predecessors=True)
        M = np.array([[D[a_][snap[b_]] for b_ in range(len(snap))] for a_ in range(len(snap))])
        M[~np.isfinite(M)] = 0
        mst = minimum_spanning_tree(coo_matrix(M)).tocoo()
        pairs = [(int(a_), snap[int(b_)]) for a_, b_ in zip(mst.row, mst.col)]
        base = None
    lines, mins = [], []
    for a_, tgt in pairs:
        start = base if base is not None else snap[a_]
        path, cur = [], tgt
        while cur != start and cur >= 0:
            path.append(cur)
            cur = pred[a_][cur]
        path.append(start)
        if len(path) < 4:
            continue
        pts = [(xs[q % nx], ys[q // nx]) for q in path[::-1]]
        cl = [clear.ravel()[q] for q in path[::-1]]
        k0 = max(1, int(end_trim / st))                             # 튜브·코어 바로 앞(앵커 근처)은 여유 측정에서 뺀다
        mins.append(min(cl[k0:-k0]) if len(cl) > 2 * k0 + 1 else min(cl))
        sl_ = LineString(pts).simplify(0.4)
        lines.append(LineString(_chaikin(list(sl_.coords), 2)))
    return lines, (2.0 * min(mins) if mins else None), len(snap)


def _dissolve(lines):
    """방사형 경로는 줄기 구간을 함께 쓴다. 같은 구간을 여러 번 그리지 않도록 겹침을 합친다(Q60: 동일 선분 중복)."""
    if not lines:
        return []
    from shapely.ops import linemerge
    u = unary_union(lines)
    if hasattr(u, "geoms"):
        u = linemerge(u)
    return [g for g in (u.geoms if hasattr(u, "geoms") else [u]) if g.geom_type == "LineString" and g.length > 0.2]


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
    if P.aware:                                                                      # 구역이 고리·여러 조각일 수 있다: 구역에서 3 m 안에 있는 튜브·코어 앵커만 쓴다(빈 칸 스냅은 circulation이 한다)
        out = [a for a in out if P.region.distance(Point(a)) <= 3.0]
        return out or [tuple(P.region.representative_point().coords[0])]
    out = [a for a in out if P.region.buffer(0.2).contains(Point(a))]
    return out or [(c.x, c.y)]


def _add_routes(P, ctx, ops_from=None, perimeter_ops=False):
    blocked = unary_union([g for g in (P.hard, P.solid.buffer(0.3) if not P.solid.is_empty else None) if g is not None and not g.is_empty])
    c0 = P.region.centroid
    if P.aware and not P.region.contains(c0):                                         # 고리 모양 구역(12F): 중심이 개구에 있으면 허브 없이 앵커끼리 최소 신장 경로
        lines, width, n = circulation(P.region, blocked, _anchors(P, ctx), hub=None)
    else:
        lines, width, n = circulation(P.region, blocked, _anchors(P, ctx), hub=(c0.x, c0.y))
    lines = _dissolve(lines)
    for ln in lines:
        P.items.append(Item(ln, "route_v", "visitor_route"))
    ops = None
    if ops_from is not None:                                                        # 운영 동선: 서비스 지점 → 가장 가까운 코어
        cores = ctx.get("cores")
        if cores is not None and not cores.is_empty:
            tgt = cores.centroid
            ol, _, _ = circulation(P.region, blocked, [ops_from, (tgt.x, tgt.y)])
            ol = _dissolve(ol)
            for ln in ol:
                P.items.append(Item(ln, "route_o", "operations_route"))
            ops = len(ol)
    if perimeter_ops:                                                              # 운영 동선(제안): 외벽과 벽 진열 사이의 서비스 레인
        if P.aware:                                                                # 슬래브 인식: 바깥 윤곽만 따른다(층에 없는 튜브·개구 둘레로 돌지 않는다)
            lane = unary_union([LineString(list(p.exterior.coords)) for p in _polys(P.region.buffer(-0.75))]).difference(unary_union([blocked, P.solid.buffer(0.15)]))
        else:
            lane = P.region.buffer(-0.75).boundary.difference(unary_union([blocked, P.solid.buffer(0.15)]))
        parts = [g for g in (lane.geoms if hasattr(lane, "geoms") else [lane]) if g.geom_type == "LineString" and g.length > 4.0]
        for g in parts:
            P.items.append(Item(g, "route_o", "operations_route"))
        ops = len(parts)
    return {"route_min_clear_width_m": width, "route_segments": len(lines), "anchors": n, "ops_route_segments": ops}


# ── 판매 ─────────────────────────────────────────────────────────────────────────────────────────
def _edge_strips(region, hard, rng, depth, offset, seg=(3.0, 6.0), gap=(0.9, 1.6), min_edge=2.5):
    """슬래브 인식 모드의 외벽 띠: 구역 바깥 윤곽의 곧은 변을 따라 끊어진 띠(외벽 진열·뱅킷)를 놓는다. 2F L자판·7F 후퇴의 꺾인 변도 따라간다.
    변의 안쪽 법선 방향으로 offset + depth/2 만큼 들인다(V2 _perimeter_strips는 경계 상자의 네 변만 쓴다). 반환: [(띠 도형, 안쪽 단위 법선)]."""
    out = []
    for poly in _polys(region):
        if poly.area < 20.0:
            continue
        ring = poly.exterior
        if not ring.is_ccw:
            ring = LineString(list(ring.coords)[::-1])
        pts = list(ring.simplify(0.25).coords)
        for a, b in zip(pts, pts[1:]):
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            if L < min_edge:
                continue
            ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
            nx, ny = -uy, ux                                                        # 반시계 방향 윤곽에서 왼쪽 = 안쪽
            ang = math.degrees(math.atan2(uy, ux))
            t = 1.0
            while t < L - 1.0:
                sl = rng.uniform(*seg)
                if t + sl > L - 1.0:
                    sl = L - 1.0 - t
                if sl < 1.2:
                    break
                c = t + sl / 2
                d = offset + depth / 2
                g = R(a[0] + ux * c + nx * d, a[1] + uy * c + ny * d, sl, depth, ang)
                if V2._free(region, None, g, hard):
                    out.append((g, (nx, ny)))
                t += sl + rng.uniform(*gap)
    return out


def _retail_band(P, rng, floor, ctx):
    """슬래브 인식 모드의 판매 B: 구역이 가로로 긴 띠(6F·7F 북쪽 판매 구역)이면 거리와 섬을 가로로 눕힌다. 가운데 대로(팝업 카트) 양쪽에 거리 둘, 한쪽 끝에 이벤트 광장."""
    x0, y0, x1, y1 = P.region.bounds
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hd = (y1 - y0) / 2
    soff = max(3.8, 0.5 * hd)                                                        # 대로 중심선에서 거리까지(띠 반폭의 절반)
    lens = [((3.0, 1.4), 3), ((4.0, 1.4), 3), ((5.0, 1.4), 2)]
    for sy in (-1, 1):
        cys = cy + sy * soff
        for side in (-1, 1):
            x = x0 + 3.0 + (1.8 if side > 0 else 0.0)
            while x < x1 - 3.0:
                (L, w) = _pick(rng, lens)
                yy = cys + side * (w / 2 + 1.0)
                body = R(x + L / 2, yy, L, w)
                cnt = R(x + L + 0.35, yy, 0.55, 0.8)
                P.put_all([(body, "body", "street_island_%.1f" % L), (cnt, "counter", "cashier_street"),
                           (LineString([(x + 0.2, yy), (x + L - 0.2, yy)]), "line", "display_line")], clear=0.6)
                x += L + 0.9 + rng.uniform(0.8, 1.6)
    for k in range(9):                                                               # 가운데 대로 팝업 카트(엇갈림)
        x = x0 + 4.5 + k * 6.0
        y = cy + (1.4 if k % 2 else -1.4)
        P.put_all([(R(x, y, 1.2, 1.2), "body", "popup_cart"), (_circle(x, y, 0.3), "line", "popup_mark")], clear=0.8)
    for (x, y) in _spots(P.region, 2.0, lambda p: math.hypot(p[0] - (x1 - 10.0), p[1] - cy)):   # 이벤트 광장: 동쪽 끝 쪽에서 10 × 5 m가 비는 곳
        z = R(x, y, 10.0, 5.0)
        if P.ok(z, soft=True, clear=0.5):
            P.zone(z, "event_popup_plaza")
            for i in range(3):
                P.items.append(Item(R(x - 3 + i * 3.0, y, 1.0, 1.0), "body", "event_plinth"))
            break


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
    for g in ([q[0] for q in _edge_strips(P.region, P.hard, rng, 0.55 if variant == "A" else 0.7, 1.35, seg=(3.0, 6.5), gap=(1.0, 1.8))] if P.aware
              else STRIPS(P.region, P.hard, rng, 0.55 if variant == "A" else 0.7, 1.35, seg=(3.0, 6.5), gap=(1.0, 1.8))):
        if P.put(g, "body", "wall_display", soft=False):
            a, b, c2, d = g.bounds
            if P.aware:                                                              # 기울어진 띠: 진열선을 띠의 긴 축 가운데에 그린다
                mr = list(g.minimum_rotated_rectangle.exterior.coords)[:4]
                mid = lambda p, q: ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
                if math.hypot(mr[1][0] - mr[0][0], mr[1][1] - mr[0][1]) >= math.hypot(mr[2][0] - mr[1][0], mr[2][1] - mr[1][1]):
                    m0, m1 = mid(mr[3], mr[0]), mid(mr[1], mr[2])                      # 긴 변 e0–e1: 짧은 변 e3–e0, e1–e2의 가운데끼리
                else:
                    m0, m1 = mid(mr[0], mr[1]), mid(mr[2], mr[3])
                u = (m1[0] - m0[0], m1[1] - m0[1])
                uL = math.hypot(*u) or 1.0
                P.line(LineString([(m0[0] + u[0] / uL * 0.1, m0[1] + u[1] / uL * 0.1), (m1[0] - u[0] / uL * 0.1, m1[1] - u[1] / uL * 0.1)]), "wall_display_line")
            else:
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
            P.zone(z, "experience_zone")
            for sx, sy in ((-2.0, -1.5), (2.0, -1.5), (0.0, 1.8)):
                P.items.append(Item(_circle(x + sx, y + sy, 0.55), "body", "demo_table"))
            P.items.append(Item(R(x, y + 3.2, 2.4, 0.6), "counter", "experience_counter"))
        SIZES = [((3.0, 1.2), 4), ((3.6, 1.2), 3), ((2.4, 1.2), 2), ((4.2, 1.4), 2)]
        pys = (3.6, 3.9)
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
                x += w + cw[0] + rng.uniform(1.1, 1.7)
            y += pys[row % 2]
            row += 1
    elif P.aware and (x1 - x0) > 1.4 * (y1 - y0):                                     # 가로로 긴 띠 구역(6F·7F 북쪽): 거리와 섬을 가로로 눕힌다
        _retail_band(P, rng, floor, ctx)
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
                P.zone(z, "event_popup_plaza")
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
    strip_list = _edge_strips(P.region, P.hard, rng, 0.7, 1.35, seg=(2.4, 3.6), gap=(0.7, 1.2)) if P.aware         else [(g_, None) for g_ in STRIPS(P.region, P.hard, rng, 0.7, 1.35, seg=(2.4, 3.6), gap=(0.7, 1.2))]
    for g, nrm in strip_list:
        if not P.put(g, "body", "banquette", soft=False):
            continue
        if nrm is not None:                                                          # 슬래브 인식: 윤곽을 따라 기울어진 띠의 안쪽 법선 방향으로 2인 식탁을 놓는다
            mr = list(g.minimum_rotated_rectangle.exterior.coords)[:4]
            e0, e1, e2 = mr[0], mr[1], mr[2]
            (pa, pb) = (e0, e1) if math.hypot(e1[0] - e0[0], e1[1] - e0[1]) >= math.hypot(e2[0] - e1[0], e2[1] - e1[1]) else (e1, e2)
            Ls = math.hypot(pb[0] - pa[0], pb[1] - pa[1]) or 1.0
            ux, uy = (pb[0] - pa[0]) / Ls, (pb[1] - pa[1]) / Ls
            if ux * -nrm[1] + uy * nrm[0] < 0:                                       # 띠 축 방향을 법선의 왼쪽(반시계)으로 맞춘다(식탁 순서만 영향)
                ux, uy = -ux, -uy
            gc = g.centroid
            ang = math.degrees(math.atan2(uy, ux))
            for i in range(max(1, int(Ls // 1.3))):
                t = 0.65 + i * 1.3 - Ls / 2
                dims_ = _pick(rng, [((0.7, 0.7), 3), ((0.9, 0.6), 2), ((0.6, 0.9), 2)])
                nm_ = "table_2top_%dx%d" % (round(dims_[0] * 10), round(dims_[1] * 10))
                dpt = 0.35 + 0.55
                P.put(R(gc.x + ux * t + nrm[0] * dpt, gc.y + uy * t + nrm[1] * dpt, dims_[0], dims_[1], ang), "body", nm_, soft=False)
            continue
        a0, b0, a1, b1 = g.bounds
        horizontal = (a1 - a0) > (b1 - b0)
        n = max(1, int(((a1 - a0) if horizontal else (b1 - b0)) // 1.3))
        for i in range(n):
            t = (a0 + 0.65 + i * 1.3) if horizontal else (b0 + 0.65 + i * 1.3)
            cx_, cy_ = (t, b1 + 0.55) if (horizontal and (b0 + b1) / 2 < cy0) else (t, b0 - 0.55) if horizontal else ((a1 + 0.55, t) if (a0 + a1) / 2 < cx0 else (a0 - 0.55, t))
            dims_, nm_ = _pick(rng, [((0.7, 0.7), 3), ((0.9, 0.6), 2), ((0.6, 0.9), 2)]), None
            nm_ = "table_2top_%dx%d" % (round(dims_[0] * 10), round(dims_[1] * 10))
            P.put(R(cx_, cy_, dims_[0], dims_[1]), "body", nm_, soft=False)
    svc = None                                                                         # 서비스 카운터 + 줄서기 구역(튜브·코어 가까이)
    base = (ctx.get("tubes") or [None])[0]
    cands = _spots(P.region, 1.5, lambda p: math.hypot(p[0] - (base["c"].x if base else cx0), p[1] - (base["c"].y - (base["r"] + 4.0) if base else cy0)))
    for (x, y) in cands:
        cnt, q = R(x, y, 8.0, 0.8), R(x, y - 2.0, 7.0, 2.2)
        if P.ok(cnt, soft=True) and P.ok(q, soft=True):
            P.items.append(Item(cnt, "counter", "service_counter")); P._take(cnt, solid=True)
            P.zone(q, "queue_zone")
            svc = (x, y + 1.2)
            break
    bars = 0
    for (x, y) in sorted(((cx0 + dx, cy0 + dy) for dx in range(-16, 17, 4) for dy in range(-16, 17, 4)), key=lambda p: math.hypot(p[0] - cx0, p[1] - cy0)):
        if bars >= 2:
            break
        cnt, zone = R(x, y, 9.0, 0.9), R(x, y, 10.5, 3.6)
        if P.ok(zone, soft=True):
            P.items.append(Item(cnt, "counter", "bar_counter")); P._take(zone); P._take(cnt, solid=True)
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
                kind, seats = _pick(rng, [((k, s), w) for k, s, w in TOPS])
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
    for (x, y) in ([] if P.atrium else sorted(((cx0 + dx, cy0 + dy) for dx in range(-20, 21) for dy in range(-20, 21)), key=lambda p: math.hypot(p[0] - cx0, p[1] - cy0))):   # 아트리움을 두른 층(12F)은 무대를 개구 아래층에 둔다
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
        P.items.append(Item(g, "body", "stage")); P._take(zone); P._take(g, solid=True)
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
        P.zone(z, "exhibition_zone")
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
            if pods % 3 == 0:                                                         # 포드 A: 마주 보는 소파 2 + 낮은 테이블
                P.items.append(Item(R(x, y - 1.1, 2.4, 0.9), "body", "lounge_sofa"))
                P.items.append(Item(R(x, y + 1.1, 2.4, 0.9, 180), "body", "lounge_sofa"))
                P.items.append(Item(R(x, y, 1.2, 0.7), "body", "lounge_table"))
            elif pods % 3 == 1:                                                       # 포드 B: 1인 의자 3 + 원형 테이블
                P.items.append(Item(_circle(x, y, 0.45), "body", "lounge_round_table"))
                for a_ in (90, 210, 330):
                    P.items.append(Item(R(x + 1.2 * math.cos(math.radians(a_)), y + 1.2 * math.sin(math.radians(a_)), 0.9, 0.9, a_ - 90), "body", "lounge_armchair"))
            else:                                                                      # 포드 C: 긴 벤치 + 낮은 테이블 2
                P.items.append(Item(R(x, y - 1.3, 3.6, 0.6), "body", "lounge_bench"))
                P.items.append(Item(R(x - 0.8, y + 0.3, 0.9, 0.7), "body", "lounge_table_small"))
                P.items.append(Item(R(x + 0.8, y + 0.3, 0.9, 0.7), "body", "lounge_table_small"))
            P._take(R(x, y, 2.4, 2.9), solid=True)
            P.line(RING(x + 2.2, y, 0.4, 12), "planter")
            P._take(zone)
            pods += 1
    info = None
    for (x, y) in _spots(P.region, 1.5, lambda p: math.hypot(p[0] - cx0, p[1] - y0)):
        c = R(x, y, 3.0, 0.7)
        if P.ok(c.buffer(0.5), soft=True):
            P.items.append(Item(c, "counter", "info_desk")); P._take(c, solid=True)
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
            P.zone(z, "terrace_zone")
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
def _program_of(n, floor):
    """구역 이름 → 배치 전략(이름 판정 순서는 V3와 같다). 모르는 이름은 None."""
    if "F&B" in n:
        return "fnb"
    if "문화" in n or "엔터" in n:
        return "culture"
    if "garden" in n.lower() or "정원" in n:
        return "garden"
    if "판매" in n or "시장" in n or "상업" in n:
        return "retail_" + ("A" if floor in A_FLOORS else "B")
    return None


def _slab_region(region, slab, hard):
    """슬래브 인식 모드: 구역 → 가구가 놓일 수 있는 영역. 반환 (영역 또는 None, 정보 dict).
    1) 구역 구멍 중 층판이 이어지고(구멍의 95 % 이상이 층판 위) 구조물이 거의 없는(15 % 미만) 것은 메운다 — 층에 없는 튜브 자리(B2의 T1~T4·PL)
    2) 층판(개구 포함) 안쪽 SLAB_EDGE_MARGIN으로 자른다 — 판 밖(2F L자 파임·7F 후퇴)·개구(에스컬레이터·아트리움) 위에는 놓지 않는다
    3) 구조물을 뺀 면적이 MIN_FREE_M2보다 작으면 None(그 구역은 비운다)."""
    info = {"slab_aware": True, "zone_region_m2": round(region.area, 1), "phantom_holes_filled": 0}
    parts = []
    for p in _polys(region):
        keep = []
        for h in p.interiors:
            H = Polygon(h)
            on_slab = H.difference(slab).area <= 0.05 * H.area
            bare = hard is None or hard.is_empty or hard.intersection(H).area <= 0.15 * H.area
            if on_slab and bare:
                info["phantom_holes_filled"] += 1
            else:
                keep.append(h)
        parts.append(Polygon(p.exterior, keep))
    reg = unary_union(parts) if parts else Polygon()
    out = reg.intersection(slab.buffer(-SLAB_EDGE_MARGIN))
    pieces = [q for q in _polys(out) if q.area > 4.0]
    out = unary_union(pieces) if pieces else Polygon()
    free = out.difference(hard) if (hard is not None and not hard.is_empty) else out
    info.update({"region_after_clip_m2": round(out.area, 1), "removed_by_slab_clip_m2": round(reg.area - out.area, 1), "free_m2": round(free.area, 1)})
    info["atrium_void"] = any(Polygon(h).area >= 200.0 and (hard is None or hard.is_empty or hard.intersection(Polygon(h)).area <= 0.15 * Polygon(h).area)
                              for q in _polys(slab) for h in q.interiors)
    if out.is_empty or free.area < MIN_FREE_M2:
        info["skip_reason"] = "구역이 층판 개구 위이거나 구조물에 막혀 가구 가능 면적 %.1f ㎡(< %.0f ㎡)" % (free.area, MIN_FREE_M2)
        return None, info
    return out, info


def layout(name, region, obst, hard, rng, floor, ctx):
    n = name or ""
    kind = _program_of(n, floor)
    if kind is None:
        return Items()
    info, slab = None, slab_of(floor)
    if slab is not None:
        region, info = _slab_region(region, slab, hard)
        if region is None:
            out = Items()
            out.meta = dict(info, program=kind, floor=floor, types={}, route_min_clear_width_m=None, route_segments=0, anchors=0, ops_route_segments=None)
            return out
    P = Packer(region, obst, hard)
    if info is not None:
        P.aware, P.atrium = True, info["atrium_void"]
    svc = None
    if kind == "fnb":
        svc = _fnb(P, rng, floor, ctx)
    elif kind == "culture":
        svc = _culture(P, rng, floor, ctx)
    elif kind == "garden":
        svc = _garden(P, rng, floor, ctx)
    else:
        _retail(P, rng, floor, ctx)
    meta = _add_routes(P, ctx, ops_from=svc, perimeter_ops=kind.startswith("retail")) if kind != "garden" else {"route_min_clear_width_m": None, "route_segments": 0, "anchors": 0, "ops_route_segments": None}
    types = {}
    for it in P.items:
        if it[1] in ("body", "counter"):
            types[it.ftype] = types.get(it.ftype, 0) + 1
    out = Items(P.items)
    out.meta = dict(meta, program=kind, floor=floor, types=types, **(info or {}))
    return out

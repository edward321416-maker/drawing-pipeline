"""흑백 모노그래프 평면 렌더러 (SANAA / 이시가미 / ArchDaily 풍).

    python src/monograph_plan_renderer.py --out output/drawing_pipeline_1F_master --floor 1F [--with-dims] [--seed 7] [--png-width 4096]
    python src/monograph_plan_renderer.py --out output/drawing_pipeline_1F_master --test-furniture      # 가구 생성기 합성 시험 시트

6개 시각 시스템:
  1. 이중선·포셰 벽, 리드미컬한 기둥, 가는 점선 격자, 문 스윙
  2. 프로그램별 가구 자동 배치 (교실·사무·회의·화장실·침실·실험실·시장·하역)
  3. 해치·점묘 (광장 점묘, 복도 타일 격자)
  4. 식물 벡터 (수목 캐노피+가지, 화단 로제트·고사리·관목) + 배경 점묘 잡음
  5. 번호 + 범례(좌하단) + 단순 북쪽 화살표, 치수 끔 (--with-dims로 켬)
  6. SVG/PDF + 4096 px PNG, 자체 점검 JSON

입력은 02 단계가 만든 raw_slices/floor_<층>_slice.json (모델 단면)과 모델의 고정 대지 데이터(m_site_source.json, grove_design.json)다.
가구·수목은 설명용 표현이며 설계 데이터가 아니다 (AGENTS.md §3 3단계, §6.6: 구조 권한 없음).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys

from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import polylabel, unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline_common as pc  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_JSON = os.path.join(ROOT, "도면", "00_엔진", "model", "m_site_source.json")
GROVE_JSON = os.path.join(ROOT, "도면", "00_엔진", "model", "grove_design.json")
FONT = "Malgun Gothic, 'Segoe UI', Arial, sans-serif"
SHEET_MM = (594.0, 420.0)                              # A2 가로 (1:200에서 건물이 시트에 크게 보이도록)

# 선 위계 (종이 mm): 절단벽 > 문·격자·수목 > 가구·점묘
W = {"wall": 0.45, "wall_in": 0.12, "tube": 0.22, "slab": 0.10, "door": 0.12, "grid": 0.08, "furn": 0.10, "plant": 0.12, "hatch": 0.06}
C = {"wall": "#000000", "grid": "#888888", "furn": "#999999", "plant": "#666666", "dot": "#777777", "tile": "#DCDCDC", "num": "#333333"}


# ── 기하 도우미 ──────────────────────────────────────────────────────────────────────────────────
def obb(region):
    """최소 회전 외접 직사각형 → (중심, u축(긴 변), v축, 길이 L, 폭 Wd)."""
    r = region.minimum_rotated_rectangle
    pts = list(r.exterior.coords)[:4]
    e = [(pts[(i + 1) % 4][0] - pts[i][0], pts[(i + 1) % 4][1] - pts[i][1]) for i in range(4)]
    l0, l1 = math.hypot(*e[0]), math.hypot(*e[1])
    ex, ey = (e[0] if l0 >= l1 else e[1])
    L, Wd = max(l0, l1), min(l0, l1)
    ux, uy = ex / L, ey / L
    c = r.centroid
    return (c.x, c.y), (ux, uy), (-uy, ux), L, Wd


def at(c, u, v, a, b):
    return (c[0] + u[0] * a + v[0] * b, c[1] + u[1] * a + v[1] * b)


def rect(c, u, v, a, b, w, h):
    """(a,b)를 중심으로 u방향 w, v방향 h인 직사각형."""
    return Polygon([at(c, u, v, a - w / 2, b - h / 2), at(c, u, v, a + w / 2, b - h / 2),
                    at(c, u, v, a + w / 2, b + h / 2), at(c, u, v, a - w / 2, b + h / 2)])


def circ(c, u, v, a, b, r):
    p = at(c, u, v, a, b)
    return Point(p).buffer(r, 12)


def line(c, u, v, a0, b0, a1, b1):
    return LineString([at(c, u, v, a0, b0), at(c, u, v, a1, b1)])


def arc_pts(cx, cy, r, a0, a1, n=14):
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def keep_inside(items, region, margin=0.35):
    safe = region.buffer(-margin)
    return [g for g in items if (not safe.is_empty) and safe.contains(g)]


# ── 2. 가구 생성기 (모두 shapely 윤곽 목록을 돌려준다) ─────────────────────────────────────────────
def gen_classroom(region, rng):
    c, u, v, L, Wd = obb(region)
    items = []
    inset = 0.7
    pu, pv = 1.45, 1.3
    cols = max(1, int((L - 2 * inset - 1.4) // pu))
    rows = max(1, int((Wd - 2 * inset) // pv))
    u0 = -L / 2 + inset + 1.4
    v0 = -(rows - 1) * pv / 2
    for i in range(cols):
        for j in range(rows):
            a, b = u0 + i * pu, v0 + j * pv
            items += [rect(c, u, v, a, b, 0.55, 1.1), circ(c, u, v, a + 0.55, b, 0.2)]
    items.append(line(c, u, v, -L / 2 + 0.25, -Wd * 0.3, -L / 2 + 0.25, Wd * 0.3))                      # 칠판선
    items.append(rect(c, u, v, -L / 2 + 0.8, 0, 0.5, 1.0))                                              # 교탁
    return keep_inside(items, region, 0.4)


def gen_staff(region, rng):
    c, u, v, L, Wd = obb(region)
    items = []
    pu, pv = 4.0, 3.4
    cols = max(1, int((L - 1.6) // pu))
    rows = max(1, int((Wd - 1.6) // pv))
    for i in range(cols):
        for j in range(rows):
            a, b = -(cols - 1) * pu / 2 + i * pu, -(rows - 1) * pv / 2 + j * pv
            for da in (-0.75, 0.75):
                for db in (-0.38, 0.38):
                    items.append(rect(c, u, v, a + da, b + db, 1.4, 0.72))
            for da in (-0.75, 0.75):
                items += [circ(c, u, v, a + da, b - 0.95, 0.2), circ(c, u, v, a + da, b + 0.95, 0.2)]
    return keep_inside(items, region, 0.3)


def gen_meeting(region, rng):
    c, u, v, L, Wd = obb(region)
    a, b = max(0.8, L * 0.3), max(0.6, Wd * 0.28)
    table = affinity.scale(Point(c).buffer(1, 24), a, b)
    table = affinity.rotate(table, math.degrees(math.atan2(u[1], u[0])), origin=c)
    n = max(6, min(10, int(2 * math.pi * max(a, b) / 0.8)))
    chairs = []
    for k in range(n):
        t = 2 * math.pi * k / n
        px, py = (a + 0.5) * math.cos(t), (b + 0.5) * math.sin(t)
        chairs.append(Point(at(c, u, v, px, py)).buffer(0.22, 10))
    return keep_inside([table] + chairs, region, 0.3)


def gen_restroom(region, rng):
    c, u, v, L, Wd = obb(region)
    items = []
    n = max(1, int((L - 0.6) // 0.95))
    x0 = -(n * 0.95) / 2
    for i in range(n + 1):                                                                              # 칸막이
        items.append(line(c, u, v, x0 + i * 0.95, Wd / 2 - 1.7, x0 + i * 0.95, Wd / 2))
    for i in range(n):
        a = x0 + i * 0.95 + 0.475
        bowl = affinity.scale(Point(at(c, u, v, a, Wd / 2 - 0.45)).buffer(1, 12), 0.2, 0.28)
        items.append(bowl)
        items.append(LineString(arc_pts(*at(c, u, v, a - 0.4, Wd / 2 - 1.7), 0.8, 0, math.pi / 2)))      # 작은 문 스윙
    items.append(rect(c, u, v, 0, -Wd / 2 + 0.35, min(L - 0.8, 0.9 * 4), 0.5))                         # 카운터
    for i in range(min(4, max(1, int(L // 1.0)))):
        items.append(circ(c, u, v, (i - 1.5) * 0.9, -Wd / 2 + 0.35, 0.16))
    return keep_inside(items, region, -0.02)                                # 칸막이 선은 벽에 닿으므로 약간 여유를 두고 포함 검사


def gen_bedroom(region, rng):
    c, u, v, L, Wd = obb(region)
    items = []
    n = max(1, int((Wd - 0.6) // 1.7))
    for j in range(n):
        b = -(n - 1) * 1.7 / 2 + j * 1.7
        a = L / 2 - 1.75                                                   # 침대 머리가 벽에서 0.5 m 이상 떨어지도록
        items += [rect(c, u, v, a, b, 2.0, 0.95), rect(c, u, v, a + 0.7, b, 0.4, 0.7), rect(c, u, v, a - 0.35, b - 0.8, 0.4, 0.4)]
    return keep_inside(items, region, 0.25)


def gen_lab(region, rng):
    ring = region.buffer(-0.3).difference(region.buffer(-0.95))
    items = [g for g in ([ring] if ring.geom_type == "Polygon" else list(ring.geoms)) if g.area > 0.2]
    c, u, v, L, Wd = obb(region)
    items.append(rect(c, u, v, 0, 0, max(1.0, L * 0.4), 1.0))
    for k in range(4):
        items.append(circ(c, u, v, (k - 1.5) * max(0.6, L * 0.4) / 4 * 1.6, 0.95, 0.17))
    sinks = [rect(c, u, v, -L * 0.2 + k * 1.4, Wd / 2 - 0.62, 0.5, 0.35) for k in range(2)]
    return keep_inside(items + sinks, region, 0.1)


def gen_market(region, rng, obstacles=None):
    """시장 홀: 좌판 격자 (카운터 + 안쪽 선 + 의자). 기둥·튜브 주변 통로는 비워 둔다."""
    c, u, v, L, Wd = obb(region)
    free = region.buffer(-1.0)
    if obstacles is not None and not obstacles.is_empty:
        free = free.difference(obstacles.buffer(1.3))
    items = []
    pu, pv = 5.2, 4.2
    nu, nv = int(L // pu), int(Wd // pv)
    for i in range(nu + 1):
        for j in range(nv + 1):
            a, b = -L / 2 + 1.5 + i * pu, -Wd / 2 + 1.5 + j * pv
            stall = rect(c, u, v, a, b, 3.0, 1.2)
            if free.contains(stall.buffer(0.5)):
                items += [stall, rect(c, u, v, a, b, 2.7, 0.9), line(c, u, v, a - 1.35, b, a + 1.35, b),
                          circ(c, u, v, a - 0.7, b + 0.95, 0.2), circ(c, u, v, a + 0.7, b + 0.95, 0.2),
                          circ(c, u, v, a - 0.7, b - 0.95, 0.2), circ(c, u, v, a + 0.7, b - 0.95, 0.2)]
    return items


def gen_pallets(region, rng, obstacles=None):
    c, u, v, L, Wd = obb(region)
    free = region.buffer(-0.8)
    if obstacles is not None and not obstacles.is_empty:
        free = free.difference(obstacles.buffer(0.8))
    items = []
    for i in range(int(L // 2.2)):
        for j in range(int(Wd // 2.0)):
            a, b = -L / 2 + 1.2 + i * 2.2, -Wd / 2 + 1.1 + j * 2.0
            p = rect(c, u, v, a, b, 1.2, 1.0)
            if free.contains(p):
                items += [p, line(c, u, v, a - 0.6, b - 0.5, a + 0.6, b + 0.5), line(c, u, v, a - 0.6, b + 0.5, a + 0.6, b - 0.5)]
    return items


GENERATORS = {"classroom": gen_classroom, "staff": gen_staff, "meeting": gen_meeting, "restroom": gen_restroom,
              "bedroom": gen_bedroom, "lab": gen_lab, "market": gen_market, "service": gen_pallets}


# ── 3·4. 점묘·식물 ───────────────────────────────────────────────────────────────────────────────
def stipple_points(region, spacing, jitter, rng):
    minx, miny, maxx, maxy = region.bounds
    pts = []
    y = miny
    row = 0
    while y <= maxy:
        x = minx + (spacing / 2 if row % 2 else 0)
        while x <= maxx:
            p = (x + rng.uniform(-jitter, jitter) * spacing, y + rng.uniform(-jitter, jitter) * spacing)
            if region.contains(Point(p)):
                pts.append(p)
            x += spacing
        y += spacing * 0.866
        row += 1
    return pts


def wobble_ring(cx, cy, r, rng, k=0.12, n=40):
    ph = [rng.uniform(0, 2 * math.pi) for _ in range(3)]
    pts = []
    for i in range(n + 1):
        t = 2 * math.pi * i / n
        rr = r * (1 + k * (math.sin(3 * t + ph[0]) * 0.6 + math.sin(5 * t + ph[1]) * 0.3 + math.sin(7 * t + ph[2]) * 0.2))
        pts.append((cx + rr * math.cos(t), cy + rr * math.sin(t)))
    return pts


def branch_lines(cx, cy, r, rng, depth=4):
    """줄기 중심에서 방사로 갈라지는 가지 (프랙탈)."""
    out = []

    def grow(x, y, ang, length, d):
        if d == 0 or length < r * 0.06:
            return
        x2, y2 = x + length * math.cos(ang), y + length * math.sin(ang)
        out.append([(x, y), (x2, y2)])
        for da in (-0.5, 0.45):
            grow(x2, y2, ang + da + rng.uniform(-0.2, 0.2), length * rng.uniform(0.55, 0.7), d - 1)

    n = rng.randint(5, 8)
    a0 = rng.uniform(0, 2 * math.pi)
    for k in range(n):
        grow(cx, cy, a0 + 2 * math.pi * k / n + rng.uniform(-0.2, 0.2), r * 0.5, depth)
    return out


def tree_shapes(cx, cy, r, rng):
    """{'rings': [...], 'lines': [...]} 한 그루의 식물 선화. 변형 3종 (가지형·로제트형·구름형)."""
    kind = rng.choice(["branch", "rosette", "cloud"])
    rings, lines_ = [], []
    if kind == "branch":
        rings += [wobble_ring(cx, cy, r, rng, 0.10), wobble_ring(cx, cy, r * 0.66, rng, 0.1)]
        lines_ += branch_lines(cx, cy, r, rng)
    elif kind == "rosette":
        rings.append(wobble_ring(cx, cy, r, rng, 0.06))
        n = rng.randint(9, 14)
        for k in range(n):
            a = 2 * math.pi * k / n
            lines_.append([(cx, cy), (cx + r * 0.95 * math.cos(a), cy + r * 0.95 * math.sin(a))])
            ring = [(cx + r * 0.5 * math.cos(a) + r * 0.22 * math.cos(t) * math.cos(a) - r * 0.09 * math.sin(t) * math.sin(a),
                     cy + r * 0.5 * math.sin(a) + r * 0.22 * math.cos(t) * math.sin(a) + r * 0.09 * math.sin(t) * math.cos(a))
                    for t in [i * math.pi / 8 for i in range(17)]]
            rings.append(ring)
    else:
        for _ in range(rng.randint(5, 8)):
            a, d = rng.uniform(0, 2 * math.pi), rng.uniform(0, r * 0.5)
            rings.append(wobble_ring(cx + d * math.cos(a), cy + d * math.sin(a), r * rng.uniform(0.35, 0.6), rng, 0.05, 24))
        lines_ += branch_lines(cx, cy, r * 0.6, rng, 3)
    return {"rings": rings, "lines": lines_, "r": r, "c": (cx, cy)}


def plant_bed(region, rng):
    """화단: 로제트(종려·고사리 별), 관목 원, 잔 점. 반환 {'rings','lines','dots'}."""
    rings, lines_, dots = [], [], []
    area = region.area
    pts = []
    tries = 0
    target = max(3, int(area / 3.2))
    minx, miny, maxx, maxy = region.bounds
    while len(pts) < target and tries < target * 40:
        tries += 1
        p = (rng.uniform(minx, maxx), rng.uniform(miny, maxy))
        if region.buffer(-0.2).contains(Point(p)) and all(math.hypot(p[0] - q[0], p[1] - q[1]) > 0.8 for q in pts):
            pts.append(p)
    for (x, y) in pts:
        t = rng.random()
        if t < 0.4:                                                                                    # 별모양 잎
            n = rng.randint(6, 9)
            r = rng.uniform(0.35, 0.7)
            a0 = rng.uniform(0, 6.28)
            for k in range(n):
                a = a0 + 2 * math.pi * k / n
                lines_.append([(x, y), (x + r * math.cos(a), y + r * math.sin(a))])
        elif t < 0.7:                                                                                  # 관목 원 겹침
            for _ in range(rng.randint(2, 3)):
                rings.append(wobble_ring(x + rng.uniform(-0.2, 0.2), y + rng.uniform(-0.2, 0.2), rng.uniform(0.25, 0.5), rng, 0.08, 16))
        else:                                                                                          # 고사리 빗살
            a = rng.uniform(0, 6.28)
            for s in range(-3, 4):
                lines_.append([(x + 0.07 * s * math.cos(a + 1.57), y + 0.07 * s * math.sin(a + 1.57)),
                               (x + 0.07 * s * math.cos(a + 1.57) + 0.55 * math.cos(a + 0.6 * s * 0.2),
                                y + 0.07 * s * math.sin(a + 1.57) + 0.55 * math.sin(a + 0.6 * s * 0.2))])
    dots = stipple_points(region, 0.45, 0.4, rng)
    return {"rings": rings, "lines": lines_, "dots": dots}


# ── SVG 도우미 ───────────────────────────────────────────────────────────────────────────────────
class Canvas:
    def __init__(self, bounds_m, scale=200):
        self.b = bounds_m                              # (xmin, ymin, xmax, ymax) 도면 좌표(m)
        self.k = scale / 1000.0                        # 종이 1 mm = k m
        self.scale = scale
        self.w = bounds_m[2] - bounds_m[0]
        self.h = bounds_m[3] - bounds_m[1]
        self.parts = {n: [] for n in ("bg", "bgdots", "ground", "plants", "furn", "walls", "cols", "grid", "doors", "num", "legend")}

    def X(self, x):
        return x - self.b[0]

    def Y(self, y):
        return self.b[3] - y

    def lw(self, mm):
        return mm * self.k

    def pts(self, coords):
        return " ".join("%.3f,%.3f" % (self.X(x), self.Y(y)) for x, y in coords)

    def path_poly(self, geom):
        d = []
        for p in pc.iter_polygons(geom):
            for ring in [p.exterior] + list(p.interiors):
                d.append("M" + " L".join("%.3f,%.3f" % (self.X(x), self.Y(y)) for x, y in ring.coords) + " Z")
        return " ".join(d)

    def add(self, layer, s):
        self.parts[layer].append(s)

    def stroke_poly(self, layer, geom, mm, color, fill="none", extra=""):
        if geom.is_empty:
            return
        self.add(layer, '<path d="%s" fill="%s" fill-rule="evenodd" stroke="%s" stroke-width="%.4f" stroke-linejoin="round" %s/>' %
                 (self.path_poly(geom), fill, color, self.lw(mm), extra))

    def stroke_line(self, layer, coords, mm, color, extra=""):
        self.add(layer, '<polyline points="%s" fill="none" stroke="%s" stroke-width="%.4f" stroke-linecap="round" stroke-linejoin="round" %s/>' %
                 (self.pts(coords), color, self.lw(mm), extra))

    def dots(self, layer, pts, r_mm, color, opacity=1.0):
        if not pts:
            return
        d = "".join("M%.2f,%.2f h0.001" % (self.X(x), self.Y(y)) for x, y in pts)
        self.add(layer, '<path d="%s" stroke="%s" stroke-width="%.4f" stroke-linecap="round" fill="none" opacity="%.2f"/>' % (d, color, self.lw(2 * r_mm), opacity))

    def text(self, layer, x_mm, y_mm, s, pt, weight="normal", fill="#222", anchor="start"):
        # 시트 좌표(종이 mm)를 도면 미터로 바꿔 놓는다: 좌상단 원점
        self.add(layer, '<text x="%.3f" y="%.3f" font-family="%s" font-size="%.4f" font-weight="%s" fill="%s" text-anchor="%s">%s</text>' %
                 (x_mm * self.k, y_mm * self.k, FONT, pt * 0.3528 * self.k, weight, fill, anchor, s.replace("&", "&amp;")))


def group_key(name: str):
    """프로그램 → (범례 이름, 가구 종류). 이름은 모델의 name_ko에서 온다."""
    n = name
    if n.startswith("코어"):
        return "코어 (피난계단)", None
    if "화장실" in n:
        return "화장실", None
    if "시장" in n:
        return "시장 홀", "market"
    if "필로티" in n or "광장" in n:
        return "필로티 광장", "plaza"
    if "하역" in n or "서비스" in n:
        return "하역·서비스", "service"
    if "개구부" in n or "선큰" in n:
        return "선큰 연결 개구부", "void"
    return n, None


# ── 메인 렌더 ────────────────────────────────────────────────────────────────────────────────────
def render(out, floor, seed=7, with_dims=False, png_width=4096, scale=200):
    raw = os.path.join(out, "raw_slices")
    sl = pc.load_slice(raw, floor)
    lay = pc.load_json(os.path.join(out, "vector", "floor_%s_layout.json" % floor))
    bnd = pc.load_bounds(raw)
    rng = random.Random(seed)
    cuts = pc.cut_geometries(sl)
    bx0, by0, bx1, by1 = lay["building"]
    cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
    k = scale / 1000.0
    Wm, Hm = SHEET_MM[0] * k, SHEET_MM[1] * k
    cv = Canvas((cx - Wm / 2, cy - Hm / 2, cx + Wm / 2, cy + Hm / 2), scale)
    slab = unary_union([pc.polygons_from_segments(p["segments"]) for p in sl["projection"]])
    footprint = slab if not slab.is_empty else box(bx0, by0, bx1, by1)

    # 구조 요소 모음
    walls = [(it, g) for kd in ("partition_wall", "core_wall", "exterior_wall") for it, g in cuts.get(kd, [])]
    cols = [g for _, g in cuts.get("column", [])]
    tubes = [(it, g) for kd in ("tube_wall",) for it, g in cuts.get(kd, [])]
    shafts = [(it, g) for it, g in cuts.get("shaft", [])]
    stairs = [(it, g) for it, g in cuts.get("stair", [])]
    obst = unary_union([g for kd in cuts.values() for _, g in kd]) if cuts else Polygon()
    zones = []
    for z in sl["zones"]:
        g = pc.polygons_from_segments(z["segments"])
        if not g.is_empty and z["kind"] in ("room", "zone", "void"):
            zones.append((z, g))
    syms = []
    for s in sl.get("symbols", []):
        g = pc.polygons_from_segments(s.get("segments", []))
        if not g.is_empty:
            syms.append((s, g))

    # 0) 대지 맥락: 모델의 태그 객체에서 뽑은 것(slice JSON의 context). 건물과 같은 좌표계다.
    cx_ = sl.get("context", {})
    canvas_box = box(*cv.b)
    ext, lawn, path = {}, Polygon(), Polygon()
    for sp in cx_.get("spaces", []):
        g = pc.polygons_from_segments(sp["segments"])
        use = str(sp["props"].get("use", ""))
        nm = sp["name_ko"]
        key = use or ("plaza" if "광장" in nm else "grove" if "숲" in nm else "sunken" if "선큰" in nm else "fire_lane" if "소방" in nm else nm)
        if "path" in key or "산책" in nm:
            path = unary_union([path, g]) if not path.is_empty else g
        elif "lawn" in key or "잔디" in nm or key == "grove":
            lawn = unary_union([lawn, g]) if not lawn.is_empty else g
        else:
            ext[key] = unary_union([ext[key], g]) if key in ext else g
    # 수목: 모델의 수목 객체는 겹친 수관이 덩어리로 합쳐져 있어 개별 위치를 알 수 없다 → 모델의 고정 원천 데이터(개별 위치·반경, 같은 좌표계)를 쓴다
    site = pc.load_json(SITE_JSON) if os.path.exists(SITE_JSON) else {}
    grove = pc.load_json(GROVE_JSON) if os.path.exists(GROVE_JSON) else {}
    trees = [tuple(t[:3]) for t in (site.get("trees") or [])] + [tuple(t[:3]) for t in (grove.get("trees") or [])]
    if not trees:
        trees = [tuple(t[:3]) for t in cx_.get("trees", [])]

    # 1) 배경 점묘 잡음: 건물·수목 주변이 짙다 (한 개의 path로)
    noise = []
    centers = [(t[0], t[1], t[2] * 2.2) for t in trees] + [(cx, cy, 45.0)]
    hole = footprint.buffer(0.3)
    nn = 110000
    for _ in range(nn):
        if rng.random() < 0.45:
            p = (rng.uniform(cv.b[0], cv.b[2]), rng.uniform(cv.b[1], cv.b[3]))
        else:
            c0 = rng.choice(centers)
            ang, d = rng.uniform(0, 6.283), abs(rng.gauss(0, c0[2]))
            p = (c0[0] + d * math.cos(ang), c0[1] + d * math.sin(ang))
        if cv.b[0] < p[0] < cv.b[2] and cv.b[1] < p[1] < cv.b[3] and not hole.contains(Point(p)):
            noise.append(p)
    third = len(noise) // 3
    cv.dots("bgdots", noise[:third], 0.11, "#8a8a8a", 0.75)
    cv.dots("bgdots", noise[third:2 * third], 0.08, "#666666", 0.7)
    cv.dots("bgdots", noise[2 * third:], 0.16, "#a8a8a8", 0.6)

    # 2) 광장·마당·선큰 (점묘, 잔디, 테라스)
    for kd, g in ext.items():
        if g.is_empty:
            continue
        g = g.intersection(canvas_box)
        if kd == "plaza":
            cv.dots("ground", stipple_points(g.difference(footprint), 0.9, 0.35, rng), 0.10, C["dot"], 0.8)
        elif kd == "sunken":
            cv.stroke_poly("ground", g, 0.15, "#555")
            for off in (0.6, 1.2, 1.8, 2.4, 3.0):
                inner = g.buffer(-off)
                if not inner.is_empty:
                    cv.stroke_poly("ground", inner, 0.08, "#888")
        elif kd == "fire_lane":
            cv.stroke_poly("ground", g, 0.08, "#999", extra='stroke-dasharray="%.3f,%.3f"' % (3 * k, 2 * k))
    for st in cx_.get("sunken_stair", []):
        g = pc.polygons_from_segments(st["segments"])
        if g.is_empty:
            continue
        x0, y0, x1, y1 = g.bounds
        n = int(st["props"].get("treads", 12))
        for i in range(n + 1):
            x = x0 + (x1 - x0) * i / n
            cv.stroke_line("ground", [(x, y0), (x, y1)], 0.09, "#777")
        cv.stroke_poly("ground", g, 0.12, "#555")
    if not lawn.is_empty:
        bed = plant_bed(lawn.difference(path.buffer(0.2)) if not path.is_empty else lawn, rng)
        cv.stroke_poly("ground", lawn, 0.08, "#aaa")
        for r in bed["rings"]:
            cv.stroke_line("plants", r, W["plant"], C["plant"])
        for l_ in bed["lines"]:
            cv.stroke_line("plants", l_, 0.09, C["plant"])
        cv.dots("plants", bed["dots"], 0.07, "#888", 0.7)
    if not path.is_empty:
        cv.dots("ground", stipple_points(path, 0.5, 0.3, rng), 0.07, "#aaa", 0.8)

    # 3) 수목: 건물 위와 겹치는 것은 빼고, 캔버스 안의 것만. 모델에 수목이 없는 방향에는 표현용 수목을 흩어 놓는다 (설명용, 설계 데이터 아님)
    extra = 0
    tries = 0
    while extra < 18 and tries < 800:
        tries += 1
        x, y = rng.uniform(cv.b[0] + 4, cv.b[2] - 4), rng.uniform(cv.b[1] + 4, cv.b[3] - 4)
        r = rng.uniform(1.6, 3.0)
        if footprint.buffer(r + 5.0).contains(Point(x, y)) or any(math.hypot(x - t[0], y - t[1]) < t[2] * 1.6 + r * 1.6 + 1.0 for t in trees):
            continue
        if cv.b[0] + 32 < x < cv.b[0] + 66 and cv.b[1] < y < cv.b[1] + 44:          # 좌하단 범례 자리는 비운다
            continue
        trees.append((x, y, r))
        extra += 1
    drawn = 0
    for (x, y, r) in trees:
        if not (cv.b[0] + 2 < x < cv.b[2] - 2 and cv.b[1] + 2 < y < cv.b[3] - 2):
            continue
        if footprint.buffer(r * 0.6).contains(Point(x, y)):
            continue
        sh = tree_shapes(x, y, max(r * 1.6, 2.0), rng)
        for ring in sh["rings"]:
            cv.add("plants", '<path d="M%s Z" fill="#ffffff" fill-opacity="0.45" stroke="%s" stroke-width="%.4f" stroke-linejoin="round"/>' %
                   (" L".join("%.3f,%.3f" % (cv.X(px), cv.Y(py)) for px, py in ring), C["plant"], cv.lw(W["plant"])))
        for ln in sh["lines"]:
            cv.stroke_line("plants", ln, 0.09, C["plant"])
        cv.dots("plants", [(x, y)], 0.25, "#444")
        drawn += 1

    # 4) 가구 (프로그램별), 구역 경계 겹침 제거
    zone_geoms = {id(z): g for z, g in zones}
    legend_groups: list = []
    furn_all = []
    font_halo = []
    prog = []
    for z, g in zones:
        name, fk = group_key(z["name_ko"])
        prog.append((z, g, name, fk))
    # 큰 영역에서는 다른 영역을 뺀 나머지에 가구를 놓는다
    for z, g, name, fk in prog:
        if fk is None or fk == "void":
            continue
        others = unary_union([g2 for (z2, g2, n2, f2) in prog if z2 is not z and g2.area < g.area])
        region = g.difference(others).buffer(-0.3) if not others.is_empty else g.buffer(-0.3)
        region = max(pc.iter_polygons(region), key=lambda p: p.area) if not region.is_empty else region
        if region.is_empty:
            continue
        if fk == "plaza":                                                       # 광장: 점묘 (규칙적 + 약간 흔들림)
            free_p = region.difference(obst.buffer(0.4)) if not obst.is_empty else region
            cv.dots("ground", stipple_points(free_p, 0.7, 0.3, rng), 0.14, "#666666", 1.0)
            continue
        gen = GENERATORS.get(fk)
        if fk in ("market", "service"):
            items = gen(region, rng, obstacles=unary_union([obst, footprint.boundary.buffer(0.01)]))
        else:
            items = gen(region, rng)
        furn_all += items
        for it in items:
            if it.geom_type == "Polygon":
                cv.stroke_poly("furn", it, W["furn"], C["furn"])
            else:
                for gg in ([it] if it.geom_type == "LineString" else list(getattr(it, "geoms", []))):
                    cv.stroke_line("furn", list(gg.coords), W["furn"], C["furn"])
    # 모델이 가진 위생도기·계단 윤곽은 연회색으로
    for s, g in syms:
        if s["category"] != "door":
            cv.stroke_poly("furn", g, W["furn"], C["furn"])
    for it, g in stairs:
        cv.stroke_poly("furn", g, W["furn"], C["furn"])
    # 복도·습식 타일 격자: 코어·화장실 영역에 아주 옅은 직교 격자
    for z, g, name, fk in prog:
        if name in ("화장실",):
            minx, miny, maxx, maxy = g.bounds
            x = math.floor(minx / 0.6) * 0.6
            while x < maxx:
                seg = LineString([(x, miny), (x, maxy)]).intersection(g)
                if not seg.is_empty and seg.geom_type == "LineString":
                    cv.stroke_line("ground", list(seg.coords), W["hatch"], C["tile"])
                x += 0.6
            y = math.floor(miny / 0.6) * 0.6
            while y < maxy:
                seg = LineString([(minx, y), (maxx, y)]).intersection(g)
                if not seg.is_empty and seg.geom_type == "LineString":
                    cv.stroke_line("ground", list(seg.coords), W["hatch"], C["tile"])
                y += 0.6

    # 5) 벽: 이중선·포셰
    for it, g in walls:
        thick = g.area / max(g.length / 2, 1e-6)
        if thick >= 0.22:
            cv.stroke_poly("walls", g, W["wall"], C["wall"], fill="#ffffff")
            inner = g.buffer(-0.075)
            if not inner.is_empty:
                cv.stroke_poly("walls", inner, W["wall_in"], "#444")
        else:
            cv.stroke_poly("walls", g, W["wall"] * 0.7, C["wall"], fill="#111111")
    for it, g in tubes:
        cv.stroke_poly("walls", g, W["tube"], "#333", fill="#ffffff", extra='fill-opacity="0.35"')
    for it, g in shafts:
        cv.stroke_poly("walls", g, W["tube"], "#222", fill="#ffffff", extra='fill-opacity="0.5"')
    cv.stroke_poly("walls", footprint.boundary.buffer(0.001), W["slab"], "#777", extra='stroke-dasharray="%.3f,%.3f"' % (2.5 * k, 1.5 * k))

    # 6) 기둥 + 가는 점선 격자
    for g in cols:
        cv.stroke_poly("cols", g, 0.1, "#000", fill="#000")
    xs = sorted({round(g.centroid.x, 2) for g in cols})
    ys = sorted({round(g.centroid.y, 2) for g in cols})
    dash = 'stroke-dasharray="%.3f,%.3f"' % (2 * k, 2 * k)
    for x in xs:
        cv.stroke_line("grid", [(x, by0 - 2.5), (x, by1 + 2.5)], W["grid"], C["grid"], dash)
    for y in ys:
        cv.stroke_line("grid", [(bx0 - 2.5, y), (bx1 + 2.5, y)], W["grid"], C["grid"], dash)

    # 7) 문 스윙
    for s, g in syms:
        if s["category"] == "door":
            cv.stroke_poly("doors", g, W["door"], "#333", fill="#ffffff", extra='fill-opacity="0.0"')

    # 8) 번호 + 범례 (이름은 범례에만)
    order = ["시장 홀", "필로티 광장", "하역·서비스", "코어 (피난계단)", "화장실", "선큰 연결 개구부"]
    groups: dict = {}
    for z, g, name, fk in prog:
        groups.setdefault(name, []).append(g)
    for it, g in tubes + shafts:
        groups.setdefault(it["name_ko"], []).append(g)
    names = [n for n in order if n in groups] + sorted(n for n in groups if n not in order)
    num_of = {n: i + 1 for i, n in enumerate(names)}
    avoid = unary_union([obst.buffer(0.3)] + [g.buffer(0.2) for g in furn_all]) if furn_all or not obst.is_empty else Polygon()
    placed = []
    nums = []
    for n in names:
        for g in groups[n]:
            region = g
            if n in order:
                free = region.difference(avoid) if not avoid.is_empty else region
            else:
                free = Polygon(max(pc.iter_polygons(g), key=lambda p: p.area).exterior).buffer(-0.3)
            cand = [p for p in pc.iter_polygons(free) if p.area > 0.8]
            if not cand:
                cand = [p for p in pc.iter_polygons(region)]
            best = max(cand, key=lambda p: p.area)
            pt = polylabel(best, tolerance=0.05)
            nums.append((num_of[n], pt.x, pt.y))
    pt_m = 8 * 0.3528 * k
    for no, x, y in nums:
        cv.add("num", '<circle cx="%.3f" cy="%.3f" r="%.3f" fill="#ffffff" fill-opacity="0.92"/>' % (cv.X(x), cv.Y(y), pt_m * 0.85))
        cv.add("num", '<text x="%.3f" y="%.3f" font-family="%s" font-size="%.3f" fill="%s" text-anchor="middle">%d</text>' %
               (cv.X(x), cv.Y(y) + pt_m * 0.35, FONT, pt_m, C["num"], no))

    # 9) 좌하단 범례 + 북쪽 화살표
    row_h = 5.2
    total = 12 + len(names) * row_h + 14 + 2 * 8.0 + 12                     # 제목 + 목록 + 간격 + 화살표 원 + 각주
    lx, ly = 16.0, SHEET_MM[1] - 12.0 - total               # 종이 mm, 시트 좌하단에 맞춘다
    cv.add("legend", '<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" fill="#ffffff" fill-opacity="0.93"/>' %
           ((lx - 5) * k, (ly - 10) * k, 66 * k, (total + 14) * k))                    # 범례 뒤 여백 (수목·점묘와 겹치지 않게)
    cv.text("legend", lx, ly, "%s 평면도" % floor.replace("F", "층") if floor.endswith("F") else floor, 10, "bold", "#111")
    y = ly + 11
    for n in names:
        cv.text("legend", lx, y, str(num_of[n]), 8, "normal", "#222")
        cv.text("legend", lx + 9, y, n, 8, "normal", "#222")
        y += row_h
    ncx, ncy, nr = lx + 8, y + 12, 8.0
    cv.add("legend", '<circle cx="%.3f" cy="%.3f" r="%.3f" fill="none" stroke="#555" stroke-width="%.4f"/>' % (ncx * k, ncy * k, nr * k, 0.2 * k))
    na = math.radians(bnd["frame"].get("north_deg", 0.0))
    ex, ey = math.sin(na), -math.cos(na)
    cv.add("legend", '<line x1="%.3f" y1="%.3f" x2="%.3f" y2="%.3f" stroke="#555" stroke-width="%.4f"/>' %
           (ncx * k, ncy * k, (ncx + ex * (nr + 3)) * k, (ncy + ey * (nr + 3)) * k, 0.25 * k))
    cv.text("legend", lx, ncy + 13, "※ 가구·수목·점묘는 설명용 표현이며 설계 데이터가 아니다", 5, "normal", "#999")

    if with_dims:
        for tier, side, p1, p2, off in lay["dims"]:
            horiz = side in ("bottom", "top")
            q1 = (p1[0], p1[1] + off) if horiz else (p1[0] + off, p1[1])
            q2 = (p2[0], p2[1] + off) if horiz else (p2[0] + off, p2[1])
            cv.stroke_line("grid", [q1, q2], 0.1, "#555")
            cv.text("grid", ((cv.X((q1[0] + q2[0]) / 2) / k)), (cv.Y((q1[1] + q2[1]) / 2) / k) - 0.5, format(int(round(math.hypot(p2[0] - p1[0], p2[1] - p1[1]) * 1000)), ","), 5, "normal", "#555", "middle")

    # 합치기
    W_, H_ = cv.w, cv.h
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm" viewBox="0 0 %.3f %.3f">' % (SHEET_MM[0], SHEET_MM[1], W_, H_),
           '<rect width="%.3f" height="%.3f" fill="#ffffff"/>' % (W_, H_)]
    for layer in ("bgdots", "ground", "plants", "furn", "walls", "cols", "grid", "doors", "num", "legend"):
        svg.append('<g id="%s">%s</g>' % (layer, "".join(cv.parts[layer])))
    svg.append("</svg>")
    outd = os.path.join(out, "final_sheets")
    os.makedirs(outd, exist_ok=True)
    base = os.path.join(outd, "monograph_%s" % floor)
    with open(base + ".svg", "w", encoding="utf-8") as fh:
        fh.write("\n".join(svg))
    import cairosvg
    cairosvg.svg2pdf(url=base + ".svg", write_to=base + ".pdf")
    cairosvg.svg2png(url=base + ".svg", write_to=base + ".png", output_width=png_width, background_color="white")
    import shutil
    shutil.copy2(base + ".png", os.path.join(outd, "monograph_site_plan.png"))
    import re
    svg_txt = "\n".join(svg)
    plan_texts = []                                                           # 평면(범례 제외)에 들어간 글자: 번호만이어야 한다
    for layer in ("bgdots", "ground", "plants", "furn", "walls", "cols", "grid", "doors", "num"):
        for t in re.findall(r"<text[^>]*>([^<]*)</text>", "".join(cv.parts[layer])):
            plan_texts.append(t)
    furn_union = unary_union(furn_all) if furn_all else Polygon()
    collide = sum(1 for no, x, y in nums if (not furn_union.is_empty) and Point(x, y).buffer(pt_m * 0.85).intersects(furn_union))
    outside = sum(1 for it in furn_all if not footprint.buffer(0.5).contains(it))
    check = {"floor": floor, "seed": seed, "rooms": len(zones), "legend": {str(num_of[n]): n for n in names}, "furniture_items": len(furn_all),
             "furniture_outside_building": outside, "numbers_colliding_with_furniture": collide,
             "plan_text_all_numeric": all(t.strip().isdigit() for t in plan_texts) if not with_dims else None, "plan_text_count": len(plan_texts),
             "trees_drawn": drawn, "trees_from_model": len(trees) - extra, "trees_illustrative": extra, "background_dots": len(noise),
             "numbers_in_plan": len(nums), "line_weights_mm": W, "dims": with_dims}
    with open(base + "_check.json", "w", encoding="utf-8") as fh:
        json.dump(check, fh, ensure_ascii=False, indent=1)
    print("MONOGRAPH", floor, "furniture=%d trees=%d numbers=%d" % (len(furn_all), drawn, len(nums)), os.path.abspath(base + ".png"))
    return base


def furniture_test(out, seed=7, png_width=3200):
    """프로그램별 가구 생성기를 합성 방에 적용해 한 장에 모은다 (우리 1층에는 교실·침실이 없으므로 생성기 검증용)."""
    rng = random.Random(seed)
    specs = [("classroom", 10.0, 7.5), ("staff", 11.0, 7.0), ("meeting", 8.0, 6.0), ("restroom", 7.5, 4.2),
             ("bedroom", 8.0, 6.5), ("lab", 9.0, 6.5), ("service", 14.0, 9.0)]
    cv = Canvas((0, 0, 4 * 16.0, 2 * 12.0), 200)
    for i, (kind, w, h) in enumerate(specs):
        col, row = i % 4, i // 4
        ox, oy = col * 16.0 + 3, (1 - row) * 12.0 + 2
        room = box(ox, oy, ox + w, oy + h)
        for it in GENERATORS[kind](room.buffer(-0.2), rng):
            if it.geom_type == "Polygon":
                cv.stroke_poly("furn", it, W["furn"], C["furn"])
            else:
                for gg in ([it] if it.geom_type == "LineString" else list(getattr(it, "geoms", []))):
                    cv.stroke_line("furn", list(gg.coords), W["furn"], C["furn"])
        cv.stroke_poly("walls", room, W["wall"], C["wall"], fill="none")
        cv.text("legend", (ox) / cv.k, (cv.b[3] - oy + 1.2) / cv.k, kind, 7, "normal", "#333")
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm" viewBox="0 0 %.3f %.3f"><rect width="100%%" height="100%%" fill="#fff"/>' %
           (cv.w / cv.k, cv.h / cv.k, cv.w, cv.h)]
    for layer in ("ground", "furn", "walls", "legend"):
        svg.append('<g id="%s">%s</g>' % (layer, "".join(cv.parts[layer])))
    svg.append("</svg>")
    path = os.path.join(out, "final_sheets", "monograph_furniture_test")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path + ".svg", "w", encoding="utf-8").write("\n".join(svg))
    import cairosvg
    cairosvg.svg2png(url=path + ".svg", write_to=path + ".png", output_width=png_width, background_color="white")
    print("FURN_TEST", os.path.abspath(path + ".png"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--floor", default="1F")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--with-dims", action="store_true")
    ap.add_argument("--png-width", type=int, default=4096)
    ap.add_argument("--scale", type=int, default=200)
    ap.add_argument("--test-furniture", action="store_true")
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    if a.test_furniture:
        furniture_test(out, a.seed)
    else:
        render(out, a.floor, a.seed, a.with_dims, a.png_width, a.scale)


if __name__ == "__main__":
    main()

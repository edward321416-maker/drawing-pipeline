"""A3 정축척 평면 렌더러 v2 — 대지 맥락·조경, 유리 커튼월, 프로그램 기호, 통합 범례.

    python src/architectural_plan_renderer.py --out output/drawing_pipeline_1F_master --floor 1F            # 1:500 배치+1층 (A3)
    python src/architectural_plan_renderer.py --out output/drawing_pipeline --floor 3F --scale 200          # 상층 (A3, 1:200)

- 용지 A3 가로 420 × 297 mm 고정, 1 m = 1000/축척 mm. 자동 맞춤 없음. 54×54 m 건물은 A3에서 1:100이 불가능(540 mm 필요) → 상층은 1:200.
- 대지 맥락(도로·보도·이웃 건물·대지경계선·건축한계선·출입구)은 모델의 태그 객체(slice JSON의 context)에서 온다. 조경(공원 산책로·식재 섬·보행로·진입 광장·서비스 진입로)은
  대지경계선·건물 위치·출입구에서 계산한 설계 표현이다 (설계 데이터가 아니라 설명용, AGENTS.md §3 3단계).
- 문 객체(부채꼴)는 도면에 직접 그리지 않고 힌지·문짝·호로 다시 그리며, 벽에는 문 개구부를 뚫는다. 출입구(entrance) 객체의 상자도 그리지 않는다(위치 정보로만 쓴다).
- 범례는 건축 프로그램 9개만. 승강기·샤프트에는 번호를 달지 않는다.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sys

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import polylabel, unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline_common as pc  # noqa: E402
import monograph_plan_renderer as mg  # noqa: E402
import furniture_library as FL
import upper_layouts as UL
import layouts_v3 as L3
import program_planner as PP
import line_hygiene as LH  # noqa: E402

A3 = (420.0, 297.0)
SCALE_BARS = {500: [0, 5, 10, 25, 50], 200: [0, 2, 5, 10, 20], 100: [0, 1, 2, 5, 10]}
LAYERS = ("bgdots", "context", "ground", "landscape", "plants", "furn", "envelope", "walls", "cols", "grid", "symbols", "doors", "num", "legend")
LEGEND = ["시장 홀", "F&B 구역", "문화·엔터 구역", "정원·테라스", "필로티 광장", "하역·서비스", "선큰 마당", "서측 캡슐", "동측 캡슐", "나선 램프 튜브", "빛 튜브", "화장실", "코어 / 피난계단·승강기"]
TXT = "#333333"

# ── 6단계 선 위계 (A3 종이 mm, 색). 모든 선은 아래 표를 거쳐 굵기·색이 정해진다 ──
T1 = (0.45, "#000000")      # 1단계: 절단 RC 벽·코어 벽·점 기둥·튜브 구조 링 (검정 채움)
T2 = (0.18, "#222222")      # 2단계: 문짝·선큰 슬래브 가장자리·화장실 칸막이
T3 = (0.12, "#444444")      # 3단계: 계단 챌판·난간·램프선·승강기 카·이웃 건물 윤곽
T4 = (0.09, "#4A4A4A")      # 4단계: 유리 커튼월·창틀 (이중선, 1:100은 0.12). 커튼월은 별도 코드로 그린다
T5 = (0.08, "#666666")      # 5단계: 가구·위생도기·문 스윙 호·샤프트 X (흰색 채움)
T6 = (0.05, "#CCCCCC")      # 6단계: 타일 격자·점묘·구조 격자·식재 (배경 질감)
RESTYLE = {
    ("context", 0.12): T6, ("context", 0.2): T3, ("context", 0.15): T3, ("context", 0.06): T6, ("context", 0.05): T6, ("context", 0.1): T6,
    ("landscape", 0.1): T5, ("landscape", 0.12): T5, ("landscape", 0.08): T5, ("landscape", 0.05): T6, ("landscape", 0.06): T6,
    ("landscape", 0.14): T3, ("landscape", 0.16): T3, ("landscape", 0.2, "#222"): T3,
    ("ground", 0.12, "#555"): T2, ("ground", 0.12, "#999"): T6, ("ground", 0.14): T3, ("ground", 0.06): T6, ("ground", 0.05): T6,
    ("ground", 0.07): T6, ("ground", 0.08): T6,
    ("furn", 0.1): T5, ("furn", 0.12, "#999999"): T5, ("furn", 0.12, "#999"): T5, ("furn", 0.12, "#444"): T3, ("furn", 0.3): T3,
    ("furn", 0.07): T5, ("furn", 0.05): T6, ("furn", 0.04): T6,
    ("envelope", 0.12): T5, ("envelope", 0.18): T2,
    ("walls", 0.5): T1, ("walls", 0.12, "#444"): T3, ("walls", 0.15): T2, ("walls", 0.35, "#000"): T1, ("walls", 0.351, "#000"): T2,
    ("walls", 0.45): T1, ("walls", 0.4): T1, ("walls", 0.25): T3, ("walls", 0.22): T3, ("walls", 0.1, "#777"): T6,
    ("cols", 0.1): T1, ("grid", 0.08): T6,
    ("symbols", 0.12): T3, ("symbols", 0.08): T5, ("symbols", 0.14, "#111"): T2, ("symbols", 0.14, "#222"): T3, ("symbols", 0.16): T3, ("symbols", 0.1): T3,
    ("doors", 0.12): T5, ("doors", 0.18): T2, ("doors", 0.2): T2, ("doors", 0.1): T5,
}


def restyle(layer, mm, color):
    for key in ((layer, round(mm, 3), color), (layer, round(mm, 3))):
        if key in RESTYLE:
            return RESTYLE[key]
    if layer == "plants":
        return T6
    return (mm, color)


def restyle_clean(layer, mm0, c0, mm2, c2):
    """C-T13A 시각 순위: ① 절단 구조·기둥·코어 > ② 외피·문 > ③ 가구·주요 공간 요소 > ④ 프로그램 표시 > ⑤ 조경·포장·해치(맥락 포함).
    ①~③ 토큰(T1~T5)은 그대로 두고, ⑤ 층(조경·이웃 건물 윤곽)만 가구보다 옅고 가늘게 한다."""
    if layer == "landscape":
        if (round(mm0, 3), c0) in ((0.2, "#222"), (0.16, "#222")):
            return 0.09, "#777777"                                                  # 서비스 진입로 연석·화살표(대지 정보)
        return (mm2, c2) if c2 in ("#CCCCCC", "#CFCFCF", "#C0C0C0") else (0.06, "#A8A8A8")
    if layer == "context" and c2 == "#444444":
        return 0.08, "#8E8E8E"                                                      # 이웃 건물 윤곽: 가구(0.08 #666)보다 옅게
    return mm2, c2


class TCanvas(mg.Canvas):
    """선 굵기·색을 6단계 위계표로 통일하는 캔버스 (SVG 선폭 = 종이 mm × 축척/1000)."""

    def stroke_poly(self, layer, geom, mm, color, fill="none", extra=""):
        mm2, c2 = restyle(layer, mm, color)
        if self.clean:
            mm2, c2 = restyle_clean(layer, mm, color, mm2, c2)
        super().stroke_poly(layer, geom, mm2, c2, fill, extra)

    def stroke_line(self, layer, coords, mm, color, extra=""):
        mm2, c2 = restyle(layer, mm, color)
        if self.clean:
            mm2, c2 = restyle_clean(layer, mm, color, mm2, c2)
        super().stroke_line(layer, coords, mm2, c2, extra)

    def dots(self, layer, pts, r_mm, color, opacity=1.0):
        if layer in ("ground", "landscape", "bgdots"):
            color, r_mm = "#C0C0C0", r_mm * 0.8                                     # 6단계: 점묘는 배경 질감
        elif layer == "plants":
            color = "#CCCCCC"
        super().dots(layer, pts, r_mm, color, opacity)


def draw_furniture(cv, items, dotted="", dashed="", dashdot=""):
    """가구 그리기: 몸체는 흰색 불투명 채움(#FFFFFF) + 5단계 윤곽(0.08 mm #666666)이라 아래 타일·점묘이 비치지 않는다.
    V3 종류: zone(점선 바닥 표시, 가장 먼저) · counter(계산대·카운터, 회색 채움 + 3단계 윤곽) · route_v(방문자 동선, 긴 점선) · route_o(운영 동선, 일점쇄선).
    큰 몸체부터 그린 뒤 세부선, 마지막에 식재선(6단계)과 동선을 얹는다."""
    for g, k in items:
        if k == "zone":
            cv.stroke_poly("furn", g, 0.07, "#999999", extra=dotted)
    bodies = sorted([g for g, k in items if k == "body"], key=lambda g: -g.area)
    for g in bodies:
        cv.stroke_poly("furn", g, 0.08, "#666666", fill="#FFFFFF")
    for g, k in items:
        if k == "counter":
            cv.stroke_poly("furn", g, 0.12, "#444", fill="#D9D9D9")
    for g, k in items:
        if k == "line":
            for ln in lines_of(g):
                cv.stroke_line("furn", list(ln.coords), 0.08, "#666666")
    for g, k in items:
        if k == "foliage":
            for ln in lines_of(g):
                cv.stroke_line("furn", list(ln.coords), 0.05, "#AAAAAA")
    for g, k in items:
        if k in ("route_v", "route_o"):
            for ln in lines_of(g):
                cv.stroke_line("furn", list(ln.coords), 0.07 if k == "route_v" else 0.05, "#666666" if k == "route_v" else "#CCCCCC", extra=dashed if k == "route_v" else dashdot)


def lines_of(g):
    if g is None or g.is_empty:
        return []
    if g.geom_type == "LineString":
        return [g]
    return [x for gg in getattr(g, "geoms", []) for x in lines_of(gg)]


def U(items):
    items = [i for i in items if i is not None and not i.is_empty]
    return unary_union(items) if items else Polygon()


def shell_of(g):
    return Polygon(max(pc.iter_polygons(g), key=lambda p: p.area).exterior)


def rad_of(sh):
    c = sh.centroid
    return max(math.hypot(x - c.x, y - c.y) for x, y in sh.exterior.coords)


def legend_group(name, kind):
    """이름 → 범례 항목(9개). 승강기·샤프트는 None(번호 없음)."""
    n = name
    if n.startswith("코어"):
        return "코어 / 피난계단·승강기"
    if "화장실" in n:
        return "화장실"
    if "시장" in n or "판매" in n or "상업" in n:
        return "시장 홀"
    if "F&B" in n:
        return "F&B 구역"
    if "문화" in n or "엔터" in n:
        return "문화·엔터 구역"
    if "garden" in n.lower() or "정원" in n:
        return "정원·테라스"
    if "필로티" in n:
        return "필로티 광장"
    if "하역" in n or "서비스" in n:
        return "하역·서비스"
    if "선큰" in n or "개구부" in n:
        return "선큰 마당"
    if "캡슐" in n:
        return "동측 캡슐" if re.search(r"캡슐\s*동|동측", n) else "서측 캡슐"        # GLB 이름 '캡슐 동/서'. 1층 마스터는 '서측 캡슐'이라 1층 출력은 그대로
    if "램프" in n or re.search(r"\bT1\b|T1$", n):
        return "나선 램프 튜브"
    if "빛" in n or re.search(r"\bT2\b|T2$", n):
        return "빛 튜브"
    return None


# ── 가구 (자유 공간에만) ─────────────────────────────────────────────────────────────────────────
def gen_booths(region, rng, obstacles):
    """시장 좌판: U자형 카운터 부스 3.6 × 2.4 m (카운터 깊이 600 mm, 진열 분할선, 안쪽은 판매자 서 있는 공간). 통로 2.4 m, 기둥·튜브·유리벽에서 1.5 m 이상."""
    c, u, v, L, Wd = mg.obb(region)
    free = region.buffer(-1.5)
    if obstacles is not None and not obstacles.is_empty:
        free = free.difference(obstacles)
    out = []
    bw, bd = 3.6, 2.4
    pu, pv = bw + 2.4, bd + 2.4
    for i in range(int((L - 2.4) // pu) + 1):
        for j in range(int((Wd - 2.4) // pv) + 1):
            a, b = -L / 2 + 2.4 + bw / 2 + i * pu, -Wd / 2 + 2.4 + bd / 2 + j * pv
            outer = mg.rect(c, u, v, a, b, bw, bd)
            if not free.contains(outer):
                continue
            inner = mg.rect(c, u, v, a, (b - bd / 2 + 0.6 + b + bd / 2 + 0.2) / 2, bw - 1.2, bd - 0.6 + 0.2)
            ucount = outer.difference(inner)                                               # U자 카운터 (+v쪽이 열림)
            out.append(ucount)
            for k in range(1, 4):                                                          # 진열 분할선
                out.append(mg.line(c, u, v, a - bw / 2 + 0.9 * k, b - bd / 2, a - bw / 2 + 0.9 * k, b - bd / 2 + 0.6))
            for sgn in (-1, 1):
                out.append(mg.line(c, u, v, a + sgn * bw / 2, b - bd / 2 + 0.6 + 0.0, a + sgn * (bw / 2 - 0.6), b - bd / 2 + 0.6))
    return out


def gen_cafe(region, rng, obstacles):
    c, u, v, L, Wd = mg.obb(region)
    free = region.buffer(-0.8)
    if obstacles is not None and not obstacles.is_empty:
        free = free.difference(obstacles)
    out = []
    for i in range(int(L // 3.0)):
        for j in range(int(Wd // 3.0)):
            a, b = -L / 2 + 1.5 + i * 3.0, -Wd / 2 + 1.5 + j * 3.0
            t = mg.circ(c, u, v, a, b, 0.45)
            if free.contains(t.buffer(0.7)):
                out += [t] + [mg.circ(c, u, v, a + 0.75 * math.cos(q), b + 0.75 * math.sin(q), 0.2) for q in (0, 1.57, 3.14, 4.71)]
    return out


def _grid(region, obstacles, pu, pv, size, builder, margin=0.8):
    c, u, v, L, Wd = mg.obb(region)
    free = region.buffer(-margin)
    if obstacles is not None and not obstacles.is_empty:
        free = free.difference(obstacles)
    out = []
    for i in range(int(L // pu)):
        for j in range(int(Wd // pv)):
            a, b = -L / 2 + pu / 2 + i * pu, -Wd / 2 + pv / 2 + j * pv
            shape = builder(c, u, v, a, b)
            if free.contains(shape[0].buffer(size)):
                out += shape
    return out


def gen_rows(region, rng, obstacles):
    return _grid(region, obstacles, 1.0, 0.6, 0.1, lambda c, u, v, a, b: [mg.rect(c, u, v, a, b, 0.45, 0.45)], 1.0)


def gen_plinths(region, rng, obstacles):
    return _grid(region, obstacles, 4.0, 4.0, 0.8, lambda c, u, v, a, b: [mg.rect(c, u, v, a, b, 1.2, 1.2), mg.rect(c, u, v, a, b, 0.7, 0.7)], 1.0)


def gen_sofas(region, rng, obstacles):
    return _grid(region, obstacles, 5.0, 4.0, 0.8, lambda c, u, v, a, b: [mg.rect(c, u, v, a, b, 2.2, 0.85), mg.rect(c, u, v, a, b + 1.2, 1.0, 0.5)], 0.9)


def gen_benches(region, rng, obstacles):
    return _grid(region, obstacles, 4.5, 3.5, 0.7, lambda c, u, v, a, b: [mg.rect(c, u, v, a, b, 2.4, 0.9), mg.circ(c, u, v, a - 0.8, b + 0.75, 0.17), mg.circ(c, u, v, a + 0.8, b + 0.75, 0.17)], 0.9)


def _old(gen):
    """기존 생성기(기하만 반환)를 [(geom,'body')]로 감싼다."""
    return lambda region, rng, obst: [(g_, "body") for g_ in gen(region, rng, obst)]


KEYWORDS = [("시장", FL.market_islands), ("판매", FL.market_islands), ("상업", FL.market_islands), ("F&B", FL.cafe_tables),
            ("문화", _old(gen_rows)), ("엔터", _old(gen_rows)),
            ("업무", FL.office_clusters), ("오피스", FL.office_clusters), ("코워킹", FL.office_clusters),
            ("회의", FL.meeting_table), ("세미나", FL.meeting_table),
            ("전시", FL.exhibition_layout), ("갤러리", FL.exhibition_layout),
            ("공방", FL.workshop_layout), ("스튜디오", FL.workshop_layout), ("실험", FL.workshop_layout), ("연구", FL.workshop_layout),
            ("휴게", FL.lounge_layout), ("라운지", FL.lounge_layout), ("카페", FL.lounge_layout)]
_UNUSED_KEYWORDS = [("시장", gen_booths), ("판매", gen_booths), ("상업", gen_booths), ("F&B", gen_cafe), ("문화", gen_rows), ("엔터", gen_rows),
            ("전시", gen_plinths), ("오피스", lambda r, g, o: mg.gen_staff(r, g)), ("휴게", gen_sofas), ("공방", gen_benches), ("연구", lambda r, g, o: mg.gen_lab(r, g))]


def program_kind(name):
    if name.startswith("코어"):
        return "core"
    if "화장실" in name:
        return "restroom"
    if "필로티" in name:
        return "piloti"
    if "하역" in name:
        return "service"
    if "선큰" in name or "개구부" in name:
        return "sunken"
    if "시장" in name:
        return "hall"
    return "program"


# ── 문 ───────────────────────────────────────────────────────────────────────────────────────────
def door_parts(g, walls):
    """1/4 부채꼴 → (힌지, 닫힌 끝, 열린 끝, 반경, 호 점열). 벽과 가까운 끝이 닫힌 위치다."""
    p = max(pc.iter_polygons(g), key=lambda q: q.area)
    pts = list(p.exterior.coords)[:-1]
    # 힌지: 가장 먼 거리에 가까운 꼭짓점(= 호 위의 점)이 가장 많은 점. 호 중간점이나 호 끝점은 그런 점이 1~2개뿐이다
    def arc_count(i):
        ds = [math.hypot(pts[i][0] - q[0], pts[i][1] - q[1]) for q in pts]
        dm = max(ds)
        return sum(1 for d in ds if d > 0.96 * dm)
    bi = max(range(len(pts)), key=arc_count)
    apex = pts[bi]
    R = max(math.hypot(x - apex[0], y - apex[1]) for x, y in pts)
    arc = [q for q in pts if abs(math.hypot(q[0] - apex[0], q[1] - apex[1]) - R) < 0.06 * R]
    arc.sort(key=lambda q: math.atan2(q[1] - apex[1], q[0] - apex[0]))
    ang = [math.atan2(q[1] - apex[1], q[0] - apex[0]) for q in arc]
    if ang[-1] - ang[0] > math.pi:                                              # ±π 경계를 걸치는 경우
        ang = [a + 2 * math.pi if a < 0 else a for a in ang]
        order = sorted(range(len(arc)), key=lambda i: ang[i])
        arc = [arc[i] for i in order]
    e1, e2 = arc[0], arc[-1]

    def score(e):
        mid = ((apex[0] + e[0]) / 2, (apex[1] + e[1]) / 2)
        if walls.is_empty:
            return 0
        if walls.buffer(0.1).contains(Point(mid)):                                # 문짝이 벽 속에 놓인 쪽은 열린 위치(옆벽에 붙음)
            return -1
        dx, dy = e[0] - apex[0], e[1] - apex[1]
        dl = math.hypot(dx, dy) or 1
        return 1 if walls.buffer(0.05).contains(Point(e[0] + dx / dl * 0.2, e[1] + dy / dl * 0.2)) else 0       # 반대쪽 문설주로 벽이 이어지는 쪽이 닫힌 위치

    closed, opened = (e1, e2) if score(e1) >= score(e2) else (e2, e1)
    if closed == e2:
        arc = list(reversed(arc))
    return apex, closed, opened, R, arc


# ── 튜브·승강기·샤프트 기호 ──────────────────────────────────────────────────────────────────────
def sector_poly(h, o, n, R, steps=20):
    """힌지 h, 닫힌 문짝 끝 o, 스윙 쪽 단위 법선 n → 90° 부채꼴 (문짝 + 스윙 경로)."""
    dx, dy = o[0] - h[0], o[1] - h[1]
    a0 = math.atan2(dy, dx)
    a1 = math.atan2(n[1], n[0])
    da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
    return Polygon([h] + [(h[0] + R * math.cos(a0 + da * i / steps), h[1] + R * math.sin(a0 + da * i / steps)) for i in range(steps + 1)])


def perp_edges(wall_union, u, min_len=0.3):
    """문 방향 u에 수직인 벽 면(선분)들."""
    out = []
    for ln in lines_of(wall_union.boundary):
        c = list(ln.coords)
        for a, b in zip(c, c[1:]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            l = math.hypot(dx, dy)
            if l >= min_len and abs((dx * u[0] + dy * u[1]) / l) < 0.2:
                out.append(LineString([a, b]))
    return out


def jamb_shift(J, dirv, edges, want=0.25):
    """문설주 J가 수직 벽 면에서 250 mm 이상 떨어지도록 dirv 방향으로 밀어야 하는 거리. J 자신의 벽 끝 면(거리 0.02 미만)은 무시한다."""
    use = [e for e in edges if e.distance(Point(J)) > 0.02]
    if not use or min(e.distance(Point(J)) for e in use) >= want:
        return 0.0
    t = 0.0
    while t < 0.8:
        t += 0.01
        if min(e.distance(Point(J[0] + dirv[0] * t, J[1] + dirv[1] * t)) for e in use) >= want:
            return t
    return 0.0


def solve_doors(doors_raw, walls_all, wall_union0, fixtures):
    """문 충돌 해결: 문설주 이격 250 mm → 4가지 방향 시험 → 개구부 상자. 반환: (문 목록, 문설주 채움 벽 목록)."""
    doors = []
    for s, g in doors_raw:
        apex, closed, opened, R, arc = door_parts(g, wall_union0)
        doors.append({"name": s["name"], "J1": apex, "J2": closed, "sector0": g, "swing": g, "open0": opened})
    fillers = []
    fx = fixtures.buffer(0.05) if not fixtures.is_empty else Polygon()
    for d in doors:
        J1, J2 = d["J1"], d["J2"]
        L = math.hypot(J2[0] - J1[0], J2[1] - J1[1])
        u = ((J2[0] - J1[0]) / L, (J2[1] - J1[1]) / L)
        edges = perp_edges(wall_union0, u)
        t1 = jamb_shift(J1, u, edges)
        t2 = jamb_shift(J2, (-u[0], -u[1]), edges)
        if L - t1 - t2 < 0.8:                                                            # 문폭은 0.8 m 아래로 줄이지 않는다
            scale_ = (L - 0.8) / max(t1 + t2, 1e-6)
            t1, t2 = t1 * scale_, t2 * scale_
        N1 = (J1[0] + u[0] * t1, J1[1] + u[1] * t1)
        N2 = (J2[0] - u[0] * t2, J2[1] - u[1] * t2)
        # 벽 두께(문 주변 칸막이·코어벽 중 얇은 것)
        near = [gg for it, gg in walls_all if gg.distance(Point(J1)) < 0.5 and gg.length > 0]
        thk = min([gg.area / (gg.length / 2) for gg in near] + [0.4]) if near else 0.15
        thk = min(max(thk, 0.1), 0.4)
        if t1 > 1e-3:
            fillers.append(LineString([J1, N1]).buffer(thk / 2, cap_style=2))
        if t2 > 1e-3:
            fillers.append(LineString([J2, N2]).buffer(thk / 2, cap_style=2))
        W_ = math.hypot(N2[0] - N1[0], N2[1] - N1[1])
        M = ((N1[0] + N2[0]) / 2, (N1[1] + N2[1]) / 2)
        nrm = (-u[1], u[0])
        depth = max(0.6, 3.0 * thk)
        cutout = mg.rect(M, u, nrm, 0, 0, W_, depth)                                        # 문폭 × (벽 두께 × 3) 개구부 상자
        d.update({"N1": N1, "N2": N2, "W": W_, "M": M, "u": u, "nrm": nrm, "thk": thk, "cutout": cutout,
                  "closure": LineString([N1, N2]).buffer(0.1, cap_style=2), "shifted": (t1 > 1e-3 or t2 > 1e-3),
                  "n0": 1 if ((d["sector0"].centroid.x - M[0]) * nrm[0] + (d["sector0"].centroid.y - M[1]) * nrm[1]) >= 0 else -1})
    filler_union = U(fillers)
    walls_test_base = wall_union0.union(filler_union) if not filler_union.is_empty else wall_union0
    for d in doors:                                                                        # 방향 시험: 원래 방향이 충돌 0이면 유지
        test = walls_test_base.difference(d["cutout"])
        others = U([o["swing"] for o in doors if o is not d])
        cands = []
        for hinge_first in (True, False):
            for sgn in (d["n0"], -d["n0"]):
                h, o = (d["N1"], d["N2"]) if hinge_first else (d["N2"], d["N1"])
                n = (d["nrm"][0] * sgn, d["nrm"][1] * sgn)
                poly = sector_poly(h, o, n, d["W"])
                inset = poly.buffer(-0.02)
                score = inset.intersection(test).area + inset.intersection(others).area + (inset.intersection(fx).area if not fx.is_empty else 0)
                cands.append((score, 0 if (hinge_first and sgn == d["n0"]) else 1, h, o, n, poly))
        cands.sort(key=lambda c: (round(c[0], 5), c[1]))
        score, _, h, o, n, poly = cands[0]
        a0 = math.atan2(o[1] - h[1], o[0] - h[0])
        a1 = math.atan2(n[1], n[0])
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        d.update({"hinge": h, "other": o, "swing_n": n, "swing": poly, "swing_score": score,
                  "leaf_end": (h[0] + n[0] * d["W"], h[1] + n[1] * d["W"]),
                  "arc": [(h[0] + d["W"] * math.cos(a0 + da * i / 20), h[1] + d["W"] * math.sin(a0 + da * i / 20)) for i in range(21)]})
    return doors, fillers


def solve_curtain_doors(lines, anchors, wall_union0, other_swings, fixtures):
    """커튼월 양개 출입문: 앵커 가까이에서 문설주 이격 250 mm, 스윙 충돌 0인 위치·방향을 고른다."""
    result, seen = [], []
    swings_acc = other_swings
    for a in anchors:
        best = None
        for ln in lines:
            d = ln.distance(Point(a))
            if best is None or d < best[0]:
                best = (d, ln)
        if best is None or best[0] > 25:
            continue
        ln = best[1]
        pr0 = ln.project(Point(a))
        found = None
        for shift in (0, 0.5, -0.5, 1.0, -1.0, 1.5, -1.5, 2.0, -2.0, 3.0, -3.0):
            pr = min(max(pr0 + shift, 1.5), ln.length - 1.5)
            p = ln.interpolate(pr)
            p2 = ln.interpolate(min(ln.length, pr + 0.3))
            t = (p2.x - p.x, p2.y - p.y)
            tl = math.hypot(*t)
            if tl < 1e-6:
                continue
            t = (t[0] / tl, t[1] / tl)
            nrm = (-t[1], t[0])
            J1, J2 = (p.x - t[0] * 1.2, p.y - t[1] * 1.2), (p.x + t[0] * 1.2, p.y + t[1] * 1.2)
            edges = perp_edges(wall_union0, t)
            use = [e for e in edges if e.distance(Point(J1)) > 0.02 and e.distance(Point(J2)) > 0.02]
            clear = (min(e.distance(Point(J)) for e in use for J in (J1, J2)) if use else 9.9) >= 0.25
            for sgn in (1, -1):
                n = (nrm[0] * sgn, nrm[1] * sgn)
                s1, s2 = sector_poly(J1, (p.x, p.y), n, 1.2), sector_poly(J2, (p.x, p.y), n, 1.2)
                inset = U([s1, s2]).buffer(-0.02)
                sc = inset.intersection(wall_union0).area + (inset.intersection(swings_acc).area if not swings_acc.is_empty else 0) + (inset.intersection(fixtures).area if not fixtures.is_empty else 0)
                cand = (0 if clear else 1, round(sc, 5), abs(shift), (p.x, p.y), t, n, J1, J2, s1, s2)
                if found is None or cand[:3] < found[:3]:
                    found = cand
            if found and found[0] == 0 and found[1] == 0:
                break
        if found is None:
            continue
        _, sc, _, c, t, n, J1, J2, s1, s2 = found
        if any(math.hypot(c[0] - q[0], c[1] - q[1]) < 4 for q in seen):
            continue
        seen.append(c)
        swings_acc = swings_acc.union(U([s1, s2]))
        result.append({"center": c, "t": t, "n": n, "J1": J1, "J2": J2, "swings": (s1, s2), "score": sc, "cutout": mg.rect(c, t, (-t[1], t[0]), 0, 0, 2.4, 0.6)})
    return result, swings_acc


def tube_symbol(name, g, hall_pt, rng):
    sh = shell_of(g)
    c = sh.centroid
    R = rad_of(sh)
    Rin = max(R - 0.18, 0.2)
    heavy, light, arrows = [], [], []
    carl, xl = [], []                                                                         # 승강기 카·문 눈금(4단계) / 샤프트 X(5단계)
    code = re.sub(r"^튜브\s*", "", name)
    is_t1 = "램프" in name or code.startswith("T1")
    is_t2 = "빛" in name or code.startswith("T2")
    is_cap = "캡슐" in name
    is_shaft = "샤프트" in name or code.startswith("M")
    is_elev = (not is_t1 and not is_t2 and not is_cap and not is_shaft) and ("승강기" in name or re.search("EV|FR|PL|T3|T4", name))
    if is_t1:
        ro, ri = R - 0.5, R - 0.5 - 2.4
        light += [Point(c.x, c.y).buffer(ro, 48).boundary, Point(c.x, c.y).buffer(ri, 48).boundary]
        for k in range(24):
            a = math.radians(15 * k)
            light.append(LineString([(c.x + ri * math.cos(a), c.y + ri * math.sin(a)), (c.x + ro * math.cos(a), c.y + ro * math.sin(a))]))
        arrows.append([(c.x + (ro - 0.6 - (ro - ri - 1.2) * i / 260) * math.cos(math.radians(i)),
                        c.y + (ro - 0.6 - (ro - ri - 1.2) * i / 260) * math.sin(math.radians(i))) for i in range(0, 261)])
    elif is_t2:
        light += [Point(c.x, c.y).buffer(R - 1.0, 48).boundary, Point(c.x, c.y).buffer(R * 0.35, 36).boundary]
        for k in range(12):
            a = math.radians(30 * k)
            light.append(LineString([(c.x + R * 0.35 * math.cos(a), c.y + R * 0.35 * math.sin(a)), (c.x + (R - 1.0) * math.cos(a), c.y + (R - 1.0) * math.sin(a))]))
    elif is_elev:
        two = R > 3.5
        half = min(1.3, Rin * 0.42) if two else Rin * 0.68
        # 문 방향: 홀(시장 홀 중심) 쪽에 가장 가까운 축
        dx, dy = (hall_pt[0] - c.x, hall_pt[1] - c.y) if hall_pt else (0, -1)
        ax = (1 if dx > 0 else -1, 0) if abs(dx) > abs(dy) else (0, 1 if dy > 0 else -1)
        spots = [(-half - 0.1, 0), (half + 0.1, 0)] if two else [(0, 0)]
        for sx, sy in spots:
            x0, y0 = c.x + sx, c.y + sy
            hoist = box(x0 - half, y0 - half, x0 + half, y0 + half)
            car = box(x0 - half + 0.15, y0 - half + 0.15, x0 + half - 0.15, y0 + half - 0.15)
            cb = car.bounds
            carl += [hoist.boundary, car.boundary]
            xl += [LineString([(cb[0], cb[1]), (cb[2], cb[3])]), LineString([(cb[0], cb[3]), (cb[2], cb[1])])]
            ex, ey = x0 + ax[0] * (half - 0.15), y0 + ax[1] * (half - 0.15)                  # 중앙 개폐문 눈금 (홀 쪽)
            px, py = -ax[1], ax[0]
            carl += [LineString([(ex - px * 0.45, ey - py * 0.45), (ex + px * 0.45, ey + py * 0.45)]),
                     LineString([(ex, ey), (ex - ax[0] * 0.3, ey - ax[1] * 0.3)])]
    elif is_shaft:
        r45 = Rin * math.cos(math.radians(45))                                                # X 끝은 안쪽 원 둘레 ±45° 위에서 끝난다
        carl += [Point(c.x, c.y).buffer(Rin, 48).boundary]
        xl += [LineString([(c.x - r45, c.y - r45), (c.x + r45, c.y + r45)]), LineString([(c.x - r45, c.y + r45), (c.x + r45, c.y - r45)])]
    return {"heavy": heavy, "light": light, "car": carl, "x": xl, "arrows": arrows, "c": (c.x, c.y), "R": R, "Rin": Rin}


# ── 코어: U자형 계단 ─────────────────────────────────────────────────────────────────────────────
def stair_core(zone, door_apexes, rng, walls_in=None):
    """계단참(1.4 m, 문 쪽) + 평행한 2개 계단단(중앙 이중 난간 150 mm), 챌판선은 진행 방향으로만, 30° 이중 절단선과 UP 화살표."""
    inner = zone.buffer(-0.25)
    if walls_in is not None and not walls_in.is_empty:                                  # 모델의 안쪽 칸막이(부속실/계단실)로 나뉜 가장 큰 조각이 계단실이다
        pieces = [p for p in pc.iter_polygons(zone.difference(walls_in.buffer(0.08))) if p.area > 6.0]
        if pieces:
            inner = max(pieces, key=lambda p: p.area).buffer(-0.12)
    c, u, v, L, Wd = mg.obb(inner)
    best = None
    for ax, half_ax in ((u, L / 2), (v, Wd / 2)):
        for sgn in (1, -1):
            if door_apexes:
                d = min(((a[0] - c[0]) * ax[0] + (a[1] - c[1]) * ax[1]) * sgn for a in door_apexes)
                d = -d
            else:
                d = 0
            if best is None or d < best[0]:
                best = (d, ax, sgn)
    _, ax, sgn = best                                                                    # 문에 가장 가까운 끝이 계단참
    if ax is u:
        Lf, Wg, gx = L, Wd, v
    else:
        Lf, Wg, gx = Wd, L, u
    f = (-ax[0] * sgn, -ax[1] * sgn)                                                     # 계단참 → 먼 끝
    P0 = (c[0] + ax[0] * sgn * (Lf / 2 - 1.4), c[1] + ax[1] * sgn * (Lf / 2 - 1.4))      # 계단참/계단단 경계 중앙

    def pt(s, t):
        return (P0[0] + f[0] * s + gx[0] * t, P0[1] + f[1] * s + gx[1] * t)

    flight = Lf - 1.4 - 1.2
    light, brk = [], []
    s_b = 0.6 * flight
    for sign, up in ((1, True), (-1, False)):
        t0, t1 = (0.075, Wg / 2 - 0.05) if sign > 0 else (-Wg / 2 + 0.05, -0.075)
        s = 0.3
        while s < flight - 0.05:
            if not (up and s > s_b):                                                      # 절단선 너머는 지운다
                light.append(LineString([pt(s, t0), pt(s, t1)]))
            s += 0.3
        for t in (0.075 * sign,):                                                        # 중앙 이중 난간 (150 mm)
            light.append(LineString([pt(0, t), pt(flight if not up else s_b, t)]))
    tan30 = math.tan(math.radians(30))
    for off in (0.0, 0.28):                                                               # 30° 이중 절단선
        brk.append(LineString([pt(s_b + off, 0.075), pt(s_b + off + (Wg / 2 - 0.125) * tan30, Wg / 2 - 0.05)]))
    arrow = (pt(-0.3, Wg / 4), pt(1.5, Wg / 4))
    landing = Polygon([pt(-1.4, -Wg / 2), pt(-1.4, Wg / 2), pt(0, Wg / 2), pt(0, -Wg / 2)])
    return {"light": light, "break": brk, "arrow": arrow, "up_text": pt(-0.95, Wg / 4), "landing": landing, "fdir": f}


# ── 커튼월 ───────────────────────────────────────────────────────────────────────────────────────
def curtain_lines(hall, covered):
    """시장 홀의 바깥 윤곽 + 구멍(필로티·하역 등과의 경계)에서 벽·튜브·코어와 맞닿은 부분을 뺀 선들."""
    rings = []
    for p in pc.iter_polygons(hall):
        rings.append(p.exterior)
        rings += list(p.interiors)
    bnd = unary_union(rings)
    if not covered.is_empty:
        bnd = bnd.difference(covered)
    return [ln for ln in lines_of(bnd) if ln.length > 0.8]


def curtain_doors(lines, anchors):
    """앵커(출입구·광장 중심 등)에서 가장 가까운 커튼월 지점에 2.4 m 양개문 개구를 낸다. 반환: 문 정의 목록, 개구 영역."""
    doors, gaps, seen = [], [], []
    for a in anchors:
        best = None
        for ln in lines:
            d = ln.distance(Point(a))
            if best is None or d < best[0]:
                best = (d, ln)
        if best is None or best[0] > 25:
            continue
        ln = best[1]
        pr = ln.project(Point(a))
        p = ln.interpolate(pr)
        if any(math.hypot(p.x - q[0], p.y - q[1]) < 4 for q in seen):
            continue
        seen.append((p.x, p.y))
        p2 = ln.interpolate(min(ln.length, pr + 0.3))
        t = (p2.x - p.x, p2.y - p.y)
        tl = math.hypot(*t)
        if tl < 1e-6:
            p2 = ln.interpolate(max(0, pr - 0.3))
            t = (p.x - p2.x, p.y - p2.y)
            tl = math.hypot(*t) or 1
        t = (t[0] / tl, t[1] / tl)
        doors.append(((p.x, p.y), t, (-t[1], t[0])))
        gaps.append(Point(p.x, p.y).buffer(1.25))
    return doors, U(gaps)


# ── 조경 설계 ────────────────────────────────────────────────────────────────────────────────────
def bezier(A, B, rng, bulge=0.2, n=48):
    dx, dy = B[0] - A[0], B[1] - A[1]
    d = math.hypot(dx, dy) or 1
    nx, ny = -dy / d, dx / d
    s = rng.choice([-1, 1])
    c1 = (A[0] + dx * 0.33 + nx * d * bulge * s, A[1] + dy * 0.33 + ny * d * bulge * s)
    c2 = (A[0] + dx * 0.66 - nx * d * bulge * s * 0.6, A[1] + dy * 0.66 - ny * d * bulge * s * 0.6)
    pts = []
    for i in range(n + 1):
        t = i / n
        pts.append(((1 - t) ** 3 * A[0] + 3 * (1 - t) ** 2 * t * c1[0] + 3 * (1 - t) * t ** 2 * c2[0] + t ** 3 * B[0],
                    (1 - t) ** 3 * A[1] + 3 * (1 - t) ** 2 * t * c1[1] + 3 * (1 - t) * t ** 2 * c2[1] + t ** 3 * B[1]))
    return LineString(pts)


def place_trees(region, rng, min_d, rmin, rmax, avoid=None, limit=40):
    out = []
    minx, miny, maxx, maxy = region.bounds
    tries = 0
    while len(out) < limit and tries < 3000:
        tries += 1
        p = Point(rng.uniform(minx, maxx), rng.uniform(miny, maxy))
        r = rng.uniform(rmin, rmax)
        if not region.buffer(-r * 0.6).contains(p):
            continue
        if avoid is not None and not avoid.is_empty and avoid.distance(p) < r:
            continue
        if any(math.hypot(p.x - q[0], p.y - q[1]) < max(min_d, (r + q[2]) * 1.1) for q in out):
            continue
        out.append((p.x, p.y, r))
    return out


def draw_trees(cv, trees, rng, weight=0.06):
    for (x, y, r) in trees:
        if cv.clean:                                                                        # C-T13A: 흔들리는 윤곽·가지·로제트 대신 정돈된 수관 기호(참 원 + 줄기 점)
            mg.tree_shapes(x, y, r, rng)                                                    # 난수열 소비는 기존과 같게(수목 위치 불변), 결과는 버린다
            cv.add("plants", '<path d="%s" fill="#ffffff" fill-opacity="0.55" stroke="#C4C4C4" stroke-width="%.4f"/>' % (cv.path_poly(Point(x, y).buffer(r, 24), "plants"), cv.lw(weight)))
            cv.dots("plants", [(x, y)], 0.10, "#C4C4C4", 1.0)                                # 줄기 점(수관 원 하나 + 중심점: 겹치는 안쪽 원 제거)
            continue
        sh = mg.tree_shapes(x, y, r, rng)
        for ring in sh["rings"]:
            cv.add("plants", '<path d="M%s Z" fill="#ffffff" fill-opacity="0.55" stroke="#CCCCCC" stroke-width="%.4f" stroke-linejoin="round"/>' %
                   (" L".join("%.3f,%.3f" % (cv.X(px), cv.Y(py)) for px, py in ring), cv.lw(weight)))      # 6단계 식재선
        for ln in sh["lines"]:
            cv.stroke_line("plants", ln, 0.06, "#B0B0B0")


def design_site(cv, k, rng, S, F, B, sunken_regions, lawn, ent_pts, service_zone, plaza_pt, bx):
    """대지 경계 안쪽을 설계한다. 반환: 점검용 통계."""
    stats = {}
    thin = (lambda pts_: pts_[::3]) if cv.clean else (lambda pts_: pts_)                   # C-T13A: 조경 점묘를 1/3로 솎는다(난수 소비·수목 위치는 그대로)
    bx0, by0, bx1, by1 = bx
    keep_out = U([F.buffer(1.5)] + [g.buffer(1.5) for g in sunken_regions])
    open_site = S.difference(keep_out)
    # 서쪽 삼각형 공원
    W = open_site.intersection(box(S.bounds[0] - 1, S.bounds[1] - 1, bx0 - 2.0, S.bounds[3] + 1))
    if not lawn.is_empty:
        W = W.difference(lawn.buffer(1.0))
    A1, B1 = (S.bounds[0] + 8.0, 13.0), (bx0 - 1.2, 13.7)
    A2, B2 = (-37.0, -2.5), (bx0 - 1.2, 2.5)
    A3, B3 = (-14.1, 51.0), (bx0 - 1.2, 25.0)
    paths = [bezier(A1, B1, rng, 0.16), bezier(A2, B2, rng, 0.18), bezier(A3, B3, rng, 0.2)]
    mid = paths[0].interpolate(0.55, normalized=True)
    paths.append(bezier((mid.x, mid.y), (-14.0, 1.5), rng, 0.18))                      # 선큰 마당으로 가는 지선
    pp = []
    for ln in paths:
        poly = ln.buffer(1.6, cap_style=1).intersection(S).difference(F.buffer(0.3)).difference(U(sunken_regions).buffer(0.2))
        pp.append(poly)
        for e in pc.iter_polygons(poly):
            cv.stroke_poly("landscape", Polygon(e.exterior), 0.10, "#555", fill="#ffffff")
        cv.dots("landscape", thin(mg.stipple_points(poly, 0.55, 0.3, rng)), 0.05, "#777", 0.8)
    path_union = U(pp)
    free = W.difference(path_union.buffer(0.9))
    free = free.buffer(-1.2).buffer(1.2)
    islands = [p for p in pc.iter_polygons(free) if p.area > 25]
    n_tree = 0
    placed_trees = []
    for isl in islands:
        smooth = isl.buffer(-0.4).buffer(0.4)
        cv.stroke_poly("landscape", smooth, 0.12, "#777")
        cv.dots("landscape", thin(mg.stipple_points(smooth.buffer(-0.3), 0.5, 0.4, rng)), 0.06, "#888", 0.85)
        trees = place_trees(smooth, rng, 8.0, 2.0, 4.5, None, 6)
        placed_trees += trees
        for (x, y, r) in mg_shrubs(smooth.buffer(-0.5), rng, [(t[0], t[1], t[2]) for t in trees]):
            if cv.clean:
                mg.wobble_ring(x, y, r, rng, 0.08, 16)                                       # 난수열 소비 유지
                cv.stroke_poly("plants", Point(x, y).buffer(r, 16), 0.10, "#666")             # 관목: 참 원
            else:
                cv.stroke_line("plants", mg.wobble_ring(x, y, r, rng, 0.08, 16), 0.10, "#666")
        draw_trees(cv, trees, rng)
        n_tree += len(trees)
    stats["park_paths"] = len(paths)
    stats["planting_islands"] = len(islands)
    stats["park_trees"] = n_tree
    # 벤치: 산책로를 따라 15 m마다
    nb = 0
    for i, ln in enumerate(paths):
        d = 9.0
        side = 1
        while d < ln.length - 4:
            p, p2 = ln.interpolate(d), ln.interpolate(d + 0.5)
            tx, ty = p2.x - p.x, p2.y - p.y
            tl = math.hypot(tx, ty) or 1
            tx, ty = tx / tl, ty / tl
            nx, ny = -ty * side, tx * side
            cx_, cy_ = p.x + nx * 2.5, p.y + ny * 2.5
            bench = Polygon([(cx_ - tx * 1.2 - nx * 0.25, cy_ - ty * 1.2 - ny * 0.25), (cx_ + tx * 1.2 - nx * 0.25, cy_ + ty * 1.2 - ny * 0.25),
                             (cx_ + tx * 1.2 + nx * 0.25, cy_ + ty * 1.2 + ny * 0.25), (cx_ - tx * 1.2 + nx * 0.25, cy_ - ty * 1.2 + ny * 0.25)])
            if S.contains(bench) and not F.buffer(0.5).intersects(bench):
                cv.stroke_poly("landscape", bench, 0.12, "#555", fill="#ffffff")
                nb += 1
            d += 15.0
            side = -side
    stats["benches"] = nb
    # 남측 진입 광장: 3 m 모듈 석재 포장 + 단 테라스 + 횡단보도
    P = open_site.intersection(box(bx0 - 8, S.bounds[1] - 2, bx1 - 6, by0 - 1.5)).difference(U(sunken_regions).buffer(1.0))
    P = P.difference(path_union.buffer(0.5))
    if not P.is_empty:
        cv.stroke_poly("landscape", P, 0.10, "#888", fill="#FBFBFB")
        minx, miny, maxx, maxy = P.bounds
        x = math.floor(minx / 3.0) * 3.0
        while x < maxx:
            for ln in lines_of(LineString([(x, miny), (x, maxy)]).intersection(P)):
                cv.stroke_line("landscape", list(ln.coords), 0.05, "#CFCFCF")
            x += 3.0
        y = math.floor(miny / 3.0) * 3.0
        while y < maxy:
            for ln in lines_of(LineString([(minx, y), (maxx, y)]).intersection(P)):
                cv.stroke_line("landscape", list(ln.coords), 0.05, "#CFCFCF")
            y += 3.0
        for t_ in range(4):                                                              # 단 테라스: 건물 남쪽 필로티를 향해 올라가는 단
            yy = by0 - 1.8 - 1.2 * t_
            for ln in lines_of(LineString([(bx0 + 9, yy), (bx0 + 31, yy)]).intersection(P)):
                cv.stroke_line("landscape", list(ln.coords), 0.14, "#555")
                for q in range(0, int(ln.length), 3):
                    p = ln.interpolate(q)
                    cv.stroke_line("landscape", [(p.x, p.y), (p.x, p.y - 0.3)], 0.08, "#777")
        stats["south_plaza_m2"] = round(P.area)
    south_pt = S.exterior.interpolate(S.exterior.project(Point(bx0 + 24, S.bounds[1] - 0.5)))
    nx_, ny_ = (south_pt.x - S.centroid.x), (south_pt.y - S.centroid.y)
    nl = math.hypot(nx_, ny_) or 1
    nx_, ny_ = nx_ / nl, ny_ / nl
    for i in range(-5, 6):                                                               # 횡단보도 줄무늬(도로 쪽)
        sx_, sy_ = south_pt.x + (-ny_) * i * 1.0, south_pt.y + nx_ * i * 1.0
        stripe = Polygon([(sx_ - 0.25 * (-ny_), sy_ - 0.25 * nx_), (sx_ + 0.25 * (-ny_), sy_ + 0.25 * nx_),
                          (sx_ + 0.25 * (-ny_) + nx_ * 5.0, sy_ + 0.25 * nx_ + ny_ * 5.0), (sx_ - 0.25 * (-ny_) + nx_ * 5.0, sy_ - 0.25 * nx_ + ny_ * 5.0)])
        cv.stroke_poly("landscape", stripe, 0.06, "#888", fill="#D8D8D8")
    # 북·동측 보행로 + 가로수
    ring = S.difference(S.buffer(-3.5))
    north = ring.intersection(box(S.bounds[0], by1 + 0.5, S.bounds[2] + 1, S.bounds[3] + 1)).difference(F.buffer(0.5))
    east = ring.intersection(box(bx1 + 0.5, S.bounds[1], S.bounds[2] + 1, S.bounds[3] + 1)).difference(F.buffer(0.5))
    drive_x0, drive_x1 = 48.0, 54.0
    drive = box(drive_x0, by1 + 0.5, drive_x1, S.bounds[3] + 3)
    walk = U([north, east]).difference(drive)
    for e in pc.iter_polygons(walk):
        cv.stroke_poly("landscape", e, 0.10, "#666", fill="#F6F6F6")
        cv.dots("landscape", thin(mg.stipple_points(e, 0.7, 0.3, rng)), 0.05, "#999", 0.8)
    center = S.buffer(-1.75).exterior
    street = []
    d = 0.0
    while d < center.length:
        p = center.interpolate(d)
        if (north.buffer(0.3).contains(p) or east.buffer(0.3).contains(p)) and not drive.buffer(2.5).contains(p) and not F.buffer(2.0).contains(p):
            if not street or all(math.hypot(p.x - q[0], p.y - q[1]) > 8.0 for q in street):
                street.append((p.x, p.y, 2.2))
        d += 1.0
    draw_trees(cv, street, rng)
    stats["street_trees"] = len(street)
    # 서비스 진입로 (6 m 연석 절단 + 진입/진출 화살표 + 회전 반경)
    y_top = S.bounds[3] + 0.5
    drv_poly = box(drive_x0, by1 + 0.7, drive_x1, y_top)
    cv.stroke_poly("landscape", drv_poly, 0.10, "#444", fill="#F2F2F2")
    for xx in (drive_x0, drive_x1):
        cv.stroke_line("landscape", [(xx, by1 + 0.7), (xx, y_top + 2)], 0.20, "#222")
    ytb = min(S.bounds[3] - 0.8, by1 + 6.0)
    for xx, sg in ((drive_x0 + 1.5, -1), (drive_x1 - 1.5, 1)):                         # 진입(남쪽으로) / 진출(북쪽으로)
        a, b = (xx, ytb + 1.2 * (-sg)), (xx, ytb - 1.2 * (-sg))
        cv.stroke_line("landscape", [a, b], 0.16, "#222")
        for da in (0.55, -0.55):
            cv.stroke_line("landscape", [b, (b[0] + math.sin(da) * 0.5, b[1] + (0.6 if b[1] < a[1] else -0.6))], 0.16, "#222")
    for cx0, a0, a1 in ((drive_x0 - 3.0, 0, 90), (drive_x1 + 3.0, 90, 180)):            # 회전 반경 호 (r = 3 m)
        cv.stroke_line("landscape", [(cx0 + 3.0 * math.cos(math.radians(a0 + (a1 - a0) * i / 16)), (by1 + 0.7 + 6.0) + 3.0 * math.sin(math.radians(a0 + (a1 - a0) * i / 16))) for i in range(17)], 0.16, "#222")
    stats["service_drive_m"] = [drive_x0, drive_x1]
    return stats, P


def mg_shrubs(region, rng, trees):
    out = []
    if region.is_empty:
        return out
    minx, miny, maxx, maxy = region.bounds
    n = int(region.area / 7.0)
    tries = 0
    while len(out) < n and tries < n * 30:
        tries += 1
        p = Point(rng.uniform(minx, maxx), rng.uniform(miny, maxy))
        if region.contains(p) and all(math.hypot(p.x - t[0], p.y - t[1]) > t[2] + 0.5 for t in trees) and all(math.hypot(p.x - q[0], p.y - q[1]) > 1.5 for q in out):
            out.append((p.x, p.y, rng.uniform(0.35, 0.85)))
    return out


# ── 메인 ─────────────────────────────────────────────────────────────────────────────────────────
# ── C-T13: V2 프로그램 컨셉 도면 보조 함수 ──────────────────────────────────────────────────
PARENT_TITLE = {"MARKET": "시장 홀", "PILOTI": "필로티", "SERVICE": "하역·서비스", "CAPSULE": "서측 캡슐"}


def _arrow(cv, layer, p, ang, mm, col, size=1.3, extra=""):
    for da in (2.6, -2.6):
        cv.stroke_line(layer, [p, (p[0] - size * math.cos(ang + da / 3), p[1] - size * math.sin(ang + da / 3))], mm, col, extra)


def draw_program_overlay(cv, k, plan, footprint, wall_union, shell_tubes, dash, grid_u=None):
    """V2: 비가구 구획(M06·P01) 옅은 바닥, 하위 구획 경계(점선), 공공·서비스 흐름 화살표.
    clean 모드(C-T13A): 공유 경계를 한 번만 그리고(노드 병합) 래스터 계단을 직선으로 단순화, 바닥 채움은 열림·닫힘으로 매끈하게."""
    from shapely.ops import linemerge
    z = plan["zones"]
    clean = getattr(cv, "clean", False)
    for key in ("M06", "P01"):
        g_ = z[key]
        if clean:
            g_ = plan["m06_vector"] if key == "M06" else plan["p_corr"]                   # 바탕 채움은 래스터 잔여 띠가 섞이기 전의 벡터 복도(둥근 링·직교 띠)로 — 구획·면적 계산은 그대로
        for p_ in PP.polys(g_):
            cv.add("ground", '<path d="%s" fill="#F4F4F4" fill-rule="evenodd" stroke="none"/>' % cv.path_poly(p_, "ground"))
    skip = U([footprint.exterior.buffer(0.5), wall_union.buffer(0.3), shell_tubes.buffer(0.3)])
    if clean:
        sm = {zid: (g.buffer(1.0).buffer(-2.0).buffer(1.0) if zid[0] in "MP" else g) for zid, g in z.items() if not g.is_empty and zid != "S04"}   # 래스터 계단을 둥근 윤곽으로 다듬은 구획의 경계만 그린다(그림 전용)
        merged = U([g.boundary for zid, g in sm.items() if not g.is_empty])
        pieces = lines_of(linemerge(merged) if merged.geom_type != "LineString" else merged)
        skip2 = U([skip] + ([grid_u.buffer(0.2)] if grid_u is not None else []))              # 구조 격자선과 겹치는 구간은 격자선이 이미 그린다
        cand = []
        for ln in pieces:
            for q in lines_of(ln.difference(skip2)):
                q = q.simplify(0.8)
                if q.length >= 7.0:                                                          # 래스터 분할이 만든 7 m 미만 조각(짧은 사선 대시)은 그리지 않는다 — 긴 경계만 남긴다
                    cand.append(q)
        orth = []                                                                            # 건축 축(0°/90°)에 맞는 긴 직선 구간만: 사선 파편은 그리지 않는다
        for q in cand:
            c_ = list(q.coords)
            for a_, b_ in zip(c_, c_[1:]):
                dx_, dy_ = b_[0] - a_[0], b_[1] - a_[1]
                ln_ = math.hypot(dx_, dy_)
                th_ = abs(math.degrees(math.atan2(dy_, dx_))) % 90.0
                if ln_ >= 6.0 and min(th_, 90.0 - th_) <= 4.0:
                    ax_ = (dx_ if abs(dx_) > abs(dy_) else 0.0, dy_ if abs(dy_) >= abs(dx_) else 0.0)
                    orth.append(LineString([a_, (a_[0] + ax_[0], a_[1] + ax_[1])]))            # 축에 정확히 맞춘 직선
        cand = orth
        kept = []
        for q in sorted(cand, key=lambda l: -l.length):                                      # 긴 선부터: 이미 그린 선에서 0.2 m 안의 평행 중복 구간은 건너뛴다
            rest_ = q.difference(U(kept).buffer(0.2)) if kept else q
            for r_ in lines_of(rest_):
                if r_.length >= 5.0:
                    kept.append(r_)
        for q in kept:
            mg.Canvas.stroke_line(cv, "furn", list(q.coords), 0.055, "#8A8A8A", dash)
    else:
        for zid, g in z.items():
            if g.is_empty or zid == "S04":
                continue
            for ln in PP.lines(g.boundary.simplify(0.8).difference(skip)):                  # 래스터 계단을 단순화해 가는 점선으로
                if ln.length > 1.0:
                    cv.stroke_line("furn", list(ln.coords), 0.07, "#888", dash)
    for fl in plan["flows"]:
        ln = fl["line"]
        ex = "" if fl["kind"] == "public" else dash
        if clean:
            mg.Canvas.stroke_line(cv, "symbols", list(ln.coords), 0.08, "#777777", ex)       # ④ 프로그램 표시: 가구(0.08 #666)보다 옅게
        else:
            cv.stroke_line("symbols", list(ln.coords), 0.12, "#444", ex)
        n = max(1, int(ln.length // 9.0))
        for i in range(1, n + 1):
            d0 = min(ln.length, i * ln.length / n)
            a, b = ln.interpolate(max(0.0, d0 - 0.4)), ln.interpolate(d0)
            if clean:
                for da in (2.6, -2.6):
                    ang = math.atan2(b.y - a.y, b.x - a.x)
                    mg.Canvas.stroke_line(cv, "symbols", [(b.x, b.y), (b.x - 1.2 * math.cos(ang + da / 3), b.y - 1.2 * math.sin(ang + da / 3))], 0.08, "#777777", ex)
            else:
                _arrow(cv, "symbols", (b.x, b.y), math.atan2(b.y - a.y, b.x - a.x), 0.12, "#444", 1.2, ex)


def draw_zone_chips(cv, k, plan, furn_union, cols_u, wall_union, tubes_u):
    """하위 구획 ID(M01…)를 빈 바닥 한가운데에 둔다. 들어갈 빈자리가 없으면 흰 배경 상자로 차폐(AGENTS.md §3.1)."""
    from shapely.ops import polylabel
    pt_m = 5.0 * 0.3528 * k
    cw, ch = 3.8 * k, 2.1 * k
    avoid = U([furn_union.buffer(0.3), cols_u.buffer(0.3), wall_union.buffer(0.2), tubes_u.buffer(0.2)])
    chips = []
    for zid, g in plan["zones"].items():
        parts = sorted([p_ for p_ in PP.polys(g) if p_.area >= (5.0 if zid in ("C04", "S04", "C03") else 14.0)], key=lambda p_: -p_.area)
        for i, p_ in enumerate(parts):
            if i > 0 and p_.area < 70:
                continue
            free = p_.difference(avoid)
            pick = None
            for q in sorted(PP.polys(free), key=lambda q_: -q_.area):
                if q.area < cw * ch * 1.3:
                    continue
                pt = polylabel(q, tolerance=0.1)
                bx = box(pt.x - cw / 2, pt.y - ch / 2, pt.x + cw / 2, pt.y + ch / 2)
                if q.buffer(0.001).contains(bx):
                    pick = (pt, bx, False)
                    break
            if pick is None:
                pt = p_.representative_point()
                pick = (pt, box(pt.x - cw / 2, pt.y - ch / 2, pt.x + cw / 2, pt.y + ch / 2), True)
            pt, bx, fb = pick
            cv.add("num", '<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" rx="%.3f" fill="#ffffff" fill-opacity="%s" stroke="%s" stroke-width="%.4f"/>' %
                   (cv.X(pt.x) - cw / 2, cv.Y(pt.y) - ch / 2, cw, ch, 0.35 * k, "1.0" if fb else "0.96", "#8A8A8A" if getattr(cv, "clean", False) else "#666", cv.lw(0.06 if getattr(cv, "clean", False) else 0.08)))
            cv.add("num", '<text x="%.3f" y="%.3f" font-family="%s" font-size="%.3f" font-weight="bold" fill="#222" text-anchor="middle">%s</text>' %
                   (cv.X(pt.x), cv.Y(pt.y) + pt_m * 0.35, mg.FONT, pt_m, zid))
            chips.append({"id": zid, "x": round(pt.x, 2), "y": round(pt.y, 2), "box": bx, "white_box_fallback": fb})
    return chips


def program_legend(cv, plan, qa_, legend, num_of, floor, scale, program, bnd):
    """V2 범례판: 18개 하위 프로그램(ID·이름·폴리곤 면적), 나머지 번호 항목, 기호 설명, 북쪽, 주의."""
    z = plan["zones"]
    k = scale / 1000.0
    x0, w = A3[0] - 98.0, 90.0                                                          # 우측 여백판(동측 맥락 위): 서측 공원·필로티를 가리지 않는다
    row = 4.1
    n_rows = 18 + 4 + 1 + len(legend) + 1 + 4
    total = 20 + n_rows * row + 40
    y0 = A3[1] - 6.0 - total
    cv.add("legend", '<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" fill="#ffffff" fill-opacity="%s" stroke="#999" stroke-width="%.4f"/>' % (x0 * k, y0 * k, w * k, total * k, "1.0" if getattr(cv, "clean", False) else "0.96", 0.1 * k))
    cv.text("legend", x0 + 4, y0 + 7, "1층 프로그램 컨셉 V2-%s · 1:%d" % (program, scale), 9, "bold", "#111")
    cv.text("legend", x0 + 4, y0 + 12, "실모델 기반 계획 후보 · 사용자 승인 전 · 1층 최종 확정 아님", 5.0, "normal", "#777")
    y = y0 + 19
    for par in ("MARKET", "PILOTI", "SERVICE", "CAPSULE"):
        ids = [i for i in PP.PROGRAMS if PP.PROGRAMS[i][1] == par]
        tot = sum(z[i].area for i in ids)
        cv.text("legend", x0 + 4, y, "%s  (구획 합계 %s ㎡)" % (PARENT_TITLE[par], format(int(round(tot)), ",")), 6.2, "bold", "#222")
        y += row
        for i in ids:
            cv.add("legend", '<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" rx="%.3f" fill="#fff" stroke="#666" stroke-width="%.4f"/>' % ((x0 + 4) * k, (y - 2.6) * k, 8.4 * k, 3.4 * k, 0.5 * k, 0.08 * k))
            cv.text("legend", x0 + 4 + 4.2, y, i, 5.2, "bold", "#222", "middle")
            cv.text("legend", x0 + 15, y, PP.PROGRAMS[i][0], 6.0, "normal", "#333")
            cv.text("legend", x0 + w - 4, y, "%s ㎡" % format(int(round(z[i].area)), ","), 6.0, "normal", "#555", "end")
            y += row
    cv.text("legend", x0 + 4, y, "번호 항목", 6.2, "bold", "#222")
    y += row
    for n in legend:
        cv.text("legend", x0 + 8, y, str(num_of[n]), 6.0, "normal", "#222", "middle")
        cv.text("legend", x0 + 15, y, n, 6.0, "normal", "#333")
        y += row
    cv.text("legend", x0 + 4, y, "기호", 6.2, "bold", "#222")
    y += row
    d_ = 'stroke-dasharray="%.3f,%.3f"' % (1.6 * k, 1.0 * k)
    cv.add("legend", '<path d="M%.3f,%.3f h%.3f" stroke="#444" stroke-width="%.4f" fill="none"/>' % ((x0 + 5) * k, (y - 1.0) * k, 8 * k, 0.12 * k))
    cv.text("legend", x0 + 15, y, "공공 흐름 (계획 후보)", 5.6, "normal", "#333")
    y += row
    cv.add("legend", '<path d="M%.3f,%.3f h%.3f" stroke="#444" stroke-width="%.4f" fill="none" %s/>' % ((x0 + 5) * k, (y - 1.0) * k, 8 * k, 0.12 * k, d_))
    cv.text("legend", x0 + 15, y, "서비스·보조 흐름 / 출입구 후보 (미승인, 모델에 문 없음)", 5.6, "normal", "#333")
    y += row
    ncx, ncy, nr = x0 + 12, y + 8, 5.0
    cv.add("legend", '<circle cx="%.3f" cy="%.3f" r="%.3f" fill="none" stroke="#555" stroke-width="%.4f"/>' % (ncx * k, ncy * k, nr * k, 0.2 * k))
    na = math.radians(bnd["frame"].get("north_deg", bnd["frame"].get("theta_deg", 0.0)))
    cv.add("legend", '<line x1="%.3f" y1="%.3f" x2="%.3f" y2="%.3f" stroke="#555" stroke-width="%.4f"/>' % (ncx * k, ncy * k, (ncx + math.sin(na) * (nr + 3)) * k, (ncy - math.cos(na) * (nr + 3)) * k, 0.25 * k))
    cv.text("legend", x0 + 26, ncy - 2.0, "면적은 구획 폴리곤 계산값(기둥 점유 포함)이다.", 4.6, "normal", "#777")
    cv.text("legend", x0 + 26, ncy + 1.6, "가구·수목은 설명용 표현이며 설계 데이터가 아니다.", 4.6, "normal", "#777")
    cv.text("legend", x0 + 26, ncy + 5.2, "soft_target 비율은 목표일 뿐 측정값이 아니다.", 4.6, "normal", "#777")


def program_check(plan, qa_, chips, furn_all, drawn_cols, program):
    from collections import Counter
    z = plan["zones"]
    par_tot = {par: sum(z[i].area for i in PP.PROGRAMS if PP.PROGRAMS[i][1] == par) for par in PARENT_TITLE}
    zones = {i: {"name": PP.PROGRAMS[i][0], "parent": PP.PROGRAMS[i][1], "area_m2": round(z[i].area, 2),
                 "actual_share_of_parent_zones": round(z[i].area / par_tot[PP.PROGRAMS[i][1]], 3) if par_tot[PP.PROGRAMS[i][1]] else None,
                 "soft_target_share": PP.PROGRAMS[i][2], "provenance": "PROPOSED_DESIGN_NOT_MODEL_VERIFIED / area=shapely polygon.area"} for i in PP.PROGRAMS}
    inv = Counter("%s/%s" % (it["zone"], it["type"]) for it in plan["furniture"])
    chip_bad = [c_["id"] for c_ in chips if not c_["white_box_fallback"] and any(c_["box"].intersects(g_) for g_ in furn_all)]
    return {"variant": program, "state": "PLAN_CANDIDATE_UNAPPROVED", "1F_FINAL_FROZEN": False, "zones": zones, "qa": {k_: v_ for k_, v_ in qa_.items() if k_ != "area_table"},
            "furniture_instances_by_zone_type": dict(inv), "furniture_instances": len(plan["furniture"]),
            "furniture_body_polygons_planned": qa_["furniture_body_polygons"], "furniture_body_polygons_in_svg": len(furn_all),
            "zone_chips": len(chips), "zone_chips_with_white_box_fallback": sum(1 for c_ in chips if c_["white_box_fallback"]), "zone_chips_overlapping_furniture": chip_bad,
            "proposed_entries": [{"id": e["id"], "center": [round(e["center"][0], 2), round(e["center"][1], 2)], "status": e["status"]} for e in plan["entries"]],
            "flows": {"public": sum(1 for f in plan["flows"] if f["kind"] == "public"), "secondary": sum(1 for f in plan["flows"] if f["kind"] == "secondary"),
                      "service": sum(1 for f in plan["flows"] if f["kind"] == "service")},
            "columns_drawn": len(drawn_cols),
            "display_fill_vs_zone_polygon_m2": {"M06_fill": round(plan["m06_vector"].area, 2), "M06_zone": round(z["M06"].area, 2), "P01_fill": round(plan["p_corr"].area, 2), "P01_zone": round(z["P01"].area, 2),
                                                "note": "바닥 채움은 래스터 잔여 띠를 뺀 벡터 복도다. 구획 면적·범례 수치는 zone 폴리곤(V2-B와 동일)"}}


def render(out, floor, scale, png_width=4096, seed=7, crops=False, center=None, tag="", side="L", top=False, program=None, final_dir=None, name=None, clean=False, notes=(), v2layout=False, bare=False, v3layout=False):
    raw = os.path.join(out, "raw_slices")
    sl = pc.load_slice(raw, floor)
    lay = pc.load_json(os.path.join(out, "vector", "floor_%s_layout.json" % floor))
    bnd = pc.load_bounds(raw)
    rng = random.Random(seed)
    k = scale / 1000.0
    cuts = pc.cut_geometries(sl)
    bx0, by0, bx1, by1 = lay["building"]
    cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
    ccx, ccy = center if center else (cx, cy)                                         # 시트 중심 (타일 모드에서는 건물 중심이 아니다)
    cv = TCanvas((ccx - A3[0] * k / 2, ccy - A3[1] * k / 2, ccx + A3[0] * k / 2, ccy + A3[1] * k / 2), scale)
    cv.parts = {n: [] for n in LAYERS}
    cv.clean = clean                                                                       # C-T13A 선 정리 모드
    cv.curve_log = []
    canvas = box(*cv.b)
    ctx = sl.get("context", {})

    def geom(items):
        return U([pc.polygons_from_segments(i["segments"]) for i in items])

    road, sidewalk, site, setback = geom(ctx.get("road", [])), geom(ctx.get("sidewalk", [])), geom(ctx.get("site", [])), geom(ctx.get("setback", []))
    marks, subway = geom(ctx.get("road_marking", [])), geom(ctx.get("subway_exit", []))
    bldgs = [pc.polygons_from_segments(i["segments"]) for i in ctx.get("context_building", [])]
    ent_pts = [(e.centroid.x, e.centroid.y) for e in [pc.polygons_from_segments(i["segments"]) for i in ctx.get("entrance", [])] if not e.is_empty]   # 위치 정보로만 쓴다(상자는 그리지 않는다)
    level_s = floor != "1F"                                                           # 상층: 구조·프로그램 볼륨만 모델에 있다(벽·문·가구 없음) → Level S 도면
    has_site = floor == "1F" and not site.is_empty                                  # 대지·도로·이웃 건물은 1층 평면에만(AGENTS §6-10). 슬라이서가 모든 층 JSON에 대지 맥락을 싣는다

    footprint = U([pc.polygons_from_segments(p["segments"]) for p in sl["projection"]]) if sl["projection"] else box(bx0, by0, bx1, by1)
    cols = [g for _, g in cuts.get("column", [])]
    walls_all = [(it, g) for kd in ("partition_wall", "core_wall", "exterior_wall") for it, g in cuts.get(kd, [])]
    tubes = [(it, g) for it, g in cuts.get("tube_wall", [])] + [(it, g) for it, g in cuts.get("shaft", [])]
    model_only_union = U([g for kd_ in ("stair", "facade") for _, g in cuts.get(kd_, []) if not g.is_empty]) if level_s else Polygon()   # 상층 전용: 모델에 있으나 전용 기호가 없는 요소(에스컬레이터·입면 부재). 승인된 1층 출력은 바꾸지 않는다
    zones = []
    for z in sl["zones"]:
        g = pc.polygons_from_segments(z["segments"])
        if not g.is_empty and z["kind"] in ("room", "zone", "void"):
            zones.append((z, g, program_kind(z["name_ko"])))
    doors_raw = [(s, pc.polygons_from_segments(s.get("segments", []))) for s in sl.get("symbols", []) if s["category"] == "door"]
    doors_raw = [(s, g) for s, g in doors_raw if not g.is_empty]
    san_sym = [pc.polygons_from_segments(s.get("segments", [])) for s in sl.get("symbols", []) if s["category"] != "door"]
    san_sym = [g for g in san_sym if not g.is_empty]
    wall_union0 = U([g for _, g in walls_all])
    doors, fillers = solve_doors(doors_raw, walls_all, wall_union0, U(san_sym))      # 문설주 이격 250 mm + 4방향 시험 + 개구부 상자
    cutouts = U([d["cutout"] for d in doors])
    gaps = U([d["closure"] for d in doors])                                           # 방 분할용(문 개구부를 메운 선)
    walls = [(it, g.difference(cutouts)) for it, g in walls_all] + [({"kind": "partition_wall", "name": "문설주 채움", "source": "tag"}, f) for f in fillers]
    wall_union = U([g for _, g in walls])
    swing_union = U([d["swing"] for d in doors])
    san_keep = [g for g in san_sym if g.intersection(swing_union.buffer(0.15)).area < 1e-6]      # 문 스윙(+150 mm) 안의 위생도기·세면대는 두지 않는다
    fixtures_dropped = len(san_sym) - len(san_keep)
    shell_tubes = U([shell_of(g) for _, g in tubes])
    dash = 'stroke-dasharray="%.3f,%.3f"' % (3 * k, 2 * k)
    dash_p = ('stroke-dasharray="%.3f,%.3f"' % (1.6 * k, 1.0 * k)) if program else ""       # V2: 미승인 출입구 후보는 점선

    # ── 대지 맥락 ──
    if has_site:
        for g, fill, w, col in ((sidewalk, "#FAFAFA", 0.12, "#999"), (road, "#F0F0F0", 0.20, "#555")):
            if not g.is_empty:
                cv.stroke_poly("context", g.intersection(canvas), w, col, fill=fill)
        if not marks.is_empty:
            cv.stroke_poly("context", marks.intersection(canvas), 0.06, "#888", fill="#bdbdbd")
        for b in bldgs:
            b = b.intersection(canvas)
            if b.is_empty:
                continue
            cv.stroke_poly("context", b, 0.20, "#555555", fill="#F0F0F0")                        # 4단계 윤곽 + 연한 포셰
            for seg in mg_hatch(b, 2.4 * k):
                cv.stroke_line("context", seg, 0.05, "#CCCCCC")
        if not subway.is_empty:
            cv.stroke_poly("context", subway.intersection(canvas), 0.15, "#555", fill="#d8d8d8")
        sb_dash = 'stroke-dasharray="%s"' % ",".join("%.3f" % (x * k) for x in (8, 2, 1, 2, 1, 2))
        if cv.clean:                                                                         # C-T13A: 대지 경계·후퇴선이 같은 자리에서 두 번 그려지던 중복 제거
            if not setback.is_empty:
                for ln in lines_of(setback.boundary.difference(site.boundary.buffer(0.35))):
                    if ln.length > 3.0:
                        cv.stroke_line("context", list(ln.coords), 0.10, "#888", 'stroke-dasharray="%.3f,%.3f"' % (4 * k, 2 * k))
            for ln in lines_of(site.boundary):                                              # 얇은 폴리곤 윤곽(양쪽 두 겹) 대신 한 겹 선
                mg.Canvas.stroke_line(cv, "context", list(ln.coords), 0.35, "#222222", sb_dash)
        else:
            if not setback.is_empty:
                cv.stroke_poly("context", setback, 0.10, "#888", extra='stroke-dasharray="%.3f,%.3f"' % (4 * k, 2 * k))
            cv.stroke_poly("context", site.boundary.buffer(0.0005), 0.35, "#222222", extra=sb_dash)

    es = {}
    for sp in ctx.get("spaces", []):
        g = pc.polygons_from_segments(sp["segments"])
        use = str(sp["props"].get("use", ""))
        es[use] = U([es[use], g]) if use in es else g
    lawn = es.get("lawn", Polygon())
    sunken_ext = es.get("sunken", Polygon())
    sunken_stair = [pc.polygons_from_segments(s["segments"]) for s in ctx.get("sunken_stair", [])]
    sunken_regions = [g for g in [sunken_ext] + sunken_stair if not g.is_empty]
    site_stats = {}
    south_plaza = Polygon()
    if has_site:
        # 모델이 정한 숲 마당(잔디)은 그대로 두고, 나머지 대지 안쪽을 설계한다
        if not lawn.is_empty:
            bed = mg.plant_bed(lawn, rng)
            cv.stroke_poly("landscape", lawn, 0.08, "#aaa")
            for r_ in bed["rings"]:
                if cv.clean:                                                                # 화단 윤곽: 흔들리는 링 → 같은 면적의 참 원
                    pg = Polygon(r_)
                    cv.stroke_poly("plants", Point(pg.centroid.x, pg.centroid.y).buffer(math.sqrt(pg.area / math.pi), 16), 0.10, "#666")
                else:
                    cv.stroke_line("plants", r_, 0.10, "#666")
            for l_ in bed["lines"]:
                if not cv.clean:                                                            # 별잎·고사리 빗살은 C-T13A에서 제거
                    cv.stroke_line("plants", l_, 0.08, "#666")
            cv.dots("plants", bed["dots"][::3] if cv.clean else bed["dots"], 0.06, "#888", 0.7)
        site_json = pc.load_json(mg.SITE_JSON) if os.path.exists(mg.SITE_JSON) else {}
        grove_json = pc.load_json(mg.GROVE_JSON) if os.path.exists(mg.GROVE_JSON) else {}
        model_trees = [tuple(t[:3]) for t in (site_json.get("trees") or [])] + [tuple(t[:3]) for t in (grove_json.get("trees") or [])]
        park = U([g for key, g in es.items() if key in ("grove", "lawn", "path")])
        keep_t = [(x, y, r) for (x, y, r) in model_trees if canvas.contains(Point(x, y)) and not park.is_empty and park.buffer(1.0).contains(Point(x, y)) and not footprint.contains(Point(x, y))]
        draw_trees(cv, [(x, y, max(r * 1.2, 1.6)) for x, y, r in keep_t], rng)
        site_stats, south_plaza = design_site(cv, k, rng, site if site.geom_type == "Polygon" else shell_of(site), footprint, setback, sunken_regions, lawn,
                                 ent_pts, None, None, (bx0, by0, bx1, by1))
        site_stats["model_trees_kept"] = len(keep_t)
        for key in ("sunken", "fire_lane"):
            if key in es and not es[key].is_empty:
                cv.stroke_poly("ground", es[key], 0.12, "#555" if key == "sunken" else "#999", extra='' if key == "sunken" else dash)
        for g in sunken_stair:                                                          # 선큰 계단: 단 테라스(가볍게)
            x0, y0, x1, y1 = g.bounds
            n = int(ctx["sunken_stair"][0]["props"].get("treads", 12))
            for i in range(n + 1):
                cv.stroke_line("ground", [(x0 + (x1 - x0) * i / n, y0), (x0 + (x1 - x0) * i / n, y1)], 0.05, "#AAA")
            cv.stroke_poly("ground", g, 0.14, "#555")

    # ── 구역 분류 ──
    hall = next((g for z, g, kd in zones if kd == "hall"), None)
    piloti = next((g for z, g, kd in zones if kd == "piloti"), None)
    service = next((g for z, g, kd in zones if kd == "service"), None)
    sunken_zone = next((g for z, g, kd in zones if kd == "sunken"), None)
    rooms_union = U([g for z, g, kd in zones if kd in ("core", "restroom")])
    capsule = next((shell_of(g) for it, g in tubes if "캡슐" in it["name_ko"]), None)
    interior_blockers = U([shell_tubes, rooms_union, sunken_zone if sunken_zone is not None else Polygon()])      # 타일·점묘이 들어가면 안 되는 곳
    hall_pt = (hall.centroid.x, hall.centroid.y) if hall is not None else None

    # ── 구조 코어 배제 구역: 코어·화장실·캡슐·튜브의 외곽 + 1.8 m. 이 안의 점 기둥은 삭제한다 (RC 코어·튜브가 하중을 진다) ──
    core_polys = [g for z, g, kd in zones if kd in ("core", "restroom")] + [g for it, g in walls_all if it["kind"] == "core_wall"] \
        + [shell_of(g) for it, g in tubes] + ([capsule] if capsule is not None else [])
    core_union = U(core_polys)
    core_exclusion = core_union.buffer(1.8)
    drawn_cols = [c_ for c_ in cols if not core_exclusion.intersects(c_)]                      # 기둥 가장자리가 1.8 m 안에 닿으면 삭제 (중심 판정보다 엄격)
    culled_cols = len(cols) - len(drawn_cols)

    # ── 유리 커튼월 선·출입문 (가구가 출입구·문 스윙을 피하도록 먼저 계산한다) ──
    cl, door_defs = [], []
    curtain_swings = Polygon()
    if hall is not None:
        covered = U([wall_union.buffer(0.25), shell_tubes.buffer(0.3), rooms_union.buffer(0.15), (capsule.buffer(0.4) if capsule is not None else Polygon())])
        clines = curtain_lines(hall, covered)
        anchors = list(ent_pts)
        if piloti is not None:
            anchors += [(piloti.centroid.x, piloti.centroid.y), (piloti.representative_point().x, piloti.representative_point().y)]
        if service is not None:
            anchors.append((service.centroid.x, service.centroid.y))
        door_defs, _sw = solve_curtain_doors(clines, anchors, wall_union0, swing_union, U(san_keep))
        gap_zone = U([d_["cutout"] for d_ in door_defs])
        all_cutouts = U([cutouts, gap_zone])
        cl = lines_of(U(clines).difference(all_cutouts))
        curtain_swings = U([s_ for d_ in door_defs for s_ in d_["swings"]])

    # ── 장애물 ──
    elev = [shell_of(g).centroid for it, g in tubes if re.search("승강기|EV|FR|PL", it["name_ko"])]
    door_zone = U([d["swing"].buffer(1.8) for d in doors] + [Point(e).buffer(2.4) for e in ent_pts] + [p.buffer(4.0) for p in elev]
                  + [curtain_swings.buffer(1.8)] + [Point(d_["center"]).buffer(2.4) for d_ in door_defs])
    obst = U([U([c.buffer(1.5) for c in drawn_cols]), shell_tubes.buffer(1.5), wall_union.buffer(1.0), rooms_union.buffer(1.5),
              (sunken_zone.buffer(1.5) if sunken_zone is not None else Polygon()), door_zone] + ([model_only_union.buffer(0.6)] if level_s else []))      # 1층은 합집합 입력을 바꾸지 않는다(난수 배치 보존)

    furn_items, sym_items = [], []                                                       # [(geometry, kind)] kind: body / line / foliage
    svc_bays, cap_plan, plan, plan_qa = [], [], None, None
    core_union_v2 = U([g for z, g, kd in zones if kd in ("core", "restroom")] + [g for it, g in walls_all if it["kind"] == "core_wall"])
    ctx_v2 = {"plaza": next((shell_of(g) for it, g in tubes if ("빛" in it["name_ko"] or re.search("T2", it["name_ko"]))), None),
              "cores": core_union_v2,
              "tubes": [{"c": shell_of(g).centroid, "r": rad_of(shell_of(g)), "name": it["name_ko"]} for it, g in tubes if "캡슐" not in it["name_ko"] and "샤프트" not in it["name_ko"] and ("T" in it["name_ko"] or "튜브" in it["name_ko"]) and rad_of(shell_of(g)) > 1.6]}
    skipped_furn = []                                                                    # 상층에서 모델에 없는 배치를 지어내지 않아 가구를 만들지 않은 구역
    layout_meta = []
    hall_net = None
    light_c = next((shell_of(g).centroid for it, g in tubes if "빛" in it["name_ko"] or re.search("T2", it["name_ko"])), None)
    for z, g, kd in zones:
        others = U([g2 for (z2, g2, k2) in zones if z2 is not z and g2.area < g.area])
        region = (g.difference(others) if not others.is_empty else g).buffer(-0.3)
        if region.is_empty:
            continue
        region = region.difference(interior_blockers.buffer(0.1)) if kd in ("hall", "piloti") else region
        if region.is_empty:
            continue
        region = max(pc.iter_polygons(region), key=lambda p: p.area)
        if kd == "hall":
            hall_net = region
            minx, miny, maxx, maxy = region.bounds
            tile = region.buffer(-0.2)
            x = math.floor(minx / 1.5) * 1.5
            while x < maxx:
                for ln in lines_of(LineString([(x, miny), (x, maxy)]).intersection(tile)):
                    cv.stroke_line("ground", list(ln.coords), 0.06, "#D0D0D0")
                x += 1.5
            y = math.floor(miny / 1.5) * 1.5
            while y < maxy:
                for ln in lines_of(LineString([(minx, y), (maxx, y)]).intersection(tile)):
                    cv.stroke_line("ground", list(ln.coords), 0.06, "#D0D0D0")
                y += 1.5
            if program is None:                                                           # V2 프로그램 모드는 계획기가 가구를 놓는다
                # 시장 홀 3개 하위 구역: 1C 안내·팝업 바(주출입구 앞) / 1B 푸드코트(빛 튜브·커튼월 쪽) / 1A 중앙 아일랜드 매대(나머지)
                zoneC = Polygon()
                main_ent = ent_pts[0] if ent_pts else hall_pt
                if door_defs:
                    idoor = min(door_defs, key=lambda d_: math.hypot(d_["center"][0] - main_ent[0], d_["center"][1] - main_ent[1]))
                    cc_, nn = idoor["center"], idoor["n"]
                    if (hall_pt[0] - cc_[0]) * nn[0] + (hall_pt[1] - cc_[1]) * nn[1] < 0:
                        nn = (-nn[0], -nn[1])
                    for dist in (4.4, 5.2, 3.8):
                        bc = (cc_[0] + nn[0] * dist, cc_[1] + nn[1] * dist)
                        bar = FL.info_bar(bc, idoor["t"], (-nn[0], -nn[1]))
                        if all(region.buffer(-0.3).contains(g_) for g_, k_ in bar if k_ == "body") and not any(obst.buffer(-0.01).intersects(g_) for g_, k_ in bar if k_ == "body"):
                            furn_items += bar
                            zoneC = Point(bc).buffer(7.0)
                            break
                zoneB = (region.intersection(Point(light_c.x, light_c.y).buffer(13.0)).difference(zoneC)) if light_c is not None else Polygon()
                zoneA = region.difference(zoneC).difference(zoneB)
                for zn, fn in ((zoneB, FL.cafe_tables), (zoneA, FL.market_islands)):
                    for P_ in pc.iter_polygons(zn):
                        if P_.area > 14:
                            furn_items += fn(P_, rng, obst)
        elif kd == "piloti":
            free_p = region.difference(obst.buffer(-0.5)) if not obst.is_empty else region
            cv.dots("ground", (lambda q_: q_[::3] if cv.clean else q_)(mg.stipple_points(free_p.difference(interior_blockers), 0.7, 0.3, rng)), 0.12, "#666", 1.0)
            inner_pl = region.difference(obst).buffer(-1.9)                                   # 원형 수목 벤치(R 1.6)가 들어갈 열린 베이
            chosen = []
            if not inner_pl.is_empty:
                minx, miny, maxx, maxy = inner_pl.bounds
                tries = 0
                while len(chosen) < 4 and tries < 5000:
                    tries += 1
                    p = Point(rng.uniform(minx, maxx), rng.uniform(miny, maxy))
                    if inner_pl.contains(p) and all(math.hypot(p.x - q[0], p.y - q[1]) > 7.0 for q in chosen):
                        chosen.append((p.x, p.y))
            for (px_, py_) in chosen:
                if program is None:
                    furn_items += FL.planter_bench(px_, py_, rng)
        elif kd == "service":
            c_, u_, v_, L_, W_ = mg.obb(region)
            far = 1 if ((c_[0] - cx) * v_[0] + (c_[1] - cy) * v_[1]) > 0 else -1
            n_b = int((L_ - 1.0) // 3.5)
            bays = []
            for i in range(n_b):
                a = -L_ / 2 + 0.5 + 3.5 / 2 + i * 3.5
                bay = mg.rect(c_, u_, v_, a, far * (W_ / 2 - 4.0), 3.5, 8.0)
                if region.buffer(0.2).contains(bay):
                    bays.append(bay)
                    sym_items.append(("bollard", mg.at(c_, u_, v_, a - 1.75, far * (W_ / 2 - 8.0 + 1.2))))
            if bays:
                sym_items.append(("dock", LineString([mg.at(c_, u_, v_, -L_ / 2 + 0.5, far * (W_ / 2 - 8.0 + 1.2)), mg.at(c_, u_, v_, -L_ / 2 + 0.5 + n_b * 3.5, far * (W_ / 2 - 8.0 + 1.2))])))
                for a_try in (L_ / 2 - 2.5, L_ / 2 - 6.0, -L_ / 2 + 2.5):
                    p_a, p_b = mg.at(c_, u_, v_, a_try, far * (W_ / 2 - 6.5)), mg.at(c_, u_, v_, a_try, far * (W_ / 2 - 2.2))
                    if region.buffer(-0.4).contains(LineString([p_a, p_b])) and not obst.buffer(-0.3).intersects(LineString([p_a, p_b])):
                        sym_items.append(("ramp", (p_a, p_b)))
                        break
            for bay in bays:
                sym_items.append(("bay", bay))
            svc_bays = list(bays)
        elif kd == "sunken":
            c_, u_, v_, L_, W_ = mg.obb(g)
            sym_items.append(("slab_edge", g))
            sym_items.append(("rail", g.buffer(-0.1)))
            for i in range(int((L_ * 0.5) // 0.3)):
                sym_items.append(("step", mg.line(c_, u_, v_, -L_ / 2 + 0.15 + i * 0.3, -W_ / 2 + 0.1, -L_ / 2 + 0.15 + i * 0.3, W_ / 2 - 0.1)))
            for i in range(int((L_ * 0.5) // 0.6)):
                sym_items.append(("tile", mg.line(c_, u_, v_, 0.15 + i * 0.6, -W_ / 2 + 0.1, 0.15 + i * 0.6, W_ / 2 - 0.1)))
            sym_items.append(("arrow", (mg.at(c_, u_, v_, -L_ / 2 + 0.7, 0), mg.at(c_, u_, v_, -L_ / 2 + L_ * 0.5 - 0.4, 0))))
            for bsgn in (-1, 1):                                                              # 선큰 바닥 단: 원형 비스트로 테이블
                bx_, by_ = mg.at(c_, u_, v_, L_ * 0.27, bsgn * W_ * 0.22)
                if g.buffer(-0.9).contains(Point(bx_, by_)):
                    furn_items += FL.bistro_cluster(bx_, by_, 3)
        elif kd == "program" and (v2layout or v3layout) and level_s:                    # V2/V3: 프로그램 성격에 맞는 가구 전략(층마다 다름)
            hard_ob = U([c_.buffer(0.2) for c_ in cols] + [shell_tubes.buffer(0.5), core_union_v2.buffer(0.5), wall_union.buffer(0.3), model_only_union.buffer(0.4)])
            soft_ob = U([c_.buffer(0.9) for c_ in cols] + [shell_tubes.buffer(1.2), core_union_v2.buffer(1.2), wall_union.buffer(0.6), model_only_union.buffer(0.8)])       # 가구용 동선 여유(1층용 obst보다 가볍다)
            items_v2 = (L3 if v3layout else UL).layout(z["name_ko"], region, soft_ob, hard_ob, rng, floor, ctx_v2)
            furn_items += items_v2
            if getattr(items_v2, "meta", None):
                layout_meta.append(items_v2.meta)
            if not items_v2:
                skipped_furn.append(z["name_ko"])
        elif kd == "program":
            for key, gen in KEYWORDS:
                if key in z["name_ko"]:
                    if level_s and key in ("문화", "엔터"):                              # gen_rows는 0.45 m 좌석을 구역 가득 깐다(13F 2081개). 모델에 없는 극장식 배치라 상층에서는 만들지 않는다
                        skipped_furn.append(z["name_ko"])
                        break
                    furn_items += gen(region, rng, obst)
                    break

    # ── C-T13: 실모델 기하 덤프(읽기 전용) + 프로그램 계획기 ──
    if program or os.environ.get("T13_DUMP"):
        import json as _json
        dump = {"hall": hall, "piloti": piloti, "service": service, "sunken": sunken_zone, "capsule": capsule, "footprint": footprint,
                "walls": wall_union, "swings": swing_union, "curtain_swings": curtain_swings, "interior_blockers": interior_blockers, "obst": obst,
                "cols_drawn": U(drawn_cols), "cols_all": U(cols), "rooms": rooms_union, "shell_tubes": shell_tubes, "lawn": lawn,
                "sunken_ext": sunken_ext, "south_plaza": south_plaza}
        out_d = {k_: (v_.wkt if v_ is not None else None) for k_, v_ in dump.items()}
        out_d["tubes"] = [{"name": it["name_ko"], "wkt": shell_of(g).wkt, "raw": g.wkt} for it, g in tubes]
        out_d["zones"] = [{"name": z["name_ko"], "kind": kd, "wkt": g.wkt} for z, g, kd in zones]
        out_d["doors"] = [{"name": d["name"], "M": d["M"], "swing": d["swing"].wkt} for d in doors]
        out_d["door_defs"] = [{"center": d_["center"], "t": d_["t"], "n": d_["n"]} for d_ in door_defs]
        out_d["ent_pts"] = ent_pts
        _lc = next((shell_of(g).centroid for it, g in tubes if "빛" in it["name_ko"] or re.search("T2", it["name_ko"])), None)
        out_d["light_c"] = (_lc.x, _lc.y) if _lc is not None else None
        out_d["bounds"] = [bx0, by0, bx1, by1]
        out_d["bays"] = [b_.wkt for b_ in svc_bays]
        if os.environ.get("T13_DUMP"):
            _json.dump(out_d, open(os.environ["T13_DUMP"], "w", encoding="utf-8"), ensure_ascii=False)
            print("T13 dump:", os.path.abspath(os.environ["T13_DUMP"]))
        if program:
            I_ = PP.input_from_dump(out_d)
            plan = PP.plan_program(program, I_, seed)
            plan_qa = PP.qa(plan, I_)
            for it_ in plan["furniture"]:
                if it_["zone"][0] == "C":
                    cap_plan.extend(it_["parts"])
                else:
                    furn_items += it_["parts"]

    # 남측 테라스: 원형 야외 비스트로 테이블
    if not south_plaza.is_empty:
        zone_s = south_plaza.buffer(-1.8).intersection(box(bx0 + 4, by0 - 10, bx1 - 14, by0 - 2.5))
        chosen_s = []
        if not zone_s.is_empty:
            minx, miny, maxx, maxy = zone_s.bounds
            tries = 0
            while len(chosen_s) < 3 and tries < 3000:
                tries += 1
                p = Point(rng.uniform(minx, maxx), rng.uniform(miny, maxy))
                if zone_s.contains(p) and all(math.hypot(p.x - q[0], p.y - q[1]) > 6.0 for q in chosen_s):
                    chosen_s.append((p.x, p.y))
        for (sx_, sy_) in chosen_s:
            furn_items += FL.bistro_cluster(sx_, sy_, 4)

    col_zone = U([c_.buffer(0.3) for c_ in drawn_cols])
    route_items = [it_ for it_ in furn_items if it_[1] in ("route_v", "route_o")]                 # 동선은 기둥·튜브에 걸쳐도 버리지 않고 그 부분만 자른다
    keep_ = col_zone.union(shell_tubes)
    route_items = [(it_[0].difference(keep_), it_[1]) for it_ in route_items]
    furn_items = [it_ for it_ in furn_items if it_[1] not in ("route_v", "route_o") and not it_[0].intersects(col_zone) and not it_[0].intersects(shell_tubes)] + route_items
    furn_all = [g_ for g_, k_ in furn_items if k_ in ("body", "counter")]
    draw_furniture(cv, furn_items, dotted='stroke-dasharray="%.3f,%.3f"' % (1 * k, 1.2 * k), dashed='stroke-dasharray="%.3f,%.3f"' % (4 * k, 1.5 * k),
                   dashdot='stroke-dasharray="%.3f,%.3f,%.3f,%.3f"' % (3 * k, 1 * k, 0.5 * k, 1 * k))
    if program:
        gxs, gys = sorted({round(g.centroid.x, 2) for g in cols}), sorted({round(g.centroid.y, 2) for g in cols})
        grid_u_ = U([LineString([(x_, by0 - 2.0), (x_, by1 + 2.0)]) for x_ in gxs] + [LineString([(bx0 - 2.0, y_), (bx1 + 2.0, y_)]) for y_ in gys])
        draw_program_overlay(cv, k, plan, footprint, wall_union, shell_tubes, dash, grid_u_)
    for kind_, geo in sym_items:
        if kind_ == "bay":
            cv.stroke_poly("furn", geo, 0.10, "#666", extra=dash)
        elif kind_ == "dock":
            cv.stroke_line("furn", list(geo.coords), 0.30, "#333")
        elif kind_ == "bollard":
            cv.dots("furn", [geo], 0.25, "#333")
        elif kind_ in ("ramp", "arrow"):
            a, b = geo
            cv.stroke_line("furn", [a, b], 0.12, "#444")
            ang = math.atan2(b[1] - a[1], b[0] - a[0])
            for da in (2.6, -2.6):
                cv.stroke_line("furn", [b, (b[0] - 0.9 * math.cos(ang + da / 3), b[1] - 0.9 * math.sin(ang + da / 3))], 0.12, "#444")
        elif kind_ == "slab_edge":
            cv.stroke_poly("walls", geo, 0.351, "#000")                                          # 선큰 슬래브 가장자리: 2단계
        elif kind_ == "rail":
            cv.stroke_poly("furn", geo, 0.10, "#444")
        elif kind_ == "step":
            cv.stroke_line("furn", list(geo.coords), 0.07, "#777")
        elif kind_ == "tile":
            cv.stroke_line("furn", list(geo.coords), 0.05, "#BBB")
    for g in san_keep:
        cv.stroke_poly("furn", g, 0.08, "#666666", fill="#FFFFFF")                              # 위생도기도 흰색 불투명 마스크

    # ── 코어: U자형 계단 ──
    arrow_zones, core_numbers_extra = [], {}
    for z, g, kd in zones:
        if kd != "core":
            continue
        stair_doors = [d for d in doors if "stair" in d["name"] and g.buffer(0.6).contains(Point(d["M"]))]
        if not stair_doors:
            stair_doors = [d for d in doors if g.buffer(1.5).contains(Point(d["M"]))]
        ss = stair_core(g, [d["M"] for d in stair_doors], rng, U([wall_union0, gaps]))        # 모델 칸막이의 문 개구부를 메운 벽으로 방을 나눈다
        for ln in ss["light"]:
            cv.stroke_line("symbols", list(ln.coords), 0.12, "#444")                           # 계단 챌판·난간: 4단계
        for ln in ss["break"]:
            cv.stroke_line("symbols", list(ln.coords), 0.14, "#111")
        a, b = ss["arrow"]
        cv.stroke_line("symbols", [a, b], 0.14, "#222")
        ang = math.atan2(b[1] - a[1], b[0] - a[0])
        for da in (2.6, -2.6):
            cv.stroke_line("symbols", [b, (b[0] - 0.7 * math.cos(ang + da / 3), b[1] - 0.7 * math.sin(ang + da / 3))], 0.14, "#222")
        cv.add("symbols", '<text x="%.3f" y="%.3f" font-family="%s" font-size="%.4f" font-weight="bold" fill="#333" text-anchor="middle">UP</text>' %
               (cv.X(ss["up_text"][0]), cv.Y(ss["up_text"][1]) + 5.0 * 0.3528 * k * 0.3, mg.FONT, 5.0 * 0.3528 * k))
        avoid_core = U([LineString([a, b]).buffer(0.6), Point(ss["up_text"]).buffer(0.7), U(ss["light"]).buffer(0.2), U(ss["break"]).buffer(0.3)]
                       + [d["swing"].buffer(0.25) for d in doors if g.buffer(1.5).contains(Point(d["M"]))])
        core_numbers_extra[id(g)] = (None, avoid_core)

    # ── 모델에 있으나 전용 기호가 없는 절단 요소(에스컬레이터·입면 부재): 해석 없이 모델 윤곽만 3단계 선으로 ──
    model_only_drawn = {}
    for kd_ in (("stair", "facade") if level_s else ()):
        for it_, g_ in cuts.get(kd_, []):
            if not g_.is_empty:
                cv.stroke_poly("symbols", g_, 0.12, "#444")
                model_only_drawn[kd_] = model_only_drawn.get(kd_, 0) + 1

    # ── 튜브·승강기·샤프트 기호 ──
    for it, g in tubes:
        sym = tube_symbol(it["name_ko"], g, hall_pt, rng)
        for h in sym["light"] + sym["car"]:                                                  # 램프선·승강기 카: 4단계
            for ln in lines_of(h):
                cv.stroke_line("symbols", list(ln.coords), 0.12, "#444")
        for h in sym["x"]:                                                                   # 샤프트 X: 5단계
            for ln in lines_of(h):
                cv.stroke_line("symbols", list(ln.coords), 0.08, "#777")
        for arr in sym["arrows"]:
            cv.stroke_line("symbols", arr, 0.16, "#222")
            b, a = arr[-1], arr[-6]
            ang = math.atan2(b[1] - a[1], b[0] - a[0])
            for da in (2.6, -2.6):
                cv.stroke_line("symbols", [b, (b[0] - 1.0 * math.cos(ang + da / 3), b[1] - 1.0 * math.sin(ang + da / 3))], 0.16, "#222")

    # ── 서측 캡슐: 바닥 마감선·진열 탁자·곡면 라운지·입구 이중문 ──
    cap_numbers = None
    if capsule is not None:
        cc, uu, vv, L_, W_ = mg.obb(capsule)
        inner = capsule.buffer(-0.35)
        fl_step = 0.4 if cv.clean else 0.2                                                 # C-T13A: 바닥 마감선 간격 2배(배경 노이즈 저감)
        for i in range(int(W_ / fl_step)):                                                 # 가는 목재 바닥 선
            ln = mg.line(cc, uu, vv, -L_ / 2, -W_ / 2 + 0.3 + i * fl_step, L_ / 2, -W_ / 2 + 0.3 + i * fl_step).intersection(inner)
            for l2 in lines_of(ln):
                cv.stroke_line("furn", list(l2.coords), 0.04, "#D6D6D6")
        target = hall.representative_point() if hall is not None else Point(cx, cy)
        pr = capsule.exterior.project(target)
        ent = capsule.exterior.interpolate(pr)
        if program:                                                                        # V2: 입구 후보·가구는 계획기 결과 (모델에 문이 없으므로 점선 후보)
            ent = capsule.exterior.interpolate(capsule.exterior.project(Point(plan["door_pt"])))
            pr = capsule.exterior.project(ent)
            cap_items = list(cap_plan)
        else:
            cap_items = FL.capsule_gallery(capsule, (ent.x, ent.y), rng)                      # 전시 플린스 3 + 양면 갤러리 벤치 + 곡면 접수 데스크 (흰색 마스크)
            if not model_only_union.is_empty:                                                  # 가구는 모델 요소(에스컬레이터)를 피한다: 겹치는 가구와 그 몸체 안의 세부선을 뺀다
                keepout = model_only_union.buffer(0.3)
                gone = U([g_ for g_, k_ in cap_items if k_ == "body" and g_.intersects(keepout)])
                drop = keepout if gone.is_empty else U([keepout, gone.buffer(0.05)])
                cap_items = [(g_, k_) for g_, k_ in cap_items if not g_.intersects(drop)]
        draw_furniture(cv, cap_items)
        cap_bodies = [g_ for g_, k_ in cap_items if k_ == "body"]
        furn_all += cap_bodies
        cap_numbers = (capsule, U([f_.buffer(0.35) for f_ in cap_bodies] + ([model_only_union.buffer(0.45)] if level_s else [])))      # 번호가 모델 윤곽(에스컬레이터)에 닿지 않게(상층만)
        # 캡슐 벽 (입구 이중문 개구)
        capsule_gap = ent.buffer(0.0) if level_s else ent.buffer(1.0)              # 상층: 모델에 캡슐 문이 없으므로 개구·이중문을 만들지 않는다(벽은 닫힌 채)
        ring_geo = capsule.boundary.difference(capsule_gap)
        for ln in lines_of(ring_geo):
            cv.stroke_line("walls", list(ln.coords), 0.40, "#000")
        for ln in lines_of(capsule.buffer(-0.18).boundary.difference(capsule_gap)):
            cv.stroke_line("walls", list(ln.coords), 0.25, "#222")
        p2 = capsule.exterior.interpolate(min(capsule.exterior.length, pr + 0.3))
        t_ = (p2.x - ent.x, p2.y - ent.y)
        tl = math.hypot(*t_) or 1
        t_ = (t_[0] / tl, t_[1] / tl)
        for sgn in (() if level_s else (-1, 1)):
            hx, hy = ent.x + t_[0] * 0.9 * sgn, ent.y + t_[1] * 0.9 * sgn
            nrm = (-t_[1], t_[0])
            if capsule.contains(Point(hx + nrm[0] * 0.5, hy + nrm[1] * 0.5)) is False:
                nrm = (-nrm[0], -nrm[1])
            a0 = math.atan2(-t_[1] * sgn, -t_[0] * sgn)
            a1 = math.atan2(nrm[1], nrm[0])
            da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
            arc = [(hx + 0.9 * math.cos(a0 + da * i / 10), hy + 0.9 * math.sin(a0 + da * i / 10)) for i in range(11)]
            cv.stroke_line("doors", arc, 0.12, "#333", dash_p)
            cv.stroke_line("doors", [(hx, hy), arc[-1]], 0.18, "#111", dash_p)

    # ── 벽 ──
    for it, g in walls:
        if g.is_empty:
            continue
        thick = g.area / max(g.length / 2, 1e-6)
        if thick >= 0.22:
            cv.stroke_poly("walls", g, 0.50, "#000", fill="#ffffff")
            inner = g.buffer(-0.075)
            if not inner.is_empty:
                cv.stroke_poly("walls", inner, 0.12, "#444")
        elif thick < 0.12:
            cv.stroke_poly("walls", g, 0.15, "#000", fill="#111111")                         # 얇은 칸막이 0.15 mm
        else:
            cv.stroke_poly("walls", g, 0.35, "#000", fill="#111111")
    for it, g in tubes:
        if "캡슐" in it["name_ko"]:
            continue
        sh = shell_of(g)
        w = 0.45 if "샤프트" not in it["name_ko"] else 0.35
        cv.stroke_poly("walls", sh, w, "#000", fill="#ffffff", extra='fill-opacity="0.0"')
        ring2 = sh.buffer(-0.18)
        if not ring2.is_empty:
            cv.stroke_poly("walls", ring2.boundary.buffer(0.0005), 0.22, "#222")
    all_cutouts = U([cutouts])                                                              # 커튼월 문 개구는 아래에서 더한다
    for ln in lines_of(footprint.boundary.difference(cutouts)):                              # 투영선(슬래브 가장자리 점선)도 문 개구부에서 끊는다
        cv.stroke_line("walls", list(ln.coords), 0.10, "#777", dash)

    # ── 문: 힌지·문짝(3단계 0.18 mm)·스윙 호(5단계 0.08 mm) ──
    for d in doors:
        cv.stroke_line("doors", d["arc"], 0.12, "#333")                                    # → 5단계
        cv.stroke_line("doors", [d["hinge"], d["leaf_end"]], 0.20, "#111")                 # → 3단계

    # ── 유리 커튼월 (닫힌 경계) + 출입 양개문 ──
    cl_count = len(cl)
    if hall is not None:
        gap_w = {500: 0.22, 200: 0.18, 100: 0.15}.get(scale, 0.2)          # 두 유리선 사이 월드 간격(m): 1:500에서 220 mm = 종이 0.44 mm → 두 선이 한 덩어리로 합쳐지지 않는다
        gl_mm = {500: 0.09, 200: 0.10, 100: 0.12}.get(scale, 0.10)         # 유리선 종이 굵기 (4단계, #4A4A4A) — 절단 벽 0.45 mm의 1/4 이하
        for ln in cl:                                                       # ① 두 선 사이를 순백색 불투명으로 채워 아래 타일·격자를 가린다
            cv.add("envelope", '<path d="%s" fill="#FFFFFF" fill-rule="evenodd" stroke="none"/>' % cv.path_poly(ln.buffer(gap_w / 2, cap_style=2)))
        for ln in cl:                                                       # ② 가는 이중선 + 헤어라인 멀리언 눈금 (유리선 사이를 가로지르는 가는 선)
            for off in (gap_w / 2, -gap_w / 2):
                for o in lines_of(ln.offset_curve(off)):
                    mg.Canvas.stroke_line(cv, "envelope", list(o.coords), gl_mm, "#4A4A4A")
            if scale <= 100:
                mg.Canvas.stroke_line(cv, "envelope", list(ln.coords), 0.05, "#888888")
            dd = 1.4
            while dd < ln.length:
                p, p2 = ln.interpolate(dd), ln.interpolate(min(ln.length, dd + 0.1))
                t = (p2.x - p.x, p2.y - p.y)
                tl = math.hypot(*t) or 1
                n_ = (-t[1] / tl, t[0] / tl)
                mg.Canvas.stroke_line(cv, "envelope", [(p.x + n_[0] * gap_w / 2, p.y + n_[1] * gap_w / 2), (p.x - n_[0] * gap_w / 2, p.y - n_[1] * gap_w / 2)], 0.08, "#555555")
                dd += 2.75
        for dd_ in door_defs:                                                                            # 양개 출입문: 두 문짝(3단계)·스윙 호(5단계)
            c_, n = dd_["center"], dd_["n"]
            for J in (dd_["J1"], dd_["J2"]):
                a0 = math.atan2(c_[1] - J[1], c_[0] - J[0])
                a1 = math.atan2(n[1], n[0])
                da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
                arc = [(J[0] + 1.2 * math.cos(a0 + da * i / 14), J[1] + 1.2 * math.sin(a0 + da * i / 14)) for i in range(15)]
                cv.stroke_line("envelope", arc, 0.12, "#333", dash_p)
                cv.stroke_line("envelope", [J, arc[-1]], 0.18, "#111", dash_p)

    # ── 기둥·격자 ──
    for g in drawn_cols:
        cv.stroke_poly("cols", g, 0.1, "#000", fill="#000")
    if level_s:                                                                                  # 모델에 있는 기둥을 도면에서 지우지 않는다(1층 승인 규칙의 삭제는 1층에만)
        drawn_ids = {id(c_) for c_ in drawn_cols}
        for g in cols:
            if id(g) not in drawn_ids:
                cv.stroke_poly("cols", g, 0.10, "#666", extra='stroke-dasharray="%.3f,%.3f"' % (1.0 * k, 0.8 * k))
    xs, ys = sorted({round(g.centroid.x, 2) for g in cols}), sorted({round(g.centroid.y, 2) for g in cols})      # 격자 위치는 모델의 전체 기둥에서
    dsh = 'stroke-dasharray="%.3f,%.3f"' % (2 * k, 2 * k)
    grid_clip = core_union.buffer(0.3)                                                                          # 격자선은 코어·튜브 벽에서 0.3 m 떨어져 끝난다
    grid_lines = [LineString([(x, by0 - 2.0), (x, by1 + 2.0)]) for x in xs] + [LineString([(bx0 - 2.0, y), (bx1 + 2.0, y)]) for y in ys]
    for gl in grid_lines:
        for piece in lines_of(gl.difference(grid_clip)):
            if piece.length > 0.5:
                cv.stroke_line("grid", list(piece.coords), 0.08, "#888", dsh)

    # ── 번호 (프로그램 9개) ──
    prog_geoms: dict = {}
    for z, g, kd in zones:
        lg = legend_group(z["name_ko"], kd)
        if lg:
            prog_geoms.setdefault(lg, []).append((kd, g, z["name_ko"]))
    for it, g in tubes:
        lg = legend_group(it["name_ko"], "tube")
        if lg and lg in ("서측 캡슐", "동측 캡슐", "나선 램프 튜브", "빛 튜브"):
            prog_geoms.setdefault(lg, []).append(("tube", g, it["name_ko"]))
    for it, g in walls_all:
        if it["kind"] == "core_wall" and it.get("source") == "name":
            prog_geoms.setdefault("코어 / 피난계단·승강기", []).append(("core_box", g, it["name_ko"]))
    PROG4 = {"시장 홀", "필로티 광장", "하역·서비스", "서측 캡슐", "동측 캡슐"}
    legend = [n for n in LEGEND if n in prog_geoms and not (program and n in PROG4)]
    num_of = {n: i + 1 for i, n in enumerate(legend)}
    furn_union = U(furn_all)
    sym_union = U([h for it, g in tubes for key in ("light", "car", "x") for h in tube_symbol(it["name_ko"], g, hall_pt, rng)[key]])
    avoid_base = U([wall_union.buffer(0.35), furn_union.buffer(0.3), sym_union.buffer(0.2), U(drawn_cols).buffer(0.3), shell_tubes.buffer(0.3), swing_union.buffer(0.2)] + ([model_only_union.buffer(0.45)] if level_s else []))
    nums = []
    for n in legend:
        for kd, g, nm in prog_geoms[n]:
            small = n in ("화장실", "코어 / 피난계단·승강기")
            rr = (1.2 if small else 1.8) * k
            if kd == "core":
                landing, avoid_core = core_numbers_extra.get(id(g), (None, Polygon()))
                reg = (landing if landing is not None else g).difference(avoid_core).difference(wall_union.buffer(0.2))
                cand = [p for p in pc.iter_polygons(reg) if p.area > 0.3] or [p for p in pc.iter_polygons(g.difference(avoid_core)) if p.area > 0.3] or list(pc.iter_polygons(g))
                pt = polylabel(max(cand, key=lambda p: p.area), tolerance=0.05)
            elif kd == "restroom":
                reg = g.difference(wall_union.buffer(0.25)).difference(U(san_keep).buffer(0.3)).difference(swing_union.buffer(0.2))
                cand = [p for p in pc.iter_polygons(reg) if p.area > 0.4] or list(pc.iter_polygons(g))
                pt = polylabel(max(cand, key=lambda p: p.area), tolerance=0.05)
            elif kd == "tube":
                sh = shell_of(g)
                if "캡슐" in nm:
                    reg = sh.buffer(-0.5).difference(cap_numbers[1] if cap_numbers else Polygon())
                    cand = [p for p in pc.iter_polygons(reg) if p.area > 1.0] or list(pc.iter_polygons(sh))
                    pt = polylabel(max(cand, key=lambda p: p.area), tolerance=0.05)
                else:
                    c_ = sh.centroid
                    pt = Point(c_.x, c_.y)
            elif kd == "core_box":
                pt = g.centroid
            else:
                reg = g.difference(avoid_base) if not avoid_base.is_empty else g
                cand = [p for p in pc.iter_polygons(reg) if p.area > 1.5] or list(pc.iter_polygons(g))
                pt = polylabel(max(cand, key=lambda p: p.area), tolerance=0.05)
            nums.append((num_of[n], pt.x, pt.y, rr))
    pt_m = 6.5 * 0.3528 * k
    for no, x, y, rr in nums:
        cv.add("num", '<circle cx="%.3f" cy="%.3f" r="%.3f" fill="#ffffff" fill-opacity="0.96" stroke="#bbb" stroke-width="%.4f"/>' % (cv.X(x), cv.Y(y), rr, cv.lw(0.08)))
        cv.add("num", '<text x="%.3f" y="%.3f" font-family="%s" font-size="%.3f" fill="%s" text-anchor="middle">%d</text>' %
               (cv.X(x), cv.Y(y) + pt_m * 0.35, mg.FONT, pt_m * (1.0 if rr > 1.5 * k else 0.85), TXT, no))

    # ── 범례 / 북쪽 / 그래픽 스케일 ──
    chips = []
    if not bare:
        if program is None:
            row_h = 5.0
            total = 11 + len(legend) * row_h + 8 + 22 + 16 + 4.0 * len(notes)
            lx, ly = (8.0 if side == "L" else A3[0] - 8.0 - 56.0), A3[1] - 6.0 - total          # 타일: 건물 바깥쪽 여백(좌/우)에 둔다
            cv.add("legend", '<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" fill="#ffffff" fill-opacity="0.94" stroke="#bbb" stroke-width="%.4f"/>' % ((lx - 3) * k, (ly - 8) * k, 62 * k, (total + 10) * k, 0.1 * k))
            title = ("%s평면도 · 배치 1:%d" % (floor.replace("F", "층 "), scale)) if floor == "1F" else ("%s 평면도 1:%d" % (floor.replace("F", "층"), scale))
            if tag:
                title += "  [%s/4]" % tag[-1]                                                           # A3 4장 타일 중 몇 번째
            cv.text("legend", lx, ly, title, 8, "bold", "#111")
            y = ly + 9
            for n in legend:
                cv.text("legend", lx, y, str(num_of[n]), 6.5, "normal", "#222")
                cv.text("legend", lx + 7, y, n, 6.5, "normal", "#222")
                y += row_h
            ncx, ncy, nr = lx + 8, y + 10, 6.0
            cv.add("legend", '<circle cx="%.3f" cy="%.3f" r="%.3f" fill="none" stroke="#555" stroke-width="%.4f"/>' % (ncx * k, ncy * k, nr * k, 0.2 * k))
            na = math.radians(bnd["frame"].get("north_deg", bnd["frame"].get("theta_deg", 0.0)))
            cv.add("legend", '<line x1="%.3f" y1="%.3f" x2="%.3f" y2="%.3f" stroke="#555" stroke-width="%.4f"/>' % (ncx * k, ncy * k, (ncx + math.sin(na) * (nr + 3)) * k, (ncy - math.cos(na) * (nr + 3)) * k, 0.25 * k))
            cv.text("legend", lx, ncy + 13, "※ 가구·수목·조경은 설명용 표현이며 설계 데이터가 아니다", 4.2, "normal", "#999")
            if level_s:
                cv.text("legend", lx, ncy + 18, "SCHEMATIC — 상층 구획벽·문 미검증(모델에 없음)", 4.2, "bold", "#555")
                cv.text("legend", lx, ncy + 22, "외피 = 모델 입면 부재 윤곽 · 가구 = PROPOSED_ONLY", 4.2, "normal", "#777")
                cv.text("legend", lx, ncy + 26, "점선 원 = 모델 기둥(코어 인접, 1층 규칙상 생략 대상)", 4.2, "normal", "#777")
                if skipped_furn:
                    cv.text("legend", lx, ncy + 30, "%s: 가구 배치 미정(좌석 배열을 만들지 않음)" % "·".join(dict.fromkeys(skipped_furn)), 4.2, "normal", "#777")
            for i_, line_ in enumerate(notes):                                                      # 도면집 시트 표기(시트 번호·적용 층·다른 층과의 차이). 감사 증거에서 생성된 문구를 그대로 쓴다
                cv.text("legend", lx, ncy + 34 + 4.0 * i_, line_, 4.2, "bold" if i_ == 0 else "normal", "#333")
        else:
            chips = draw_zone_chips(cv, k, plan, U(furn_all + [g_ for g_, k_ in cap_plan if k_ == 'body']), U(drawn_cols), wall_union, shell_tubes)
            program_legend(cv, plan, plan_qa, legend, num_of, floor, scale, program, bnd)
        bar = SCALE_BARS.get(scale, [0, 2, 5, 10, 20])
        per_m = 1000.0 / scale
        sx0, sy0 = (76.0 if side == "L" else 40.0), (11.0 if top else A3[1] - 8.5)         # 윗 타일은 위쪽 여백, 아래 타일은 아래쪽 여백
        bar_pad = 22.0
        if scale == 200 and not tag:                                                          # 1:200 단일 시트: 건물이 종이 높이의 91 %라 아래 여백의 막대가 코어·외피선을 가린다 → 좌상단 여백, 10 m 막대
            bar, sx0, sy0, bar_pad = [0, 2, 5, 10], 10.0, 11.0, 8.0
        cv.add("legend", '<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" fill="#ffffff" fill-opacity="%s" stroke="#bbb" stroke-width="%.4f"/>' % ((sx0 - 4) * k, (sy0 - 6) * k, (bar[-1] * per_m + bar_pad) * k, 12.5 * k, "1.0" if cv.clean else "0.94", 0.1 * k))
        for i in range(len(bar) - 1):
            cv.add("legend", '<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" fill="%s" stroke="#111" stroke-width="%.4f"/>' % ((sx0 + bar[i] * per_m) * k, sy0 * k, (bar[i + 1] - bar[i]) * per_m * k, 1.6 * k, "#111" if i % 2 == 0 else "#fff", 0.15 * k))
        for m in bar:
            cv.text("legend", sx0 + m * per_m, sy0 - 1.2, str(m) + (" m" if m == bar[-1] else ""), 5.5, "normal", "#333", "middle")
        cv.text("legend", sx0, sy0 + 5.2, "1:%d  A3 420×297 mm" % scale, 4.5, "normal", "#555")


    # ── 저장 ──
    W_, H_ = cv.w, cv.h
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm" viewBox="0 0 %.3f %.3f">' % (A3[0], A3[1], W_, H_), '<rect width="%.3f" height="%.3f" fill="#ffffff"/>' % (W_, H_)]
    if level_s:
        svg.insert(1, '<metadata>LEVEL_S SCHEMATIC floor=%s scale=1:%d walls_doors=UNVERIFIED furniture=PROPOSED_ONLY</metadata>' % (floor, scale))
    for layer in LAYERS:
        svg.append('<g id="%s"%s>%s</g>' % (layer, ' data-status="PROPOSED_ONLY"' if (level_s and layer == "furn") else "", "".join(cv.parts[layer])))
    svg.append("</svg>")
    outd = os.path.join(out, "final_sheets")
    os.makedirs(outd, exist_ok=True)
    base = os.path.join(outd, "plan_%s_A3_1to%d%s" % (floor, scale, tag))
    if final_dir and not name:                                                            # 타일 모드: 기존 시트를 덮어쓰지 않고 지정 폴더에 쓴다
        outd = final_dir
        os.makedirs(outd, exist_ok=True)
        base = os.path.join(outd, "plan_%s_A3_1to%d%s_cleanline" % (floor, scale, tag))
    if name:
        outd = final_dir or outd
        os.makedirs(outd, exist_ok=True)
        base = os.path.join(outd, name)
    open(base + ".svg", "w", encoding="utf-8").write("\n".join(svg))
    import cairosvg
    cairosvg.svg2pdf(url=base + ".svg", write_to=base + ".pdf")
    cairosvg.svg2png(url=base + ".svg", write_to=base + ".png", output_width=png_width, background_color="white")

    plan_texts = [t for layer in ("context", "ground", "landscape", "plants", "furn", "envelope", "walls", "cols", "grid", "doors", "num")
                  for t in re.findall(r"<text[^>]*>([^<]*)</text>", "".join(cv.parts[layer]))]
    sym_texts = re.findall(r"<text[^>]*>([^<]*)</text>", "".join(cv.parts["symbols"]))
    fcol = [it for it in furn_all if not col_zone.disjoint(it)]
    shell_noncap = U([shell_of(g) for it, g in tubes if "캡슐" not in it["name_ko"]])                # 캡슐 안의 자기 가구는 제외
    ftub = [it for it in furn_all if not shell_noncap.disjoint(it)]
    furn_poly_union = U(furn_all)
    collide = sum(1 for no, x, y, rr in nums if (not furn_poly_union.is_empty) and Point(x, y).buffer(rr).intersects(furn_poly_union))
    numbered_small = sum(1 for no, x, y, rr in nums if rr < 1.5 * k)
    elev_numbers = sum(1 for n in legend for kd, g, nm in prog_geoms[n] if kd == "tube" and re.search("승강기|EV|FR|PL|샤프트", nm))
    sh_in = []
    for it, g in tubes:
        if "샤프트" in it["name_ko"]:
            sym = tube_symbol(it["name_ko"], g, hall_pt, rng)
            xl = [ln for ln in sym["x"] if ln.geom_type == "LineString" and len(ln.coords) == 2]
            sh_in.append(all(shell_of(g).buffer(-0.1).contains(Point(p)) for ln in xl for p in ln.coords))
    # 충돌 해결 점검 (문·벽·기물·기둥)
    swing_hits_walls = sum(1 for d in doors if d["swing"].buffer(-0.02).intersection(wall_union).area > 1e-4)
    swing_hits_doors = sum(1 for i, d in enumerate(doors) for o in doors[i + 1:] if d["swing"].buffer(-0.02).intersection(o["swing"].buffer(-0.02)).area > 1e-4)
    fixtures_in_swing = sum(1 for g in san_keep if g.intersection(swing_union.buffer(0.15)).area > 1e-6)
    residual = wall_union.intersection(cutouts).area
    jamb_viol = 0
    for d in doors:
        edges = perp_edges(wall_union0, d["u"])
        for J, J0 in ((d["N1"], d["J1"]), (d["N2"], d["J2"])):
            use = [e for e in edges if e.distance(Point(J0)) > 0.02]
            if use and min(e.distance(Point(J)) for e in use) < 0.25 - 1e-3:
                jamb_viol += 1
    min_col_core = min((core_union.distance(c_) for c_ in drawn_cols), default=None)                    # 기둥 가장자리 기준
    min_col_core_center = min((core_union.distance(c_.centroid) for c_ in drawn_cols), default=None)    # 기둥 중심 기준 (지시서 판정식)
    curtain_swing_hits = sum(1 for dd_ in door_defs for s_ in dd_["swings"] if s_.buffer(-0.02).intersection(wall_union0).area > 1e-4)
    tiers = {"T1_cut_walls_cols": "%.2f mm %s" % T1, "T2_door_leaf_partition": "%.2f mm %s" % T2, "T3_stair_ramp_elevator": "%.2f mm %s" % T3,
             "T4_glass_curtain_wall": "%.2f mm %s (1:100: 0.12)" % T4, "T5_furniture_fixture_swing_shaftX": "%.2f mm %s" % T5, "T6_grid_tile_stipple_foliage": "%.2f mm %s" % T6}
    check = {"floor": floor, "sheet_mm": list(A3), "scale": "1:%d" % scale, "world_per_sheet_m": [A3[0] * k, A3[1] * k], "mm_per_m": 1000.0 / scale,
             "canvas_matches_A3": abs(cv.w - A3[0] * k) < 1e-6 and abs(cv.h - A3[1] * k) < 1e-6, "scale_bar_10m_mm": 10 * 1000.0 / scale,
             "legend_items": len(legend), "legend": {str(num_of[n]): n for n in legend}, "numbers": len(nums), "numbers_on_elevators_or_shafts": elev_numbers,
             "small_bubbles_core_restroom": numbered_small, "entrance_boxes_drawn": 0, "door_gaps_punched": len(doors),
             "furniture_items": len(furn_all), "layout_meta": layout_meta,
             "furniture_v3": [{"kind": it_[1], "type": getattr(it_, "ftype", None), "wkt": it_[0].wkt} for it_ in furn_items if getattr(it_, "ftype", None)],
             "furniture_touching_column": len(fcol), "furniture_touching_tube": len(ftub), "numbers_colliding_with_furniture": collide,
             "plan_text_all_numeric": all(t.strip().isdigit() for t in plan_texts), "symbol_texts": sym_texts,
             "shaft_X_inside_circle": all(sh_in) if sh_in else None, "curtain_wall_segments": cl_count, "curtain_doors": len(door_defs), "site": site_stats,
             "window_world": [round(v, 4) for v in cv.b], "tag": tag, "model_only_outlines_drawn": model_only_drawn,
             "capsule_entrance_generated": (not level_s) and capsule is not None, "furniture_not_generated_for": list(dict.fromkeys(skipped_furn)),
             "furniture_overlapping_model_outlines": sum(1 for it_ in furn_all if (not model_only_union.is_empty) and it_.intersects(model_only_union.buffer(0.05))),
             "level": "S_SCHEMATIC" if level_s else "1F_APPROVED_PROGRAM", "walls_doors_verified": False if level_s else None,
             "furniture_status": "PROPOSED_ONLY" if level_s else None, "culled_columns_drawn_dashed": level_s,
             "columns_in_model": len(cols), "columns_drawn": len(drawn_cols), "columns_culled": culled_cols,
             "min_drawn_column_edge_to_core_or_tube_m": None if min_col_core is None else round(min_col_core, 2),
             "min_drawn_column_center_to_core_or_tube_m": None if min_col_core_center is None else round(min_col_core_center, 2),
             "door_swing_hits_wall": swing_hits_walls, "door_swing_hits_other_door": swing_hits_doors, "curtain_door_swing_hits_wall": curtain_swing_hits,
             "fixtures_dropped_in_swing": fixtures_dropped, "fixtures_remaining_in_swing": fixtures_in_swing, "door_opening_residual_wall_area_m2": round(residual, 6),
             "door_jamb_clearance_violations": jamb_viol, "doors_shifted_for_250mm_clearance": sum(1 for d in doors if d["shifted"]), "lineweight_tiers": tiers}
    if program:
        check["program"] = program_check(plan, plan_qa, chips, furn_all, drawn_cols, program)
    json.dump(check, open(base + "_check.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if clean:
        json.dump(cv.curve_log, open(base + "_curvelog.json", "w", encoding="utf-8"), ensure_ascii=False)
    print("PLAN", floor, "1:%d" % scale, "legend=%d nums=%d furn=%d curtain=%d cols=%d/%d" % (len(legend), len(nums), len(furn_all), cl_count, len(drawn_cols), len(cols)), os.path.abspath(base + ".png"))
    if crops and any(kd == "core" for z, g, kd in zones):
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        tmp = base + "_tmp14000.png"
        cairosvg.svg2png(url=base + ".svg", write_to=tmp, output_width=14000, background_color="white")
        im = Image.open(tmp)
        Wp, Hp = im.size
        sx_, sy_ = Wp / (cv.b[2] - cv.b[0]), Hp / (cv.b[3] - cv.b[1])

        def crop_at(center, size_m, name):
            u_, v_ = (center[0] - cv.b[0]) * sx_, (cv.b[3] - center[1]) * sy_
            h_ = size_m / 2 * sx_
            im.crop((int(u_ - h_), int(v_ - h_), int(u_ + h_), int(v_ + h_))).resize((800, 800), Image.LANCZOS).save(os.path.join(outd, name))

        core_c = next((g for z, g, kd in zones if kd == "core" and g.centroid.x > cx and g.centroid.y < cy), None)
        wc_c = next((g for z, g, kd in zones if kd == "restroom" and g.centroid.x > cx and g.centroid.y < cy), None)
        if core_c is not None:
            cen = U([core_c, wc_c] if wc_c is not None else [core_c]).centroid
            crop_at((cen.x, cen.y), 14.0, "crop_core_restroom.png")
        if capsule is not None:
            crop_at((capsule.centroid.x + 2.0, capsule.centroid.y), 16.0, "crop_tube_capsule.png")
        if door_defs and hall_pt:                                                          # 커튼월 + 출입문 + 시장 가구 (사양서 지정 이름)
            main_e = ent_pts[0] if ent_pts else hall_pt
            idr = min(door_defs, key=lambda d_: math.hypot(d_["center"][0] - main_e[0], d_["center"][1] - main_e[1]))
            nn_ = idr["n"]
            if (hall_pt[0] - idr["center"][0]) * nn_[0] + (hall_pt[1] - idr["center"][1]) * nn_[1] < 0:
                nn_ = (-nn_[0], -nn_[1])
            crop_at((idr["center"][0] + nn_[0] * 4.5, idr["center"][1] + nn_[1] * 4.5), 14.0, "crop_curtainwall_furniture.png")
        os.remove(tmp)
    return base, check


def capsule_hits(ln, capsule):
    return capsule is not None and ln.intersects(capsule.buffer(0.5))


def mg_hatch(geom, spacing, angle=45.0):
    ang = math.radians(angle)
    if geom.is_empty:
        return []
    minx, miny, maxx, maxy = geom.bounds
    r = math.hypot(maxx - minx, maxy - miny) / 2 + spacing
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    dx, dy = math.cos(ang), math.sin(ang)
    out = []
    for i in range(-int(r / spacing) - 1, int(r / spacing) + 2):
        ox, oy = cx - dy * i * spacing, cy + dx * i * spacing
        for ln in lines_of(LineString([(ox - dx * r, oy - dy * r), (ox + dx * r, oy + dy * r)]).intersection(geom)):
            out.append(list(ln.coords))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--floor", default="1F")
    ap.add_argument("--scale", type=int, default=0, help="축척 분모. 0이면 1층 500, 그 밖 200")
    ap.add_argument("--png-width", type=int, default=4096)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--crops", action="store_true", help="코어+화장실, 캡슐+튜브 확대 점검 800×800 px 두 장")
    ap.add_argument("--program", choices=["A", "B"], default=None, help="C-T13 V2 프로그램 컨셉 후보 (1층 1:500)")
    ap.add_argument("--final-dir", default=None, help="V2 산출물 폴더")
    ap.add_argument("--name", default=None, help="V2 산출물 파일 이름(확장자 제외)")
    ap.add_argument("--v2layout", action="store_true", help="상층 프로그램별 가구 전략(upper_layouts)")
    ap.add_argument("--v3layout", action="store_true", help="상층 프로그램별 가구·동선 계획 V3(layouts_v3): 유형 있는 가구 + 방문자/운영 동선")
    ap.add_argument("--bare", action="store_true", help="범례·축척 막대·북쪽 표시를 생략(도면집 시트가 자체 패널을 둔다)")
    ap.add_argument("--note", action="append", default=[], help="범례 아래에 쓸 줄(반복 지정). 도면집 시트 번호·적용 층·층간 차이")
    ap.add_argument("--cleanline", action="store_true", help="C-T13A 선 정리: 호·베지어 경로, 조경·구획 경계 정리, 시각 순위 조정")
    a = ap.parse_args()
    scale = a.scale or (500 if a.floor == "1F" else 100)                             # 1층 1:500, 상층 1:100
    out_ = os.path.abspath(a.out)
    layout = pc.load_json(os.path.join(out_, "vector", "floor_%s_layout.json" % a.floor))
    bx0, by0, bx1, by1 = layout["building"]
    k_ = scale / 1000.0
    hw, hh = A3[0] * k_ / 2, A3[1] * k_ / 2                                           # A3 한 장이 덮는 월드 반폭·반높이
    if (bx1 - bx0 + 4 > 2 * hw or by1 - by0 + 4 > 2 * hh) and scale <= 100:
        # 54×54 m 건물은 A3 한 장(1:100에서 42 × 29.7 m)에 들어가지 않는다 → 같은 A3·같은 1:100 축척으로 4장(2×2 타일)으로 나눈다
        # 범례는 건물 바깥 좌/우 여백(10 m), 축척 막대는 위/아래 여백(2.6 m)에 둔다 → 도면 요소와 겹치지 않는다
        mx_, my_ = 10.0, 2.6
        xs_ = [bx0 - mx_ + hw, bx1 + mx_ - hw]
        ys_ = [by1 + my_ - hh, by0 - my_ + hh]
        n_ = 0
        for ri_, yc in enumerate(ys_):
            for ci_, xc in enumerate(xs_):
                n_ += 1
                render(out_, a.floor, scale, a.png_width, a.seed, a.crops and n_ == 1, center=(xc, yc), tag="_t%d" % n_,
                       side="L" if ci_ == 0 else "R", top=(ri_ == 0), final_dir=a.final_dir, clean=a.cleanline, notes=tuple(a.note), v2layout=a.v2layout, bare=a.bare, v3layout=a.v3layout)
    else:
        if scale == 100:
            print("1:100 단일 시트")
        render(out_, a.floor, scale, a.png_width, a.seed, a.crops, program=a.program, final_dir=a.final_dir, name=a.name, clean=a.cleanline, notes=tuple(a.note), v2layout=a.v2layout, bare=a.bare, v3layout=a.v3layout)


if __name__ == "__main__":
    main()

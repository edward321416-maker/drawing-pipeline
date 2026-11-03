"""2D 건축 가구 라이브러리 (프로그램별 유형). 몸체(body)는 닫힌 폴리곤 → 흰색 불투명 채움으로 그려 아래 타일·점묘이 비치지 않게 한다.

각 생성기는 [(geometry, kind)] 를 돌려준다. kind: 'body'(흰 채움 + 윤곽), 'line'(세부선), 'foliage'(식재선, 6단계).
모든 치수는 미터(월드). 가구는 설명용 표현이며 설계 데이터가 아니다.
"""
from __future__ import annotations

import math
import os
import sys

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import monograph_plan_renderer as mg  # noqa: E402


def rrect(c, u, v, a, b, w, h, r=0.15):
    """바깥 모서리를 r로 둥글린 직사각형."""
    p = mg.rect(c, u, v, a, b, w, h)
    q = p.buffer(-r).buffer(r, 8)
    return q if not q.is_empty else p


def chair(cx, cy, fx, fy, s=0.42):
    """의자: 둥근 좌판 + 등받이 곡선. (fx, fy) = 앉는 사람이 바라보는 방향."""
    n = math.hypot(fx, fy) or 1
    fx, fy = fx / n, fy / n
    px, py = -fy, fx
    h = s / 2
    seat = Polygon([(cx - fx * h - px * h, cy - fy * h - py * h), (cx + fx * h - px * h, cy + fy * h - py * h),
                    (cx + fx * h + px * h, cy + fy * h + py * h), (cx - fx * h + px * h, cy - fy * h + py * h)]).buffer(-0.04).buffer(0.04, 6)
    a0 = math.atan2(fy, fx)
    rb = h + 0.05
    ccx, ccy = cx + fx * 0.04, cy + fy * 0.04
    back = LineString([(ccx + rb * math.cos(a0 + math.radians(t)), ccy + rb * math.sin(a0 + math.radians(t))) for t in range(130, 231, 10)])
    return [(seat, "body"), (back, "line")]


def stool(cx, cy, r=0.18):
    return [(Point(cx, cy).buffer(r, 12), "body")]


# ── 1 시장 홀 ──
def island_booth(c, u, v, a, b):
    """중앙 아일랜드형 매대 3.2 × 2.2 m: 둥근 외곽 + 600 mm 카운터 + 분할선 + 서 있는 공간 + 스툴 2."""
    out = [(rrect(c, u, v, a, b, 3.2, 2.2, 0.15), "body"), (mg.rect(c, u, v, a, b, 2.0, 1.0), "body")]
    for k in range(1, 4):                                                    # 카운터 트레이 분할선
        x = a - 1.6 + 0.8 * k
        out.append((mg.line(c, u, v, x, b + 0.5, x, b + 1.1), "line"))
        out.append((mg.line(c, u, v, x, b - 1.1, x, b - 0.5), "line"))
    for sgn in (-1, 1):
        out.append((mg.line(c, u, v, a + sgn * 1.0, b - 0.5, a + sgn * 1.6, b - 0.5), "line"))
        out.append((mg.line(c, u, v, a + sgn * 1.0, b + 0.5, a + sgn * 1.6, b + 0.5), "line"))
    for dx in (-0.5, 0.5):
        px, py = mg.at(c, u, v, a + dx, b)
        out += stool(px, py, 0.18)
    return out


def market_islands(region, rng, obstacles, margin=1.5):
    """아일랜드를 등을 맞댄 쌍으로 격자 배치. 주 통로 1.8 m 이상, 기둥·튜브 등 장애물에서 margin 이상."""
    if region.is_empty:
        return []
    c, u, v, L, Wd = mg.obb(region)
    free = region.buffer(-margin)
    if obstacles is not None and not obstacles.is_empty:
        free = free.difference(obstacles)
    pu, pv = 3.2 + 1.8, 2.2 * 2 + 0.2 + 1.8
    best = []
    for ou in (0.0, 1.25, 2.5, 3.75):                                              # 격자 위상을 바꿔 가장 많이 들어가는 배치를 고른다
        for ov in (0.0, 1.6, 3.2, 4.8):
            cand = []
            for i in range(int(L // pu) + 1):
                for j in range(int(Wd // pv) + 1):
                    a, b = -L / 2 + 1.6 + ou + i * pu, -Wd / 2 + 2.3 + ov + j * pv
                    pos = [(a, b - 1.2), (a, b + 1.2)]                              # 등을 맞댄 쌍. 쌍이 안 들어가면 낱개라도
                    fit = [free.contains(rrect(c, u, v, pa, pb, 3.2, 2.2, 0.15).buffer(0.15)) for pa, pb in pos]
                    cand += [p for p, f in zip(pos, fit) if f]
            if len(cand) > len(best):
                best = cand
    out = []
    for pa, pb in best:
        out += island_booth(c, u, v, pa, pb)
    return out


def cafe_tables(region, rng, obstacles, margin=1.0):
    """4인 정사각 카페 테이블(850 mm + 의자 4)과 8인 공용 긴 테이블(2400 × 900 + 양쪽 의자 4씩)."""
    if region.is_empty:
        return []
    c, u, v, L, Wd = mg.obb(region)
    free = region.buffer(-margin)
    if obstacles is not None and not obstacles.is_empty:
        free = free.difference(obstacles)
    out = []
    for j in range(int((Wd - 1.0) // 3.1) + 1):
        for i in range(int((L - 1.0) // 3.7) + 1):
            a, b = -L / 2 + 1.0 + 1.8 + i * 3.7, -Wd / 2 + 1.0 + 1.3 + j * 3.1
            if j % 2 == 0:                                                    # 공용 긴 테이블
                table = rrect(c, u, v, a, b, 2.4, 0.9, 0.05)
                parts = [(table, "body")]
                for k in range(4):
                    for sgn in (-1, 1):
                        x, y = mg.at(c, u, v, a - 0.9 + 0.6 * k, b + sgn * 0.7)
                        fx, fy = (-sgn * v[0], -sgn * v[1])
                        parts += chair(x, y, fx, fy)
                foot = table.buffer(0.75)
            else:                                                             # 4인 정사각 테이블
                table = rrect(c, u, v, a, b, 0.85, 0.85, 0.05)
                parts = [(table, "body")]
                for dx, dy in ((0.65, 0), (-0.65, 0), (0, 0.65), (0, -0.65)):
                    x, y = mg.at(c, u, v, a + dx, b + dy)
                    px, py = mg.at(c, u, v, a, b)
                    parts += chair(x, y, px - x, py - y)
                foot = table.buffer(0.75)
            if free.contains(foot):
                out += parts
    return out


def info_bar(c_point, axis_u, normal, stools=5):
    """안내·시음 바 3.0 × 0.8 m (둥근 끝) + 앞쪽 원형 스툴 4~5개. c_point: 바 중심, axis_u: 바 방향, normal: 스툴이 놓이는 앞쪽."""
    u = axis_u
    v = (-u[1], u[0])
    if (normal[0] * v[0] + normal[1] * v[1]) < 0:
        v = (-v[0], -v[1])
    out = [(rrect(c_point, u, v, 0, 0, 3.0, 0.8, 0.4), "body")]
    for k in range(stools):
        a = (k - (stools - 1) / 2) * 0.6
        x, y = mg.at(c_point, u, v, a, 0.8)
        out += stool(x, y, 0.18)
    return out


# ── 2 필로티 광장 ──
def planter_bench(cx, cy, rng, r_out=1.6, r_in=1.15):
    """원형 수목 벤치: 바깥 목재 벤치 링(방사 슬랫 눈금) + 안쪽 식재 원(식물 선화)."""
    out = [(Point(cx, cy).buffer(r_out, 40), "body"), (Point(cx, cy).buffer(r_in, 40), "body")]
    for k in range(24):
        a = math.radians(15 * k)
        out.append((LineString([(cx + r_in * math.cos(a), cy + r_in * math.sin(a)), (cx + r_out * math.cos(a), cy + r_out * math.sin(a))]), "line"))
    sh = mg.tree_shapes(cx, cy, 0.95, rng)
    for ring in sh["rings"]:
        out.append((LineString(ring), "foliage"))
    for ln in sh["lines"]:
        out.append((LineString(ln), "foliage"))
    return out


def bistro_cluster(cx, cy, n_chairs=4, r=0.45):
    """원형 야외 비스트로 테이블(r = 450 mm) + 방사 의자."""
    out = [(Point(cx, cy).buffer(r, 20), "body")]
    for k in range(n_chairs):
        a = 2 * math.pi * k / n_chairs + 0.4
        x, y = cx + (r + 0.27) * math.cos(a), cy + (r + 0.27) * math.sin(a)
        out += chair(x, y, cx - x, cy - y, 0.36)
    return out


# ── 5 서측 캡슐 ──
def capsule_gallery(capsule, entry_pt, rng):
    """전시 플린스 아일랜드 3 (2.4 × 1.2 m, 유물 윤곽) + 양면 갤러리 벤치 (1.8 × 0.6 m, 좌석 분할선) + 곡면 안내 데스크."""
    cc, u, v, L, Wd = mg.obb(capsule)
    inner = capsule.buffer(-0.5)
    out = []
    for k, s in enumerate((-0.30, 0.0, 0.30)):
        a = s * L
        body = rrect(cc, u, v, a, 0, 2.4, 1.2, 0.2)
        out.append((body, "body"))
        for q in range(3):                                                   # 유물 윤곽
            ox = a + (q - 1) * 0.65
            ring = mg.wobble_ring(*mg.at(cc, u, v, ox, 0.0), 0.2 + 0.05 * (q % 2), rng, 0.15, 16)
            out.append((LineString(ring), "line"))
    for s in (-0.15, 0.15):
        a = s * L
        for sgn in (-1, 1):
            out.append((rrect(cc, u, v, a, sgn * 0.33, 1.8, 0.6, 0.05), "body"))
            for q in range(1, 3):
                out.append((mg.line(cc, u, v, a - 0.9 + 0.6 * q, sgn * 0.33 - 0.3, a - 0.9 + 0.6 * q, sgn * 0.33 + 0.3), "line"))
    if entry_pt is not None:                                                  # 곡면 접수·오디오 가이드 데스크
        ex, ey = entry_pt
        dx, dy = cc[0] - ex, cc[1] - ey
        ang = math.atan2(dy, dx)
        cx2, cy2 = ex + math.cos(ang) * 2.2, ey + math.sin(ang) * 2.2
        pts = [(cx2 + 1.7 * math.cos(ang + math.radians(t)), cy2 + 1.7 * math.sin(ang + math.radians(t))) for t in range(120, 241, 10)]
        pts += [(cx2 + 1.1 * math.cos(ang + math.radians(t)), cy2 + 1.1 * math.sin(ang + math.radians(t))) for t in range(240, 119, -10)]
        out.append((Polygon(pts), "body"))
    return [(g, k) for g, k in out if (k != "body" or inner.buffer(0.1).contains(g)) and (k == "body" or inner.buffer(0.1).intersects(g))]


# ── 상층 프로그램 ──
def office_clusters(region, rng, obstacles, margin=1.0):
    """업무·코워킹: 2인 모듈(1600 × 1600) 등을 맞댄 책상 + 사무 의자 + 칸막이 스크린."""
    return _cells(region, obstacles, 3.4, 3.0, margin, lambda c, u, v, a, b: _office(c, u, v, a, b))


def _office(c, u, v, a, b):
    out = []
    for sgn in (-1, 1):
        out.append((mg.rect(c, u, v, a, b + sgn * 0.4, 1.6, 0.7), "body"))
        x, y = mg.at(c, u, v, a, b + sgn * 1.0)
        fx, fy = -sgn * v[0], -sgn * v[1]
        out += chair(x, y, fx, fy, 0.45)
    out.append((mg.line(c, u, v, a - 0.8, b, a + 0.8, b), "line"))             # 칸막이 스크린
    return out


def meeting_table(region, rng, obstacles, margin=0.8):
    """회의실·세미나: 큰 타원(보트형) 테이블 + 의자 8~12."""
    if region.is_empty:
        return []
    c, u, v, L, Wd = mg.obb(region)
    a, b = max(1.0, L * 0.3), max(0.6, Wd * 0.25)
    table = affinity.scale(Point(c).buffer(1, 32), a, b)
    table = affinity.rotate(table, math.degrees(math.atan2(u[1], u[0])), origin=c)
    n = max(8, min(12, int(2 * math.pi * max(a, b) / 0.85)))
    out = [(table, "body")]
    for k in range(n):
        t = 2 * math.pi * k / n
        px, py = (a + 0.5) * math.cos(t), (b + 0.5) * math.sin(t)
        x, y = mg.at(c, u, v, px, py)
        out += chair(x, y, c[0] - x, c[1] - y, 0.45)
    return [(g, k_) for g, k_ in out if region.buffer(-0.3).contains(g)]


def exhibition_layout(region, rng, obstacles, margin=1.0):
    """전시·갤러리·홀: 자립 전시 칸막이 + 미술관 벤치 + 조각 플린스."""
    def cell(c, u, v, a, b):
        return [(mg.rect(c, u, v, a, b - 1.4, 3.0, 0.12), "body"), (rrect(c, u, v, a, b + 0.4, 1.8, 0.6, 0.05), "body"),
                (rrect(c, u, v, a + 1.7, b + 0.4, 1.0, 1.0, 0.1), "body")]
    return _cells(region, obstacles, 5.2, 4.4, margin, cell)


def workshop_layout(region, rng, obstacles, margin=1.0):
    """공방·스튜디오·실험실: 작업대 2400 × 1200 + 스툴 + 벽면 선반(깊이 450, 사선)."""
    out = []
    if region.is_empty:
        return out
    shelf = region.buffer(-0.2).difference(region.buffer(-0.65))
    if not shelf.is_empty and shelf.geom_type in ("Polygon", "MultiPolygon"):
        for p in ([shelf] if shelf.geom_type == "Polygon" else list(shelf.geoms)):
            if p.area > 0.5:
                out.append((p, "body"))
        for seg in mg_hatch_lines(shelf, 0.45):
            out.append((seg, "line"))

    def cell(c, u, v, a, b):
        parts = [(rrect(c, u, v, a, b, 2.4, 1.2, 0.05), "body")]
        for sx in (-0.6, 0.6):
            for sgn in (-1, 1):
                x, y = mg.at(c, u, v, a + sx, b + sgn * 0.9)
                parts += stool(x, y, 0.17)
        return parts
    return out + _cells(region.buffer(-0.7), obstacles, 4.0, 3.6, margin, cell)


def lounge_layout(region, rng, obstacles, margin=0.9):
    """휴게·라운지·카페: ㄱ자 소파(방석 이음선·등받이선) + 낮은 원형 커피 테이블 + 안락의자."""
    def cell(c, u, v, a, b):
        sofa = mg.rect(c, u, v, a - 0.4, b, 2.4, 0.9).union(mg.rect(c, u, v, a - 1.2 + 0.45, b + 1.25, 0.9, 1.6))
        parts = [(sofa, "body"), (mg.line(c, u, v, a - 1.6, b - 0.25, a + 0.8, b - 0.25), "line")]
        for q in range(1, 3):
            parts.append((mg.line(c, u, v, a - 1.6 + 0.8 * q, b - 0.45, a - 1.6 + 0.8 * q, b + 0.25), "line"))
        x, y = mg.at(c, u, v, a + 0.2, b + 1.4)
        parts.append((Point(x, y).buffer(0.4, 16), "body"))
        ax, ay = mg.at(c, u, v, a + 1.5, b + 1.4)
        parts.append((rrect(c, u, v, a + 1.5, b + 1.4, 0.9, 0.9, 0.12), "body"))
        parts.append((mg.line(c, u, v, a + 1.05, b + 1.85, a + 1.95, b + 1.85), "line"))
        return parts
    return _cells(region, obstacles, 5.0, 4.2, margin, cell)


def _cells(region, obstacles, pu, pv, margin, builder):
    if region.is_empty:
        return []
    c, u, v, L, Wd = mg.obb(region)
    free = region.buffer(-margin)
    if obstacles is not None and not obstacles.is_empty:
        free = free.difference(obstacles)
    out = []
    for i in range(int(L // pu)):
        for j in range(int(Wd // pv)):
            a, b = -L / 2 + pu / 2 + i * pu, -Wd / 2 + pv / 2 + j * pv
            parts = builder(c, u, v, a, b)
            bodies = [g for g, k in parts if k == "body"]
            if bodies and free.contains(Polygon().union(bodies[0]).buffer(0.2)) and all(free.contains(g.buffer(0.05)) for g in bodies):
                out += parts
    return out


def mg_hatch_lines(geom, spacing):
    out = []
    minx, miny, maxx, maxy = geom.bounds
    r = math.hypot(maxx - minx, maxy - miny)
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    n = int(r / spacing) + 1
    for i in range(-n, n + 1):
        ox, oy = cx + i * spacing * 0.7071, cy - i * spacing * 0.7071
        ln = LineString([(ox - r, oy - r), (ox + r, oy + r)]).intersection(geom)
        for g in ([ln] if ln.geom_type == "LineString" else list(getattr(ln, "geoms", []))):
            if g.geom_type == "LineString" and g.length > 0.1:
                out.append(g)
    return out

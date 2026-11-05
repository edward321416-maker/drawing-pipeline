"""상층 프로그램별 가구 전략(V2). 같은 심볼 복제가 아니라 프로그램 성격에 따라 배치 논리가 다르다.

  retail(판매)    외벽 진열 띠 + 섬 부스(층마다 방향·간격·크기가 다른 두 변형) + 빛 튜브 둘레 휴게 벤치
  fnb(F&B)        외벽 뱅킷 + 식사 군집(4인 테이블) + 공용 긴 테이블 + 바 카운터(스툴) + 서비스 카운터
  culture(문화·엔터) 중앙 이벤트 무대(계단·배경벽) + 라운지 포드 + 전시 플린스 줄 + 집합 계단(단) + 미디어 월
  garden(정원)    식재 띠(화단) + 수목 + 테라스 테이블 세트 + 벤치

모든 배치는 설계 데이터가 아니라 PROPOSED_ONLY 표현이다. 좌표는 입력(구역 폴리곤·장애물)에서 계산하고 숫자 좌표를 직접 쓰지 않는다.
반환: [(shapely 도형, 'body'|'line'|'foliage')] — architectural_plan_renderer.draw_furniture가 그린다.
"""
import math

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union


def _free(region, obst, g, hard=None):
    if g.is_empty or not region.contains(g):
        return False
    if obst is not None and not obst.is_empty and g.intersects(obst):
        return False
    if hard is not None and not hard.is_empty and g.intersects(hard):
        return False
    return True


def _rect(cx, cy, w, h, ang=0.0):
    b = box(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    return affinity.rotate(b, ang, origin=(cx, cy)) if ang else b


def _ring(cx, cy, r, n=20):
    return LineString([(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n + 1)])


def _bench_ring(c, R, count, ang0, length=1.6, depth=0.5):
    out = []
    for i in range(count):
        a = ang0 + 360.0 * i / count
        x, y = c.x + R * math.cos(math.radians(a)), c.y + R * math.sin(math.radians(a))
        out.append(_rect(x, y, length, depth, a + 90.0))
    return out


def _perimeter_strips(region, hard, rng, depth, offset, seg=(3.0, 6.0), gap=(0.9, 1.6)):
    """건물 4변을 따라 끊어진 띠(외벽 진열·뱅킷). region 경계 안쪽 offset에 depth 폭."""
    x0, y0, x1, y1 = region.bounds
    out = []
    for side in ("S", "N", "W", "E"):
        horizontal = side in ("S", "N")
        length = (x1 - x0) if horizontal else (y1 - y0)
        pos = (y0 + offset + depth / 2) if side == "S" else (y1 - offset - depth / 2) if side == "N" else (x0 + offset + depth / 2) if side == "W" else (x1 - offset - depth / 2)
        t = (x0 if horizontal else y0) + 1.0
        end = (x1 if horizontal else y1) - 1.0
        while t < end:
            L = rng.uniform(*seg)
            if t + L > end:
                L = end - t
            if L < 1.2:
                break
            c = t + L / 2
            g = _rect(c, pos, L, depth) if horizontal else _rect(pos, c, depth, L)
            if _free(region, None, g, hard):
                out.append(g)
            t += L + rng.uniform(*gap)
    return out


def retail(region, obst, hard, rng, floor, ctx):
    """판매층. variant A(3F 등): 가로 섬 부스, 엇갈린 열. variant B(8F 등): 세로 쌍 섬 + 넓은 가로수길."""
    items = []
    variant = "A" if floor in ("2F", "3F", "4F", "5F", "B1", "B2") else "B"
    for g in _perimeter_strips(region, hard, rng, 0.55, 1.35, seg=(3.0, 6.5), gap=(1.0, 1.8)):
        items.append((g, "body"))                                                       # 벽 진열 선반
        x0, y0, x1, y1 = g.bounds
        if (x1 - x0) > (y1 - y0):
            items.append((LineString([(x0 + 0.1, (y0 + y1) / 2), (x1 - 0.1, (y0 + y1) / 2)]), "line"))
        else:
            items.append((LineString([((x0 + x1) / 2, y0 + 0.1), ((x0 + x1) / 2, y1 - 0.1)]), "line"))
    x0, y0, x1, y1 = region.bounds
    plaza = ctx.get("plaza")                                                              # 빛 튜브 둘레는 비워 두고 벤치 링
    if variant == "A":
        w, h, px, py = 3.0, 1.2, 5.2, 3.9
        rows = int((y1 - y0 - 6) // py)
        for r in range(rows):
            y = y0 + 4.2 + r * py
            off = (px / 2) if r % 2 else 0.0
            x = x0 + 4.2 + off
            while x < x1 - 3.5:
                g = _rect(x, y, w, h)
                if _free(region, obst, g) and not (plaza is not None and g.distance(plaza) < 2.5):
                    items.append((g, "body"))
                    items.append((LineString([(x - w / 2 + 0.15, y), (x + w / 2 - 0.15, y)]), "line"))
                    items.append((_rect(x + w / 2 + 0.45, y, 0.5, 0.5), "body"))          # 계산대
                x += px
    else:
        w, h, px, py = 1.4, 4.0, 4.8, 6.4
        cols = int((x1 - x0 - 6) // px)
        for c in range(cols):
            x = x0 + 4.0 + c * px
            off = (py / 2) if c % 3 == 1 else 0.0
            y = y0 + 4.5 + off
            while y < y1 - 4.0:
                for dx in (-0.85, 0.85):                                                   # 쌍 섬(팝업 부스)
                    g = _rect(x + dx, y, w, h)
                    if _free(region, obst, g) and not (plaza is not None and g.distance(plaza) < 2.5):
                        items.append((g, "body"))
                        items.append((LineString([(x + dx, y - h / 2 + 0.2), (x + dx, y + h / 2 - 0.2)]), "line"))
                y += py
    for t in ctx.get("tubes", []):                                                         # 튜브 둘레 휴게 벤치
        for g in _bench_ring(t["c"], t["r"] + 1.9, 5 if t["r"] > 3 else 3, 15.0 if variant == "A" else 40.0):
            if _free(region, None, g, hard):
                items.append((g, "body"))
    return items


def fnb(region, obst, hard, rng, floor, ctx):
    """F&B층. 뱅킷(외벽), 4인 군집, 공용 긴 테이블, 바 카운터, 서비스 카운터가 구역별로 다르다."""
    items = []
    x0, y0, x1, y1 = region.bounds
    for g in _perimeter_strips(region, hard, rng, 0.7, 1.35, seg=(2.4, 3.6), gap=(0.7, 1.2)):  # 뱅킷 + 앞 테이블
        items.append((g, "body"))
        a0, b0, a1, b1 = g.bounds
        horizontal = (a1 - a0) > (b1 - b0)
        n = max(1, int(((a1 - a0) if horizontal else (b1 - b0)) // 1.3))
        for i in range(n):
            t = ((a0 + 0.65 + i * 1.3) if horizontal else (b0 + 0.65 + i * 1.3))
            cx, cy = (t, b1 + 0.55) if (horizontal and (b0 + b1) / 2 < (y0 + y1) / 2) else (t, b0 - 0.55) if horizontal else ((a1 + 0.55, t) if (a0 + a1) / 2 < (x0 + x1) / 2 else (a0 - 0.55, t))
            tb = _rect(cx, cy, 0.7, 0.7)
            if _free(region, None, tb, hard):
                items.append((tb, "body"))
    px, py = 5.4, 4.2
    # 바 카운터: 중앙 근처 빈 자리 2곳
    bars = 0
    cx0, cy0 = (x0 + x1) / 2, (y0 + y1) / 2
    cands = sorted(((cx0 + dx, cy0 + dy) for dx in range(-18, 19, 3) for dy in range(-18, 19, 3)), key=lambda p: math.hypot(p[0] - cx0, p[1] - cy0))
    for (x, y) in cands:
        if bars >= 2:
            break
        g = _rect(x, y, 9.0, 0.9)
        zone = _rect(x, y, 10.5, 3.6)
        if _free(region, obst, zone):
            items.append((g, "body"))
            for i in range(11):
                items.append((_ring(x - 4.4 + i * 0.88, y + 0.9, 0.22, 10), "line"))     # 스툴
            bars += 1
            obst = unary_union([obst, zone]) if obst is not None else zone
    row = 0
    y = y0 + 4.0
    while y < y1 - 3.5:
        x = x0 + 4.0 + (px / 2 if row % 2 else 0.0)
        longrow = (row % 4 == 2)
        while x < x1 - 3.5:
            if longrow:
                g = _rect(x + 2.0, y, 6.0, 1.0)
                if _free(region, obst, g):
                    items.append((g, "body"))
                    for i in range(6):
                        for sg in (-0.7, 0.7):
                            items.append((_rect(x + 0.0 + i * 0.95 + 0.0, y + sg, 0.38, 0.38), "body"))
                x += 8.4
            else:
                for dx in (0.0, 1.9):                                                      # 2×1 군집(4인 테이블 2개)
                    t = _rect(x + dx, y, 1.0, 0.8)
                    if _free(region, obst, _rect(x + dx, y, 2.0, 1.8)):
                        items.append((t, "body"))
                        for sx, sy in ((-0.7, 0), (0.7, 0), (0, -0.6), (0, 0.6)):
                            items.append((_rect(x + dx + sx, y + sy, 0.36, 0.36), "body"))
                x += px
        y += py
        row += 1
    # 서비스 카운터: 코어/튜브 가까운 빈 곳
    for t in ctx.get("tubes", [])[:1]:
        g = _rect(t["c"].x, t["c"].y - (t["r"] + 3.2), 9.0, 0.8)
        if _free(region, None, g, hard):
            items.append((g, "body"))
            items.append((LineString([(g.bounds[0] + 0.3, g.centroid.y), (g.bounds[2] - 0.3, g.centroid.y)]), "line"))
    return items


def culture(region, obst, hard, rng, floor, ctx):
    """문화·엔터층. 무대·라운지 포드·전시 플린스·집합 계단·미디어 월(좌석 2000개 같은 날조 없음).
    큰 요소(무대·계단·전시)는 기둥·튜브 자체만 피하고(구조 사이에 끼워 넣음), 라운지는 동선 여유를 둔다."""
    items = []
    taken = Polygon()
    x0, y0, x1, y1 = region.bounds
    cx0, cy0 = (x0 + x1) / 2, (y0 + y1) / 2

    def ok(g):
        return _free(region, None, g, hard) and (taken.is_empty or not g.intersects(taken))

    def put(g, kind="body", pad=0.0):
        nonlocal taken
        items.append((g, kind))
        taken = unary_union([taken, g.buffer(pad)]) if not taken.is_empty else g.buffer(pad)

    # 1) 이벤트 무대: 중앙에 가까운 빈 자리(가로/세로 두 방향 시도)
    stage = None
    cands = sorted(((cx0 + dx, cy0 + dy) for dx in range(-20, 21) for dy in range(-20, 21)), key=lambda p: math.hypot(p[0] - cx0, p[1] - cy0))
    for (x, y) in cands:
        for (w, h) in ((7.5, 4.0), (4.0, 7.5)):
            g = _rect(x, y, w, h)
            zone = _rect(x, y, w + 2.4, h + 2.4)
            if ok(zone):
                stage = (x, y, w, h, g, zone)
                break
        if stage:
            break
    if stage:
        x, y, w, h, g, zone = stage
        put(g, "body", 1.2)
        wide = w > h
        for i in range(1, 4):                                                                 # 무대 앞 계단(관객 쪽)
            if wide:
                items.append((LineString([(x - w / 2, y - h / 2 - i * 0.3), (x + w / 2, y - h / 2 - i * 0.3)]), "line"))
            else:
                items.append((LineString([(x - w / 2 - i * 0.3, y - h / 2), (x - w / 2 - i * 0.3, y + h / 2)]), "line"))
        back = _rect(x, y + h / 2 - 0.35, w - 0.8, 0.22) if wide else _rect(x + w / 2 - 0.35, y, 0.22, h - 0.8)
        items.append((back, "body"))                                                          # 배경 미디어 월
        for i in range(-2, 3):                                                                # 스탠딩 마커
            pt = (x + i * 1.5, y - h / 2 - 1.9) if wide else (x - w / 2 - 1.9, y + i * 1.5)
            items.append((_ring(pt[0], pt[1], 0.32, 12), "line"))
    # 2) 집합 계단(단): 한 변 중앙에 3단
    for side in ("N", "S", "E", "W"):
        horizontal = side in ("S", "N")
        base = (y1 - 4.6) if side == "N" else (y0 + 4.6) if side == "S" else (x1 - 4.6) if side == "E" else (x0 + 4.6)
        sgn = -1 if side in ("N", "E") else 1
        c = cx0 if horizontal else cy0
        steps = []
        for i in range(3):
            g = _rect(c, base + sgn * i * 0.9, 12.0, 0.9) if horizontal else _rect(base + sgn * i * 0.9, c, 0.9, 12.0)
            steps.append(g)
        if all(ok(g) for g in steps):
            for g in steps:
                put(g, "body")
            break
    # 3) 전시 플린스 줄: 가장 많이 놓이는 변
    best = None
    for side in ("S", "N", "W", "E"):
        horizontal = side in ("S", "N")
        pos = (y0 + 2.6) if side == "S" else (y1 - 2.6) if side == "N" else (x0 + 2.6) if side == "W" else (x1 - 2.6)
        pl = []
        for i in range(9):
            t = ((x0 + 5 + i * 4.2) if horizontal else (y0 + 5 + i * 4.2))
            g = _rect(t, pos, 1.6, 1.6) if horizontal else _rect(pos, t, 1.6, 1.6)
            if ok(g):
                pl.append(g)
        if best is None or len(pl) > len(best):
            best = pl
    for g in (best or []):
        put(g, "body", 0.3)
        items.append((_ring(g.centroid.x, g.centroid.y, 0.45, 12), "line"))
    # 4) 라운지 포드(소파 2 + 낮은 테이블 + 화분): 동선 여유를 두고 가장자리 쪽부터
    pods = 0
    ring = sorted(((x, y) for x in range(int(x0) + 4, int(x1) - 3, 3) for y in range(int(y0) + 4, int(y1) - 3, 3)),
                  key=lambda p: min(p[0] - x0, x1 - p[0], p[1] - y0, y1 - p[1]))
    for (x, y) in ring:
        if pods >= 12:
            break
        zone = _rect(x, y, 5.6, 4.2)
        if _free(region, obst, zone) and (taken.is_empty or not zone.intersects(taken)):
            for sy, ang in ((-1.1, 0), (1.1, 180)):
                items.append((_rect(x, y + sy, 2.4, 0.9, ang), "body"))
            items.append((_rect(x, y, 1.2, 0.7), "body"))
            items.append((_ring(x + 2.2, y, 0.4, 12), "line"))
            taken = unary_union([taken, zone]) if not taken.is_empty else zone
            pods += 1
    return items


def garden(region, obst, hard, rng, floor, ctx):
    """정원·테라스층. 식재 띠, 수목, 테라스 테이블, 벤치(가구 언어가 다르다)."""
    items = []
    x0, y0, x1, y1 = region.bounds
    row = 0
    y = y0 + 3.0
    while y < y1 - 2.5:
        x = x0 + 3.0 + (rng.uniform(0.0, 2.0))
        while x < x1 - 3.0:
            L = rng.uniform(6.0, 11.0)
            g = _rect(x + L / 2, y, L, 1.6)
            if _free(region, obst, g.buffer(0.6)):
                bed = g.buffer(0.25)
                items.append((bed, "body"))
                n = int(L // 1.0)
                for i in range(n):
                    r = rng.uniform(0.35, 0.65)
                    items.append((_ring(x + 0.6 + i * (L - 1.2) / max(1, n - 1), y + rng.uniform(-0.3, 0.3), r, 14), "foliage"))
            x += L + rng.uniform(3.0, 4.5)
        y += 4.8
        row += 1
    for i in range(10):                                                                       # 수목
        px, py = rng.uniform(x0 + 2.0, x1 - 2.0), rng.uniform(y0 + 2.0, y1 - 2.0)
        g = Point(px, py).buffer(1.5)
        if _free(region, obst, g):
            items.append((_ring(px, py, 1.4, 18), "foliage"))
            items.append((_ring(px, py, 0.9, 14), "foliage"))
            obst = unary_union([obst, g]) if obst is not None else g
    for i in range(6):                                                                        # 테라스 테이블 세트
        px, py = rng.uniform(x0 + 3.0, x1 - 3.0), rng.uniform(y0 + 3.0, y1 - 3.0)
        g = Point(px, py).buffer(1.6)
        if _free(region, obst, g):
            items.append((Point(px, py).buffer(0.5, 14), "body"))
            for k in range(4):
                a = math.radians(90 * k + 45)
                items.append((Point(px + 1.0 * math.cos(a), py + 1.0 * math.sin(a)).buffer(0.25, 8), "body"))
            obst = unary_union([obst, g]) if obst is not None else g
    return items


def layout(name, region, obst, hard, rng, floor, ctx):
    n = name or ""
    if "F&B" in n:
        return fnb(region, obst, hard, rng, floor, ctx)
    if "문화" in n or "엔터" in n:
        return culture(region, obst, hard, rng, floor, ctx)
    if "garden" in n.lower() or "정원" in n:
        return garden(region, obst, hard, rng, floor, ctx)
    if "판매" in n or "시장" in n or "상업" in n:
        return retail(region, obst, hard, rng, floor, ctx)
    return []

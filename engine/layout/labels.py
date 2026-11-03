# FILE: layout/labels.py
from __future__ import annotations

from dataclasses import dataclass

from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath
from shapely.geometry import LineString, Polygon, box
from shapely.ops import nearest_points, polylabel, unary_union

from render.style import FONT_FAMILY, TEXT_ROLES

WIDTH_FACTOR = 1.1     # 글리프 잉크 폭 -> 실제 진행 폭 여유
HEIGHT_FACTOR = 1.4    # 글자 크기 -> 한 줄 높이(상·하 여백 포함)
LINE_GAP_PT = 1.0
LEADER_STEPS_M = (0.5, 1.5, 3.0, 5.0, 8.0)
SCAN_STEP_M = 0.5


def _scan(lo: float, hi: float, step: float = SCAN_STEP_M) -> list[float]:
    out, v = [], lo
    while v <= hi + 1e-9:
        out.append(v)
        v += step
    return out


class LabelPlacementError(RuntimeError):
    pass


@dataclass(frozen=True)
class Placement:
    lines: tuple
    line_centers: tuple
    box: Polygon
    leader: LineString | None


class LabelSolver:
    """영역 안의 빈 공간에 라벨을 계산 배치한다. 들어가지 않으면 지시선으로 밖에 낸다."""

    def __init__(self, params, canvas: Polygon):
        self.params = params
        self.canvas = canvas
        self.taken: list[Polygon] = []
        self.m_per_pt = 0.0254 / 72.0 * params.scale_denominator

    def _line_size(self, text: str, role: str):
        spec = TEXT_ROLES[role]
        prop = FontProperties(family=FONT_FAMILY, weight=spec.weight)
        ink = TextPath((0, 0), text, size=spec.size, prop=prop).get_extents()
        return ink.width * WIDTH_FACTOR * self.m_per_pt, spec.size * HEIGHT_FACTOR * self.m_per_pt

    def _block_size(self, lines):
        sizes = [self._line_size(t, r) for t, r in lines]
        gap = LINE_GAP_PT * self.m_per_pt
        width = max(s[0] for s in sizes)
        height = sum(s[1] for s in sizes) + gap * (len(sizes) - 1)
        return width, height, [s[1] for s in sizes], gap

    def _commit(self, lines, heights, gap, hit, leader):
        y_top = hit.centroid.y + (hit.bounds[3] - hit.bounds[1]) / 2 - self.params.label_pad_m
        cx = hit.centroid.x
        centers = []
        for lh in heights:
            centers.append((cx, y_top - lh / 2))
            y_top -= lh + gap
        self.taken.append(hit)
        return Placement(tuple(lines), tuple(centers), hit, leader)

    def place(self, region, lines, obstacles) -> Placement:
        width, height, heights, gap = self._block_size(lines)
        pad = self.params.label_pad_m
        half_w, half_h = width / 2 + pad, height / 2 + pad
        parts = [g for g in (obstacles, *self.taken) if g is not None and not g.is_empty]
        blocked = unary_union(parts) if parts else Polygon()
        inner = region.buffer(-0.1)

        def fits(cx, cy, need_inside):
            b = box(cx - half_w, cy - half_h, cx + half_w, cy + half_h)
            if not self.canvas.contains(b) or b.intersects(blocked):
                return None
            if need_inside and not inner.contains(b):
                return None
            return b

        if not inner.is_empty:
            poly = inner if inner.geom_type == "Polygon" else max(inner.geoms, key=lambda g: g.area)
            center = polylabel(poly, tolerance=0.05)
            hit = fits(center.x, center.y, True)
            if hit is None:
                minx, miny, maxx, maxy = inner.bounds
                step = 0.5 if inner.area < 400 else 1.0
                step = min(step, max(0.04, min(half_w, half_h) / 2))   # 라벨이 작을수록(큰 축척) 촘촘히 훑는다
                while ((maxx - minx) / step) * ((maxy - miny) / step) > 40000:
                    step *= 1.5
                cands = []
                x = minx + half_w
                while x <= maxx - half_w:
                    y = miny + half_h
                    while y <= maxy - half_h:
                        cands.append((x, y))
                        y += step
                    x += step
                cands.sort(key=lambda p: (p[0] - center.x) ** 2 + (p[1] - center.y) ** 2)
                for cx, cy in cands:
                    hit = fits(cx, cy, True)
                    if hit is not None:
                        break
            if hit is not None:
                return self._commit(lines, heights, gap, hit, None)

        minx, miny, maxx, maxy = region.bounds
        mx, my = (minx + maxx) / 2, (miny + maxy) / 2
        cx_lo, cy_lo, cx_hi, cy_hi = self.canvas.bounds
        xs = _scan(cx_lo + half_w, cx_hi - half_w)
        ys = _scan(cy_lo + half_h, cy_hi - half_h)
        for step in LEADER_STEPS_M:
            # 영역 바깥 네 변을 따라 후보를 훑고, 영역 중심에 가까운 순서로 시도한다
            ring = (
                [(x, maxy + half_h + step) for x in xs] + [(x, miny - half_h - step) for x in xs]
                + [(maxx + half_w + step, y) for y in ys] + [(minx - half_w - step, y) for y in ys]
            )
            ring.sort(key=lambda p: (p[0] - mx) ** 2 + (p[1] - my) ** 2)
            for cx, cy in ring:
                hit = fits(cx, cy, False)
                if hit is not None:
                    # 지시선은 대상 영역에서 라벨 상자에 가장 가까운 두 점을 잇는다(영역 중심에서 긋지 않는다)
                    start, end = nearest_points(region, hit)
                    leader = LineString([start.coords[0], end.coords[0]])
                    return self._commit(lines, heights, gap, hit, leader)
        raise LabelPlacementError(f"라벨 '{lines[0][0]}'를 배치할 빈 공간이 없습니다")

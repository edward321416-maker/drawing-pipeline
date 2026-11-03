"""평면의 표기 계층: 격자 기호, 치수, 표제, 방위표, 축척 막대.

위치와 숫자는 모두 건물 외곽(bounds)과 파라미터에서 계산한다. 이 모듈은 그리는 도구(pen)만 받으며
렌더러를 import하지 않는다. 그린 선·글자는 pen이 검사용 기록으로 남기므로 T1~T4가 그대로 적용된다.

아래 미터 상수는 params.annotation_base_scale(1:300)에서 종이 위 크기가 맞도록 정한 값이다. 도면 축척이 달라지면
annotation_factor(params) = 축척 / 기준 축척을 곱해 종이 위 크기를 유지한다(글자·선 두께는 pt·mm 고정이므로).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from shapely.geometry import LineString, Point, Polygon, box

TICK_M = 0.4
TITLE_Y_M = 15.5      # 건물 위쪽 끝에서 표제 중심까지
SUBTITLE_Y_M = 13.2
SITE_TITLE_Y_M = 9.0  # 대지 도면: 도면 테두리 위쪽 끝에서 표제 중심까지(격자 기호 띠가 없어 더 가깝다)
SITE_SUBTITLE_Y_M = 6.2
ARROW_BASE_X_M = 8.0  # 건물 오른쪽 끝에서 안쪽으로
ARROW_BASE_Y_M = 12.0
ARROW_LEN_M = 4.0     # 진북이 정확히 위쪽이어도 'N'이 위쪽 여백(19 m) 안에 들어오는 길이
SCALE_BAR_Y_M = 5.5   # 건물 아래쪽 끝에서 아래로
SITE_SIDE_MARGIN_M = 3.0   # 대지 도면 테두리 좌우 바깥 여백(축척 막대 '0' 글자가 잘리지 않도록)
SCALE_BAR_CHOICES_M = (5.0, 10.0, 20.0, 40.0, 50.0)


@dataclass(frozen=True)
class Annotation:
    title: str
    subtitle: str
    north_angle_deg: float = 0.0  # 도면 위쪽에서 시계 방향으로 잰 진북 방향


def annotation_factor(params) -> float:
    """기준 축척(1:300)에서 정한 미터 값에 곱해 종이 위 크기를 유지하는 비율."""
    return params.scale_denominator / params.annotation_base_scale


def scale_bar_spec(params) -> tuple[float, tuple[float, ...]]:
    """축척 막대의 길이(m)와 눈금. 종이 위 약 65 mm에 가장 가까운 둥근 길이를 고른다(1:300에서 20 m, 1:200에서 10 m, 1:400에서 20 m)."""
    target = params.scale_bar_m * annotation_factor(params)
    length = min(SCALE_BAR_CHOICES_M, key=lambda c: abs(c - target))
    return length, (0.0, length / 4, length / 2, length)


def _mm(meters: float) -> str:
    return f"{meters * 1000:,.0f}"


def grid_positions(lo: float, hi: float, spacing: float) -> list[float]:
    k0 = math.ceil((lo - 1e-6) / spacing)
    k1 = math.floor((hi + 1e-6) / spacing)
    return [k * spacing for k in range(k0, k1 + 1)]


def _letter(i: int) -> str:
    return "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[i]


def _north_arrow(pen, base, ann: Annotation, k: float) -> None:
    """방위표: 도면 위쪽에서 시계 방향 north_angle_deg."""
    th = math.radians(ann.north_angle_deg)
    d = (math.sin(th), math.cos(th))
    n = (math.cos(th), -math.sin(th))
    bx, by = base
    tip = (bx + ARROW_LEN_M * k * d[0], by + ARROW_LEN_M * k * d[1])
    neck = (tip[0] - 1.4 * k * d[0], tip[1] - 1.4 * k * d[1])
    pen.line("annot:north_shaft", LineString([(bx, by), neck]), "cut_medium", 6.0)
    head = Polygon([tip, (neck[0] + 0.55 * k * n[0], neck[1] + 0.55 * k * n[1]),
                    (neck[0] - 0.55 * k * n[0], neck[1] - 0.55 * k * n[1])])
    pen.polygon("annot:north_head", head, "cut_heavy", "#000000", 6.0)
    pen.text("annot:north_label", "N", "room", tip[0] + 1.4 * k * d[0], tip[1] + 1.4 * k * d[1])


def _scale_bar(pen, x0, yb, params, k: float) -> None:
    length, ticks = scale_bar_spec(params)
    pen.line("annot:scale_bar", LineString([(x0, yb), (x0 + length, yb)]), "cut_medium", 6.0)
    for t in ticks:
        pen.line(f"annot:scale_tick_{t:g}", LineString([(x0 + t, yb), (x0 + t, yb + 0.8 * k)]), "projection_light", 6.0)
        label = f"{t:g} m" if t == ticks[-1] else f"{t:g}"
        pen.text(f"annot:scale_label_{t:g}", label, "micro", x0 + t, yb - 1.0 * k)


def draw_annotations(pen, bounds, params, ann: Annotation) -> None:
    x0, y0, x1, y1 = bounds
    k = annotation_factor(params)
    sp = params.grid_spacing_m
    xs = grid_positions(x0, x1, sp)
    ys = grid_positions(y0, y1, sp)
    r = params.bubble_radius_m * k
    top_c = y1 + params.bubble_offset_m * k
    left_c = x0 - params.bubble_offset_m * k
    d1, d2 = params.dim_tier1_m * k, params.dim_tier2_m * k
    tick_m = TICK_M * k

    # 격자선을 기호까지 잇고, 기호를 그린다 (가로 1·2·3 / 세로 A·B·C)
    for i, x in enumerate(xs):
        pen.line(f"annot:ext_x{i + 1}", LineString([(x, y1 + 1), (x, top_c - r)]), "grid", 0.5)
        pen.polygon(f"annot:bubble_x{i + 1}", Point(x, top_c).buffer(r, quad_segs=16), "projection_light",
                    "white", 6.0, outline_only=True)
        pen.text(f"annot:bubble_x{i + 1}", str(i + 1), "room", x, top_c)
    for j, y in enumerate(ys):
        pen.line(f"annot:ext_y{_letter(j)}", LineString([(x0 - 1, y), (left_c + r, y)]), "grid", 0.5)
        pen.polygon(f"annot:bubble_y{_letter(j)}", Point(left_c, y).buffer(r, quad_segs=16), "projection_light",
                    "white", 6.0, outline_only=True)
        pen.text(f"annot:bubble_y{_letter(j)}", _letter(j), "room", left_c, y)

    # 치수선 2단: 칸별(1단), 전체(2단). 위쪽은 가로, 왼쪽은 세로(글자 90° 회전)
    def tick(owner, x, y):
        pen.line(owner, LineString([(x - tick_m, y - tick_m), (x + tick_m, y + tick_m)]), "projection_light", 4.0)

    for tier, offset in (("bay", d1), ("all", d2)):
        yd = y1 + offset
        stops = xs if tier == "bay" else [xs[0], xs[-1]]
        pen.line(f"annot:dim_top_{tier}", LineString([(xs[0], yd), (xs[-1], yd)]), "grid", 4.0)
        for n, x in enumerate(stops):
            tick(f"annot:dim_top_{tier}_tick{n}", x, yd)
        for n, (a, b) in enumerate(zip(stops[:-1], stops[1:])):
            pen.text(f"annot:dim_top_{tier}_{n}", _mm(b - a), "sub", (a + b) / 2, yd)
        xd = x0 - offset
        stops_y = ys if tier == "bay" else [ys[0], ys[-1]]
        pen.line(f"annot:dim_left_{tier}", LineString([(xd, ys[0]), (xd, ys[-1])]), "grid", 4.0)
        for n, y in enumerate(stops_y):
            tick(f"annot:dim_left_{tier}_tick{n}", xd, y)
        for n, (a, b) in enumerate(zip(stops_y[:-1], stops_y[1:])):
            pen.text(f"annot:dim_left_{tier}_{n}", _mm(b - a), "sub", xd, (a + b) / 2, rotation=90.0)

    # 표제, 방위표, 축척 막대
    pen.text("annot:title", ann.title, "title", x0, y1 + TITLE_Y_M * k, ha="left")
    pen.text("annot:subtitle", ann.subtitle, "sub", x0, y1 + SUBTITLE_Y_M * k, ha="left")
    _north_arrow(pen, (x1 - ARROW_BASE_X_M * k, y1 + ARROW_BASE_Y_M * k), ann, k)
    _scale_bar(pen, x0, y0 - SCALE_BAR_Y_M * k, params, k)


LEGEND_ROW_M = 1.9          # 범례 한 줄 높이(기준 축척 1:300 기준 m)
LEGEND_W_M = 20.0           # 좌측 범례 열 폭(기준 축척 m). 가장 긴 이름이 들어가는 폭
LEGEND_PAD_M = 3.0          # 범례 열과 도면 사이 여백


def site_canvas(window, params, n_entries: int = 0) -> tuple:
    """대지 도면의 캔버스: 보이는 창(window) 왼쪽에 범례 열, 위쪽에 표제 띠, 아래쪽에 여백을 더한다."""
    k = annotation_factor(params)
    wx0, wy0, wx1, wy1 = window
    ml, mb, mr, mt = params.annotation_margins_m
    left = (LEGEND_W_M + LEGEND_PAD_M + 2.0) * k if n_entries else SITE_SIDE_MARGIN_M * k   # +2 m: 축척 막대 '0' 글자 여유
    return (wx0 - left, wy0 - mb * k, wx1 + SITE_SIDE_MARGIN_M * k, wy1 + mt * k)


def draw_site_legend(pen, window, params, entries) -> None:
    """범례(참고 도면 방식): 창 왼쪽 열에 굵은 제목 한 줄과 '번호 이름' 목록만 둔다. 견본·테두리는 없다.
    도면 안에는 번호만 적고 이름은 여기에 둔다. entries = dict(number, name) 목록."""
    wx0, wy0, wx1, wy1 = window
    k = annotation_factor(params)
    lx = wx0 - (LEGEND_W_M + LEGEND_PAD_M) * k
    row_h = LEGEND_ROW_M * k
    base_y = wy0 + 12.0 * k                       # 아래 12 m(기준)는 방위표·축척 막대 자리
    top_y = base_y + (len(entries) + 1.4) * row_h
    pen.text("legend:title", "범례", "room", lx, top_y, ha="left")
    for i, e in enumerate(entries):
        cy = top_y - (i + 1.6) * row_h
        pen.text(f"legend:{i}:no", str(e["number"]), "sub", lx, cy, ha="left")
        pen.text(f"legend:{i}:name", e["name"], "sub", lx + 3.2 * k, cy, ha="left")


def draw_site_annotations(pen, window, params, ann: Annotation, has_legend: bool = True) -> None:
    """대지 도면(건물 + 대지 + 도로 + 이웃 건물)의 표기: 표제, 방위표, 축척 막대. 테두리는 그리지 않는다(참고 도면).

    범례가 있으면 방위표와 축척 막대는 범례 열 아래에 둔다. 격자 기호·치수선은 건물만의 도면에 있다."""
    wx0, wy0, wx1, wy1 = window
    k = annotation_factor(params)
    lx = wx0 - (LEGEND_W_M + LEGEND_PAD_M) * k if has_legend else wx0
    pen.text("annot:title", ann.title, "title", lx, wy1 + SITE_TITLE_Y_M * k, ha="left")
    pen.text("annot:subtitle", ann.subtitle, "sub", lx, wy1 + SITE_SUBTITLE_Y_M * k, ha="left")
    _north_arrow(pen, (lx + 3.0 * k, wy0 + 3.0 * k), ann, k)
    _scale_bar(pen, lx, wy0 - SCALE_BAR_Y_M * k, params, k)
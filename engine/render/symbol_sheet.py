"""코어 심볼 시트: 코어 심볼 4개를 한 장에 1:50으로 그린다. 위치·숫자·글자 위치는 모두 심볼 기하에서 계산한다."""
from __future__ import annotations

from dataclasses import replace

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from shapely.geometry import box  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

from layout.labels import LabelSolver  # noqa: E402
from render.plan_renderer import Pen, RenderResult, finish_render  # noqa: E402
from render.symbol_draw import draw_stair_details  # noqa: E402
from symbols.stair_core import CORE_VES_SIDE as VES_SIDE, build_stair_core  # noqa: E402
GAP_X_M, GAP_Y_M = 5.0, 4.5
SHEET_ORDER = (("A", "B"), ("C", "D"))               # 위 행, 아래 행


def build_sheet_cores(sizes: dict, params, door_offsets: dict | None = None) -> list:
    """sizes = {코어 이름: (가로, 세로)} (월드에서의 외곽 치수). 시트 위의 격자 칸에 배치한 코어 심볼 목록.
    door_offsets = {코어 이름: 홀 쪽 문 이동량(m)} — 마스터에 반영된 설계 조정과 같은 값을 쓴다."""
    p = params.stair
    door_offsets = door_offsets or {}
    col_w = [max(sizes[row[c]][0] for row in SHEET_ORDER if row[c] in sizes) for c in range(2)]
    row_h = [max(sizes[cid][1] for cid in row if cid in sizes) for row in SHEET_ORDER]
    cores = []
    for r, row in enumerate(SHEET_ORDER):
        y0 = (row_h[1] + GAP_Y_M) if r == 0 else 0.0
        for c, cid in enumerate(row):
            if cid not in sizes:
                continue
            x0 = 0.0 if c == 0 else col_w[0] + GAP_X_M
            w, d = sizes[cid]
            cores.append(build_stair_core(cid, (x0, y0, x0 + w, y0 + d), VES_SIDE[cid], p,
                                          hall_door_offset=door_offsets.get(cid, 0.0)))
    return cores


def _draw_core(pen, c):
    cid = c.core_id
    pen.polygon(f"{cid}:wall", c.walls, "cut_heavy", "#1a1a1a", 3.0)
    pen.polygon(f"{cid}:partition", c.partition, "cut_medium", "#666666", 3.0)
    draw_stair_details(pen, c)


def _obstacle(pen, cid):
    parts = []
    for _artist, rec in pen.line_artists:
        if not rec.owner.startswith(f"{cid}:") or rec.leader:
            continue
        parts.append(rec.geom if rec.filled else (rec.geom.boundary if rec.geom.geom_type == "Polygon" else rec.geom).buffer(0.05))
    return unary_union(parts)


def render_core_sheet(cores, params, out_png, title: str, subtitle: str, legend: str) -> RenderResult:
    p = params.stair
    sp = replace(params, scale_denominator=p.sheet_scale_denominator, dpi=p.sheet_dpi, label_pad_m=0.08, label_gap_m=0.1)
    x0 = min(c.bounds[0] for c in cores)
    y0 = min(c.bounds[1] for c in cores)
    x1 = max(c.bounds[2] for c in cores)
    y1 = max(c.bounds[3] for c in cores)
    canvas = (x0 - 3.0, y0 - 3.5, x1 + 3.0, y1 + 5.0)

    inch_per_m = 1.0 / (sp.scale_denominator * 0.0254)
    fig = plt.figure(figsize=((canvas[2] - canvas[0]) * inch_per_m, (canvas[3] - canvas[1]) * inch_per_m),
                     dpi=sp.dpi, facecolor="white")
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(canvas[0], canvas[2])
    ax.set_ylim(canvas[1], canvas[3])
    ax.set_aspect("equal")
    ax.axis("off")
    pen = Pen(ax)
    solver = LabelSolver(sp, box(*canvas))

    label_items = []
    for c in cores:
        _draw_core(pen, c)
        obstacle = _obstacle(pen, c.core_id)
        swings = unary_union([d.swing for d in c.doors])
        w, d = c.bounds[2] - c.bounds[0], c.bounds[3] - c.bounds[1]
        label_items.append((f"{c.core_id}:name", solver.place(
            c.opening, [(f"코어 {c.core_id}", "room"), (f"{w * d:,.0f}㎡", "sub")], obstacle)))
        label_items.append((f"{c.core_id}:vestibule", solver.place(
            c.vestibule, [("부속실", "sub"), (f"{c.vestibule.area:.1f}㎡", "sub")], unary_union([obstacle, swings]))))
        label_items.append((f"{c.core_id}:up", solver.place(c.landings[0], [("UP", "micro")], obstacle)))

    for owner, placement in label_items:
        if placement.leader is not None:
            pen.line(owner, placement.leader, "detail", 9.0, leader=True)
        for (text, role), (cx, cy) in zip(placement.lines, placement.line_centers):
            pen.text(owner, text, role, cx, cy)

    for c in cores:
        bx0, by0, bx1, by1 = c.bounds
        cx = (bx0 + bx1) / 2
        pen.text(f"{c.core_id}:heading", f"코어 {c.core_id} ({bx1 - bx0:.1f} × {by1 - by0:.1f} m)", "room", cx, by1 + 0.8)
        pen.text(f"{c.core_id}:summary",
                 f"계단 {c.steps_provided}단 (필요 {c.steps_required}단) · 부속실 {c.vestibule.area:.1f}㎡ (3㎡ 이상)",
                 "sub", cx, by0 - 2.2)
    pen.text("sheet:title", title, "title", x0, y1 + 3.4, ha="left")
    pen.text("sheet:subtitle", subtitle, "sub", x0, y1 + 2.7, ha="left")
    pen.text("sheet:legend", legend, "sub", x0, y1 + 2.1, ha="left")
    return finish_render(fig, ax, pen, out_png, sp.dpi, canvas)

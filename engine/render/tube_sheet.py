"""튜브 심볼 시트: T1~T4와 서측 캡슐을 한 장에 1:50으로 그린다. 위치·숫자·글자 위치는 모두 심볼 기하에서 계산한다."""
from __future__ import annotations

import math
from dataclasses import replace

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from shapely.geometry import box  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

from layout.labels import LabelSolver  # noqa: E402
from render.plan_renderer import Pen, RenderResult, finish_render  # noqa: E402
from render.tube_draw import draw_tube  # noqa: E402
from symbols.tube import move_tube  # noqa: E402

CELL_M, GAP_M = 9.0, 6.0
GRID = (("T1", "T2"), ("T3", "T4"))     # 위 행, 아래 행
CAPSULE_ID = "CAP_W"


def _extent(t):
    x0, y0, x1, y1 = t.outer.bounds
    return x1 - x0, y1 - y0


def place_on_sheet(tubes: dict) -> list:
    """tubes = {id: 월드 좌표의 튜브}. 4개는 2x2 격자 칸의 중심에, 서측 캡슐은 오른쪽에 아래 맞춤으로 둔다."""
    out = []
    for r, row in enumerate(GRID):
        y0 = (CELL_M + GAP_M) if r == 0 else 0.0
        for c, tid in enumerate(row):
            if tid not in tubes:
                continue
            t = tubes[tid]
            tx, ty = c * (CELL_M + GAP_M) + CELL_M / 2, y0 + CELL_M / 2
            out.append(move_tube(t, tx - t.center[0], ty - t.center[1]))
    if CAPSULE_ID in tubes:
        t = tubes[CAPSULE_ID]
        bx0, by0, _bx1, _by1 = t.outer.bounds
        out.append(move_tube(t, 2 * (CELL_M + GAP_M) - bx0, 0.0 - by0))
    return out


def _obstacle(pen, tid):
    parts = []
    for _artist, rec in pen.line_artists:
        if not rec.owner.startswith(f"{tid}:") or rec.leader:
            continue
        parts.append(rec.geom if rec.filled else (rec.geom.boundary if rec.geom.geom_type == "Polygon" else rec.geom).buffer(0.05))
    return unary_union(parts)


def _center_lines(t, p):
    if t.kind == "ramp":
        w = (t.band.area / ((t.band.exterior.length + t.band.interiors[0].length) / 2))
        return t.void, [("램프", "room"), (f"폭 {w:.1f} m", "sub")]
    if t.kind == "elevator":
        return t.lobby, [("승강 로비", "room"), (f"{t.lobby.area:.1f}㎡", "sub")]
    if t.kind == "light":
        return t.void, [("빛 튜브", "room"), (f"Ø{2 * (t.outer.area / math.pi) ** 0.5:.1f} m", "sub")]
    return t.void, [("서측 캡슐", "room"), (f"{t.inner.area:,.0f}㎡", "sub")]


def _summary(t, p):
    dia = 2 * (t.outer.area / math.pi) ** 0.5
    if t.kind == "ramp":
        r_rim_out = t.rims[1][1].bounds
        rim_d = r_rim_out[2] - r_rim_out[0]
        return f"바깥 림 Ø{dia:.1f} m · 안쪽 림 Ø{rim_d:.1f} m · 림 두께 {p.glass_t_m} m"
    if t.kind == "elevator":
        sh = t.shafts[0].clear.bounds
        depth = t.lobby.bounds[3] - t.lobby.bounds[1]
        return f"승강로 {sh[2] - sh[0]:.1f}×{sh[3] - sh[1]:.1f} m 2대 · 출입구 {p.entry_w_m} m · 로비 깊이 {depth:.1f} m"
    return f"유리 벽 두께 {p.glass_t_m} m"


def render_tube_sheet(tubes, params, out_png, title: str, subtitle: str, legend: str) -> RenderResult:
    p = params.tube
    sp = replace(params, scale_denominator=p.sheet_scale_denominator, dpi=p.sheet_dpi, label_pad_m=0.08, label_gap_m=0.1)
    x0 = min(t.outer.bounds[0] for t in tubes)
    y0 = min(t.outer.bounds[1] for t in tubes)
    x1 = max(t.outer.bounds[2] for t in tubes)
    y1 = max(t.outer.bounds[3] for t in tubes)
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

    for t in tubes:
        draw_tube(pen, t)
    label_items = []
    for t in tubes:
        region, lines = _center_lines(t, p)
        label_items.append((f"{t.tube_id}:label", solver.place(region, lines, _obstacle(pen, t.tube_id))))
    for owner, placement in label_items:
        if placement.leader is not None:
            pen.line(owner, placement.leader, "detail", 9.0, leader=True)
        for (text, role), (cx, cy) in zip(placement.lines, placement.line_centers):
            pen.text(owner, text, role, cx, cy)

    for t in tubes:
        bx0, by0, bx1, by1 = t.outer.bounds
        cx = (bx0 + bx1) / 2
        w, h = bx1 - bx0, by1 - by0
        size = f"Ø{w:.1f} m" if t.kind != "capsule" else f"{w:.1f} × {h:.1f} m"
        pen.text(f"{t.tube_id}:heading", f"{t.label} ({size})", "room", cx, by1 + 0.8)
        pen.text(f"{t.tube_id}:summary", _summary(t, p), "sub", cx, by0 - 1.2)
    pen.text("sheet:title", title, "title", x0, y1 + 3.4, ha="left")
    pen.text("sheet:subtitle", subtitle, "sub", x0, y1 + 2.7, ha="left")
    pen.text("sheet:legend", legend, "sub", x0, y1 + 2.1, ha="left")
    return finish_render(fig, ax, pen, out_png, sp.dpi, canvas)

"""화장실 심볼 시트: 화장실 B(공용·장애인 겸용)와 C(남·여·장애인)를 한 장에 1:50으로 그린다."""
from __future__ import annotations

from dataclasses import replace

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from shapely.geometry import box  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

from layout.labels import LabelSolver  # noqa: E402
from render.plan_renderer import Pen, RenderResult, finish_render  # noqa: E402
from render.restroom_draw import draw_restroom  # noqa: E402
from symbols.restroom import PROGRAM_BY_ROOM, build_restroom  # noqa: E402

GAP_X_M = 6.0


def build_sheet_restrooms(sizes: dict, params, columns: dict | None = None) -> list:
    """sizes = {방 이름: (가로, 세로)}. 시트 위에 나란히 놓은 화장실 심볼 목록. columns = {방 이름: 시트 좌표 기준 기둥 폴리곤 목록}."""
    out, x = [], 0.0
    for rid in ("B", "C"):
        if rid not in sizes:
            continue
        w, d = sizes[rid]
        cols = (columns or {}).get(rid, [])
        out.append(build_restroom(rid, (x, 0.0, x + w, d), PROGRAM_BY_ROOM[rid], params.restroom, cols))
        x += w + GAP_X_M
    return out


def render_restroom_sheet(rooms, params, out_png, title: str, subtitle: str, legend: str) -> RenderResult:
    p = params.restroom
    sp = replace(params, scale_denominator=p.sheet_scale_denominator, dpi=p.sheet_dpi, label_pad_m=0.08, label_gap_m=0.1)
    x0 = min(r.bounds[0] for r in rooms)
    y0 = min(r.bounds[1] for r in rooms)
    x1 = max(r.bounds[2] for r in rooms)
    y1 = max(r.bounds[3] for r in rooms)
    canvas = (x0 - 3.0, y0 - 4.5, x1 + 3.0, y1 + 7.0)

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
    for rr in rooms:
        obstacles = unary_union(draw_restroom(pen, rr))
        for u in rr.units:
            label_items.append((f"{rr.room_id}:{u.name}:label", solver.place(
                u.interior, [(u.label, "room"), (f"{u.interior.area:.1f}㎡", "sub")], obstacles)))
    for owner, placement in label_items:
        if placement.leader is not None:
            pen.line(owner, placement.leader, "detail", 9.0, leader=True)
        for (text, role), (cx, cy) in zip(placement.lines, placement.line_centers):
            pen.text(owner, text, role, cx, cy)

    for rr in rooms:
        bx0, by0, bx1, by1 = rr.bounds
        cx = (bx0 + bx1) / 2
        pen.text(f"{rr.room_id}:heading", f"화장실 {rr.room_id} ({bx1 - bx0:.1f} × {by1 - by0:.1f} m)", "room", cx, y1 + 2.4)
        general = [c for c in rr.cubicles if c.kind == "general"]
        acc = [c for c in rr.cubicles if c.kind == "accessible"]

        def dims(c):
            w, h = c.clear.bounds[2] - c.clear.bounds[0], c.clear.bounds[3] - c.clear.bounds[1]
            return f"{min(w, h):.2f}×{max(w, h):.2f}"

        parts = []
        if general:
            parts.append(f"일반 큐비클 {dims(general[0])} m")
        if acc:
            parts.append(f"장애인 {dims(acc[0])} m")
        parts.append(f"출입구 앞 통로 {p.entry_clear_m} m")
        pen.text(f"{rr.room_id}:summary", " · ".join(parts), "sub", cx, by0 - 2.2)
    pen.text("sheet:title", title, "title", x0, y1 + 5.0, ha="left")
    pen.text("sheet:subtitle", subtitle, "sub", x0, y1 + 4.3, ha="left")
    pen.text("sheet:legend", legend, "sub", x0, y1 + 3.7, ha="left")
    return finish_render(fig, ax, pen, out_png, sp.dpi, canvas)

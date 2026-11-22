"""Grid, dimension chains and level mark (world-metre annotations shared by SVG and DXF)."""
from __future__ import annotations

from shapely.geometry import LineString, Point

from . import source as SRC
from .model import MODEL_VERIFIED, PROPOSED, Drawing

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
BUBBLE_R = 1.0            # m at 1:200 -> 10 mm paper diameter
DIM1, DIM2, BUB = 2.2, 3.9, 6.0


def building_envelope():
    b = SRC.pc.load_bounds(str(SRC.SRC_DIR))["building"]
    return (round(b["xmin"], 1), round(b["ymin"], 1), round(b["xmax"], 1), round(b["ymax"], 1))


def typical_grid():
    """Column grid from the 34-column typical floor (8F): the structural grid is the same on every level."""
    g = SRC.load_floor("8F")
    xs = sorted({round(x, 1) for x, _ in g.columns})
    ys = sorted({round(y, 1) for _, y in g.columns})
    return xs, ys


def _ctext(d, x, y, s, role, **kw):
    d.text(x, y - 0.2, s, role, **kw)


def add_grid_and_dims(d: Drawing, floor_z: float, floor: str):
    bx0, by0, bx1, by1 = building_envelope()
    xs, ys = typical_grid()
    letters = {x: LETTERS[i] for i, x in enumerate(xs)}
    numbers = {y: str(i + 1) for i, y in enumerate(sorted(ys, reverse=True))}
    V = MODEL_VERIFIED
    for x in xs:
        d.add("A-GRID", LineString([(x, by0 - BUB + BUBBLE_R), (x, by1 + BUB - BUBBLE_R)]), "grid", prov=V, ref="grid " + letters[x])
        for yy in (by1 + BUB, by0 - BUB):
            d.add("A-ANNO-SYMB", Point(x, yy).buffer(BUBBLE_R, quad_segs=14), "projection_light", fill="#ffffff", prov=V, ref="bubble " + letters[x])
            _ctext(d, x, yy, letters[x], "room", layer="A-ANNO-SYMB", prov=V)
    for y in ys:
        d.add("A-GRID", LineString([(bx0 - BUB + BUBBLE_R, y), (bx1 + BUB - BUBBLE_R, y)]), "grid", prov=V, ref="grid " + numbers[y])
        for xx in (bx0 - BUB, bx1 + BUB):
            d.add("A-ANNO-SYMB", Point(xx, y).buffer(BUBBLE_R, quad_segs=14), "projection_light", fill="#ffffff", prov=V, ref="bubble " + numbers[y])
            _ctext(d, xx, y, numbers[y], "room", layer="A-ANNO-SYMB", prov=V)

    def chain(vals, fixed, horizontal, tier):
        off = DIM1 if tier == 1 else DIM2
        pos = (by1 if horizontal else bx1) + off
        pts = vals
        line = LineString([(pts[0], pos), (pts[-1], pos)]) if horizontal else LineString([(pos, pts[0]), (pos, pts[-1])])
        d.add("A-ANNO-DIMS", line, "dim", prov=V, ref="dim chain")
        edge = (by1 if horizontal else bx1)
        for v in pts:
            a, b = ((v, edge + 0.6), (v, pos + 0.5)) if horizontal else ((edge + 0.6, v), (pos + 0.5, v))
            d.add("A-ANNO-DIMS", LineString([a, b]), "hair", prov=V, ref="dim extension")
            tk = [(v - 0.25, pos - 0.25), (v + 0.25, pos + 0.25)] if horizontal else [(pos - 0.25, v - 0.25), (pos + 0.25, v + 0.25)]
            d.add("A-ANNO-DIMS", LineString(tk), "projection_light", prov=V, ref="dim tick")
        for a, b in zip(pts, pts[1:]):
            s = "%d" % round((b - a) * 1000)
            w = len(s) * 0.58 * 6.25 * 0.3528 / 5.0
            if b - a < w + 0.4:
                continue
            m = (a + b) / 2
            if horizontal:
                d.text(m, pos + 0.4, s, "sub", layer="A-ANNO-DIMS", prov=V)
            else:
                d.text(pos - 0.35, m, s, "sub", layer="A-ANNO-DIMS", prov=V, rotate=-90)
    chain([bx0] + xs + [bx1], by1, True, 1)
    chain([bx0, bx1], by1, True, 2)
    chain([by0] + ys + [by1], bx1, False, 1)
    chain([by0, by1], bx1, False, 2)
    d.text(bx0 - 8.0, by0 - 9.2, "▽ FFL %+.3f (%s)" % (round(floor_z, 3), floor), "sub", anchor="start",
           layer="A-ANNO-SYMB", prov=V, weight="bold")

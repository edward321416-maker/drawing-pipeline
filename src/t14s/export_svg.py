"""SVG writer (paper-mm user units, 1:200) + vector PDF / PNG through cairosvg.

The plan is drawn into a clipped group so the same Drawing feeds the A1 sheet and the A3 split sheets.
"""
from __future__ import annotations

import html
from pathlib import Path

import cairosvg
from shapely.geometry import GeometryCollection, LineString, MultiLineString, MultiPolygon, Polygon

from render.style import FONT_FAMILY, TEXT_ROLES
from .model import LAYERS, MM_PER_M, PEN_COLOR, PEN_DASH, PEN_MM, PT, Drawing

FONT = ", ".join('"%s"' % f if " " in f else f for f in FONT_FAMILY) + ", sans-serif"


def f3(v: float) -> str:
    s = "%.3f" % v
    return s.rstrip("0").rstrip(".") if "." in s else s


class Xf:
    """World metres (y up) -> paper mm (y down) for a plan window placed at origin (ox, oy) of the sheet."""

    def __init__(self, window, origin):
        self.wx0, self.wy0, self.wx1, self.wy1 = window
        self.ox, self.oy = origin
        self.k = MM_PER_M

    def pt(self, x, y):
        return (self.ox + (x - self.wx0) * self.k, self.oy + (self.wy1 - y) * self.k)

    @property
    def rect(self):
        return (self.ox, self.oy, (self.wx1 - self.wx0) * self.k, (self.wy1 - self.wy0) * self.k)


def _ring(coords, xf):
    return "M" + " L".join("%s %s" % tuple(map(f3, xf.pt(c[0], c[1]))) for c in coords)


def geom_path(g, xf) -> tuple:
    """(path_d_for_areas, path_d_for_lines)"""
    area, line = [], []

    def walk(gg):
        if gg.is_empty:
            return
        if isinstance(gg, Polygon):
            area.append(_ring(gg.exterior.coords, xf) + " Z")
            for r in gg.interiors:
                area.append(_ring(r.coords, xf) + " Z")
        elif isinstance(gg, LineString):
            line.append(_ring(gg.coords, xf))
        elif isinstance(gg, (MultiPolygon, MultiLineString, GeometryCollection)):
            for p in gg.geoms:
                walk(p)
    walk(g)
    return " ".join(area), " ".join(line)


class Svg:
    def __init__(self, w_mm, h_mm, title=""):
        self.w, self.h, self.title = w_mm, h_mm, title
        self.parts: list = []
        self.defs: list = []

    def add(self, s):
        self.parts.append(s)

    def rect(self, x, y, w, h, stroke="#000", sw=0.25, fill="none", extra=""):
        self.add('<rect x="%s" y="%s" width="%s" height="%s" fill="%s" stroke="%s" stroke-width="%s" %s/>'
                 % (f3(x), f3(y), f3(w), f3(h), fill, stroke, f3(sw), extra))

    def line(self, x1, y1, x2, y2, stroke="#000", sw=0.25, dash=None):
        d = ' stroke-dasharray="%s"' % ",".join(map(f3, dash)) if dash else ""
        self.add('<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s" stroke-width="%s"%s/>'
                 % (f3(x1), f3(y1), f3(x2), f3(y2), stroke, f3(sw), d))

    def circle(self, cx, cy, r, stroke="#000", sw=0.25, fill="none"):
        self.add('<circle cx="%s" cy="%s" r="%s" fill="%s" stroke="%s" stroke-width="%s"/>'
                 % (f3(cx), f3(cy), f3(r), fill, stroke, f3(sw)))

    def path(self, d, stroke="#000", sw=0.25, fill="none", extra=""):
        self.add('<path d="%s" fill="%s" stroke="%s" stroke-width="%s" stroke-linejoin="round" %s/>'
                 % (d, fill, stroke, f3(sw), extra))

    def text(self, x, y, s, pt=6.25, weight="normal", color="#333", anchor="middle", rotate=0.0, box=False):
        size = pt * PT
        tr = ' transform="rotate(%s %s %s)"' % (f3(rotate), f3(x), f3(y)) if rotate else ""
        if box and s:
            w = sum((1.0 if ord(c) > 0x2E80 else 0.58) for c in s) * size * (1.06 if weight == "bold" else 1.0)
            h = size * 1.25
            bx = x - w / 2 - 0.35 if anchor == "middle" else (x - 0.35 if anchor == "start" else x - w - 0.35)
            self.add('<rect x="%s" y="%s" width="%s" height="%s" fill="#fff"%s/>'
                     % (f3(bx), f3(y - h * 0.78), f3(w + 0.7), f3(h + 0.2), tr))
        self.add('<text x="%s" y="%s" font-size="%s" font-family="%s" font-weight="%s" fill="%s" text-anchor="%s"%s>%s</text>'
                 % (f3(x), f3(y), f3(size), html.escape(FONT, quote=True), weight, color, anchor, tr, html.escape(s)))

    def string(self) -> str:
        head = ('<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" '
                'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" width="%smm" height="%smm" '
                'viewBox="0 0 %s %s">\n<title>%s</title>\n<rect width="%s" height="%s" fill="#ffffff"/>\n'
                % (f3(self.w), f3(self.h), f3(self.w), f3(self.h), html.escape(self.title), f3(self.w), f3(self.h)))
        defs = "<defs>%s</defs>\n" % "".join(self.defs) if self.defs else ""
        return head + defs + "\n".join(self.parts) + "\n</svg>\n"


def draw_plan(svg: Svg, d: Drawing, xf: Xf, clip_id="planclip", exclude_layers=()):
    """Draw every item/text of the Drawing, layer by layer, clipped to the plan window."""
    x, y, w, h = xf.rect
    svg.defs.append('<clipPath id="%s"><rect x="%s" y="%s" width="%s" height="%s"/></clipPath>'
                    % (clip_id, f3(x), f3(y), f3(w), f3(h)))
    svg.add('<g clip-path="url(#%s)">' % clip_id)
    by_layer: dict = {}
    for it in d.items:
        by_layer.setdefault(it.layer, []).append(it)
    for name, _desc in LAYERS:
        if name in exclude_layers:
            continue
        items = by_layer.get(name, [])
        texts = [t for t in d.texts if t.layer == name]
        if not items and not texts:
            continue
        svg.add('<g id="%s" inkscape:groupmode="layer" inkscape:label="%s">' % (name, name))
        for prov in sorted({i.prov for i in items}):
            svg.add('<g data-prov="%s">' % prov)
            for it in (i for i in items if i.prov == prov):
                area, line = geom_path(it.geom, xf)
                col = PEN_COLOR.get(it.pen, "#444") if it.pen else "none"
                sw = PEN_MM.get(it.pen, 0.1) if it.pen else 0
                dash = PEN_DASH.get(it.dash or (it.pen if it.pen in PEN_DASH else ""), None)
                da = ' stroke-dasharray="%s"' % ",".join(map(f3, dash)) if dash else ""
                op = ' opacity="%s"' % f3(it.opacity) if it.opacity < 1 else ""
                if area:
                    svg.add('<path d="%s" fill="%s" fill-rule="evenodd" stroke="%s" stroke-width="%s" '
                            'stroke-linejoin="round"%s%s/>' % (area, it.fill or "none", col, f3(sw), da, op))
                if line:
                    svg.add('<path d="%s" fill="none" stroke="%s" stroke-width="%s" stroke-linecap="round" '
                            'stroke-linejoin="round"%s%s/>' % (line, col, f3(sw), da, op))
            svg.add("</g>")
        for t in texts:
            role = TEXT_ROLES[t.role]
            px, py = xf.pt(t.x, t.y)
            svg.text(px, py, t.s, t.size_pt or role.size, t.weight or role.weight, t.color or role.color,
                     t.anchor, t.rotate, t.box)
        svg.add("</g>")
    svg.add("</g>")


def save_svg(svg: Svg, path) -> str:
    s = svg.string()
    Path(path).write_text(s, encoding="utf-8")
    return s


def svg_to_pdf(svg_text: str, path):
    cairosvg.svg2pdf(bytestring=svg_text.encode("utf-8"), write_to=str(path))


def svg_to_png(svg_text: str, path, width_px: int):
    cairosvg.svg2png(bytestring=svg_text.encode("utf-8"), write_to=str(path), output_width=width_px)

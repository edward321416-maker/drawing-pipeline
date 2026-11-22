"""DXF writer: real-world millimetres (plot at 1:200), one DXF layer per drawing layer, provenance in XDATA."""
from __future__ import annotations

import ezdxf
from ezdxf import colors
from ezdxf.enums import TextEntityAlignment
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Polygon

from render.style import TEXT_ROLES
from .model import DXF_LW, LAYERS, PEN_COLOR, PT, SCALE_DEN, Drawing

VALID_LW = [0, 5, 9, 13, 15, 18, 20, 25, 30, 35, 40, 50, 53, 60, 70, 80, 90, 100, 106, 120, 140, 158, 200, 211]


def _lw(pen):
    v = DXF_LW.get(pen, 15 if pen == "circ" else 9)
    return min(VALID_LW, key=lambda a: abs(a - v))


def _rgb(hexs):
    h = hexs.lstrip("#")
    return colors.rgb2int((int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)))


def _pts(coords):
    return [(x * 1000.0, y * 1000.0) for x, y, *_ in coords]


def _walk(g):
    if g.is_empty:
        return
    if isinstance(g, (Polygon, LineString)):
        yield g
    elif hasattr(g, "geoms"):
        for p in g.geoms:
            yield from _walk(p)


def write_dxf(d: Drawing, path):
    doc = ezdxf.new("R2018", setup=True)
    doc.units = ezdxf.units.MM
    doc.header["$INSUNITS"] = 4
    doc.appids.add("T14S")
    for name, desc in LAYERS:
        lay = doc.layers.add(name, color=7)
        try:
            lay.description = desc
        except Exception:
            pass
    msp = doc.modelspace()
    n = 0
    for it in d.items:
        base = {"layer": it.layer, "lineweight": _lw(it.pen) if it.pen else 0}
        if it.pen:
            base["true_color"] = _rgb(PEN_COLOR.get(it.pen, "#444444"))
        for g in _walk(it.geom):
            if isinstance(g, Polygon):
                rings = [g.exterior] + list(g.interiors)
                if it.fill:
                    h = msp.add_hatch(dxfattribs={"layer": it.layer})
                    h.rgb = tuple(int(it.fill.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
                    for r in rings:
                        h.paths.add_polyline_path(_pts(r.coords), is_closed=True)
                    h.set_xdata("T14S", [(1000, it.prov)])
                if it.pen:
                    for r in rings:
                        e = msp.add_lwpolyline(_pts(r.coords), close=True, dxfattribs=base)
                        e.set_xdata("T14S", [(1000, it.prov)])
                        n += 1
            else:
                e = msp.add_lwpolyline(_pts(g.coords), dxfattribs=base)
                e.set_xdata("T14S", [(1000, it.prov)])
                n += 1
    for t in d.texts:
        role = TEXT_ROLES[t.role]
        size_mm = (t.size_pt or role.size) * PT * SCALE_DEN
        e = msp.add_text(t.s, height=size_mm, rotation=t.rotate,
                         dxfattribs={"layer": t.layer, "true_color": _rgb(t.color or role.color)})
        al = {"middle": TextEntityAlignment.MIDDLE_CENTER, "start": TextEntityAlignment.MIDDLE_LEFT,
              "end": TextEntityAlignment.MIDDLE_RIGHT}[t.anchor]
        e.set_placement((t.x * 1000.0, (t.y + 0.2) * 1000.0), align=al)
        e.set_xdata("T14S", [(1000, t.prov)])
        n += 1
    doc.saveas(str(path))
    return n

"""Verified structure layer: everything here comes straight from the model slice (MODEL_VERIFIED)."""
from __future__ import annotations

from shapely.geometry import LineString, Point, box

from .model import MODEL_VERIFIED, Drawing
from .source import COL_R, FloorGeometry


def add_structure(d: Drawing, g: FloorGeometry):
    V = MODEL_VERIFIED
    d.add("A-WALL-EXT", LineString(g.outline.exterior.coords), "cut_heavy", prov=V, ref="slab edge")
    if g.facade.get("glass") is not None:
        d.add("A-GLAZ", g.facade["glass"], "projection_light", prov=V, ref="A-FACD_glass")
    if g.facade.get("louver") is not None:
        d.add("A-GLAZ", g.facade["louver"], "detail", prov=V, ref="A-FACD_louver")
    if g.facade.get("mullion") is not None:
        d.add("A-GLAZ", g.facade["mullion"], "projection_light", fill="#333333", prov=V, ref="A-FACD_mullion")
    for i, h in enumerate(g.holes):
        d.add("A-FLOR-OPEN", h, "cut_medium", prov=V, ref="slab opening %d" % (i + 1))
    for x, y in g.columns:
        d.add("A-COLS", Point(x, y).buffer(COL_R, quad_segs=12), "cut_heavy", fill="#000000", prov=V, ref="column")
    for cid, b in g.cores.items():
        d.add("A-WALL-CORE", box(*b), "cut_heavy", prov=V, ref="core %s footprint (model: solid box)" % cid)
    for n, t in g.tubes.items():
        d.add("A-TUBE", t.outer, "cut_medium", prov=V, ref="tube %s outer" % n)
    for n, s in g.shafts.items():
        d.add("A-TUBE", s, "cut_medium", prov=V, ref="shaft %s" % n)
    for e in g.escalators:
        d.add("A-STAR", e["poly"], "projection_light", prov=V, ref="escalator cut %s" % e["name"])

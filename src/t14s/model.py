"""Layered drawing model shared by the SVG, DXF and PDF exporters (one source -> three formats).

World units are metres, y up (slice frame). Pens/text roles follow AGENTS.md 3.1 via engine/render/style.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from shapely.geometry.base import BaseGeometry

from render.style import LINE_CLASSES, TEXT_ROLES

MODEL_VERIFIED = "MODEL_VERIFIED"
PROPOSED = "PROPOSED_DESIGN"
SYMBOL_REUSE = "PROPOSED_DESIGN__VERIFIED_1F_SYMBOL"

SCALE_DEN = 200
MM_PER_M = 1000.0 / SCALE_DEN                       # paper mm per world metre at 1:200
PT = 0.3528                                          # mm per pt

# draw order (bottom -> top), name, description
LAYERS = [
    ("A-ZONE", "Program zone tint (hatch)"),
    ("A-FLOR-OPEN", "Floor openings / voids"),
    ("A-GRID", "Structural grid"),
    ("A-FURN", "Furniture and fit-out (proposed)"),
    ("A-FIXT", "Sanitary fixtures"),
    ("A-STAR", "Stairs, escalators, ramps"),
    ("A-WALL-PART", "Partitions"),
    ("A-DOOR", "Doors and swings"),
    ("A-GLAZ", "Curtain wall / glazing"),
    ("A-TUBE", "Vertical tubes"),
    ("A-WALL-CORE", "Core walls"),
    ("A-WALL-EXT", "Slab edge / exterior"),
    ("A-COLS", "Structural columns"),
    ("A-CIRC", "Circulation routes (proposed)"),
    ("A-ANNO-TAGS", "Room tags"),
    ("A-ANNO-TEXT", "Text"),
    ("A-ANNO-DIMS", "Dimensions"),
    ("A-ANNO-SYMB", "Annotation symbols"),
]
LAYER_ORDER = {n: i for i, (n, _) in enumerate(LAYERS)}

# paper mm per pen (cut ~0.5 / 0.3 / 0.16 / 0.09 / 0.07 as in tools/t14d_sheet.py); colours from the engine style table
PEN_MM = {"cut_heavy": 0.50, "cut_medium": 0.30, "projection_light": 0.16, "detail": 0.09, "grid": 0.07,
          "dim": 0.09, "hair": 0.05, "boundary": 0.2, "context": 0.09}
PEN_COLOR = {k: v.color for k, v in LINE_CLASSES.items()}
PEN_MM["circ"] = 0.18
DXF_CIRC_LW = 15
PEN_COLOR.update({"dim": "#555555", "hair": "#999999", "circ": "#2f5d8a", "zone": "#cfcfcf"})
PEN_MM["zone"] = 0.05
PEN_DASH = {"detail": (1.2, 0.8), "grid": (4.0, 1.0, 0.8, 1.0), "circ": (2.2, 0.9, 0.5, 0.9)}   # paper mm
DXF_LW = {"cut_heavy": 50, "cut_medium": 30, "projection_light": 15, "detail": 9, "grid": 5, "dim": 9, "hair": 5,
          "boundary": 20, "context": 9}


@dataclass
class Item:
    layer: str
    geom: BaseGeometry
    pen: str | None = "projection_light"
    fill: str | None = None
    prov: str = PROPOSED
    ref: str = ""
    dash: str | None = None            # key into PEN_DASH
    opacity: float = 1.0


@dataclass
class Text:
    x: float
    y: float
    s: str
    role: str = "sub"                  # key into TEXT_ROLES
    layer: str = "A-ANNO-TEXT"
    anchor: str = "middle"
    box: bool = False                  # white halo/box behind the text (AGENTS 3.1 zero-collision fallback)
    rotate: float = 0.0
    prov: str = PROPOSED
    size_pt: float | None = None
    color: str | None = None
    weight: str | None = None


def text_extent_m(s: str, size_pt: float, weight: str = "normal") -> tuple:
    """Rough (width, height) in world metres of a one-line label, CJK counted full-width."""
    mm = size_pt * PT
    w = sum((1.0 if ord(c) > 0x2E80 else 0.58) for c in s) * mm * (1.06 if weight == "bold" else 1.0)
    return w / MM_PER_M, mm * 1.25 / MM_PER_M


@dataclass
class Drawing:
    floor: str
    items: list = field(default_factory=list)
    texts: list = field(default_factory=list)
    rooms: list = field(default_factory=list)       # dicts: id,name,program,poly,area_m2,prov,...
    notes: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    def add(self, layer, geom, pen="projection_light", fill=None, prov=PROPOSED, ref="", dash=None, opacity=1.0):
        if geom is None or geom.is_empty:
            return
        assert layer in LAYER_ORDER, layer
        self.items.append(Item(layer, geom, pen, fill, prov, ref, dash, opacity))

    def text(self, x, y, s, role="sub", **kw):
        self.texts.append(Text(x, y, s, role, **kw))

    def counts_by_prov(self) -> dict:
        out: dict = {}
        for it in self.items:
            out[it.prov] = out.get(it.prov, 0) + 1
        return out

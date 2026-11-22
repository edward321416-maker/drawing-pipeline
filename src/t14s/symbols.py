"""Wrappers around the verified engine symbol builders (stair core, restroom, tubes) -> Drawing items.

The 1F master verified these symbols; on upper floors the *location* is model-verified (core footprints, tube openings)
while the interior content is a PROPOSED_DESIGN reuse of the same symbol.
"""
from __future__ import annotations

import json
import math

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from . import ROOT
from .model import PROPOSED, SYMBOL_REUSE, Drawing
from .source import COL_R

from engine_params import load_params
from symbols.restroom import PROGRAM_BY_ROOM, all_doors, build_restroom
from symbols.stair_core import CORE_VES_SIDE, build_stair_core
from symbols.tube import build_capsule, build_elevator, build_light, build_ramp

PARAMS = load_params()
ADJ = json.loads((ROOT / "engine" / "model" / "design_adjustments.json").read_text(encoding="utf-8"))
M1F = json.loads((ROOT / "engine" / "model" / "m_1f_source.json").read_text(encoding="utf-8"))
WALL_FILL = "#666666"
CORE_FILL = "#1a1a1a"


def core_hall_offset(cid: str) -> float:
    return ADJ.get("core_hall_door_offset", {}).get(cid, {}).get("offset_m", 0.0)


def wc_bounds() -> dict:
    """Verified 1F restroom bounds (slice frame == m_1f_source frame) with the user-approved shifts applied."""
    out = {}
    for wid, b in M1F["wc"].items():
        dy = ADJ.get("restroom_shift", {}).get(wid, {}).get("dy_m", 0.0)
        out[wid] = (b[0], b[1] + dy, b[2], b[3] + dy)
    return out


def _door_items(d: Drawing, leaf, arc, ref, prov=SYMBOL_REUSE, sliding=False):
    if leaf is not None:
        d.add("A-DOOR", leaf, "projection_light", prov=prov, ref=ref + " leaf")
    if arc is not None:
        d.add("A-DOOR", arc, "detail", prov=prov, ref=ref + " swing")


def add_core(d: Drawing, cid: str, bounds, served: bool) -> dict:
    """Core interior = verified 1F stair-core symbol (4-way square stair, vestibule, fire doors). Returns facts."""
    core = build_stair_core(cid, bounds, CORE_VES_SIDE[cid], PARAMS.stair, hall_door_offset=core_hall_offset(cid))
    S = SYMBOL_REUSE
    d.add("A-WALL-CORE", core.walls, "cut_heavy", fill=CORE_FILL, prov=S, ref="core %s wall" % cid)
    d.add("A-WALL-CORE", core.partition, "cut_medium", fill=WALL_FILL, prov=S, ref="core %s vestibule partition" % cid)
    for fl in core.flights:
        d.add("A-STAR", fl.polygon, "detail", prov=S, ref="core %s flight %d" % (cid, fl.index))
        for line, solid in fl.tread_lines:
            d.add("A-STAR", line, "projection_light" if solid else "detail", prov=S, ref="tread",
                  dash=None if solid else "detail")
    for ld in core.landings:
        d.add("A-STAR", ld, "projection_light", prov=S, ref="core %s landing" % cid)
    if core.break_line is not None:
        d.add("A-STAR", core.break_line, "projection_light", prov=S, ref="core %s cut line (1.5 m)" % cid)
    d.add("A-STAR", core.arrow, "projection_light", prov=S, ref="core %s UP arrow" % cid)
    d.add("A-STAR", core.arrow_head, "projection_light", fill="#333333", prov=S, ref="core %s UP arrow head" % cid)
    for door in core.doors:
        d.add("A-DOOR", LineString([door.hinge, door.open_end]), "projection_light", prov=S, ref="core %s door leaf" % cid)
        d.add("A-DOOR", door.arc, "detail", prov=S, ref="core %s door swing" % cid)
    hall_door = core.doors[0]
    return {"core": core, "served": served, "hall_swing": hall_door.swing, "vestibule": core.vestibule,
            "well": core.well, "hall_door_c": ((hall_door.hinge[0] + hall_door.closed_end[0]) / 2,
                                               (hall_door.hinge[1] + hall_door.closed_end[1]) / 2)}


def add_restroom(d: Drawing, rid: str, bounds) -> dict:
    rr = build_restroom(rid, bounds, PROGRAM_BY_ROOM[rid], PARAMS.restroom)
    S = SYMBOL_REUSE
    d.add("A-WALL-PART", rr.walls, "cut_medium", fill=WALL_FILL, prov=S, ref="restroom %s wall" % rid)
    if not rr.inner_walls.is_empty:
        d.add("A-WALL-PART", rr.inner_walls, "cut_medium", fill=WALL_FILL, prov=S, ref="restroom %s inner wall" % rid)
    for i, g in enumerate(rr.thin):
        d.add("A-WALL-PART", g, "projection_light", fill="#888888", prov=S, ref="restroom %s cubicle partition %d" % (rid, i + 1))
    for f in rr.fixtures:
        d.add("A-FIXT", f.polygon, "projection_light", prov=S, ref="restroom %s %s" % (rid, f.name))
    for g in rr.details:
        d.add("A-FIXT", g, "detail", prov=S, ref="restroom %s basin bowl" % rid)
    swings = []
    for dr in all_doors(rr):
        _door_items(d, dr.leaf, dr.arc, "restroom %s door %s" % (rid, dr.name))
        if dr.travel is not None:
            d.add("A-DOOR", dr.travel, "detail", prov=S, ref="restroom %s sliding travel" % rid, dash="detail")
        if dr.swing is not None:
            swings.append(dr.swing)
    clear = unary_union([u.clear_zone for u in rr.units] + [u.corridor for u in rr.units if u.corridor is not None])
    units = [{"name": u.name, "label": u.label, "poly": u.interior} for u in rr.units]
    return {"rr": rr, "swings": unary_union(swings) if swings else Polygon(), "clear": clear, "units": units,
            "footprint": box(*bounds).buffer(0.08), "program": PROGRAM_BY_ROOM[rid]}


def _round_r(r: float) -> float:
    return round(r * 20) / 20.0


def add_tube(d: Drawing, name: str, tube, ramp_here: bool, columns, envelope) -> dict:
    """tube: source.Tube. Returns facts (obstacle polygons, entry points)."""
    S = SYMBOL_REUSE
    c = (round(tube.center[0], 2), round(tube.center[1], 2))
    r = _round_r(tube.r)
    entry = None
    if name == "T1":
        tb = build_ramp("T1", "T1 나선 램프", c, r, PARAMS.tube, columns, envelope) if ramp_here else \
            build_light("T1", "T1 빛 튜브", c, r, PARAMS.tube, columns, envelope)
    elif name == "T2":
        tb = build_light("T2", "T2 빛 튜브", c, r, PARAMS.tube, columns, envelope)
    elif name in ("T3", "T4"):
        tb = build_elevator(name, "%s 전망 승강기" % name, c, r, PARAMS.tube, columns, envelope)
    elif name.startswith("cap"):
        tb = build_capsule(name, "캡슐 " + name[3:], tube.outer, PARAMS.tube, columns, envelope)
    else:
        return add_small_shaft(d, name, tube)
    d.add("A-TUBE", tb.ring, "cut_medium", fill="#ffffff", prov=S, ref="%s glass wall" % name)
    if tb.inner_ring is not None:
        d.add("A-TUBE", tb.inner_ring, "cut_medium", fill="#ffffff", prov=S, ref="%s inner rim" % name)
    if tb.spiral is not None:
        d.add("A-STAR", tb.spiral, "projection_light", prov=S, ref="%s spiral ramp arrow" % name)
        d.add("A-STAR", tb.arrow_head, "projection_light", fill="#333333", prov=S, ref="%s spiral arrow head" % name)
    for sh in tb.shafts:
        d.add("A-TUBE", sh.walls, "cut_medium", fill=WALL_FILL, prov=S, ref="%s %s wall" % (name, sh.name))
        for dg in sh.diagonals:
            d.add("A-TUBE", dg, "projection_light", prov=S, ref="%s %s X" % (name, sh.name))
        d.add("A-DOOR", sh.door.leaf, "projection_light", prov=S, ref="%s %s door" % (name, sh.name))
    for dr in tb.doors:
        d.add("A-DOOR", dr.leaf, "projection_light", prov=S, ref="%s entry sliding door" % name)
    if tb.entry_zone is not None:
        entry = tb.entry_zone
    return {"tube": tb, "entry_zone": entry, "kind": tb.kind, "center": c, "r": r}


def add_small_shaft(d: Drawing, name: str, tube) -> dict:
    """FR / M1 / M2 / PL (verified openings): ring + X, labelled by the caller."""
    S = SYMBOL_REUSE
    outer = tube.outer
    inner = outer.buffer(-PARAMS.tube.glass_t_m)
    d.add("A-TUBE", outer.difference(inner), "cut_medium", fill=WALL_FILL, prov=S, ref="%s shaft wall" % name)
    x0, y0, x1, y1 = inner.bounds
    for dg in (LineString([(x0, y0), (x1, y1)]), LineString([(x0, y1), (x1, y0)])):
        d.add("A-TUBE", dg.intersection(inner), "projection_light", prov=S, ref="%s shaft X" % name)
    return {"kind": "shaft", "center": tube.center, "r": tube.r, "entry_zone": None}


def add_ev_shaft(d: Drawing, name: str, poly) -> dict:
    """EV1 / EV2 emergency elevator shafts (model 'shaft' squares)."""
    S = SYMBOL_REUSE
    inner = poly.buffer(-PARAMS.tube.shaft_wall_t_m, join_style=2)
    d.add("A-TUBE", poly.difference(inner), "cut_medium", fill=WALL_FILL, prov=S, ref="%s shaft wall" % name)
    x0, y0, x1, y1 = inner.bounds
    for dg in (LineString([(x0, y0), (x1, y1)]), LineString([(x0, y1), (x1, y0)])):
        d.add("A-TUBE", dg, "projection_light", prov=S, ref="%s shaft X" % name)
    return {"kind": "shaft", "center": (poly.centroid.x, poly.centroid.y)}

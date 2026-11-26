# -*- coding: utf-8 -*-
"""R10B  A-201 (2F plan, 1:200) interior fit-out DEVELOPMENT layer.

Everything produced here is evidence class FIT_OUT_DEVELOPMENT: a design-development candidate, NOT verified, and no
code/regulatory compliance is claimed.  The PR30 plan (rooms, walls, doors, columns, cores, tubes, voids, existing A-FURN /
A-FIXT) is IMMUTABLE: this module only reads it and returns NEW geometry.  No room is subdivided, no programme changed, no
ceiling height is assumed.  Output is deterministic (no randomness).

Public API
    develop_fitout(PR, G) -> FitList (list[FitItem], with .dropped / .info side data)
    derive_corridors(site_or_PR, G=None) -> main / secondary corridor zones used for the hall
    Site(PR, G) -> read-only view of the obstacles (shared with fitout_checks_r10b)
Room ids follow the printed convention "2-NN" (PR.rooms id "NN").
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "src", ROOT / "engine"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import nearest_points, unary_union
from shapely.prepared import prep

from t14s.walknet import WalkNet

PROV = "FIT_OUT_DEVELOPMENT"
MARGIN = 0.01             # m: hall exclusion buffers are inflated by this so polygonised arcs never end up closer than the stated clearance
EPS = 0.005              # m: placements sit this far inside their region boundary so float noise cannot flip `covers`
TOL_AREA = 1e-6          # m2: area below this is float noise, not an overlap (explicit, reported by the checks)

# --------------------------------------------------------------------------------------------- dimension basis (mm)
_BRIEF = "R10B fit-out brief (task spec): "
_GEN = "generic design-development assumption"
_PGM = "src/t14s/program.py boh_items (L249-L300): "
DIMS = {
    # kind: (w_mm, d_mm, basis)
    "chair": (420, 420, _BRIEF + "dining chair 0.42x0.42 m (cf. src/furniture_library.py:26 chair s=0.42); pull-out zone 0.45 m behind = " + _GEN),
    "stool": (360, 360, "stool dia 0.36 m = src/furniture_library.py:41 stool r=0.18; pull-out 0.45 m = " + _GEN),
    "table_4top": (900, 900, _BRIEF + "4-top table 0.9x0.9 m (cf. src/t14s/fitout.py:_fnb table 0.9x0.9)"),
    "table_2top": (700, 700, _BRIEF + "2-top table 0.7x0.7 m"),
    "table_comm": (2400, 900, _BRIEF + "communal table 2.4x0.9 m, 8 chairs (cf. src/furniture_library.py:402 communal_table)"),
    "banquette": (None, 550, _BRIEF + "wall banquette 0.55 m deep (cf. src/furniture_library.py:412 banquette 0.55); seat 0.6 m/person = " + _GEN),
    "cash_counter": (1200, 600, _BRIEF + "service/cash counter 1.2x0.6 m (cf. src/furniture_library.py:352 cash_counter 1.2x0.6)"),
    "service_counter": (3000, 800, _BRIEF + "hall service counter 3.0x0.8 m with stools (cf. src/upper_layouts.py:fnb bar counters)"),
    "range": (800, 700, _PGM + "cooking range 0.8x0.7 m (L276-L281)"),
    "hood": (None, 800, "exhaust hood outline over a range run, 0.8 m deep = range 0.7 m + 0.1 m front overhang (" + _GEN + "); overhead, drawn dashed; ceiling height NOT assumed"),
    "sink_double": (1200, 600, _BRIEF + "double sink 1.2x0.6 m"),
    "fridge": (700, 800, _BRIEF + "reach-in refrigerator 0.7x0.8 m"),
    "dishwasher": (700, 700, _BRIEF + "dishwasher / pass-through 0.7x0.7 m"),
    "prep_counter": (None, 700, _BRIEF + "stainless wall prep counter 0.7 m deep (= " + _PGM + "L276 strip depth 0.7)"),
    "island": (2400, 1000, _BRIEF + "central island 2.4x1.0 m only if room depth >= 4.4 m (= " + _PGM + "L288-L289)"),
    "sink_wash": (700, 600, _PGM + "washing sink 0.7x0.6 m (L293)"),
    "dish_table": (1200, 700, _BRIEF + "dish table 1.2x0.7 m (cf. " + _PGM + "L298 table 1.8x0.8)"),
    "rack": (None, 500, _BRIEF + "shelving rack 0.5 m deep (cf. " + _PGM + "L305 rack 0.5)"),
    "shelf": (None, 450, _BRIEF + "wall shelf 0.45 m deep (cf. " + _PGM + "L301 wall_strips depth 0.45)"),
    "cart": (600, 900, _BRIEF + "pallet/cart parking only if the room allows; cart 0.6x0.9 m = " + _GEN),
}
SEAT_PER_BANQ_M = 0.6           # m of banquette per person (generic)

CHAIR = 0.42
PULL = 0.45                     # chair pull-out zone behind the chair
HALL_GAP = 1.5                  # secondary aisle between hall seating clusters (brief)
CLUSTER_GAP = 0.9               # lane inside one cluster (brief: aisles >= 0.9 m between table groups)
ROOM_GAP = 0.9                  # dining-unit aisle between table groups (brief: >= 0.9 m)
COL_CLEAR_HALL = 0.6            # brief: 0.6 m around columns in the hall
COL_CLEAR_ROOM = 0.3            # generic (rooms are small); brief gives no value
HAZARD_CLEAR = 1.5              # brief: 1.5 m from void edges, tube walls, core walls, stairs/escalator landings
FURN_CLEAR_HALL = 0.6           # brief: 0.6 m from existing PR furniture in the hall
FURN_CLEAR_ROOM = 0.1           # generic (overlap itself is excluded by the checks; 0.1 m keeps items from touching)
MAIN_CORR_HALF = 1.5            # main corridor 3.0 m wide
SEC_CORR_HALF = 0.9             # service corridor 1.8 m wide (>= 1.5 secondary-aisle rule)
WALL_INSET = 0.15               # brief: >= 0.15 m from walls except banquettes
BANQ_INSET = 0.125              # brief: furniture within room.poly.buffer(-0.12); 5 mm margin against float noise
WORK_AISLE = 1.0                # kitchens: 1.0 m minimum working aisle
STORE_AISLE = 0.9               # storage / wash rooms: >= 0.9 m aisle
DOOR_APRON = 0.9                # keep-clear depth in front of an internal door (both sides)
UNIT_DOOR_APRON = 1.2           # keep-clear depth in front of a dining-unit entrance (project rule: 1.2 m clear)


@dataclass
class FitItem:
    id: str
    room_id: str
    kind: str
    geom: BaseGeometry
    clear: "BaseGeometry | None"
    dims_mm: tuple
    basis: str
    prov: str = PROV
    group: str = ""
    seats: int = 0
    draw: str = "solid"           # "dashed" for overhead hood outlines


class FitList(list):
    """list[FitItem] plus side data (dropped items, seat counts, derived corridors)."""
    dropped: list
    info: dict


# ------------------------------------------------------------------------------------------------ helpers
def _flat(g):
    if g is None or g.is_empty:
        return []
    if g.geom_type.startswith("Multi") or g.geom_type == "GeometryCollection":
        out = []
        for x in g.geoms:
            out += _flat(x)
        return out
    return [g]


def _circumcenter(a, b, c):
    ax, ay = a
    bx, by = b
    cx, cy = c
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-9:
        return None
    a2, b2, c2 = ax * ax + ay * ay, bx * bx + by * by, cx * cx + cy * cy
    return ((a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d, (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d)


def furniture_polys(it_geom, line_buf=0.03):
    """PR furniture geometry as filled shapes: closed rings (stool circles) -> polygon, open lines -> thin strip."""
    out = []
    for g in _flat(it_geom):
        if g.geom_type == "Polygon":
            out.append(g)
        elif g.geom_type == "LineString":
            c = list(g.coords)
            if len(c) >= 8 and math.dist(c[0], c[-1]) < 1e-6:
                out.append(Polygon(c).buffer(0))
            else:
                out.append(g.buffer(line_buf))
    return out


@dataclass
class Door:
    idx: int
    ref: str
    sector: Polygon
    hinge: tuple
    mid: tuple          # midpoint of the wall opening (closed leaf position)
    tip: tuple          # end of the opening away from the hinge
    radius: float
    seg: LineString     # wall opening (hinge -> tip)
    rooms: list

    def apron(self, depth):
        return self.seg.buffer(depth, cap_style=2)


def parse_doors(PR, room_polys):
    """Swing sectors (pie slices) from the A-DOOR swing arcs of the PR plan.  The wall opening is the radial edge whose
    midpoint lies on a room boundary."""
    allb = unary_union([p.exterior for p in room_polys.values()])
    doors = []
    for idx, it in enumerate(PR.items):
        if it.layer != "A-DOOR" or "swing" not in it.ref or "sliding" in it.ref:
            continue
        for k, arc in enumerate(_flat(it.geom)):
            pts = list(arc.coords)
            if len(pts) < 3:
                continue
            c = _circumcenter(pts[0], pts[len(pts) // 2], pts[-1])
            if c is None:
                continue
            r = math.dist(c, pts[0])
            sector = Polygon([c] + pts).buffer(0)
            cand = []
            for q in (pts[0], pts[-1]):
                mid = ((c[0] + q[0]) / 2, (c[1] + q[1]) / 2)
                cand.append((Point(mid).distance(allb), mid, q))
            _, mid, tip = min(cand, key=lambda t: t[0])
            rooms = [rid for rid, p in room_polys.items() if p.distance(Point(mid)) < 0.15]
            doors.append(Door(idx, it.ref, sector, c, mid, tip, r, LineString([c, tip]), rooms))
    return doors


class Site:
    """Read-only obstacle view of the PR plan (nothing here is ever mutated)."""

    def __init__(self, PR, G):
        self.PR, self.G = PR, G
        self.rooms = {"2-" + r["id"]: r for r in PR.rooms}
        self.room_polys = {k: r["poly"] for k, r in self.rooms.items()}
        by = {}
        for i, it in enumerate(PR.items):
            by.setdefault(it.layer, []).append(it)

        def polys(layer, line_buf=0.0):
            out = []
            for it in by.get(layer, []):
                for g in _flat(it.geom):
                    if g.geom_type == "Polygon":
                        out.append(g)
                    elif line_buf > 0 and g.geom_type == "LineString":
                        out.append(g.buffer(line_buf))
            return out

        self.cols = unary_union(polys("A-COLS"))
        self.wall_core = unary_union(polys("A-WALL-CORE"))
        self.wall_part = unary_union(polys("A-WALL-PART"))
        self.wall_ext = unary_union(polys("A-WALL-EXT", 0.05))
        self.glaz = unary_union(polys("A-GLAZ"))
        self.tube = unary_union(polys("A-TUBE"))
        self.void = unary_union(polys("A-FLOR-OPEN"))
        self.star = unary_union(polys("A-STAR", 0.02))
        self.rail = unary_union(polys("A-RAIL", 0.03))
        self.hard = unary_union([self.cols, self.wall_core, self.wall_part, self.wall_ext, self.glaz, self.tube, self.void, self.star])
        furn = []
        for layer in ("A-FURN", "A-FIXT"):
            for it in by.get(layer, []):
                furn += furniture_polys(it.geom)
        self.furn_list = furn
        self.furn = unary_union(furn) if furn else Polygon()
        self.doors = parse_doors(PR, self.room_polys)
        self.door_sectors = unary_union([d.sector for d in self.doors]) if self.doors else Polygon()
        self.hall = self.rooms["2-10"]["poly"]
        self._grid = None

    # structural grid derived from the column positions (not hard-coded)
    def grid(self):
        if self._grid is None:
            xs = sorted(c[0] for c in self.G.columns)
            ys = sorted(c[1] for c in self.G.columns)

            def cluster(v, tol=0.3):
                out = []
                for a in v:
                    if out and abs(a - out[-1][-1]) <= tol:
                        out[-1].append(a)
                    else:
                        out.append([a])
                return [(float(np.mean(c)), len(c)) for c in out]

            def lines(v):
                cl = cluster(v)
                gaps = [b[0] - a[0] for a, b in zip(cl, cl[1:]) if 8.5 <= b[0] - a[0] <= 9.5]
                pitch = float(np.median(gaps)) if gaps else 9.0
                # interior grid lines = clusters having a neighbouring line one pitch away on both sides (perimeter columns are
                # inset 0.6 m from the slab edge, so a 0.8 m tolerance is used)
                vals = [c[0] for c in cl]
                inner = [x for x in vals if any(abs(y - (x - pitch)) < 0.8 for y in vals) and any(abs(y - (x + pitch)) < 0.8 for y in vals)]
                phase = float(np.mean([x - pitch * round(x / pitch) for x in inner])) if inner else 0.0
                k0 = int(math.floor((min(v) - pitch - phase) / pitch))
                k1 = int(math.ceil((max(v) + pitch - phase) / pitch))
                return pitch, [phase + k * pitch for k in range(k0, k1 + 1)]

            px, X = lines(xs)
            py, Y = lines(ys)
            self._grid = {"pitch_x": px, "pitch_y": py, "X": X, "Y": Y}
        return self._grid

    def furn_near(self, poly, d=1.0):
        return self.furn.intersection(poly.buffer(d)) if not self.furn.is_empty else Polygon()


# ------------------------------------------------------------------------------------------------ corridors
def derive_corridors(site: Site) -> dict:
    """Main hall corridors (3.0 m clear = centre line +-1.5 m) and secondary service corridors (1.8 m).
    Centre lines = the planner's visitor routes between core / tube / WC access nodes (PR.meta graph, A-CIRC) plus a stub from
    every dining-unit door apron to the nearest route, found with the planner's own raster walking graph on the hall polygon."""
    PR, hall = site.PR, site.hall
    gr = PR.meta["graph"]
    main = [LineString(e["coords"]) for e in gr["edges"] if e.get("length_m", 0) > 0 and len(e["coords"]) >= 2]
    svc = [LineString(e["coords"]) for e in gr["service_edges"] if len(e["coords"]) >= 2]
    region = hall.buffer(-0.35).difference(site.cols.buffer(0.62)).difference(site.door_sectors.buffer(0.05)).buffer(0)
    stubs = []
    notes = []
    net = WalkNet(region, 0.3)
    if net.n and main:
        cells = set()
        for ls in main:
            for d in np.arange(0.0, ls.length + 0.3, 0.3):
                c, _ = net.nearest(ls.interpolate(min(d, ls.length)).coords[0], 1.0)
                if c is not None:
                    cells.add(c)
        dist, pred = net.dist_from(sorted(cells))
        for rid, r in sorted(site.rooms.items()):
            if r["kind"] != "unit" or not r.get("door"):
                continue
            dr = r["door"]
            sr = dr["w"] if dr["w"] < 1.6 else dr["w"] / 2
            apron = (dr["center"][0] + dr["n"][0] * (sr + 0.45), dr["center"][1] + dr["n"][1] * (sr + 0.45))
            cell, dd = net.nearest(apron, 1.2)
            if cell is None or not np.isfinite(dist[cell]):
                notes.append("unit door %s: apron not on the walkable network, no stub" % rid)
                continue
            pts = net.path(pred, cell)
            ls = LineString([tuple(dr["center"])] + [tuple(p) for p in reversed(pts)])
            stubs.append(ls)
    lines_main = main + stubs
    zone_main = unary_union([l.buffer(MAIN_CORR_HALF) for l in lines_main]).intersection(hall) if lines_main else Polygon()
    zone_sec = unary_union([l.buffer(SEC_CORR_HALF) for l in svc]).intersection(hall) if svc else Polygon()
    return {"main_lines": lines_main, "service_lines": svc, "main_zone": zone_main, "service_zone": zone_sec, "notes": notes,
            "n_trunk": len(main), "n_stubs": len(stubs)}


# ------------------------------------------------------------------------------------------------ units (local frame)
class Unit:
    """A seating / equipment group.  Templates are built once in a local frame; `placed` only transforms the two summary
    geometries (foot, clear) so lattice trials are cheap, and the individual parts are transformed lazily when emitted."""

    def __init__(self, kind, parts, cluster=""):
        self.kind, self.cluster = kind, cluster
        self._parts, self._m = parts, None
        self.foot = unary_union([p[1] for p in parts])
        cl = [p[4] for p in parts if p[4] is not None]
        self.clear_u = unary_union(cl) if cl else None
        self.b = self.foot.bounds
        self.seats = sum(p[3] for p in parts)

    @property
    def parts(self):
        if self._m is None:
            return self._parts
        m = self._m
        return [(k, affinity.affine_transform(g, m), d, s, None if c is None else affinity.affine_transform(c, m)) for k, g, d, s, c in self._parts]

    def placed(self, p, t, n, cluster=None):
        m = [t[0], n[0], t[1], n[1], p[0], p[1]]
        u = object.__new__(Unit)
        u.kind = self.kind
        u.cluster = self.cluster if cluster is None else cluster
        u._parts, u._m = self._parts, m
        u.foot = affinity.affine_transform(self.foot, m)
        u.clear_u = None if self.clear_u is None else affinity.affine_transform(self.clear_u, m)
        u.b = u.foot.bounds
        u.seats = self.seats
        return u


def _chair(cx, cy, dx, dy):
    """chair whose centre lies at (cx, cy); (dx, dy) = unit direction from the table to the chair."""
    seat = box(cx - CHAIR / 2, cy - CHAIR / 2, cx + CHAIR / 2, cy + CHAIR / 2)
    zx, zy = cx + dx * (CHAIR / 2 + PULL / 2), cy + dy * (CHAIR / 2 + PULL / 2)
    w, h = (PULL, CHAIR) if abs(dx) > 0.5 else (CHAIR, PULL)
    return ("chair", seat, (420, 420), 1, box(zx - w / 2, zy - h / 2, zx + w / 2, zy + h / 2))


def _tbl(kind, cx, cy, w, h):
    d = DIMS[kind]
    return (kind, box(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), (int(round(w * 1000)), int(round(h * 1000))), 0, None)


@lru_cache(maxsize=None)
def u_4top():
    p = [_tbl("table_4top", 0, 0, 0.9, 0.9)]
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        p.append(_chair(dx * 0.66, dy * 0.66, dx, dy))
    return Unit("4top", p)


@lru_cache(maxsize=None)
def u_2top():
    p = [_tbl("table_2top", 0, 0, 0.7, 0.7)]
    for dx in (1, -1):
        p.append(_chair(dx * 0.56, 0, dx, 0))
    return Unit("2top", p)


@lru_cache(maxsize=None)
def u_comm():
    p = [_tbl("table_comm", 0, 0, 2.4, 0.9)]
    for k in range(4):
        for dy in (1, -1):
            p.append(_chair(-0.9 + 0.6 * k, dy * 0.66, 0, dy))
    return Unit("comm", p)


@lru_cache(maxsize=None)
def u_bank(L):
    """wall banquette bay.  Local frame: wall at y=0, room side +y, bay centred on x=0, L long."""
    p = [("banquette", box(-L / 2, 0, L / 2, 0.55), (int(round(L * 1000)), 550), int(round(L / SEAT_PER_BANQ_M)), None)]
    n = int(round(L / 0.9))
    for i in range(n):
        cx = -L / 2 + 0.45 + 0.9 * i
        p.append(_tbl("table_4top", cx, 0.55 + 0.10 + 0.45, 0.9, 0.9))
        for sx in (-0.225, 0.225):
            p.append(_chair(cx + sx, 0.55 + 0.10 + 0.9 + 0.21, 0, 1))
    return Unit("bank", p)


@lru_cache(maxsize=None)
def u_counter(stools=4):
    """hall service counter 3.0x0.8, staff side -y (1.0 m clear), customer side +y with stools."""
    p = [("service_counter", box(-1.5, 0, 1.5, 0.8), (3000, 800), 0, box(-1.5, -1.0, 1.5, 0.0))]
    for i in range(stools):
        x = (i - (stools - 1) / 2) * 0.7
        cy = 0.8 + 0.05 + 0.18
        p.append(("stool", Point(x, cy).buffer(0.18, 12), (360, 360), 1, box(x - 0.18, cy + 0.18, x + 0.18, cy + 0.18 + PULL)))
    return Unit("counter", p)


@lru_cache(maxsize=None)
def u_cash():
    return Unit("cash_counter", [("cash_counter", box(-0.6, 0, 0.6, 0.6), (1200, 600), 0, box(-0.6, 0.6, 0.6, 1.5))])


@lru_cache(maxsize=None)
def u_2top_wall():
    """2-top along a wall: chairs tangent to the wall, table 0.7 deep (wall at y=0)."""
    u = u_2top()
    return Unit("2top_edge", [(k, affinity.translate(g, 0, 0.35), d, s, None if c is None else affinity.translate(c, 0, 0.35)) for k, g, d, s, c in u.parts])


class Placer:
    """foot of every unit must lie in `region`; its chair pull-out / staff zones (clear) in `region_c` (default: region); wall
    banquettes use `region_w`.  Units of different clusters keep `gap` apart, units of the same cluster `cgap`."""

    def __init__(self, region, gap, cluster_gap=None, region_c=None, region_w=None):
        def pp(r):
            return prep(r) if (r is not None and not r.is_empty) else None
        self.region = region
        self.prep = pp(region)
        self.prep_c = pp(region_c) if region_c is not None else self.prep
        self.prep_w = pp(region_w) if region_w is not None else self.prep
        self.gap = gap
        self.cgap = gap if cluster_gap is None else cluster_gap
        self.units = []

    def fits(self, u, gap=None, wall=False, extra=()):
        pf = self.prep_w if wall else self.prep
        if pf is None or not pf.covers(u.foot):
            return False
        if u.clear_u is not None:
            pc = self.prep_c if not wall else (self.prep_c if self.prep_c is not None else pf)
            if pc is None or not pc.covers(u.clear_u):
                return False
        for lst in (self.units, extra):
            for v in lst:
                g = self.cgap if (u.cluster and u.cluster == v.cluster) else self.gap
                if gap is not None:
                    g = gap
                if (u.b[0] - g > v.b[2]) or (v.b[0] - g > u.b[2]) or (u.b[1] - g > v.b[3]) or (v.b[1] - g > u.b[3]):
                    continue
                if u.foot.distance(v.foot) < g - 1e-9:
                    return False
                if u.clear_u is not None and u.clear_u.intersection(v.foot).area > TOL_AREA:
                    return False
                if v.clear_u is not None and v.clear_u.intersection(u.foot).area > TOL_AREA:
                    return False
        return True

    def add(self, u):
        self.units.append(u)
        return u

    def try_add(self, u, gap=None, wall=False):
        if self.fits(u, gap, wall):
            self.units.append(u)
            return True
        return False


def best_lattice(pl, make, anchor, px, py, limit, step=0.3, order="rows"):
    """Regular lattice of units (pitch px x py) whose phase is searched (step m) so that the most units fit inside `limit` and
    the placer's regions / gaps.  The anchor is the lattice node of phase 0 (e.g. a bay centre on the column grid); among
    equally good phases the one closest to the anchor wins."""
    minx, miny, maxx, maxy = limit.bounds
    pl_lim = prep(limit)
    nx0 = -int(math.ceil((anchor[0] - minx) / px)) - 1
    nx1 = int(math.ceil((maxx - anchor[0]) / px)) + 1
    ny0 = -int(math.ceil((anchor[1] - miny) / py)) - 1
    ny1 = int(math.ceil((maxy - anchor[1]) / py)) + 1
    best = None
    for ox in np.arange(-px / 2, px / 2 - 1e-9, step):
        for oy in np.arange(-py / 2, py / 2 - 1e-9, step):
            trial = []
            for j in range(ny0, ny1 + 1):
                for i in range(nx0, nx1 + 1):
                    u = make(anchor[0] + ox + i * px, anchor[1] + oy + j * py)
                    if not pl_lim.covers(u.foot):
                        continue
                    if pl.fits(u, extra=trial):
                        trial.append(u)
            score = (len(trial), sum(u.seats for u in trial), -(abs(ox) + abs(oy)))
            if best is None or score > best[0]:
                best = (score, trial)
    return best[1] if best else []


# ------------------------------------------------------------------------------------------------ wall segments
def wall_segments(poly, min_len=0.5):
    """Straight, merged boundary segments of a polygon (exterior + holes) with inward unit normals."""
    segs = []
    rings = [poly.exterior] + list(poly.interiors)
    for ring in rings:
        c = list(ring.coords)[:-1]
        n = len(c)
        if n < 3:
            continue
        # drop vertices that are collinear with their neighbours
        keep = []
        for i in range(n):
            a, b, d = c[i - 1], c[i], c[(i + 1) % n]
            cr = (b[0] - a[0]) * (d[1] - b[1]) - (b[1] - a[1]) * (d[0] - b[0])
            if abs(cr) > 1e-7:
                keep.append(b)
        for i in range(len(keep)):
            a, b = keep[i], keep[(i + 1) % len(keep)]
            L = math.dist(a, b)
            if L < min_len:
                continue
            t = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
            nrm = (-t[1], t[0])
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            if not poly.contains(Point(mid[0] + nrm[0] * 0.2, mid[1] + nrm[1] * 0.2)):
                nrm = (-nrm[0], -nrm[1])
                t = (-t[0], -t[1])
                a, b = b, a
            segs.append({"p0": a, "p1": b, "t": t, "n": nrm, "L": L, "mid": mid})
    return segs


# ------------------------------------------------------------------------------------------------ emission
class Emitter:
    def __init__(self):
        self.items = FitList()
        self.items.dropped = []
        self.items.info = {}
        self._seq = {}

    def unit(self, rid, u, note=""):
        key = (rid, u.kind)
        self._seq[key] = self._seq.get(key, 0) + 1
        grp = "%s-%s-%03d" % (rid, u.kind, self._seq[key])
        for i, (k, g, d, s, c) in enumerate(u.parts):
            basis = DIMS[k][2]
            if note:
                basis = basis + " | " + note
            self.items.append(FitItem("%s-%s%02d" % (grp, k, i), rid, k, g, c, tuple(d), basis, PROV, grp, s))

    def single(self, rid, kind, geom, dims, clear=None, note="", draw="solid", seats=0, tag=""):
        key = (rid, "s-" + kind)
        self._seq[key] = self._seq.get(key, 0) + 1
        grp = "%s-%s-%03d" % (rid, kind, self._seq[key])
        basis = DIMS[kind][2] + ((" | " + note) if note else "")
        self.items.append(FitItem(grp, rid, kind, geom, clear, tuple(dims), basis, PROV, grp, seats, draw))

    def drop(self, rid, kind, reason):
        self.items.dropped.append({"room": rid, "kind": kind, "reason": reason})


# ------------------------------------------------------------------------------------------------ dining units
def _door_keepouts(site, room_poly):
    """swing sectors + aprons of every PR door that opens on this room's boundary."""
    ko = []
    for d in site.doors:
        if room_poly.distance(Point(d.mid)) < 0.15 and room_poly.buffer(0.2).intersects(d.sector):
            ko.append(d.sector.buffer(0.05))
            ko.append(d.apron(DOOR_APRON))
    return unary_union(ko) if ko else Polygon()


def _route_line(region, a, b, step=0.15):
    net = WalkNet(region, step)
    if not net.n:
        return None
    ca, da = net.nearest(a, 0.9)
    cb, db = net.nearest(b, 0.9)
    if ca is None or cb is None:
        return None
    r = net.route(ca, cb)
    if r is None:
        return None
    pts, _ = r
    ls = net.smooth(pts, 0.15) if len(pts) >= 2 else None
    coords = [tuple(a)] + ([tuple(p) for p in ls.coords] if ls is not None else [tuple(p) for p in pts]) + [tuple(b)]
    return LineString(coords)


def _lane_L(poly, walk, a, b):
    """axis-aligned L-shaped lane a -> b whose 1.2 m wide strip lies inside the walkable area; the variant whose corner is
    closest to a wall is taken so the lane does not split the room.  None if neither variant is walkable."""
    best = None
    for corner in ((b[0], a[1]), (a[0], b[1])):
        ln = LineString([a, corner, b])
        if not walk.buffer(0.02).contains(ln):
            continue
        d = Point(corner).distance(poly.exterior)
        if best is None or d < best[0]:
            best = (d, ln)
    return best[1] if best else None


def _unit_support_doors(site, rid):
    """doors in the wall between this dining room and one of its own BOH rooms (kitchen / wash / storage)."""
    room = site.rooms[rid]
    sup = [k for k, r in site.rooms.items() if r.get("parent_id") == room["id"]]
    out = []
    for d in site.doors:
        if rid in d.rooms and any(s in d.rooms for s in sup):
            out.append(d)
    return out


def furnish_dining(site, rid, em):
    room = site.rooms[rid]
    poly = room["poly"]
    area = poly.area
    dr = room["door"]
    inward = (-dr["n"][0], -dr["n"][1])
    keep = _door_keepouts(site, poly)
    ex = site.furn_near(poly)
    hardn = site.hard.intersection(poly.buffer(1.0))
    cols = site.cols.intersection(poly.buffer(1.0))
    # keep-free lanes: main door -> every door to its own kitchen / BOH (>= 1.2 m = centre line +-0.6 m)
    walk = poly.buffer(-0.2).difference(cols.buffer(0.35)).difference(ex.buffer(0.05)).buffer(0)
    a = (dr["center"][0] + inward[0] * 0.7, dr["center"][1] + inward[1] * 0.7)
    lanes, lane_notes = [], []
    for sd in _unit_support_doors(site, rid):
        v = (sd.tip[0] - sd.hinge[0], sd.tip[1] - sd.hinge[1])
        L = math.hypot(*v) or 1.0
        t = (v[0] / L, v[1] / L)
        nrm = (-t[1], t[0])
        pin = None
        for sgn in (1, -1):
            p = (sd.mid[0] + sgn * nrm[0] * 0.7, sd.mid[1] + sgn * nrm[1] * 0.7)
            if poly.buffer(-0.1).contains(Point(p)):
                pin = p
        if pin is None:
            lane_notes.append("door %s: no point inside the dining room, lane not determinable" % sd.ref)
            continue
        start = a
        if lanes:                                    # branch off the existing lane network
            start = nearest_points(unary_union(lanes), Point(pin))[0].coords[0]
        ln = _lane_L(poly, walk, start, pin)
        if ln is None:
            ln = _route_line(walk, start, pin)
        if ln is None:
            lane_notes.append("door %s: no walkable path from the entrance, lane not determinable" % sd.ref)
            continue
        lanes.append(ln)
    lane_zone = unary_union([l.buffer(0.6) for l in lanes]) if lanes else Polygon()
    tt = (-dr["n"][1], dr["n"][0])
    hw = dr["w"] / 2 + 0.3
    c0 = dr["center"]
    entry = Polygon([(c0[0] - tt[0] * hw, c0[1] - tt[1] * hw), (c0[0] + tt[0] * hw, c0[1] + tt[1] * hw),
                     (c0[0] + tt[0] * hw + inward[0] * UNIT_DOOR_APRON, c0[1] + tt[1] * hw + inward[1] * UNIT_DOOR_APRON),
                     (c0[0] - tt[0] * hw + inward[0] * UNIT_DOOR_APRON, c0[1] - tt[1] * hw + inward[1] * UNIT_DOOR_APRON)])
    blocked = unary_union([hardn.buffer(0.1), cols.buffer(COL_CLEAR_ROOM), keep, ex.buffer(FURN_CLEAR_ROOM), lane_zone, entry])
    region = poly.buffer(-WALL_INSET).difference(blocked).buffer(0)
    blocked_w = unary_union([hardn, cols.buffer(COL_CLEAR_ROOM), keep, ex.buffer(FURN_CLEAR_ROOM), lane_zone, entry])   # banquettes sit 0.125 m from the wall, so walls are not buffered
    region_w = poly.buffer(-BANQ_INSET).difference(blocked_w).buffer(0)
    # chair pull-out zones may use the wall margin and the lanes (aisles are measured from the chair backs), but never walls,
    # columns, door swings + aprons or existing furniture
    region_c = poly.buffer(-0.03).difference(unary_union([hardn, cols, keep, ex.buffer(0.05)])).buffer(0)
    pl = Placer(region, ROOM_GAP, region_c=region_c, region_w=region_w)
    em.items.info.setdefault("lanes", {})[rid] = {"n": len(lanes), "length_m": [round(l.length, 2) for l in lanes], "notes": lane_notes,
                                                    "lines": [list(l.coords) for l in lanes]}
    segs = wall_segments(poly)
    # 1. cash counter near the entrance (nearest free wall run, 0.9 m front)
    best = None
    for sg in segs:
        for s in np.arange(0.0, sg["L"] - 1.2 + 1e-9, 0.1):
            cx = sg["p0"][0] + sg["t"][0] * (s + 0.6) + sg["n"][0] * (WALL_INSET + EPS)
            cy = sg["p0"][1] + sg["t"][1] * (s + 0.6) + sg["n"][1] * (WALL_INSET + EPS)
            u = u_cash().placed((cx, cy), sg["t"], sg["n"])
            if pl.fits(u):
                d = Point(cx, cy).distance(Point(dr["center"]))
                if best is None or d < best[0] - 1e-9:
                    best = (d, u)
    if best is not None:
        pl.add(best[1])
        em.unit(rid, best[1], "placed on the free wall run nearest to the unit entrance, 0.9 m queue/front zone")
    else:
        em.drop(rid, "cash_counter", "no free wall run for 1.2x0.6 + 0.9 m front inside the room outside door swing/apron/lane")
    # 2. banquette bays along the longest walls (cap by room size)
    cap = int(area / 1.6)                         # density cap: 1 seat / 1.6 m2 gross (generic assumption)
    max_bays = 99
    bays = 0
    for sg in sorted(segs, key=lambda s: -s["L"]):
        L = 1.8
        s = 0.0
        while bays < max_bays and sum(q.seats for q in pl.units) < 0.6 * cap and s <= sg["L"] - L + 1e-9:
            cx = sg["p0"][0] + sg["t"][0] * (s + L / 2) + sg["n"][0] * (BANQ_INSET + EPS)
            cy = sg["p0"][1] + sg["t"][1] * (s + L / 2) + sg["n"][1] * (BANQ_INSET + EPS)
            u = u_bank(L).placed((cx, cy), sg["t"], sg["n"])
            if pl.fits(u, wall=True):
                pl.add(u)
                em.unit(rid, u, "banquette bay along a wall: banquette 0.55 m + 2 four-tops")
                bays += 1
                s += L + ROOM_GAP
            else:
                s += 0.1
    # 3. 4-tops on a module lattice (pitch = table group 1.74 m + 1.0 m aisle) aligned with the room axes, best phase
    x0, y0, x1, y1 = poly.bounds
    c = ((x0 + x1) / 2, (y0 + y1) / 2)
    pitch = 1.74 + ROOM_GAP
    seats = sum(q.seats for q in pl.units)
    for u in best_lattice(pl, lambda x, y: u_4top().placed((x, y), (1, 0), (0, 1)), c, pitch, pitch, poly, 0.25):
        if seats + u.seats > cap:
            break
        pl.add(u)
        seats += u.seats
        em.unit(rid, u, "4-top on module lattice (pitch %.2f m, aisle %.1f m) aligned with the room axes" % (pitch, ROOM_GAP))
    # 4. 2-tops in leftover space, up to the density cap (<= 1 seat per 1.6 m2 gross, generic assumption)
    for u in best_lattice(pl, lambda x, y: u_2top().placed((x, y), (1, 0), (0, 1)), c, 1.54 + ROOM_GAP, 0.7 + ROOM_GAP, poly, 0.25):
        if seats + u.seats > cap:
            break
        pl.add(u)
        seats += u.seats
        em.unit(rid, u, "2-top filler on module lattice, density cap %d seats (1 seat / 1.6 m2 gross, generic)" % cap)


# ------------------------------------------------------------------------------------------------ back of house
def _existing_ranges(site, poly):
    out = []
    for g in site.furn_list:
        if poly.buffer(0.05).contains(g) and g.area > 0.3:
            b = g.bounds
            w, h = b[2] - b[0], b[3] - b[1]
            if (abs(w - 0.8) < 0.03 and abs(h - 0.7) < 0.03) or (abs(w - 0.7) < 0.03 and abs(h - 0.8) < 0.03):
                out.append(g)
    return out


class Bay:
    """wall-run placer: items are rectangles w (along wall) x d (into the room) at WALL_INSET from a wall."""

    def __init__(self, site, rid, aisle, em):
        self.site, self.rid, self.em, self.aisle = site, rid, em, aisle
        room = site.rooms[rid]
        self.poly = room["poly"]
        self.keep = _door_keepouts(site, self.poly)
        self.ex = site.furn_near(self.poly, 0.5)
        self.hardn = site.hard.intersection(self.poly.buffer(1.0))
        self.cols = site.cols.intersection(self.poly.buffer(1.0))
        self.region = self.poly.buffer(-BANQ_INSET).difference(unary_union([self.keep, self.cols.buffer(0.15), self.ex.buffer(0.01), self.hardn.buffer(0.0)])).buffer(0)
        self.pre = prep(self.region) if not self.region.is_empty else None
        self.placed = []          # (geom, kind)
        self.placed_u = Polygon()
        self.fronts_u = Polygon()  # working-aisle zones of everything placed so far
        self.segs = self._walls()

    def _walls(self):
        segs = wall_segments(self.poly, 0.5)
        dpts = [Point(d.mid) for d in self.site.doors if self.poly.distance(Point(d.mid)) < 0.15]
        for s in segs:
            s["doors"] = sum(1 for p in dpts if LineString([s["p0"], s["p1"]]).distance(p) < 0.15)
        return sorted(segs, key=lambda s: (s["doors"], -s["L"]))

    def rect_at(self, sg, s, w, d, off=BANQ_INSET):
        off = off + EPS
        t, n, p0 = sg["t"], sg["n"], sg["p0"]
        pts = [(p0[0] + t[0] * (s + a) + n[0] * (off + b), p0[1] + t[1] * (s + a) + n[1] * (off + b)) for a, b in ((0, 0), (w, 0), (w, d), (0, d))]
        return Polygon(pts)

    def front(self, sg, s, w, d, depth, off=BANQ_INSET):
        return self.rect_at(sg, s, w, depth, off + d)

    def ok(self, g, fr, fr_depth_ok=True):
        if self.pre is None or not self.pre.covers(g):
            return False
        if not self.placed_u.is_empty and g.intersection(self.placed_u).area > TOL_AREA:
            return False
        if not self.fronts_u.is_empty and g.intersection(self.fronts_u).area > TOL_AREA:
            return False
        if fr is not None:
            if not self.poly.buffer(1e-6).contains(fr):
                return False
            blockers = unary_union([self.hardn, self.ex, self.placed_u, self.cols])
            if fr.intersection(blockers).area > TOL_AREA:
                return False
        return True

    def run(self, kind, w, d, n, aisle=None, scan=0.05):
        """place up to n consecutive items on the wall giving the longest flush run; returns list of dicts."""
        aisle = self.aisle if aisle is None else aisle
        best = None
        for si, sg in enumerate(self.segs):
            for s in np.arange(0.0, sg["L"] - w + 1e-9, scan):
                cnt, tmp_u, got = 0, self.placed_u, []
                ss = s
                while cnt < n and ss + w <= sg["L"] + 1e-9:
                    g = self.rect_at(sg, ss, w, d)
                    fr = self.front(sg, ss, w, d, aisle)
                    old = self.placed_u
                    self.placed_u = tmp_u
                    ok = self.ok(g, fr)
                    self.placed_u = old
                    if not ok:
                        break
                    got.append({"g": g, "fr": fr, "sg": sg, "s": ss, "w": w, "d": d})
                    tmp_u = unary_union([tmp_u, g])
                    cnt += 1
                    ss += w
                if cnt and (best is None or cnt > best[0]):
                    best = (cnt, got)
                if best is not None and best[0] >= n:
                    break
            if best is not None and best[0] >= n:
                break
        if best is None:
            return []
        for r in best[1]:
            self.placed_u = unary_union([self.placed_u, r["g"]])
            self.fronts_u = unary_union([self.fronts_u, r["fr"]])
            self.placed.append((r["g"], kind))
        return best[1]

    def fill(self, kind, d, lmax, lmin, aisle=None, scan=0.1):
        """fill leftover wall runs with items of length lmax .. lmin (prep counters, racks, shelves)."""
        aisle = self.aisle if aisle is None else aisle
        out = []
        for sg in self.segs:
            s = 0.0
            while s <= sg["L"] - lmin + 1e-9:
                done = False
                L = min(lmax, sg["L"] - s)
                while L >= lmin - 1e-9:
                    g = self.rect_at(sg, s, L, d)
                    fr = self.front(sg, s, L, d, aisle)
                    if self.ok(g, fr):
                        self.placed_u = unary_union([self.placed_u, g])
                        self.fronts_u = unary_union([self.fronts_u, fr])
                        self.placed.append((g, kind))
                        out.append({"g": g, "fr": fr, "sg": sg, "s": s, "w": L, "d": d})
                        s += L
                        done = True
                        break
                    L -= 0.1
                if not done:
                    s += scan
        return out


def _emit_bay(em, rid, kind, res, note="", seats=0):
    for r in res:
        em.single(rid, kind, r["g"], (int(round(r["w"] * 1000)), int(round(r["d"] * 1000))), clear=r["fr"], note=note, seats=seats)


def _hood(bay, tmin, tmax, sg):
    h = bay.rect_at(sg, tmin - 0.05, (tmax - tmin) + 0.10, 0.8, 0.13)
    return h.intersection(bay.poly.buffer(-BANQ_INSET - EPS)).buffer(0)       # never wider than the inner room margin


def furnish_boh(site, rid, em):
    room = site.rooms[rid]
    role = room["role"]
    poly = room["poly"]
    if role == "kitchen":
        bay = Bay(site, rid, WORK_AISLE, em)
        ex_ranges = _existing_ranges(site, poly)
        need = max(0, 4 - len(ex_ranges))
        res = bay.run("range", 0.8, 0.7, need) if need else []
        total = len(ex_ranges) + len(res)
        if res:
            _emit_bay(em, rid, "range", res, note="new range run (aisle-checked)")
        if total < 3:
            em.drop(rid, "range", "only %d of the 3-4 ranges fit (%d existing PR range + %d new): no free wall run with 1.0 m working aisle outside door swings" % (total, len(ex_ranges), len(res)))
        # one hood over the new run, and one over each existing PR range (overhead, dashed, exempt from floor-overlap checks)
        if res:
            sg = res[0]["sg"]
            em.single(rid, "hood", _hood(bay, res[0]["s"], res[-1]["s"] + res[-1]["w"], sg), (int(round((res[-1]["s"] + res[-1]["w"] - res[0]["s"] + 0.1) * 1000)), 800),
                      draw="dashed", note="over new range run")
        for g in ex_ranges:
            c = g.centroid
            sg = min(bay.segs, key=lambda q: LineString([q["p0"], q["p1"]]).distance(c))
            ts = [(x - sg["p0"][0]) * sg["t"][0] + (y - sg["p0"][1]) * sg["t"][1] for x, y in g.exterior.coords]
            em.single(rid, "hood", _hood(bay, min(ts), max(ts), sg), (int(round((max(ts) - min(ts) + 0.1) * 1000)), 800), draw="dashed",
                      note="over existing PR range (PR geometry untouched)")
        for kind, w, d in (("sink_double", 1.2, 0.6), ("fridge", 0.7, 0.8), ("dishwasher", 0.7, 0.7)):
            r = bay.run(kind, w, d, 1)
            if r:
                _emit_bay(em, rid, kind, r)
            else:
                em.drop(rid, kind, "no free wall run %.1f x %.1f m with 1.0 m working aisle outside door swing/apron/existing furniture" % (w, d))
        isl_dep = min(poly.bounds[2] - poly.bounds[0], poly.bounds[3] - poly.bounds[1])
        if isl_dep < 4.4:
            em.items.info.setdefault("island_skipped", {})[rid] = "room depth %.2f m < 4.4 m" % isl_dep
        _emit_bay(em, rid, "prep_counter", bay.fill("prep_counter", 0.7, 2.4, 0.9))
    elif role == "wash":
        bay = Bay(site, rid, STORE_AISLE, em)
        r = bay.run("sink_wash", 0.7, 0.6, 2)
        if r:
            _emit_bay(em, rid, "sink_wash", r)
        else:
            em.drop(rid, "sink_wash", "no free wall run 0.7x0.6 with 0.9 m aisle")
        r = bay.run("dish_table", 1.2, 0.7, 1)
        if r:
            _emit_bay(em, rid, "dish_table", r)
        else:
            em.drop(rid, "dish_table", "no free wall run 1.2x0.7 with 0.9 m aisle")
        _emit_bay(em, rid, "shelf", bay.fill("shelf", 0.45, 2.4, 0.9))
        em.items.info.setdefault("cart_skipped", {})[rid] = "wash room %.1f m2 < 9 m2: pallet/cart parking not attempted" % poly.area
    else:                                           # storage
        bay = Bay(site, rid, STORE_AISLE, em)
        _emit_bay(em, rid, "rack", bay.fill("rack", 0.5, 2.4, 0.9))
        em.items.info.setdefault("cart_skipped", {})[rid] = "storage room %.1f m2 < 9 m2: pallet/cart parking not attempted" % poly.area


# ------------------------------------------------------------------------------------------------ hall 2-10
def hall_region(site, corr):
    hall = site.hall
    haz = unary_union([site.void, site.tube, site.wall_core, site.star, site.rail]).buffer(HAZARD_CLEAR + MARGIN)
    wallish = unary_union([site.wall_part, site.wall_core, site.glaz, site.wall_ext]).buffer(0.35)
    open_haz = hall.boundary.difference(wallish).buffer(HAZARD_CLEAR + MARGIN)       # slab edge without wall/glazing = free edge
    ko = []
    for d in site.doors:
        if "2-10" in d.rooms:
            ko += [d.sector.buffer(0.05), d.apron(UNIT_DOOR_APRON)]
    door_ko = unary_union(ko) if ko else Polygon()
    parts = {"hazards(void/tube/core/stair/rail) +1.5": haz, "free slab edge +1.5": open_haz, "columns +0.6": site.cols.buffer(COL_CLEAR_HALL + MARGIN),
             "door swing+apron": door_ko, "existing furniture +0.6": site.furn.buffer(FURN_CLEAR_HALL + MARGIN),
             "main corridors 3.0 m": corr["main_zone"].buffer(MARGIN), "service corridors 1.8 m": corr["service_zone"].buffer(MARGIN)}
    region = hall.buffer(-WALL_INSET).difference(unary_union(list(parts.values()))).buffer(0)
    return region, parts


def furnish_hall(site, em, corr):
    rid = "2-10"
    hall = site.hall
    region, parts = hall_region(site, corr)
    em.items.info["hall_region_m2"] = round(region.area, 1)
    pl = Placer(region, HALL_GAP, CLUSTER_GAP)
    gr = site.grid()
    X, Y = gr["X"], gr["Y"]
    bays = []
    for i in range(len(X) - 1):
        for j in range(len(Y) - 1):
            bb = box(X[i], Y[j], X[i + 1], Y[j + 1])
            if bb.intersects(region):
                bays.append((i, j, bb, ((X[i] + X[i + 1]) / 2, (Y[j] + Y[j + 1]) / 2), region.intersection(bb).area))
    em.items.info["hall_bays"] = len(bays)
    p4 = 1.74 + CLUSTER_GAP
    # 1. two service counters (3.0 x 0.8, 4 stools, 1.0 m staff side): free spots on a 0.5 m search grid, the second one as
    #    far as possible from the first
    minx, miny, maxx, maxy = hall.bounds
    cands = []
    cen = region.centroid
    for x in np.arange(minx, maxx, 0.5):
        for y in np.arange(miny, maxy, 0.5):
            if not region.contains(Point(x, y)):
                continue
            for t, n in (((1, 0), (0, 1)), ((0, 1), (-1, 0))):
                u = u_counter().placed((x, y), t, n, cluster="counter-%.1f-%.1f" % (x, y))
                if pl.fits(u):
                    cands.append((math.dist((x, y), (cen.x, cen.y)), (x, y), u))
                    break
    chosen = []
    if cands:
        cands.sort(key=lambda c: c[0])
        chosen.append(cands[0])
        rest = [c for c in cands[1:] if c[2].foot.distance(cands[0][2].foot) >= HALL_GAP]
        if rest:
            chosen.append(max(rest, key=lambda cc: math.dist(cc[1], cands[0][1])))
    for _, _, u in chosen:
        pl.add(u)
        em.unit(rid, u, "service counter: free spot nearest to the centre of the free hall area; staff side 1.0 m, stools on the guest side")
    if len(chosen) < 2:
        em.drop(rid, "service_counter", "only %d of 2 counters fit (3.0 m counter + 1.0 m staff side + stools, 1.5 m gaps)" % len(chosen))
    # 2. wall banquette bays along unit walls, 2-top rows along the facade
    segs = wall_segments(hall, 1.8)
    nb = nw = 0
    off = WALL_INSET + EPS + 0.005
    for k, sg in enumerate(sorted(segs, key=lambda s: (round(s["mid"][1], 1), round(s["mid"][0], 1)))):
        mid = Point(sg["mid"])
        near = [r for r in site.rooms.values() if r is not site.rooms[rid] and r["poly"].distance(mid) < 0.3]
        if any(r["kind"] == "restroom" for r in near):
            continue
        facade = site.glaz.distance(mid) < 0.35 or site.wall_ext.distance(mid) < 0.35
        if near and not facade:
            L, cap, mk, kind, note = 3.6, 4, (lambda: u_bank(3.6)), "bank", "wall banquette bay (banquette 0.55 m + 4 four-tops) along a unit wall"
        elif facade:
            L, cap, mk, kind, note = 1.54, 99, u_2top_wall, "window", "2-top row along the facade (chairs tangent to the glazing)"
        else:
            continue
        s, put = 0.0, 0
        cl = "wall-%d" % k
        while s <= sg["L"] - L + 1e-9 and put < cap:
            c0 = (sg["p0"][0] + sg["t"][0] * (s + L / 2) + sg["n"][0] * off, sg["p0"][1] + sg["t"][1] * (s + L / 2) + sg["n"][1] * off)
            u = mk().placed(c0, sg["t"], sg["n"], cluster=cl)
            if pl.fits(u):
                pl.add(u)
                em.unit(rid, u, note)
                put += 1
                nb += kind == "bank"
                nw += kind == "window"
                s += L + CLUSTER_GAP
            else:
                s += 0.1
    # 3. module patterns aligned with the column grid: one cluster per 9 x 9 m bay (pattern by bay parity), lattice phase
    #    searched inside the bay so the 1.98 m aisles stay on the column lines
    counts = {"A": 0, "B": 0, "C": 0}
    for i, j, bb, c, fa in sorted(bays, key=lambda b: (b[0], b[1])):
        if fa < 12.0:
            continue
        cl = "bay-%d-%d" % (i, j)
        lim = bb.buffer(-0.75)                       # 2 x 0.75 = 1.5 m aisle across the column line
        pats = {
            "A": ((lambda x, y: u_4top().placed((x, y), (1, 0), (0, 1), cluster=cl)), p4, p4),
            "B": (((lambda x, y: u_comm().placed((x, y), (1, 0), (0, 1), cluster=cl)), 2.4 + CLUSTER_GAP, p4) if i % 2 == 0 else
                  ((lambda x, y: u_comm().placed((x, y), (0, 1), (-1, 0), cluster=cl)), p4, 2.4 + CLUSTER_GAP)),
            "C": ((lambda x, y: u_2top().placed((x, y), (1, 0), (0, 1), cluster=cl)), 1.54 + CLUSTER_GAP, 0.7 + CLUSTER_GAP),
        }
        cand = {k: best_lattice(pl, mk, c, px_, py_, lim, 0.45) for k, (mk, px_, py_) in pats.items()}
        mx = max(sum(u.seats for u in v) for v in cand.values())
        if mx == 0:
            continue
        for k in ["ABC"[(i + j + r) % 3] for r in range(3)]:       # preference rotates with the bay parity -> a mix of patterns
            if sum(u.seats for u in cand[k]) >= 0.85 * mx:
                pat = k
                break
        for u in cand[pat]:
            pl.add(u)
            em.unit(rid, u, "pattern %s on the column-grid module, bay (%d,%d), aisles >= %.1f m between clusters" % (pat, i, j, HALL_GAP))
            counts[pat] += 1
    # 4. leftover pockets (re-computed twice): richest of 4-top / communal / 2-top lattices per pocket
    n_left = 0
    for rnd in range(3):
        left = region.difference(unary_union([u.foot.buffer(HALL_GAP) for u in pl.units])) if pl.units else region
        pockets = sorted([g for g in _flat(left) if g.geom_type == "Polygon" and g.area > 3.0], key=lambda g: (round(g.centroid.y, 1), round(g.centroid.x, 1)))
        for k, comp in enumerate(pockets):
            cl = "pocket-%d-%d" % (rnd, k)
            cc = (comp.centroid.x, comp.centroid.y)
            opts = {
                "4top": ((lambda x, y: u_4top().placed((x, y), (1, 0), (0, 1), cluster=cl)), p4, p4),
                "comm": ((lambda x, y: u_comm().placed((x, y), (1, 0), (0, 1), cluster=cl)), 2.4 + CLUSTER_GAP, p4),
                "comm90": ((lambda x, y: u_comm().placed((x, y), (0, 1), (-1, 0), cluster=cl)), p4, 2.4 + CLUSTER_GAP),
                "2top": ((lambda x, y: u_2top().placed((x, y), (1, 0), (0, 1), cluster=cl)), 1.54 + CLUSTER_GAP, 0.7 + CLUSTER_GAP),
            }
            res = {kk: best_lattice(pl, mk, cc, px_, py_, comp, 0.45) for kk, (mk, px_, py_) in opts.items()}
            kk = max(res, key=lambda q: sum(u.seats for u in res[q]))
            for u in res[kk]:
                pl.add(u)
                em.unit(rid, u, "%s in a leftover pocket (>= %.1f m from other clusters)" % (kk, HALL_GAP))
                n_left += 1
    em.items.info["hall_pattern_units"] = counts
    em.items.info["hall_wall_units"] = {"bank": nb, "window": nw}
    em.items.info["hall_pocket_units"] = n_left
    return pl


def develop_fitout(PR, G):
    site = Site(PR, G)
    em = Emitter()
    corr = derive_corridors(site)
    em.items.info["corridors"] = {"n_trunk": corr["n_trunk"], "n_stubs": corr["n_stubs"], "notes": corr["notes"],
                                  "main_zone_m2": round(corr["main_zone"].area, 1), "service_zone_m2": round(corr["service_zone"].area, 1)}
    for rid in sorted(site.rooms):
        r = site.rooms[rid]
        if r["kind"] == "unit" and r["role"] == "dining":
            furnish_dining(site, rid, em)
        elif r["kind"] == "support":
            furnish_boh(site, rid, em)
        elif r["kind"] == "hall":
            furnish_hall(site, em, corr)
        # restrooms: nothing is added (existing A-FIXT untouched; verified by fitout_checks_r10b)
    seats = {}
    for it in em.items:
        seats[it.room_id] = seats.get(it.room_id, 0) + it.seats
    em.items.info["seats"] = seats
    em.items.info["seats_total"] = sum(seats.values())
    return em.items

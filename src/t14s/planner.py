"""C-T14T planner. Extends the C-T14S planner (layout.Planner) with targeted corrections; verified geometry is never changed.

P0  geometric circulation graph per floor (cores, restrooms, lift lobbies, escalator landings, freight landing, unit doors),
    routes computed on a walkable raster (wall setback, 1.2 m clear band at columns, door swings, voids excluded)
P1  open-to-below / no-slab hatch, free-opening classification, proposed edge protection, projected escalator axes,
    inaccessible-core notation, no internal identifiers in visible text
P2  sales/dining vs back-of-house sub-division, service doors and routes to the freight landing, culture concepts, garden design
"""
from __future__ import annotations

import math

import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Point, Polygon, box
from shapely.ops import nearest_points, polylabel, unary_union

from . import annotate as AN
from . import fitout as FO
from . import layout as LY
from . import program as PG
from . import source as SRC
from . import structure as ST
from . import symbols as SY
from .layout import APRON_DIR, HALL_NAME, TINT, UL_NAME, UNIT_NAME, TUBE_KO, door_symbol, oriented_rect, polys
from .model import MODEL_VERIFIED, PROPOSED, SYMBOL_REUSE, Drawing, text_extent_m
from .walknet import WalkNet

import upper_layouts as UL
from symbols.stair_core import CORE_VES_SIDE

COL_CLEAR = SRC.COL_R + 0.62            # route centre line to column centre: leaves a 1.2 m clear band at a column
SIDE_KO = {"W": "서측 캡슐", "E": "동측 캡슐", "N": "북측 급행"}
ROLE_KO = {"board": "승차", "arrive": "하차", "through": "통과"}
SUPPORT_TINT = "#ebe7df"


def hatch_lines(poly, spacing, angle_deg):
    """Vector hatch: parallel lines clipped to the polygon (editable in SVG/DXF, no raster)."""
    if poly is None or poly.is_empty:
        return None
    x0, y0, x1, y1 = poly.bounds
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    R = math.hypot(x1 - x0, y1 - y0) / 2 + 1.0
    g = affinity.rotate(unary_union([LineString([(cx - R, cy + k), (cx + R, cy + k)]) for k in np.arange(-R, R, spacing)]), angle_deg, origin=(cx, cy))
    out = g.intersection(poly)
    return None if out.is_empty else out


def _gap_rect(dr, thick=0.3):
    ang = math.degrees(math.atan2(dr["t"][1], dr["t"][0]))
    g = affinity.rotate(box(-dr["w"] / 2, -thick, dr["w"] / 2, thick), ang, origin=(0, 0))
    return affinity.translate(g, dr["center"][0], dr["center"][1])


class Planner2(LY.Planner):
    CARVE_PREFIX = ("core", "wc", "tube", "esc", "fr")

    def __init__(self, g, seed=7):
        super().__init__(g, seed)
        self.decisions: dict = {}
        self.access: dict = {}
        self.cars_meta: list = []
        self.graph: dict = {}
        self.routes, self.svc_routes = [], []
        self.label_zones: list = []
        self.swing_in = Polygon()
        self.garden_des: dict = {}
        self.walk = Polygon()
        self._entry_blocked = set()

    def decide(self, did, fact):
        self.decisions.setdefault(did, []).append(fact)

    # ------------------------------------------------------------------ structure & symbols (P0/P1)
    def structure_and_symbols(self):
        g, d = self.g, self.d
        ST.add_structure(d, g)
        self.core_info, self.wc_info, self.tube_info = {}, {}, {}
        for k, poly in g.cars.items():
            self.cars_meta.append({"source_id": k, "bounds_m": [round(v, 2) for v in poly.bounds], "drawn": False,
                                   "reason": "lift-car section object sits inside the T3/T4 shaft symbol; not drawn separately"})
        for cid, b in sorted(g.cores.items()):
            served = g.slab.intersection(box(*b).buffer(2.0).difference(box(*b))).area > 6.0
            self.core_info[cid] = SY.add_core(d, cid, b, served)
            self.vertical.append({"id": "코어 " + cid, "name": "코어 %s (특별피난계단)" % cid, "status": "MODEL_VERIFIED footprint / " + (
                "interior = 1F symbol reuse (PROPOSED)" if served else "no floor slab at this level (model); stair shaft continues, no access")})
            if not served:
                d.notes.append("CORE_%s_NO_SLAB_AT_LEVEL: no verified floor slab at the core door; core drawn as closed pass-through shaft (decision D-02)" % cid)
                self.decide("D-02", {"floor": g.floor, "core": cid, "core_bounds_m": [round(v, 2) for v in b]})
                cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
                d.text(cx, cy + 0.5, "코어 %s" % cid, "micro", box=True, prov=PROPOSED)
                d.text(cx, cy - 0.7, "출입 불가", "micro", box=True, prov=PROPOSED)
        wc_all = unary_union([box(*b).buffer(0.1) for b in SY.wc_bounds().values()])
        for wid, b in SY.wc_bounds().items():
            fp = box(*b)
            if wid in g.cores and self.core_info[wid]["served"] and g.slab.buffer(0.06).contains(fp):
                self.wc_info[wid] = SY.add_restroom(d, wid, b)
            else:
                d.notes.append("RESTROOM_%s_OMITTED: adjacent core absent/unserved or footprint not on the slab at this level" % wid)
        cores_u = unary_union([box(*b) for b in g.cores.values()])
        base_blocked = unary_union([cores_u, wc_all, self.col_u.buffer(0.3)])
        for n, t in sorted(g.tubes.items()):
            rot, fr_door = 0.0, None
            other = unary_union([x.outer for k, x in g.tubes.items() if k != n])
            if n in ("T3", "T4"):
                r = SY.choose_entry_rotation(n, t, g.slab, base_blocked.union(other))
                if r is None:
                    d.notes.append("TUBE_%s_ENTRY_BLOCKED: no apron on slab around the glass cylinder (decision D-03)" % n)
                    self.decide("D-03", {"floor": g.floor, "tube": n, "result": "no clear side"})
                    rot = 0.0
                    self._entry_blocked = self._entry_blocked | {n}
                elif r != 0:
                    rot = float(r)
                    d.notes.append("TUBE_%s_ENTRY_TURNED %+d deg: south entry abuts the capsule opening; lobby entry turned toward the hall (PROPOSED, decision D-03)" % (n, rot))
                    self.decide("D-03", {"floor": g.floor, "tube": n, "turn_deg": rot})
            elif n == "FR":
                best = SY.choose_fr_door(t, g.slab, base_blocked.union(other))
                fr_door = best[1:] if best else None
                if not best:
                    d.notes.append("FR_LANDING_NOT_FOUND: no clear 2.6 m freight landing on slab (decision D-05)")
                    self.decide("D-05", {"floor": g.floor, "reason": "no clear landing at the freight lift"})
            self.tube_info[n] = SY.add_tube(d, n, t, bool(g.ramps), self.cols, g.outline, entry_rot=rot, fr_door=fr_door)
            nm = TUBE_KO.get(n, n)
            if n == "T1" and not g.ramps:
                nm = "T1 빛 튜브 (램프 없음)"
            if n == "FR":
                nm += " (반입 접점 제안)"
            self.vertical.append({"id": n, "name": nm, "status": "MODEL_VERIFIED opening / content = 1F symbol reuse (PROPOSED)"})
            cx, cy = self.tube_info[n]["center"]
            ly = cy - 0.2 - (self.tube_info[n]["r"] * 0.62 if n in ("T3", "T4") else 0.0)
            d.text(cx, ly, n if n[0] != "c" else ("W" if n == "capW" else "E"), "micro", prov=SYMBOL_REUSE, box=True)
        for n, s in sorted(g.shafts.items()):
            SY.add_ev_shaft(d, n, s)
            self.vertical.append({"id": n, "name": TUBE_KO.get(n, n), "status": "MODEL_VERIFIED opening / content = symbol (PROPOSED)"})
            d.text(s.centroid.x, s.centroid.y - 0.2, n, "micro", prov=SYMBOL_REUSE, box=True)
        for e in g.escalators:
            x0, y0, x1, y1 = e["poly"].bounds
            long_x = (x1 - x0) > (y1 - y0)
            for i in range(1, 6):
                f = i / 6
                seg = LineString([(x0 + f * (x1 - x0), y0), (x0 + f * (x1 - x0), y1)]) if long_x else LineString([(x0, y0 + f * (y1 - y0)), (x1, y0 + f * (y1 - y0))])
                d.add("A-STAR", seg, "detail", prov=MODEL_VERIFIED, ref="escalator tread (schematic)")
        for e in g.esc_ends:
            self.vertical.append({"id": "ESC " + e["label"], "name": "에스컬레이터 %s (%s·%s)" % (e["label"], SIDE_KO[e["side"]], ROLE_KO[e["role"]]),
                                  "status": "MODEL_VERIFIED axis", "source_id": e["source_id"]})
        self.plan_access()

    # ------------------------------------------------------------------ access nodes (P0)
    def plan_access(self):
        g = self.g
        A = self.access
        for cid, ci in self.core_info.items():
            if ci["served"]:
                n = APRON_DIR[CORE_VES_SIDE[cid]]
                c = ci["hall_door_c"]
                A["core " + cid] = {"type": "core", "pt": Point(c[0] + n[0] * 1.6, c[1] + n[1] * 1.6), "apron": oriented_rect(c, n, 2.8, 2.4), "status": "ON_SLAB"}
        for wid, wi in self.wc_info.items():
            A["wc " + wid] = {"type": "wc", "pt": wi["swings"].centroid, "apron": wi["swings"].buffer(1.2), "status": "ON_SLAB"}
        for n, ti in self.tube_info.items():
            if ti.get("kind") == "elevator":
                if n in self._entry_blocked:
                    A["tube " + n] = {"type": "elevator", "pt": Point(*ti["center"]), "apron": None, "status": "ENTRY_BLOCKED",
                                      "reason": "entry apron on every tried side is void/blocked", "decision": "D-03"}
                    continue
                nn, ec = ti["entry_n"], ti["entry_c"]
                A["tube " + n] = {"type": "elevator", "pt": Point(ec[0] + nn[0] * 1.5, ec[1] + nn[1] * 1.5),
                                  "apron": SY.entry_apron(ti["center"], ti["r"], ti["entry_rot"], 3.0, 2.8), "status": "ON_SLAB",
                                  "turn_deg": ti["entry_rot"]}
            elif n == "FR" and ti.get("door_n"):
                nn, ec = ti["door_n"], ti["door_c"]
                A["fr"] = {"type": "fr", "pt": Point(ec[0] + nn[0] * 1.5, ec[1] + nn[1] * 1.5), "apron": ti["apron"].buffer(0.6), "status": "ON_SLAB"}
        for e in g.esc_ends:
            if e["role"] == "through":
                continue
            end = e["low"] if e["role"] == "board" else e["high"]
            u = e["u"]
            out = (-u[0], -u[1]) if e["role"] == "board" else u
            nid = "esc %s %s" % (e["label"], e["role"])
            wdt = e["width"] + 1.0
            P = lambda s: Point(end[0] + out[0] * s, end[1] + out[1] * s)           # noqa: E731
            solid = unary_union([box(*b) for b in g.cores.values()] + [w["footprint"] for w in self.wc_info.values()])
            if solid.buffer(0.05).intersects(Point(end)) or solid.buffer(0.05).intersects(P(1.2)):
                A[nid] = {"type": "escalator", "pt": Point(*end), "apron": None, "status": "BLOCKED_BY_SOLID", "esc": e["source_id"], "role": e["role"],
                          "decision": "D-01", "reason": "escalator end lies inside a core / restroom footprint (verified model conflict)", "end": [round(end[0], 2), round(end[1], 2)]}
                self.d.notes.append("ESC_END_INSIDE_SOLID %s %s: escalator end lies inside a core footprint (decision D-01)" % (e["label"], e["role"]))
                self.decide("D-01", {"floor": g.floor, "escalator": e["label"], "role": e["role"], "end_m": [round(end[0], 2), round(end[1], 2)],
                                     "issue": "escalator end inside core/restroom footprint", "source_id": e["source_id"]})
                continue
            if g.slab.contains(P(1.2)) and g.slab.contains(P(2.4)):
                A[nid] = {"type": "escalator", "pt": P(2.2), "apron": oriented_rect((end[0], end[1]), out, wdt, 3.2).intersection(g.slab),
                          "status": "ON_SLAB", "esc": e["source_id"], "role": e["role"]}
                continue
            hit = next((s for s in np.arange(0.2, 40.0, 0.1) if g.slab.contains(P(s))), None)
            if hit is not None and g.slab.contains(P(hit + 1.0)):
                pt, gap = P(hit + 1.0), hit
            else:
                q = nearest_points(g.slab, Point(end))[0]
                pt, gap = q, Point(end).distance(q)
            A[nid] = {"type": "escalator", "pt": pt, "apron": oriented_rect((pt.x - out[0] * 0.5, pt.y - out[1] * 0.5), out, wdt, 3.0).intersection(g.slab),
                      "status": "AT_OPENING_EDGE", "esc": e["source_id"], "role": e["role"], "gap_m": round(gap, 2), "decision": "D-01",
                      "end": [round(end[0], 2), round(end[1], 2)]}
            self.d.notes.append("ESC_LANDING_NOT_ON_SLAB %s %s: escalator end lies in an opening; nearest verified slab %.1f m along its axis (decision D-01)" % (e["label"], e["role"], gap))
            self.decide("D-01", {"floor": g.floor, "escalator": e["label"], "role": e["role"], "end_m": [round(end[0], 2), round(end[1], 2)],
                                 "gap_to_slab_m": round(gap, 2), "access_edge_m": [round(pt.x, 2), round(pt.y, 2)], "source_id": e["source_id"]})

    def required_nodes(self):
        return {k: v["pt"] for k, v in self.access.items() if v["status"] in ("ON_SLAB", "AT_OPENING_EDGE") and self.g.slab.contains(v["pt"])}

    def free_area(self):
        super().free_area()
        ap = [v["apron"] for v in self.access.values() if v.get("apron") is not None and not v["apron"].is_empty]
        if ap:
            self.aprons = unary_union([self.aprons] + ap).intersection(self.g.slab)

    def place_doors(self):
        """One door per unit on the longest edge facing the hall whose apron (swing + 0.45 m) is walkable; units without one merge into the hall."""
        for _round in range(3):
            uu = unary_union([u["poly"] for u in self.units]) if self.units else Polygon()
            hall = self.free.difference(uu).buffer(0)
            hall_b = hall.buffer(0.08)
            walk0 = hall.buffer(-0.35).difference(self.col_u.buffer(COL_CLEAR))
            keep = []
            for u in self.units:
                edge = u["poly"].boundary.intersection(hall_b)
                if edge.is_empty:
                    segs = []
                elif edge.geom_type == "MultiLineString":
                    try:
                        segs = LY.lines(LY.linemerge(edge))
                    except ValueError:
                        segs = LY.lines(edge)
                else:
                    segs = LY.lines(edge)
                door = None
                for s in sorted(segs, key=lambda s: -s.length):
                    if s.length < 2.7:
                        continue
                    wdt = 1.8 if u["poly"].area >= 50 and s.length >= 3.4 else 1.2
                    for frac in ((0.3, 0.7, 0.5, 0.2, 0.8) if u["poly"].area >= 38 else (0.5, 0.35, 0.65, 0.25, 0.75)):
                        p = s.interpolate(frac, normalized=True)
                        if p.distance(self.col_u) < wdt / 2 + 0.55:
                            continue
                        dist = s.project(p)
                        a, b = s.interpolate(max(dist - 0.4, 0)), s.interpolate(min(dist + 0.4, s.length))
                        tv = (b.x - a.x, b.y - a.y)
                        Ln = math.hypot(*tv) or 1.0
                        t = (tv[0] / Ln, tv[1] / Ln)
                        t = (math.copysign(1.0, t[0]), 0.0) if abs(t[0]) >= abs(t[1]) else (0.0, math.copysign(1.0, t[1]))   # walls are orthogonal
                        opening = LineString([(p.x - t[0] * wdt / 2, p.y - t[1] * wdt / 2), (p.x + t[0] * wdt / 2, p.y + t[1] * wdt / 2)])
                        if not opening.within(u["poly"].boundary.buffer(0.03)):
                            continue
                        nvec = (-t[1], t[0])
                        if not hall.contains(Point(p.x + nvec[0] * 0.5, p.y + nvec[1] * 0.5)):
                            nvec = (-nvec[0], -nvec[1])
                        if not hall.contains(Point(p.x + nvec[0] * 0.5, p.y + nvec[1] * 0.5)):
                            continue
                        sr = wdt if wdt < 1.6 else wdt / 2
                        ap = Point(p.x + nvec[0] * (sr + 0.45), p.y + nvec[1] * (sr + 0.45))
                        if not walk0.contains(ap.buffer(0.45)):
                            continue
                        door = {"center": (p.x, p.y), "t": t, "n": nvec, "w": wdt}
                        break
                    if door:
                        break
                if door:
                    leaves, arcs, sw = door_symbol(door["center"], door["t"], door["n"], door["w"])
                    door.update({"leaves": leaves, "arcs": arcs, "swing": sw})
                    u["door"] = door
                    keep.append(u)
            if len(keep) == len(self.units):
                break
            self.units = keep
        self._prune_unreachable()
        self.hall_all = self.free.difference(unary_union([u["poly"] for u in self.units]) if self.units else Polygon()).buffer(0)
        self.swing_u = unary_union([u["door"]["swing"] for u in self.units]) if self.units else Polygon()

    def _prune_unreachable(self):
        """A unit whose door apron lies in a walkable pocket cut off from the main hall network is merged into the hall."""
        nodes = list(self.required_nodes().values())
        for _ in range(4):
            if not self.units or not nodes:
                break
            uu = unary_union([u["poly"] for u in self.units])
            sw = unary_union([u["door"]["swing"] for u in self.units])
            region = self.free.difference(uu).buffer(-0.35).difference(self.col_u.buffer(COL_CLEAR)).difference(sw.buffer(0.05)).buffer(0)
            net = WalkNet(region, 0.4)
            if not net.n:
                break
            cnt = {}
            for p in nodes:
                c, _ = net.nearest((p.x, p.y), 1.2)
                if c is not None:
                    cnt[int(net.comp[c])] = cnt.get(int(net.comp[c]), 0) + 1
            if not cnt:
                break
            main = max(cnt, key=cnt.get)
            keep = []
            for u in self.units:
                dr = u["door"]
                sr = dr["w"] if dr["w"] < 1.6 else dr["w"] / 2
                c, _ = net.nearest((dr["center"][0] + dr["n"][0] * (sr + 0.45), dr["center"][1] + dr["n"][1] * (sr + 0.45)), 1.0)
                if c is not None and int(net.comp[c]) == main:
                    keep.append(u)
            if len(keep) == len(self.units):
                break
            self.units = keep

    # ------------------------------------------------------------------ units: sub-division (P2)
    def subdivide_units(self):
        concept = PG.CULTURE_CONCEPT.get(self.g.floor)
        names = concept[1] if concept else LY.CULTURE_USES
        cul = sorted([u for u in self.units if u["prog"] == "culture"], key=lambda u: -u["poly"].area)
        for i, u in enumerate(cul):
            u["use"] = names[i % len(names)]
        uu = unary_union([u["poly"] for u in self.units]) if self.units else Polygon()
        walk0 = self.free.difference(uu).buffer(-0.35).difference(self.col_u.buffer(COL_CLEAR)).difference(self.swing_u.buffer(0.05))
        for u in self.units:
            u.setdefault("use", "")
            plan = PG.plan_unit(u["poly"], u["door"], u["prog"], self.hall_all, self.col_u, self.rng, u["use"] or None)
            if plan:
                for dr in plan["doors"]:
                    leaves, arcs, sw = door_symbol(dr["center"], dr["t"], dr["n"], dr["w"])
                    dr.update({"leaves": leaves, "arcs": arcs, "swing": sw})
                bad = [dr for dr in plan["doors"] if dr["swing"].intersection(self.col_u).area > 1e-6 or not u["poly"].buffer(0.03).contains(dr["swing"])]
                if bad:
                    plan = None
            if plan:
                keep = []
                for dr in plan["doors"]:
                    if dr["kind"] == "service":
                        ap = Point(dr["center"][0] - dr["n"][0] * 0.9, dr["center"][1] - dr["n"][1] * 0.9)
                        if not walk0.contains(ap.buffer(0.3)):
                            self.d.notes.append("SERVICE_DOOR_DROPPED unit at (%.1f, %.1f): no walkable apron in front of the service door; back-of-house is reached through the sales space" % (u["poly"].centroid.x, u["poly"].centroid.y))
                            continue
                    keep.append(dr)
                plan["doors"] = keep
            u["plan"] = plan

    def walls_and_door_items(self):
        g, d = self.g, self.d
        if not self.units:
            return
        edges = unary_union([u["poly"].boundary for u in self.units])
        excl = unary_union([g.outline.exterior.buffer(0.07)] + [h.exterior.buffer(0.07) for h in g.holes] +
                           [box(*b).buffer(0.07) for b in g.cores.values()] + [w["footprint"].buffer(0.1) for w in self.wc_info.values()])
        walls = edges.difference(excl).buffer(0.075, cap_style=3, join_style=2)
        gaps = [_gap_rect(u["door"]) for u in self.units]
        for u in self.units:
            for dr in (u["plan"]["doors"] if u.get("plan") else []):
                if dr["kind"] == "service":
                    gaps.append(_gap_rect(dr))
        walls = walls.difference(unary_union(gaps))
        d.add("A-WALL-PART", walls, "cut_medium", fill="#666666", prov=PROPOSED, ref="unit partition walls (150 mm)")
        parts, igaps = [], []
        for u in self.units:
            if not u.get("plan"):
                continue
            parts += u["plan"]["parts"]
            igaps += [_gap_rect(dr) for dr in u["plan"]["doors"] if dr["kind"] in ("internal", "pass")]
        if parts:
            pw = unary_union(parts).buffer(0.05, cap_style=3, join_style=2)
            if igaps:
                pw = pw.difference(unary_union(igaps))
            d.add("A-WALL-PART", pw, "cut_medium", fill="#808080", prov=PROPOSED, ref="back-of-house partitions (100 mm)")
        swings_in = []
        for u in self.units:
            dr = u["door"]
            d.add("A-DOOR", MultiLineString([[tuple(c) for c in l.coords] for l in dr["leaves"]]), "projection_light", prov=PROPOSED, ref="unit door leaf")
            d.add("A-DOOR", MultiLineString([[tuple(c) for c in a.coords] for a in dr["arcs"]]), "detail", prov=PROPOSED, ref="unit door swing")
            self.doors.append({"center": dr["center"], "width": dr["w"], "kind": "double" if dr["w"] >= 1.6 else "single", "use": "main"})
            for pd in (u["plan"]["doors"] if u.get("plan") else []):
                d.add("A-DOOR", MultiLineString([[tuple(c) for c in l.coords] for l in pd["leaves"]]), "projection_light", prov=PROPOSED, ref="%s door leaf" % pd["kind"])
                d.add("A-DOOR", MultiLineString([[tuple(c) for c in a.coords] for a in pd["arcs"]]), "detail", prov=PROPOSED, ref="%s door swing" % pd["kind"])
                swings_in.append(pd["swing"])
                self.doors.append({"center": pd["center"], "width": pd["w"], "kind": "single", "use": pd["kind"]})
        self.swing_in = unary_union(swings_in) if swings_in else Polygon()

    # ------------------------------------------------------------------ rooms
    def build_rooms(self):
        g = self.g
        concept = PG.CULTURE_CONCEPT.get(g.floor)
        rooms = []
        for ui, u in enumerate(self.units):
            pl = u.get("plan")
            prog = u["prog"]
            nm = u["use"] if prog == "culture" else UNIT_NAME.get(prog, "점포")
            if pl:
                for sr in pl["rooms"]:
                    main = sr["role"] == "main"
                    name = (nm + (" (객석)" if prog == "fnb" else "")) if main else sr["name"]
                    rooms.append({"name": name, "program": prog, "poly": sr["poly"].buffer(0), "kind": "unit" if main else "support", "role": sr["kind"],
                                  "use": u["use"], "prov": PROPOSED, "door": u["door"], "uidx": ui})
            else:
                rooms.append({"name": nm, "program": prog, "poly": u["poly"], "kind": "unit", "use": u["use"], "prov": PROPOSED, "door": u["door"], "uidx": ui,
                              "role": {"retail": "sales", "fnb": "dining", "culture": "culture"}.get(prog, "sales")})
        hall = self.hall_all.buffer(0.02).buffer(-0.02)
        hp = {p: hall.intersection(z) for p, z in self.prog_poly.items()}
        left = hall.difference(unary_union(list(hp.values()))) if hp else hall
        for piece in polys(left, 0.01):
            p = min(self.prog_poly.items(), key=lambda kv: piece.distance(kv[1]))[0] if self.prog_poly else "retail"
            hp[p] = hp[p].union(piece) if p in hp else piece
        for p, hg in hp.items():
            for comp in polys(hg.buffer(0.03).buffer(-0.03), 12.0):
                hn = concept[2] if (p == "culture" and concept) else HALL_NAME.get(p, "홀")
                rooms.append({"name": hn, "program": p, "poly": comp, "kind": "garden" if p == "garden" else "hall", "role": "garden" if p == "garden" else "public_circulation",
                              "use": "", "prov": PROPOSED})
        for wid, wi in self.wc_info.items():
            for un in wi["units"]:
                rooms.append({"name": "화장실 " + un["label"], "program": "restroom", "poly": un["poly"], "kind": "restroom", "role": "restroom", "use": un["name"], "prov": SYMBOL_REUSE})
        rooms.sort(key=lambda r: (-round(r["poly"].centroid.y / 7.0), r["poly"].centroid.x))
        main_id = {}
        for i, r in enumerate(rooms):
            r["id"] = "%02d" % (i + 1)
            r["area_m2"] = round(r["poly"].area, 1)
            if r["kind"] == "unit":
                main_id[r["uidx"]] = r["id"]
        for r in rooms:
            if r["kind"] == "support":
                r["parent_id"] = main_id.get(r["uidx"])
                r["name"] = "%s (%s)" % (r["name"], r["parent_id"])
        self.rooms = rooms

    # ------------------------------------------------------------------ circulation graph (P0)
    def circulation(self):
        g = self.g
        halls = unary_union([r["poly"] for r in self.rooms if r["kind"] in ("hall", "garden")])
        region = halls.buffer(-0.35).difference(self.col_u.buffer(COL_CLEAR)).difference(self.swing_u.buffer(0.05)).buffer(0)
        self.walk = region
        net = WalkNet(region, 0.3)
        self.net = net
        G = {"model": "raster walking graph on the walkable hall polygon: 0.35 m wall setback, column face + 0.62 m, door swings and voids excluded",
             "grid_step_m": 0.3, "nodes": [], "edges": [], "service_edges": [], "unit_doors": [], "unresolved": []}
        self.graph = G
        if not net.n:
            G["unresolved"].append({"id": "network", "reason": "no walkable hall area", "decision": None})
            return
        vis = {}
        for nid, a in self.access.items():
            if a["type"] == "fr":
                continue
            rec = {"id": nid, "type": a["type"], "access_x": round(a["pt"].x, 2), "access_y": round(a["pt"].y, 2), "status": a["status"], "cell": None}
            if a["status"] in ("ENTRY_BLOCKED", "BLOCKED_BY_SOLID"):
                rec.update({"reason": a["reason"], "decision": a.get("decision")})
            elif a["status"] == "AT_OPENING_EDGE":
                pass
            else:
                cell, dist = net.nearest((a["pt"].x, a["pt"].y), 1.2)
                if cell is None:
                    rec.update({"status": "UNREACHABLE", "reason": "no walkable cell within 1.2 m of the access point (nearest %.1f m)" % dist})
                else:
                    rec.update({"cell": cell, "snap_m": round(dist, 2), "x": round(float(net.xy[cell][0]), 2), "y": round(float(net.xy[cell][1]), 2)})
            for k in ("gap_m", "decision", "turn_deg", "esc", "role", "end"):
                if a.get(k) is not None:
                    rec.setdefault(k, a[k])
            vis[nid] = rec
        cells = [v["cell"] for v in vis.values() if v["cell"] is not None]
        main_comp = None
        if cells:
            cnt = {}
            for c in cells:
                cnt[int(net.comp[c])] = cnt.get(int(net.comp[c]), 0) + 1
            main_comp = max(cnt, key=cnt.get)
        if main_comp is not None:
            sel = np.nonzero(net.comp == main_comp)[0]
            from scipy.spatial import cKDTree
            tmain = cKDTree(net.xy[sel])
            for v in vis.values():
                if v["status"] == "AT_OPENING_EDGE":                      # nearest standing place on the verified slab to the escalator end
                    e0 = v["end"]
                    dd, ii = tmain.query(e0)
                    cell = int(sel[ii])
                    v.update({"cell": cell, "snap_m": 0.0, "gap_m": round(float(dd), 2), "x": round(float(net.xy[cell][0]), 2), "y": round(float(net.xy[cell][1]), 2)})
                    for rec_ in self.decisions.get("D-01", []):
                        if rec_.get("source_id") == v.get("esc") and rec_.get("role") == v.get("role"):
                            rec_["axis_gap_m"] = rec_.pop("gap_to_slab_m", None)
                            rec_["gap_to_slab_m"] = round(float(dd), 2)                  # straight distance to the nearest standing place on verified slab
                            rec_["access_edge_m"] = [v["x"], v["y"]]
        for v in vis.values():
            if v["cell"] is not None and int(net.comp[v["cell"]]) != main_comp:
                v.update({"status": "UNREACHABLE", "reason": "walkable network is disconnected from the main visitor network (clear route not found)"})
        conn = [k for k, v in vis.items() if v["cell"] is not None and v["status"] in ("ON_SLAB", "AT_OPENING_EDGE")]
        tabs = {k: net.dist_from(vis[k]["cell"]) for k in conn}
        trunk = set()
        if len(conn) >= 1:
            done, rest = {conn[0]}, set(conn[1:])
            trunk.add(vis[conn[0]]["cell"])
            while rest:
                best = None
                for a in done:
                    for b in rest:
                        dd = tabs[a][0][vis[b]["cell"]]
                        if best is None or dd < best[0]:
                            best = (dd, a, b)
                if best is None or not np.isfinite(best[0]):
                    break
                _, a, b = best
                pts = net.path(tabs[a][1], vis[b]["cell"])
                ls = net.smooth(pts, 0.3)
                prov = vis[a]["status"] == "AT_OPENING_EDGE" or vis[b]["status"] == "AT_OPENING_EDGE"
                if ls is not None and ls.length > 0.01:
                    clr = min((Point(c).distance(ls) for c in g.columns), default=99.0) - SRC.COL_R
                    self.routes.append((a, b, ls, prov))
                    G["edges"].append({"a": a, "b": b, "length_m": round(ls.length, 2), "provisional": prov, "min_column_clear_m": round(clr, 2),
                                       "coords": [[round(x, 2), round(y, 2)] for x, y in ls.coords]})
                else:                                                       # two landings share one standing place (e.g. express escalator arrival + next boarding)
                    q = [round(float(net.xy[vis[a]["cell"]][0]), 2), round(float(net.xy[vis[a]["cell"]][1]), 2)]
                    G["edges"].append({"a": a, "b": b, "length_m": 0.0, "provisional": prov, "min_column_clear_m": None, "coords": [q, q], "note": "same standing place"})
                trunk.update(net.nearest(p, 0.5)[0] for p in pts if net.nearest(p, 0.5)[0] is not None)
                done.add(b)
                rest.discard(b)
        for k, v in vis.items():
            if v["status"] in ("UNREACHABLE", "ENTRY_BLOCKED", "BLOCKED_BY_SOLID") or v["status"] == "AT_OPENING_EDGE":
                G["unresolved"].append({"id": k, "type": v["type"], "status": v["status"], "decision": v.get("decision"),
                                        "reason": v.get("reason") or ("escalator end lies in an opening; route stops at the verified slab edge, gap %.1f m" % v.get("gap_m", 0.0))})
        # unit doors (destinations) and the stub from the trunk
        dist_trunk = net.dist_from(sorted(trunk))[0] if trunk else None
        uid_room = {r["uidx"]: r["id"] for r in self.rooms if r["kind"] == "unit"}
        for ui, u in enumerate(self.units):
            dr = u["door"]
            sr = dr["w"] if dr["w"] < 1.6 else dr["w"] / 2
            pt = (dr["center"][0] + dr["n"][0] * (sr + 0.45), dr["center"][1] + dr["n"][1] * (sr + 0.45))
            cell, dist = net.nearest(pt, 1.0)
            ok = cell is not None and int(net.comp[cell]) == main_comp
            stub = float(dist_trunk[cell]) if ok and dist_trunk is not None and np.isfinite(dist_trunk[cell]) else None
            G["unit_doors"].append({"room": uid_room.get(ui), "x": round(dr["center"][0], 2), "y": round(dr["center"][1], 2), "reachable": bool(ok and stub is not None), "stub_m": None if stub is None else round(stub, 1)})
            if not (ok and stub is not None):
                G["unresolved"].append({"id": "door room %s" % uid_room.get(ui), "type": "unit_door", "status": "UNREACHABLE", "decision": None,
                                        "reason": "unit door apron is not on the walkable network"})
        # service network: freight landing -> service doors of back-of-house rooms
        fr = self.access.get("fr")
        G["service_root"] = None
        svc_doors = [(ui, dr) for ui, u in enumerate(self.units) if u.get("plan") for dr in u["plan"]["doors"] if dr["kind"] == "service"]
        fr_cell = net.nearest((fr["pt"].x, fr["pt"].y), 1.2)[0] if fr else None
        if fr is None:
            G["unresolved"].append({"id": "fr", "type": "fr", "status": "NO_LANDING", "decision": "D-05", "reason": "no freight landing found at the verified FR shaft"})
        elif fr_cell is None or int(net.comp[fr_cell]) != main_comp:
            G["unresolved"].append({"id": "fr", "type": "fr", "status": "UNREACHABLE", "decision": "D-05", "reason": "freight landing is not on the walkable network"})
        else:
            G["service_root"] = {"x": round(float(net.xy[fr_cell][0]), 2), "y": round(float(net.xy[fr_cell][1]), 2)}
            tree = {fr_cell}
            dist0 = net.dist_from(fr_cell)[0]
            order = []
            for ui, dr in svc_doors:
                pt = (dr["center"][0] - dr["n"][0] * 0.9, dr["center"][1] - dr["n"][1] * 0.9)       # in front of the service door, on the hall side
                cell, dist = net.nearest(pt, 1.0)
                order.append((float(dist0[cell]) if cell is not None else 1e9, ui, dr, cell, pt))
            for _, ui, dr, cell, pt in sorted(order, key=lambda o: o[0]):
                rid = uid_room.get(ui)
                if cell is None or int(net.comp[cell]) != main_comp:
                    G["unresolved"].append({"id": "service door room %s" % rid, "type": "service_door", "status": "UNREACHABLE", "decision": None,
                                            "reason": "service door apron is not on the walkable network"})
                    continue
                dist, pred = net.dist_from(sorted(tree))
                pts = net.path(pred, cell)
                ls = net.smooth(pts, 0.3) if len(pts) >= 2 else None
                tree.update(net.nearest(p, 0.5)[0] for p in pts if net.nearest(p, 0.5)[0] is not None)
                if ls is not None and ls.length > 0.3:
                    clr = min((Point(c).distance(ls) for c in g.columns), default=99.0) - SRC.COL_R
                    self.svc_routes.append(("service door room %s" % rid, "service", ls))
                    G["service_edges"].append({"a": "service door room %s" % rid, "length_m": round(ls.length, 2), "min_column_clear_m": round(clr, 2),
                                               "coords": [[round(x, 2), round(y, 2)] for x, y in ls.coords]})
                G.setdefault("service_doors", []).append({"room": rid, "x": round(dr["center"][0], 2), "y": round(dr["center"][1], 2), "reachable": True, "apron": [round(pt[0], 2), round(pt[1], 2)]})
        G["not_modeled"] = []
        if g.ramps:
            G["not_modeled"].append({"id": "T1 ramp", "reason": "ramp entry/exit points are not defined in the verified model or the 1F symbol; not counted as connected or failed", "decision": "D-08"})
            self.decide("D-08", {"floor": g.floor, "element": "T1 spiral ramp"})
        G["nodes"] = [{k: v for k, v in rec.items() if k != "cell"} for rec in vis.values()]
        self.vis_nodes = vis
        self.svc_nodes = [(dr["center"][0] - dr["n"][0] * 0.9, dr["center"][1] - dr["n"][1] * 0.9) for _, dr in svc_doors]
        G["summary"] = {"visitor_nodes": len(vis), "connected": sum(1 for v in vis.values() if v["status"] == "ON_SLAB"),
                        "provisional_at_opening_edge": sum(1 for v in vis.values() if v["status"] == "AT_OPENING_EDGE"),
                        "unresolved": len(G["unresolved"]), "unit_doors": len(G["unit_doors"]),
                        "unit_doors_reachable": sum(1 for x in G["unit_doors"] if x["reachable"]), "service_doors": len(svc_doors)}

    # ------------------------------------------------------------------ labels
    def _label_blockers(self):
        circ = unary_union([r[2].buffer(0.7) for r in self.routes] + [r[2].buffer(0.6) for r in self.svc_routes]) if (self.routes or self.svc_routes) else Polygon()
        return unary_union([self.swing_u.buffer(0.15), self.swing_in.buffer(0.1), self.col_u.buffer(0.6), circ, self.aprons])

    def place_labels(self, kinds=None):
        d = self.d
        blockers = self._label_blockers()
        for r in self.rooms:
            if r.get("label") is not None or (kinds and r["kind"] not in kinds):
                continue
            poly = r["poly"]
            if r["kind"] == "restroom":
                modes = [("tag", None)]
            else:
                nm, ar = r["name"], "%s㎡" % format(r["area_m2"], ",.1f")
                wn, hn = text_extent_m(nm, 8.0, "bold")
                wa, ha = text_extent_m(ar, 6.25)
                bw, bh = 0.95 + 0.2 + max(wn, wa), max(0.95, hn + ha + 0.15)
                modes = [("full", (bw, bh, nm, ar, wn, wa, hn, ha)), ("tag", None)]
            r["label"] = None
            for mode, dat in modes:
                w, h = (dat[0], dat[1]) if dat else (0.95, 0.95)
                free = poly.buffer(-0.3, join_style=2).difference(blockers).difference(unary_union(self.label_zones) if self.label_zones else Polygon())
                spot = None
                for comp in sorted(polys(free), key=lambda p: -p.area)[:4]:
                    if comp.area < w * h * 1.05:
                        continue
                    pole = polylabel(comp, 0.15)
                    cand0 = box(pole.x - w / 2, pole.y - h / 2, pole.x + w / 2, pole.y + h / 2)
                    if comp.contains(cand0):
                        spot = (pole.x, pole.y, cand0)
                        break
                    ex = comp.buffer(-min(w, h) / 2)
                    if ex.is_empty:
                        continue
                    bx0, by0, bx1, by1 = ex.bounds
                    gx, gy = np.meshgrid(np.arange(bx0, bx1 + 0.4, 0.4), np.arange(by0, by1 + 0.4, 0.4))
                    ins = shapely.contains_xy(ex, gx.ravel(), gy.ravel())
                    pts = np.column_stack([gx.ravel()[ins], gy.ravel()[ins]])
                    if not len(pts):
                        continue
                    order = np.argsort((pts[:, 0] - pole.x) ** 2 + (pts[:, 1] - pole.y) ** 2)
                    for k in order[:600]:
                        px, py = float(pts[k, 0]), float(pts[k, 1])
                        cand = box(px - w / 2, py - h / 2, px + w / 2, py + h / 2)
                        if comp.contains(cand):
                            spot = (px, py, cand)
                            break
                    if spot:
                        break
                if spot:
                    r["label"] = {"mode": mode, "cx": spot[0], "cy": spot[1], "dat": dat}
                    self.label_zones.append(spot[2].buffer(0.25))
                    break
            if r["label"] is None and kinds is None:
                pole = polylabel(max(polys(poly), key=lambda q: q.area), 0.15) if polys(poly) else poly.representative_point()
                r["label"] = {"mode": "tag", "cx": pole.x, "cy": pole.y, "dat": None, "forced": True}
                d.notes.append("LABEL_FORCED_TAG room %s (%s, %.1f m2): too narrow for a clear label, white-masked tag used" % (r["id"], r["name"], r["area_m2"]))

    # ------------------------------------------------------------------ garden (P2)
    def make_garden(self):
        for r in self.rooms:
            if r["kind"] != "garden":
                continue
            poly = r["poly"]
            lab = r.get("label")
            keep = None
            if lab and lab["mode"] == "full":
                bw, bh = lab["dat"][0], lab["dat"][1]
                keep = box(lab["cx"] - bw / 2 - 0.4, lab["cy"] - bh / 2 - 0.4, lab["cx"] + bw / 2 + 0.4, lab["cy"] + bh / 2 + 0.4)
            anchors = [(v["x"], v["y"]) for v in self.vis_nodes.values() if v.get("x") is not None and poly.distance(Point(v["x"], v["y"])) < 3.0]
            for dd in self.graph.get("unit_doors", []):
                if poly.distance(Point(dd["x"], dd["y"])) < 3.5:
                    anchors.append((dd["x"], dd["y"]))
            des = PG.garden_design(poly, [x[2] for x in self.routes if not x[3]], anchors, self.col_u, self.rng, keep)
            self.garden_des[r["id"]] = des
            r["garden"] = {"path_m": round(sum(l.length for l in des["lines"]), 1), "loop_m": round(des["loop_m"], 1), "beds": len(des["beds"]),
                           "bed_m2": round(sum(b.area for b in des["beds"]), 1), "trees": len(des["trees"]), "shrubs": len(des["shrubs"]),
                           "benches": len(des["benches"]), "shade_pergolas": len(des["shade"]), "entrances": len(anchors)}

    # ------------------------------------------------------------------ furniture
    def furnish(self):
        d = self.d
        allr = [r[2] for r in self.routes] + [r[2] for r in self.svc_routes]
        circ_buf = unary_union([r.buffer(1.1) for r in allr]) if allr else Polygon()
        label_u = unary_union(self.label_zones) if self.label_zones else Polygon()
        tubes_ctx = [{"c": Point(*ti["center"]), "r": ti["r"]} for n, ti in self.tube_info.items() if n in ("T1", "T2")]
        unit_doors = {}
        for u in self.units:
            if u.get("plan"):
                unit_doors[id(u)] = unary_union([Point(dr["center"][0] - dr["n"][0] * 0.8, dr["center"][1] - dr["n"][1] * 0.8).buffer(0.9)
                                                 for dr in u["plan"]["doors"] if dr["kind"] in ("internal", "pass")] or [Polygon()])
        for r in self.rooms:
            items = []
            if r["kind"] == "unit" and r["program"] in ("retail", "fnb", "culture"):
                dr = r["door"]
                door = {"center": dr["center"], "inward": (-dr["n"][0], -dr["n"][1]), "swing": dr["swing"], "width": dr["w"]}
                u = self.units[r["uidx"]]
                reserved = unary_union([label_u, unit_doors.get(id(u), Polygon())])
                fam = PG.USE_FAMILY.get(r["use"], ("라운지", None))[0] if r["program"] == "culture" else r["use"]
                items = FO.fit(r["poly"], r["program"], fam, door, self.col_u, reserved, self.rng)
            elif r["kind"] == "support":
                items = PG.boh_items(r["poly"], r["role"], unary_union([self.swing_in.buffer(0.3), label_u]), self.col_u, self.rng)
            elif r["kind"] == "hall":
                reg = r["poly"].buffer(-1.3, join_style=2)
                obst = unary_union([circ_buf, self.swing_u.buffer(0.3), label_u, self.aprons.buffer(0.3)])
                hard = self.col_u.buffer(SRC.COL_R + 1.2)
                for comp in polys(reg.difference(obst), 12.0):
                    try:
                        ctx = {"tubes": [t for t in tubes_ctx if comp.distance(t["c"]) < 14], "plaza": None}
                        items += UL.layout(UL_NAME.get(r["program"], "판매"), comp, obst, hard, self.rng, self.g.floor, ctx)
                    except Exception as e:                                       # keep the build going, record the reason
                        d.notes.append("FURNITURE_FALLBACK room %s: %s" % (r["id"], repr(e)[:90]))
            elif r["kind"] == "garden":
                des = self.garden_des.get(r["id"])
                if des:
                    for x, y, rad in des["trees"]:
                        d.add("A-FURN", Point(x, y).buffer(rad, quad_segs=10), "detail", fill="#dde6d6", prov=PROPOSED, ref="tree (proposed)")
                        d.add("A-FURN", Point(x, y).buffer(0.12), "detail", fill="#777777", prov=PROPOSED, ref="tree trunk")
                    for x, y, rad in des["shrubs"]:
                        d.add("A-FURN", Point(x, y).buffer(rad, quad_segs=8), "detail", fill="#e6ede0", prov=PROPOSED, ref="shrub (proposed)")
                    for b in des["benches"]:
                        d.add("A-FURN", b, "projection_light", fill="#ffffff", prov=PROPOSED, ref="bench (proposed)")
                    for sq in des["shade"]:
                        d.add("A-FURN", sq, "detail", dash="detail", prov=PROPOSED, ref="shade pergola (proposed)")
                        for cx, cy in sq.exterior.coords[:4]:
                            d.add("A-FURN", Point(cx, cy).buffer(0.15), "detail", fill="#555555", prov=PROPOSED, ref="pergola post")
                    r["n_furniture"] = len(des["trees"]) + len(des["shrubs"]) + len(des["benches"]) + len(des["shade"])
                continue
            bodies = [g for g, k in items if k == "body"]
            lns = [g for g, k in items if k == "line"]
            fol = [g for g, k in items if k == "foliage"]
            if bodies:
                d.add("A-FURN", shapely_multi([b for b in bodies if b.geom_type == "Polygon"]), "projection_light", fill="#ffffff", prov=PROPOSED, ref="furniture room " + r["id"])
            if lns:
                d.add("A-FURN", MultiLineString([[tuple(c) for c in l.coords] for l in lns if l.geom_type == "LineString"]), "detail", prov=PROPOSED, ref="furniture detail room " + r["id"])
            for f in fol:
                d.add("A-FURN", f, "detail", fill="#eeeeee" if f.geom_type == "Polygon" else None, prov=PROPOSED, ref="planting room " + r["id"])
            r["n_furniture"] = len(items)

    # ------------------------------------------------------------------ tints, routes, notation
    def tints_and_routes(self):
        d = self.d
        for r in self.rooms:
            if r["kind"] in ("hall", "garden", "unit", "support"):
                tint = TINT.get(r["program"], "#f6f6f6") if r["kind"] in ("hall", "garden") else ("#ffffff" if r["kind"] == "unit" else SUPPORT_TINT)
                d.add("A-ZONE", r["poly"], None, fill=tint, prov=PROPOSED, ref="zone tint %s" % r["id"])
        for rid, des in self.garden_des.items():
            if des.get("paths") is not None and not des["paths"].is_empty:
                d.add("A-ZONE", des["paths"], "detail", fill="#fcfcfa", prov=PROPOSED, ref="garden walkway (proposed, 2.4 m)")
            for b in des["beds"]:
                d.add("A-ZONE", b, "detail", fill="#e9efe4", prov=PROPOSED, ref="planting bed (proposed)")
        for a, b, ls, prov in self.routes:
            d.add("A-CIRC", ls, "prov" if prov else "circ", dash=None if prov else "circ", prov=PROPOSED,
                  ref="%scirculation %s -> %s" % ("provisional (landing not in verified model) " if prov else "", a, b))
        for a, b, ls in self.svc_routes:
            d.add("A-CIRC-SVC", ls, "svc", prov=PROPOSED, ref="service route %s" % a)
        for k, v in getattr(self, "vis_nodes", {}).items():
            if v.get("x") is None or v["status"] not in ("ON_SLAB", "AT_OPENING_EDGE"):
                continue
            p = Point(v["x"], v["y"])
            if v["status"] == "AT_OPENING_EDGE":
                d.add("A-CIRC", p.buffer(0.42, quad_segs=4), "prov", fill="#ffffff", prov=PROPOSED, ref="node %s (landing not in verified model)" % k)
            else:
                d.add("A-CIRC", p.buffer(0.28, quad_segs=6), "circ", fill="#2f5d8a", prov=PROPOSED, ref="node " + k)
        for x, y in getattr(self, "svc_nodes", []):
            d.add("A-CIRC-SVC", box(x - 0.22, y - 0.22, x + 0.22, y + 0.22), "svc", fill="#9a5b1e", prov=PROPOSED, ref="service door node")
        fr = self.access.get("fr")
        if fr is not None and self.graph.get("service_root"):
            sx, sy = self.graph["service_root"]["x"], self.graph["service_root"]["y"]
            d.add("A-CIRC-SVC", box(sx - 0.5, sy - 0.5, sx + 0.5, sy + 0.5), "svc", fill="#9a5b1e", prov=PROPOSED, ref="freight landing / delivery interface")
            d.text(sx, sy - 1.5, "FR 반입 접점", "micro", box=True, prov=PROPOSED, color="#9a5b1e")

    def openings_and_projection(self):
        g, d = self.g, self.d
        env = AN.building_envelope()
        envbox = box(*env)
        solids = unary_union([t.outer for t in g.tubes.values()] + list(g.shafts.values()) + [box(*b) for b in g.cores.values()] +
                             [w["footprint"] for w in self.wc_info.values()])
        outside = envbox.difference(g.outline).difference(solids)
        notes_open = []
        if outside.area > 20:
            hl = hatch_lines(outside.buffer(-0.15), 1.6, 45)
            d.add("A-FLOR-HATCH", hl, "hatch", prov=MODEL_VERIFIED, ref="no slab at this level inside the building envelope (derived from verified slab outline)")
            big = max(polys(outside.difference(solids.buffer(2.0)).buffer(-1.0)), key=lambda p: p.area, default=None)
            if big is not None and big.area > 15:
                c = polylabel(big, 0.3)
                txt = {"2F": "2F 바닥판 없음 · 1F 상부 개방 (모델 사실)", "7F": "7F 바닥판 없음 (y<+5 m) · 6F 옥상 하부 노출"}.get(g.floor, "바닥판 없음 · 하부 개방")
                d.text(c.x, c.y, txt, "room", box=True, prov=MODEL_VERIFIED)
                d.text(c.x, c.y - 1.2, "%s㎡ · 관통 구조(기둥·튜브·코어)는 그대로 표시" % format(outside.area, ",.0f"), "sub", box=True, prov=MODEL_VERIFIED)
            notes_open.append({"kind": "no_slab_region", "area_m2": round(outside.area, 1)})
        free_open = []
        for h in g.holes:
            tm = [n for n, t in g.tubes.items() if t.outer.buffer(0.35).contains(h)]
            sm = [k for k, s in g.shafts.items() if s.buffer(0.35).contains(h) or h.buffer(0.35).contains(s)]
            if tm and not tm[0].startswith("cap"):
                continue
            if sm:
                continue
            is_cap = bool(tm)
            inner = h.buffer(-0.12)
            hl = hatch_lines(inner, 1.0, 45)
            d.add("A-FLOR-HATCH", hl, "hatch", prov=MODEL_VERIFIED, ref="slab opening, open to below (verified opening)")
            if is_cap:
                c = polylabel(h, 0.3)
                d.text(c.x, c.y + 2.2, "%s 개구 · 하부 개방" % ("서측 캡슐" if tm[0] == "capW" else "동측 캡슐"), "sub", box=True, prov=MODEL_VERIFIED)
                notes_open.append({"kind": "capsule_opening", "tube": tm[0], "area_m2": round(h.area, 1)})
                continue
            free_open.append(h)
            ring = h.buffer(0.15, join_style=2).exterior
            d.add("A-RAIL", LineString(ring.coords), "rail", prov=PROPOSED, ref="proposed edge protection (not verified)")
            c = polylabel(h, 0.3)
            wlab, _ = text_extent_m("개구부 · 하부 개방", 8.0, "bold")
            if h.area > 60:
                if h.area > 250:
                    d.text(c.x, c.y + 0.6, "대규모 중앙 개구부 %s㎡" % format(h.area, ",.0f"), "room", box=True, prov=MODEL_VERIFIED)
                    d.text(c.x, c.y - 0.7, "하부 개방 · 가장자리 난간 제안(미검증)", "sub", box=True, prov=PROPOSED)
                else:
                    d.text(c.x, c.y + 0.5, "개구부 · 하부 개방", "sub", box=True, prov=MODEL_VERIFIED)
                    d.text(c.x, c.y - 0.6, "난간 제안(미검증)", "micro", box=True, prov=PROPOSED)
            notes_open.append({"kind": "free_opening", "area_m2": round(h.area, 1), "bounds_m": [round(v, 1) for v in h.bounds]})
        # exposed slab edges inside the envelope (notches, bays): proposed edge protection
        open_edge = g.outline.exterior.difference(envbox.exterior.buffer(0.3))
        if not open_edge.is_empty:
            inner = g.outline.buffer(-0.15, join_style=2).exterior
            rl = inner.intersection(open_edge.buffer(0.3))
            if not rl.is_empty:
                d.add("A-RAIL", rl, "rail", prov=PROPOSED, ref="proposed edge protection at exposed slab edge (not verified)")
                notes_open.append({"kind": "exposed_slab_edge_rail", "length_m": round(float(rl.length), 1)})
        # columns that stand in open volume (continue through the opening)
        n_thru = 0
        for x, y in g.columns:
            if not g.slab.buffer(0.05).contains(Point(x, y)):
                d.add("A-ANNO-SYMB", Point(x, y).buffer(0.78, quad_segs=12), "detail", dash="detail", prov=MODEL_VERIFIED, ref="column continues through open volume (verified position)")
                n_thru += 1
        notes_open.append({"kind": "columns_through_open_volume", "count": n_thru})
        # escalator axes projected from other levels
        for e in g.esc_ends:
            lo, hi = e["low"], e["high"]
            d.add("A-STAR-PROJ", LineString([lo, hi]), "proj", prov=MODEL_VERIFIED, ref="escalator axis %s (projected from %s)" % (e["label"], e["from"]))
            u = e["u"]
            tip = (hi[0], hi[1])
            nx, ny = -u[1], u[0]
            head = Polygon([tip, (tip[0] - u[0] * 0.9 + nx * 0.35, tip[1] - u[1] * 0.9 + ny * 0.35), (tip[0] - u[0] * 0.9 - nx * 0.35, tip[1] - u[1] * 0.9 - ny * 0.35)])
            d.add("A-STAR-PROJ", head, "proj", fill="#7a3b8c", prov=MODEL_VERIFIED, ref="escalator direction (up)")
            if e["role"] == "board":
                p, s = lo, "승차 →%s" % e["to"]
            elif e["role"] == "arrive":
                p, s = hi, "하차 ←%s" % e["from"]
            else:
                p, s = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2), "통과 %s→%s" % (e["from"], e["to"])
            off = (0.0, 1.0) if abs(u[0]) > abs(u[1]) else (1.3, 0.0)
            d.text(p[0] + off[0], p[1] + off[1], s, "micro", box=True, prov=MODEL_VERIFIED, color="#7a3b8c")
        self.open_notes = notes_open

    # ------------------------------------------------------------------ driver
    def run(self):
        self.structure_and_symbols()
        self.free_area()
        self.connect_pockets()
        self.place_doors()
        self.subdivide_units()
        self.walls_and_door_items()
        self.build_rooms()
        self.circulation()
        self.place_labels(("garden",))
        self.make_garden()
        self.place_labels()
        self.furnish()
        self.tints_and_routes()
        self.openings_and_projection()
        self.draw_labels()
        AN.add_grid_and_dims(self.d, self.g.z, self.g.floor)
        self.d.rooms = self.rooms
        self.d.meta.update({"vertical": self.vertical, "doors": self.doors, "graph": self.graph, "decisions": self.decisions,
                            "cars": self.cars_meta, "openings": getattr(self, "open_notes", [])})
        return self.d


def shapely_multi(polys_):
    from shapely.geometry import MultiPolygon
    return MultiPolygon(polys_)


def plan_floor(floor: str, seed=7) -> Drawing:
    return Planner2(SRC.load_floor(floor), seed).run()

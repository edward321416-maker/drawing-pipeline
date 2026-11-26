# -*- coding: utf-8 -*-
"""Independent checks for the R10B 2F fit-out development layer (FIT_OUT_DEVELOPMENT).

check_fitout(PR, G, items) -> JSON-serialisable dict.  Hard violation lists (must be EMPTY):
  a_outside_room, b_hits_obstacle, b_clear_hits_obstacle, b2_hall_clearance, c_door_swing, d_overlaps_existing,
  e_overlaps_new, e2_clear_hits_other, f_corridor_encroach
Reported (not pass/fail on new items): f_* corridor widths / free-floor fraction, g_restroom door clearance and cubicle sizes.
Tolerances (explicit, never relaxed per item): TOL_AREA 1e-6 m2 overlap area (float noise), COVER_EPS 1e-6 m containment slack,
DIST_EPS 1e-9 m on minimum-distance rules.  Obstacles are read straight from PR.items (raw layer geometry); the door swing
sectors and the corridor centre lines come from fitout_r10b (parse_doors / derive_corridors).
"""
from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize, unary_union
from shapely.strtree import STRtree

import fitout_r10b as F

TOL_AREA = F.TOL_AREA
COVER_EPS = 1e-6
DIST_EPS = 1e-9
OBSTACLE_LAYERS = ("A-COLS", "A-WALL-CORE", "A-WALL-PART", "A-WALL-EXT", "A-TUBE", "A-FLOR-OPEN", "A-STAR", "A-GLAZ")
OVERHEAD = {"hood"}


def _raw(PR, layer):
    out = []
    for it in PR.items:
        if it.layer == layer:
            out += [g for g in F._flat(it.geom) if not g.is_empty]
    return out


def _hit(a, b):
    """True when a and b overlap by more than float noise (polygon/polygon) or touch/cross (line involved)."""
    if a.geom_type == "Polygon" and b.geom_type == "Polygon":
        return a.intersection(b).area > TOL_AREA
    return a.intersects(b)


def _tree(geoms):
    return STRtree(geoms) if geoms else None


def _query(tree, geoms, g):
    if tree is None:
        return []
    return [geoms[i] for i in tree.query(g)]


def check_fitout(PR, G, items) -> dict:
    site = F.Site(PR, G)
    rooms = site.rooms
    rep = {"tolerances": {"TOL_AREA_m2": TOL_AREA, "COVER_EPS_m": COVER_EPS, "DIST_EPS_m": DIST_EPS}, "n_items": len(items)}
    inner = {}
    v_a, v_b, v_bc, v_b2, v_c, v_d, v_e, v_e2, v_f = [], [], [], [], [], [], [], [], []

    # ---------------------------------------------------------------- (a) inside own room.poly.buffer(-0.12)
    for it in items:
        r = rooms.get(it.room_id)
        if r is None:
            v_a.append({"id": it.id, "reason": "unknown room " + it.room_id})
            continue
        if it.room_id not in inner:
            inner[it.room_id] = r["poly"].buffer(-0.12).buffer(COVER_EPS)
        if not inner[it.room_id].covers(it.geom):
            v_a.append({"id": it.id, "room": it.room_id, "kind": it.kind, "outside_m2": round(it.geom.difference(inner[it.room_id]).area, 6)})

    # ---------------------------------------------------------------- (b) obstacles (raw PR layers)
    lay = {l: _raw(PR, l) for l in OBSTACLE_LAYERS}
    trees = {l: _tree(g) for l, g in lay.items()}
    for it in items:
        for l in OBSTACLE_LAYERS:
            for g in _query(trees[l], lay[l], it.geom):
                if _hit(it.geom, g):
                    v_b.append({"id": it.id, "room": it.room_id, "kind": it.kind, "layer": l})
                    break
            if it.clear is not None:
                for g in _query(trees[l], lay[l], it.clear):
                    if _hit(it.clear, g):
                        v_bc.append({"id": it.id, "room": it.room_id, "kind": it.kind, "layer": l})
                        break

    # ---------------------------------------------------------------- (b2) hall clearances
    cols_u = unary_union(_raw(PR, "A-COLS"))
    haz_u = unary_union([unary_union(lay[l]) for l in ("A-FLOR-OPEN", "A-TUBE", "A-WALL-CORE", "A-STAR")] + [unary_union(_raw(PR, "A-RAIL"))])
    furn_old = []
    for layer in ("A-FURN", "A-FIXT"):
        for it in PR.items:
            if it.layer == layer:
                furn_old += F.furniture_polys(it.geom)
    furn_u = unary_union(furn_old)
    for it in items:
        if it.room_id != "2-10":
            continue
        for g, need, nm in ((cols_u, F.COL_CLEAR_HALL, "column"), (haz_u, F.HAZARD_CLEAR, "void/tube/core/stair/rail"), (furn_u, F.FURN_CLEAR_HALL, "existing furniture")):
            d = it.geom.distance(g)
            if d < need - DIST_EPS:
                v_b2.append({"id": it.id, "kind": it.kind, "to": nm, "dist_m": round(d, 4), "need_m": need})

    # ---------------------------------------------------------------- (c) door swings
    doors = site.doors
    sectors = [d.sector for d in doors]
    st = _tree(sectors)
    for it in items:
        for i in (st.query(it.geom) if st is not None else []):
            d = doors[i]
            if it.geom.intersection(d.sector).area > TOL_AREA:
                v_c.append({"id": it.id, "room": it.room_id, "kind": it.kind, "door_ref": d.ref, "door_item_index": d.idx, "door_rooms": d.rooms})

    # ---------------------------------------------------------------- (d) existing A-FURN / A-FIXT
    ft = _tree(furn_old)
    for it in items:
        if it.kind in OVERHEAD:
            continue
        for g in _query(ft, furn_old, it.geom):
            if _hit(it.geom, g):
                v_d.append({"id": it.id, "room": it.room_id, "kind": it.kind, "what": "geometry"})
                break
        if it.clear is not None:
            for g in _query(ft, furn_old, it.clear):
                if _hit(it.clear, g):
                    v_d.append({"id": it.id, "room": it.room_id, "kind": it.kind, "what": "clear zone"})
                    break

    # ---------------------------------------------------------------- (e) other new items
    geoms = [it.geom for it in items]
    tr = _tree(geoms)
    for i, it in enumerate(items):
        if it.kind in OVERHEAD:
            continue
        for j in (tr.query(it.geom) if tr is not None else []):
            o = items[j]
            if j <= i or o.kind in OVERHEAD:
                continue
            if it.geom.intersection(o.geom).area > TOL_AREA:
                v_e.append({"a": it.id, "b": o.id, "room_a": it.room_id, "room_b": o.room_id})
    for i, it in enumerate(items):
        if it.clear is None or it.kind in OVERHEAD:
            continue
        for j in (tr.query(it.clear) if tr is not None else []):
            o = items[j]
            if o.kind in OVERHEAD or o.group == it.group:
                continue
            if it.clear.intersection(o.geom).area > TOL_AREA:
                v_e2.append({"item": it.id, "clear_of": it.kind, "hits": o.id})

    # ---------------------------------------------------------------- (f) hall circulation
    hall = site.hall
    corr = F.derive_corridors(site)
    hall_items = [it for it in items if it.room_id == "2-10"]
    zone_main = corr["main_zone"]
    main_u = unary_union(corr["main_lines"])
    svc_u = unary_union(corr["service_lines"]) if corr["service_lines"] else None
    for it in hall_items:
        if it.geom.distance(main_u) < F.MAIN_CORR_HALF - DIST_EPS:
            v_f.append({"id": it.id, "kind": it.kind, "dist_to_main_centreline_m": round(it.geom.distance(main_u), 4), "need_m": F.MAIN_CORR_HALF})
        if it.clear is not None and it.clear.distance(main_u) < F.MAIN_CORR_HALF - DIST_EPS:
            v_f.append({"id": it.id, "kind": it.kind, "what": "clear zone", "dist_to_main_centreline_m": round(it.clear.distance(main_u), 4)})
        if svc_u is not None and it.geom.distance(svc_u) < F.SEC_CORR_HALF - DIST_EPS:
            v_f.append({"id": it.id, "kind": it.kind, "what": "service corridor", "dist_m": round(it.geom.distance(svc_u), 4), "need_m": F.SEC_CORR_HALF})
    new_hall = unary_union([it.geom for it in hall_items]) if hall_items else Polygon()
    free_base = hall.difference(unary_union([cols_u, furn_u]))
    free_new = free_base.difference(new_hall)

    def widths(free, line, R=3.0, step=0.5):
        out = []
        for d in np.arange(0.6, line.length - 0.6 + 1e-9, step):      # ends sit on door aprons / access points in the wall line
            p = line.interpolate(d)
            a = line.interpolate(max(d - 0.25, 0.0))
            b = line.interpolate(min(d + 0.25, line.length))
            tx, ty = b.x - a.x, b.y - a.y
            L = (tx * tx + ty * ty) ** 0.5
            if L < 1e-9:
                continue
            nx, ny = -ty / L, tx / L
            seg = LineString([(p.x - nx * R, p.y - ny * R), (p.x + nx * R, p.y + ny * R)])
            inter = seg.intersection(free)
            best = 0.0
            for g in F._flat(inter):
                if g.geom_type == "LineString" and g.distance(p) < 1e-6:
                    best = max(best, g.length)
            out.append(best)
        return out
    per_line, reduced = [], 0                    # reduced = samples where the fit-out alone pushes the width below 3.0 m
    for k, ln in enumerate(corr["main_lines"]):
        w0, w1 = widths(free_base, ln), widths(free_new, ln)
        reduced += sum(1 for a, b in zip(w0, w1) if b < 3.0 - 1e-6 and a >= 3.0 - 1e-6)
        per_line.append({"line": k, "length_m": round(ln.length, 2), "min_width_pr_only_m": round(min(w0), 2) if w0 else None,
                         "min_width_with_fitout_m": round(min(w1), 2) if w1 else None,
                         "samples_below_3m_with_fitout": int(sum(1 for b in w1 if b < 3.0 - 1e-6))})
    allw = [x["min_width_with_fitout_m"] for x in per_line if x["min_width_with_fitout_m"] is not None]
    allw0 = [x["min_width_pr_only_m"] for x in per_line if x["min_width_pr_only_m"] is not None]
    hall_union_all = unary_union([new_hall, furn_u.intersection(hall.buffer(0.01)), cols_u.intersection(hall.buffer(0.01))])
    hall_union_old = unary_union([furn_u.intersection(hall.buffer(0.01)), cols_u.intersection(hall.buffer(0.01))])
    rep["f_hall_circulation"] = {
        "cross_section_cap_m": 6.0,
        "n_main_lines": len(corr["main_lines"]), "n_stub_lines": corr["n_stubs"], "per_main_line": per_line,
        "min_main_corridor_width_with_fitout_m": min(allw) if allw else None,
        "min_main_corridor_width_pr_only_m": min(allw0) if allw0 else None,
        "samples_where_new_items_push_width_below_3m": int(reduced),
        "note": "clear width = cross-section perpendicular to the centre line through hall floor not occupied by columns / existing furniture / new items (hall polygon already excludes voids, tubes, cores); values < 3.0 m that also appear in pr_only are caused by existing PR geometry, not by this layer",
        "floor_fraction_ge_1.2m_from_furniture_with_fitout": round(hall.difference(hall_union_all.buffer(1.2)).area / hall.area, 4),
        "floor_fraction_ge_1.2m_from_furniture_pr_only": round(hall.difference(hall_union_old.buffer(1.2)).area / hall.area, 4),
        "hall_area_m2": round(hall.area, 1),
    }

    # ---------------------------------------------------------------- (g) restrooms (read only)
    rep["g_restrooms"] = _restrooms(PR, site, items)

    # ---------------------------------------------------------------- per-room counts + seats
    per_room = {}
    for it in items:
        d = per_room.setdefault(it.room_id, {"items": 0, "seats": 0, "by_kind": {}})
        d["items"] += 1
        d["seats"] += int(it.seats)
        d["by_kind"][it.kind] = d["by_kind"].get(it.kind, 0) + 1
    for rid, d in per_room.items():
        a = rooms[rid]["area_m2"]
        d["area_m2"] = a
        d["m2_per_seat"] = round(a / d["seats"], 2) if d["seats"] else None
    rep["per_room"] = per_room
    rep["seats_total"] = sum(d["seats"] for d in per_room.values())
    rep["violations"] = {"a_outside_room": v_a, "b_hits_obstacle": v_b, "b_clear_hits_obstacle": v_bc, "b2_hall_clearance": v_b2,
                         "c_door_swing": v_c, "d_overlaps_existing": v_d, "e_overlaps_new": v_e, "e2_clear_hits_other": v_e2,
                         "f_corridor_encroach": v_f}
    rep["violation_counts"] = {k: len(v) for k, v in rep["violations"].items()}
    rep["n_violations"] = int(sum(rep["violation_counts"].values()))
    rep["exempt"] = {"overhead_kinds_exempt_from_d_e": sorted(OVERHEAD), "n_overhead": sum(1 for it in items if it.kind in OVERHEAD)}
    return rep


# ------------------------------------------------------------------------------------------------ restrooms
def _restrooms(PR, site, items):
    out = {"rule": "AGENTS.md 3.2 / params.yaml restroom: >= 1.2 m clear inside the door; general cubicle >= 0.9 x 1.2 m, accessible >= 1.6 x 2.0 m",
           "new_items_in_restrooms": sum(1 for it in items if site.rooms[it.room_id]["kind"] == "restroom"), "rooms": {}}
    fix = []
    for it in PR.items:
        if it.layer == "A-FIXT":
            fix += [(it.ref, g) for g in F._flat(it.geom) if g.geom_type == "Polygon"]
    part = [(it.ref, g) for it in PR.items if it.layer == "A-WALL-PART" for g in F._flat(it.geom) if g.geom_type == "Polygon" and "cubicle partition" in it.ref]
    lines_all = [(it.ref, g) for it in PR.items if it.layer == "A-DOOR" for g in F._flat(it.geom) if g.geom_type == "LineString" and "cubicle" in it.ref]
    for rid, r in sorted(site.rooms.items()):
        if r["kind"] != "restroom":
            continue
        poly = r["poly"]
        rec = {"name": r["name"], "doors": [], "cubicles": []}
        for d in site.doors:
            if rid not in d.rooms:
                continue
            v = (d.tip[0] - d.hinge[0], d.tip[1] - d.hinge[1])
            L = (v[0] ** 2 + v[1] ** 2) ** 0.5
            nrm = (-v[1] / L, v[0] / L)
            inw = None
            for sgn in (1, -1):
                if poly.contains(Point(d.mid[0] + sgn * nrm[0] * 0.3, d.mid[1] + sgn * nrm[1] * 0.3)):
                    inw = (sgn * nrm[0], sgn * nrm[1])
            if inw is None:
                continue
            ray = LineString([(d.mid[0] + inw[0] * 0.02, d.mid[1] + inw[1] * 0.02), (d.mid[0] + inw[0] * 4.0, d.mid[1] + inw[1] * 4.0)])
            hits = [(ray.intersection(g).distance(Point(d.mid)), ref) for ref, g in fix + part if ray.intersects(g)]
            depth = min([h[0] for h in hits], default=None)
            wall_d = ray.intersection(poly.exterior)
            wl = [Point(d.mid).distance(g) for g in F._flat(wall_d) if Point(d.mid).distance(g) > 0.3]       # ignore the wall line the door sits in
            wd = min(wl) if wl else None
            clear = min([x for x in (depth, wd, 4.0) if x is not None])
            inside_swing = bool(d.sector.intersects(poly.buffer(-0.05)) and d.sector.intersection(poly).area > 0.05)
            rec["doors"].append({"door_ref": d.ref, "swings_into_room": inside_swing, "clear_depth_inside_m": round(clear, 2),
                                 "first_obstacle": (min(hits)[1] if hits else "room wall"), "ok_ge_1.2m": bool(clear >= 1.2 - 1e-9)})
        # cubicles: cells enclosed by the room boundary + partition outlines + cubicle door leaves
        segs = [poly.exterior] + [g.exterior for ref, g in part if poly.buffer(0.1).intersects(g)] + [g for ref, g in lines_all if poly.buffer(0.1).intersects(g)]
        cells = list(polygonize(unary_union(segs)))
        for ref, g in fix:
            if "양변기" not in ref or not poly.buffer(0.05).contains(g.centroid):
                continue
            acc = "장애인" in ref
            cell = next((c for c in cells if c.contains(g.centroid)), None)
            need = (1.6, 2.0) if acc else (0.9, 1.2)
            if cell is None or cell.area > 5.0 or cell.area < 0.3:
                rec["cubicles"].append({"fixture": ref, "accessible": acc, "status": "not enclosed by existing partition items (open stall front or shared cell): size cannot be read", "need_m": need})
                continue
            mrr = cell.minimum_rotated_rectangle
            xs = list(mrr.exterior.coords)
            e = sorted([((xs[0][0] - xs[1][0]) ** 2 + (xs[0][1] - xs[1][1]) ** 2) ** 0.5, ((xs[1][0] - xs[2][0]) ** 2 + (xs[1][1] - xs[2][1]) ** 2) ** 0.5])
            ok = bool(e[0] >= need[0] - 1e-6 and e[1] >= need[1] - 1e-6)
            rec["cubicles"].append({"fixture": ref, "accessible": acc, "size_m": [round(e[0], 2), round(e[1], 2)], "need_m": need, "ok": ok})
        out["rooms"][rid] = rec
    return out

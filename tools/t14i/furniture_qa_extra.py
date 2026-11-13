"""Furniture / circulation QA for the extra floors (B2, B1, 2F, 4F, 5F, 6F, 7F, 11F, 12F) on real geometry.

tools/t14g/furniture_qa.py keeps its floor list in __main__ and reads plans/_raw/raw_plan_<F>_check.json under the run. The extra floors live under
<run>/v4/extra/raw/, so this module re-implements check_floor with the check-json path as a parameter. The metric definitions are copied from
furniture_qa.py (same constants, same structure() source = model slices, not the layout engine); `selftest` re-runs the five V3 floors and
compares every shared key with <run>/furniture_qa.json, so a drift between the two implementations is caught.

Extra metrics for the extra floors (slab openings and plate outline differ from V3 floors):
  on_opening_pairs     furniture bodies overlapping a slab opening (hole of the slab projection) by > 0.01 m2
  outside_slab         bodies not inside slab.buffer(0.05)  (same definition as furniture_qa.py; includes openings and the area outside the plate)
  routes_over_void_m   length of visitor/operation routes that lie on openings or outside the plate
  per_program          furniture bodies by layout program (from layout_meta)

    python -X utf8 tools/t14i/furniture_qa_extra.py <run> [out.json]
"""
import json
import math
import os
import sys
from collections import Counter

import t14i  # noqa: F401  (sys.path for src/ and tools/)
from t14i import common as cm

import pipeline_common as pc
from shapely import wkt
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

from t14g import furniture_qa as FQ

EXTRA_FLOORS = ["B2", "B1", "2F", "4F", "5F", "6F", "7F", "11F", "12F"]
V3_FLOORS = ["3F", "8F", "10F", "13F", "15F"]


def extra_raw_dir(run):
    return os.path.join(run, "v4", "extra", "raw")


def check_floor_extra(run, floor, check_json):
    chk = json.load(open(check_json, encoding="utf-8"))
    items = [(i["type"], i["kind"], wkt.loads(i["wkt"])) for i in chk["furniture_v3"]]
    bodies = [(t, g) for t, k, g in items if k in ("body", "counter")]
    slab, cols, tubes, cores = FQ.structure(run, floor)
    res = {"floor": floor, "programs": [m["program"] for m in chk.get("layout_meta", [])], "units": 0}
    pairs = 0
    for i in range(len(bodies)):
        for j in range(i + 1, len(bodies)):
            if bodies[i][1].intersects(bodies[j][1]) and frozenset((bodies[i][0], bodies[j][0])) not in FQ.INTENDED_STACK:
                if bodies[i][1].intersection(bodies[j][1]).area > 0.01:
                    pairs += 1
    res["overlapping_pairs"] = pairs
    tube_u = unary_union([s for _, s in tubes]) if tubes else Point(0, 0).buffer(0)
    hard = unary_union([g for g in (cols, tube_u, cores) if not g.is_empty])
    res["touching_structure"] = sum(1 for _, g in bodies if g.intersects(hard))
    res["within_0.2m_of_structure"] = sum(1 for _, g in bodies if g.distance(hard) < 0.2)
    res["outside_slab"] = sum(1 for _, g in bodies if not slab.buffer(0.05).contains(g))
    units = [(t, g) for t, g in bodies if t not in FQ.ACCESSORY]
    res["units"] = len(units)
    sig = Counter((t, round(g.bounds[2] - g.bounds[0], 1), round(g.bounds[3] - g.bounds[1], 1)) for t, g in units)
    top, n = sig.most_common(1)[0]
    res["max_identical_share"] = round(n / len(units), 3)
    res["most_repeated"] = list(top)
    res["types"] = sorted({t.split("_")[0] if t.startswith(("brand_cell", "street_island", "cashier")) else t for t, _ in units})
    res["n_types"] = len(res["types"])
    free = slab.buffer(-0.3).difference(unary_union([hard.buffer(0.2)] + [g.buffer(0.1) for _, g in bodies]))
    ctr = slab.centroid
    anchors = []
    for name, sh in tubes:
        if "캡슐" in name or sh.area < 8.0:
            continue
        c = sh.centroid
        d = math.hypot(ctr.x - c.x, ctr.y - c.y) or 1.0
        r = math.sqrt(sh.area / math.pi)
        anchors.append(Point(c.x + (ctr.x - c.x) / d * (r + 1.8), c.y + (ctr.y - c.y) / d * (r + 1.8)))
    res["aisle_anchors"] = len(anchors)
    best = None
    struct_free = slab.buffer(-0.3).difference(hard.buffer(0.2))
    for r in (1.2, 1.0, 0.9, 0.75, 0.6, 0.45):
        es = struct_free.buffer(-r)
        big = max((p for p in (es.geoms if hasattr(es, "geoms") else [es]) if p.geom_type == "Polygon"), key=lambda p: p.area, default=None)
        valid = [a for a in anchors if big is not None and big.distance(a) < 1.3]
        er = free.buffer(-r)
        comps = [p for p in (er.geoms if hasattr(er, "geoms") else [er]) if p.geom_type == "Polygon" and not p.is_empty]
        near = {i for i, p in enumerate(comps) for a in valid if p.distance(a) < 1.3}
        if len(valid) >= 2 and comps and len(near) == 1 and all(any(p.distance(a) < 1.3 for p in comps) for a in valid):
            best = 2 * r
            res["aisle_anchors_reachable_by_structure"] = len(valid)
            break
    res["aisle_width_connecting_all_anchors_m"] = best
    res["passes"] = bool(pairs == 0 and res["touching_structure"] == 0 and res["max_identical_share"] <= FQ.MAX_SHARE and res["n_types"] >= FQ.MIN_TYPES
                         and best is not None and best >= 1.2)
    # ── extra metrics ────────────────────────────────────────────────────────────────────────────────
    holes = unary_union([p for q in pc.iter_polygons(slab) for p in [__import__("shapely.geometry", fromlist=["Polygon"]).Polygon(h) for h in q.interiors]]) if not slab.is_empty else slab
    res["on_opening_pairs"] = sum(1 for _, g in bodies if (not holes.is_empty) and g.intersection(holes).area > 0.01)
    routes = [g for t, k, g in items if k in ("route_v", "route_o") and g.geom_type == "LineString"]
    off = slab.buffer(-0.1)
    res["routes_over_void_m"] = round(sum(r.difference(off).length for r in routes), 2)
    res["route_length_m"] = round(sum(r.length for r in routes), 1)
    per = Counter()
    metas = chk.get("layout_meta", [])
    res["layout_meta"] = [{k: v for k, v in m.items() if k != "types"} for m in metas]
    res["bodies"] = len(bodies)
    res["slab_edge_margin_m"] = 0.05
    res["passes_extra"] = bool(res["passes"] and res["outside_slab"] == 0 and res["on_opening_pairs"] == 0 and res["routes_over_void_m"] <= 0.5)
    return res


def selftest(run):
    """The five V3 floors through this module must give the same shared numbers as the stored furniture_qa.json (V3 implementation)."""
    stored = {f["floor"]: f for f in cm.jl(os.path.join(run, "furniture_qa.json"))["floors"]}
    bad = []
    for f in V3_FLOORS:
        r = check_floor_extra(run, f, os.path.join(run, "plans", "_raw", "raw_plan_%s_check.json" % f))
        for k, v in stored[f].items():
            if k in r and r[k] != v:
                bad.append((f, k, v, r[k]))
    return bad


def run_all(run, floors=None, out=None):
    floors = floors or EXTRA_FLOORS
    raw = extra_raw_dir(run)
    rs = [check_floor_extra(run, f, os.path.join(raw, "raw_plan_%s_check.json" % f)) for f in floors]
    d = FQ.check_distinct(rs)
    res = {"floors": rs, "distinct": d}
    if out:
        cm.jd(res, out)
    return res


if __name__ == "__main__":
    run = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else cm.RUN_DEFAULT
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(cm.v4_dir(run, "extra"), "furniture_qa_extra.json")
    mism = selftest(run)
    print("selftest vs V3 furniture_qa.json: %s" % ("OK (no shared key differs)" if not mism else "MISMATCH %s" % mism))
    res = run_all(run, out=out)
    for r in res["floors"]:
        print(r["floor"], "units", r["units"], "types", r["n_types"], "share", r["max_identical_share"], "overlap", r["overlapping_pairs"], "touch", r["touching_structure"],
              "soft<0.2m", r["within_0.2m_of_structure"], "outside_slab", r["outside_slab"], "on_opening", r["on_opening_pairs"], "route_over_void_m", r["routes_over_void_m"],
              "aisle", r["aisle_width_connecting_all_anchors_m"], "PASS" if r["passes"] else "FAIL", "EXTRA_PASS" if r["passes_extra"] else "EXTRA_FAIL")
    print("distinct: max jaccard", res["distinct"]["max_jaccard"], "PASS" if res["distinct"]["passes"] else "FAIL")
    print("written", os.path.abspath(out))

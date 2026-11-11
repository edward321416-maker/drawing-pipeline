"""Independent furniture / circulation QA on real geometry.

Furniture geometry comes from the exported typed list (raw_plan_<F>_check.json -> furniture_v3); the structure it must not touch
(columns, tube shells, cores) and the slab come straight from the model slices (raw_slices), NOT from the layout engine.

  collisions     furniture pairs overlapping > 0.01 m2 (intended stacking, e.g. media wall on the stage, excluded)
  structure      furniture touching a column / tube shell / core wall (hard) and within 0.2 m (soft)
  repetition     share of the most common identical footprint among furniture units (chairs/stools/plants excluded)
  diversity      number of distinct furniture types among the units
  aisle          widest clear aisle such that every tube anchor stays connected, by erosion of the free floor (not the engine's own router)
  distinct       Jaccard similarity of the furniture type sets between floors (layouts must differ by program)
"""
import json
import math
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))
import pipeline_common as pc  # noqa: E402
import book_views as bv  # noqa: E402
from shapely import wkt  # noqa: E402
from shapely.geometry import Point, Polygon  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

ACCESSORY = {"chair", "terrace_chair", "stool", "shrub", "tree", "popup_mark"}
INTENDED_STACK = {frozenset(("stage", "media_wall"))}
MAX_SHARE, MIN_TYPES = 0.35, 5


def _shell(g):
    ps = [p for p in (g.geoms if hasattr(g, "geoms") else [g]) if p.geom_type == "Polygon"]
    return Polygon(max(ps, key=lambda p: p.area).exterior)


def structure(run, floor):
    sl = pc.load_slice(os.path.join(run, "raw_slices"), floor)
    cuts = pc.cut_geometries(sl)
    slab = bv._union([pc.polygons_from_segments(p["segments"]) for p in sl["projection"]])
    cols = unary_union([g for _, g in cuts.get("column", [])]) if cuts.get("column") else Polygon()
    tubes = [(it["name_ko"], _shell(g)) for it, g in cuts.get("tube_wall", [])]
    cores = unary_union([g for _, g in cuts.get("core_wall", [])]) if cuts.get("core_wall") else Polygon()
    return slab, cols, tubes, cores


def check_floor(run, floor):
    chk = json.load(open(os.path.join(run, "plans", "_raw", "raw_plan_%s_check.json" % floor), encoding="utf-8"))
    items = [(i["type"], i["kind"], wkt.loads(i["wkt"])) for i in chk["furniture_v3"]]
    bodies = [(t, g) for t, k, g in items if k in ("body", "counter")]
    slab, cols, tubes, cores = structure(run, floor)
    res = {"floor": floor, "programs": [m["program"] for m in chk.get("layout_meta", [])], "units": 0}
    pairs = 0
    for i in range(len(bodies)):
        for j in range(i + 1, len(bodies)):
            if bodies[i][1].intersects(bodies[j][1]) and frozenset((bodies[i][0], bodies[j][0])) not in INTENDED_STACK:
                if bodies[i][1].intersection(bodies[j][1]).area > 0.01:
                    pairs += 1
    res["overlapping_pairs"] = pairs
    tube_u = unary_union([s for _, s in tubes]) if tubes else Polygon()
    hard = unary_union([g for g in (cols, tube_u, cores) if not g.is_empty])
    res["touching_structure"] = sum(1 for _, g in bodies if g.intersects(hard))
    res["within_0.2m_of_structure"] = sum(1 for _, g in bodies if g.distance(hard) < 0.2)
    res["outside_slab"] = sum(1 for _, g in bodies if not slab.buffer(0.05).contains(g))
    units = [(t, g) for t, g in bodies if t not in ACCESSORY]
    res["units"] = len(units)
    sig = Counter((t, round(g.bounds[2] - g.bounds[0], 1), round(g.bounds[3] - g.bounds[1], 1)) for t, g in units)
    top, n = sig.most_common(1)[0]
    res["max_identical_share"] = round(n / len(units), 3)
    res["most_repeated"] = list(top)
    res["types"] = sorted({t.split("_")[0] if t.startswith(("brand_cell", "street_island", "cashier")) else t for t, _ in units})
    res["n_types"] = len(res["types"])
    # aisle width by erosion of the free floor
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
        valid = [a for a in anchors if big is not None and big.distance(a) < 1.3]       # 구조만으로도 이 폭이 닿는 앵커(튜브 사이 좁은 틈은 가구 탓이 아니다)
        er = free.buffer(-r)
        comps = [p for p in (er.geoms if hasattr(er, "geoms") else [er]) if p.geom_type == "Polygon" and not p.is_empty]
        near = {i for i, p in enumerate(comps) for a in valid if p.distance(a) < 1.3}
        if len(valid) >= 2 and comps and len(near) == 1 and all(any(p.distance(a) < 1.3 for p in comps) for a in valid):
            best = 2 * r
            res["aisle_anchors_reachable_by_structure"] = len(valid)
            break
    res["aisle_width_connecting_all_anchors_m"] = best
    res["passes"] = bool(pairs == 0 and res["touching_structure"] == 0 and res["max_identical_share"] <= MAX_SHARE and res["n_types"] >= MIN_TYPES
                         and best is not None and best >= 1.2)
    return res


def check_distinct(results):
    sets = {r["floor"]: set(r["types"]) for r in results}
    prim = {r["floor"]: (r["programs"] or [""])[0] for r in results}
    out, worst = {}, 0.0
    fl = sorted(sets)
    for i, a in enumerate(fl):
        for b in fl[i + 1:]:
            if prim[a] == prim[b]:                                                     # 같은 프로그램(10F·15F F&B)은 비슷해야 한다. 서로 다른 프로그램만 비교한다
                continue
            j = len(sets[a] & sets[b]) / max(1, len(sets[a] | sets[b]))
            out["%s~%s" % (a, b)] = round(j, 2)
            worst = max(worst, j)
    return {"jaccard": out, "max_jaccard": round(worst, 2), "passes": worst <= 0.5}


if __name__ == "__main__":
    run = os.path.abspath(sys.argv[1])
    rs = [check_floor(run, f) for f in ("3F", "8F", "10F", "13F", "15F")]
    d = check_distinct(rs)
    json.dump({"floors": rs, "distinct": d}, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in rs:
        print(r["floor"], "units", r["units"], "types", r["n_types"], "share", r["max_identical_share"], "overlap", r["overlapping_pairs"], "touch", r["touching_structure"],
              "soft<0.2m", r["within_0.2m_of_structure"], "aisle", r["aisle_width_connecting_all_anchors_m"], "PASS" if r["passes"] else "FAIL")
    print("distinct:", d["max_jaccard"], "PASS" if d["passes"] else "FAIL")

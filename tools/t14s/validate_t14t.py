"""C-T14T deterministic checks (technical usability + route geometry only; this is NOT an architectural or visual review).

    python -I tools/t14s/validate_t14t.py [--out outputs/T14T] [--report docs/t14t_corrections/build_test_report.json]

Each floor is re-planned (the planner is deterministic) so the geometry checks run on the same model that produced the files;
the metadata of the produced files is compared with it. Unresolved circulation items are reported explicitly and are never
counted as a pass: `circulation_complete` is False while any item is open, and each open item must carry a decision id.
"""
import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

import ezdxf  # noqa: E402
import fitz  # noqa: E402
from PIL import Image  # noqa: E402
from shapely.geometry import LineString, Point, box  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
from t14s import planner as PL  # noqa: E402
from t14s import sheets as SH  # noqa: E402
from t14s import source as SRC  # noqa: E402

A1_MM, A3_MM = (841.0, 594.0), (420.0, 297.0)
COL_R = SRC.COL_R
ID_PATTERN = re.compile(r"A-[A-Z]{3,}-[A-Z]|_car_\d|ESCL|_slice|source_id|[A-Za-z_]\.00\d")
VERIFIED_ONLY = {"A-COLS", "A-WALL-EXT", "A-FLOR-OPEN"}
PROPOSED_ONLY = {"A-CIRC", "A-CIRC-SVC", "A-WALL-PART", "A-FURN", "A-ZONE", "A-RAIL"}


def names(f):
    s = "T14T_%s_plan" % f
    return {"svg": s + "_A1_1to200.svg", "a1pdf": s + "_A1_1to200.pdf", "a3pdf": s + "_A3_split_1to200.pdf",
            "png": s + "_A1_1to200.png", "dxf": s + ".dxf", "json": s + "_metadata.json"}


def check_floor(out, f):
    res, ok = {}, True

    def rec(k, passed, detail=""):
        nonlocal ok
        res[k] = {"pass": bool(passed), "detail": detail}
        ok = ok and bool(passed)
    d = os.path.join(out, f)
    n = names(f)
    rec("files_present", all(os.path.exists(os.path.join(d, v)) for v in n.values()), "6 expected files")
    if not res["files_present"]["pass"]:
        return {"floor": f, "pass": False, "checks": res, "unresolved": [], "circulation_complete": False, "not_modeled": []}
    g = SRC.load_floor(f)
    # ---------------------------------------------------------------- file validity
    svg_p = os.path.join(d, n["svg"])
    txt = open(svg_p, encoding="utf-8").read()
    try:
        root = ET.parse(svg_p).getroot()
        rec("svg_parses", root.get("width") == "841mm" and root.get("height") == "594mm", "A1 841x594 mm declared")
        rec("svg_layers_present", all(('id="%s"' % L) in txt for L in ("A-COLS", "A-WALL-EXT", "A-WALL-CORE", "A-DOOR", "A-CIRC", "A-ANNO-SYMB")), "layer groups")
        rec("svg_has_provenance", 'data-prov="MODEL_VERIFIED"' in txt and 'data-prov="PROPOSED_DESIGN"' in txt, "data-prov groups")
        visible = re.findall(r"<text[^>]*>([^<]*)</text>", txt)
        leaks = sorted({t for t in visible if ID_PATTERN.search(t)})
        rec("no_internal_identifiers_in_visible_text", not leaks, "leaks=%s" % leaks[:4])
    except Exception as e:  # noqa: BLE001
        rec("svg_parses", False, repr(e))
    try:
        with fitz.open(os.path.join(d, n["a1pdf"])) as pdf:
            pg = pdf[0]
            w, h = pg.rect.width / 72 * 25.4, pg.rect.height / 72 * 25.4
            rec("a1_pdf_size", len(pdf) == 1 and abs(w - A1_MM[0]) < 1.0 and abs(h - A1_MM[1]) < 1.0, "%.1f x %.1f mm" % (w, h))
            rec("a1_pdf_vector", len(pg.get_images()) == 0 and len(pg.get_drawings()) > 500, "images=%d drawings=%d" % (len(pg.get_images()), len(pg.get_drawings())))
            rec("a1_pdf_text", "1:200" in pg.get_text() and f in pg.get_text(), "scale + floor text extractable")
            # physical scale: column discs are 0.9 m = 4.5 mm and the outer columns span 52.8 m = 264 mm on the sheet
            discs = [dr for dr in pg.get_drawings() if dr.get("fill") == (0.0, 0.0, 0.0) and 4.2 <= dr["rect"].width / 72 * 25.4 <= 4.8 and abs(dr["rect"].width - dr["rect"].height) < 0.5]
            xs = [(dr["rect"].x0 + dr["rect"].x1) / 2 / 72 * 25.4 for dr in discs]
            span = (max(xs) - min(xs)) if xs else 0.0
            rec("physical_scale_1to200", len(discs) >= len(g.columns) - 1 and abs(span - 264.0) < 1.5, "column discs=%d (source %d), grid span %.1f mm (expected 264.0)" % (len(discs), len(g.columns), span))
        with fitz.open(os.path.join(d, n["a3pdf"])) as pdf:
            sizes = [(p.rect.width / 72 * 25.4, p.rect.height / 72 * 25.4) for p in pdf]
            rec("a3_pdf_size", len(pdf) == 2 and all(abs(w - A3_MM[0]) < 1.0 and abs(h - A3_MM[1]) < 1.0 for w, h in sizes), "pages=%d" % len(pdf))
            rec("a3_pdf_vector", all(len(p.get_images()) == 0 for p in pdf), "no raster images")
    except Exception as e:  # noqa: BLE001
        rec("pdf_opens", False, repr(e))
    try:
        with Image.open(os.path.join(d, n["png"])) as im:
            im.load()
            rec("png_decodes", im.size == (6622, 4677), "%dx%d" % im.size)
    except Exception as e:  # noqa: BLE001
        rec("png_decodes", False, repr(e))
    try:
        doc = ezdxf.readfile(os.path.join(d, n["dxf"]))
        aud = doc.audit()
        rec("dxf_opens_audits", len(aud.errors) == 0 and len(doc.modelspace()) > 300, "entities=%d audit_errors=%d" % (len(doc.modelspace()), len(aud.errors)))
        cols = [e for e in doc.modelspace() if e.dxf.layer == "A-COLS" and e.dxftype() == "LWPOLYLINE"]
        rec("dxf_columns_match_source", len(cols) == len(g.columns), "%d vs %d" % (len(cols), len(g.columns)))
        rec("dxf_units_mm", doc.units == 4, "INSUNITS=%s" % doc.units)
        dtext = [e.dxf.text for e in doc.modelspace() if e.dxftype() == "TEXT"]
        rec("dxf_no_internal_identifiers", not [t for t in dtext if ID_PATTERN.search(t)], "text entities=%d" % len(dtext))
    except Exception as e:  # noqa: BLE001
        rec("dxf_opens_audits", False, repr(e))
    meta = json.load(open(os.path.join(d, n["json"]), encoding="utf-8"))
    gv = meta["geometry_verified"]
    rec("meta_state", meta["review_state"] == "C_T14T_READY_FOR_CHATGPT_INDEPENDENT_REVIEW" and meta["approval"] == "NOT_APPROVED" and meta["frozen"] is False, "review state / no approval claimed")
    rec("source_geometry_unchanged", meta["source"]["slice_sha256"] == g.slice_sha256 and gv["columns"] == len(g.columns) and abs(gv["slab_net_m2"] - round(g.slab.area, 1)) < 0.06
        and gv["cores"] == sorted(g.cores), "slice sha256 + columns/slab/cores vs pinned slice")
    # ---------------------------------------------------------------- geometry on the same deterministic model
    pl = PL.Planner2(g, 7)
    d_ = pl.run()
    rec("deterministic_replan_matches_metadata", [(r["id"], r["area_m2"]) for r in sorted(d_.rooms, key=lambda r: r["id"])] == [(r["id"], r["area_m2"]) for r in meta["design_proposed"]["rooms"]],
        "rooms=%d" % len(d_.rooms))
    wx0, wy0, wx1, wy1 = SH.window_full()
    bad = [it.ref for it in d_.items if it.geom.bounds[0] < wx0 - 1e-6 or it.geom.bounds[1] < wy0 - 1e-6 or it.geom.bounds[2] > wx1 + 1e-6 or it.geom.bounds[3] > wy1 + 1e-6]
    rec("no_geometry_outside_sheet_window", not bad, "outside: %s" % bad[:3])
    rec("labels_placed", sum(1 for r in d_.rooms if r.get("label") is None) == 0, "every room has a label or forced tag")
    ext = [it for it in d_.items if it.layer == "A-WALL-EXT"]
    opn = sorted(round(it.geom.area, 3) for it in d_.items if it.layer == "A-FLOR-OPEN")
    rec("drawing_uses_verified_geometry", len([it for it in d_.items if it.layer == "A-COLS"]) == len(g.columns) and ext and abs(Polygon_area(ext[0].geom) - g.outline.area) < 0.01
        and opn == sorted(round(h.area, 3) for h in g.holes), "columns, slab edge and openings equal the pinned slice")
    slab = g.slab
    # rooms inside the verified slab
    out_rooms = [r["id"] for r in d_.rooms if r["poly"].difference(slab.buffer(0.06)).area > 0.2]
    rec("rooms_within_slab", not out_rooms, "rooms outside slab: %s" % out_rooms[:5])
    # routes (visitor + provisional + service) inside the slab, away from cores, clear of columns
    allr = [("visitor", a, b, ls) for a, b, ls, prov in pl.routes] + [("service", a, "service", ls) for a, b, ls in pl.svc_routes]
    core_u = unary_union([box(*b).buffer(-0.02) for b in g.cores.values()])
    outside = [(k, a) for k, a, b, ls in allr if ls.difference(slab.buffer(0.05)).length > 0.01]
    rec("routes_within_slab", not outside, "routes=%d outside=%s" % (len(allr), outside[:3]))
    in_core = [(k, a) for k, a, b, ls in allr if ls.intersects(core_u)]
    rec("routes_avoid_cores", not in_core, "crossing cores: %s" % in_core[:3])
    worst = min(((min((Point(c).distance(ls) for c in g.columns), default=99.0) - COL_R), a) for k, a, b, ls in allr) if allr else (99.0, "-")
    rec("corridor_to_column_clearance", worst[0] >= 0.55, "min clear gap column face -> route centre line = %.2f m (rule >= 0.60 m, 0.55 tolerance) at %s" % worst)
    # doors, swings and partitions
    doors = []
    for u in pl.units:
        doors.append(("unit", u["door"]["center"], u["door"]["swing"]))
        for dr in (u["plan"]["doors"] if u.get("plan") else []):
            doors.append((dr["kind"], dr["center"], dr["swing"]))
    col_u = pl.col_u
    hit_col = [(k, tuple(round(v, 1) for v in c)) for k, c, sw in doors if sw.intersection(col_u).area > 1e-6]
    rec("door_swings_clear_of_columns", not hit_col, "%d doors checked, hits=%s" % (len(doors), hit_col[:3]))
    mains = [sw for k, c, sw in doors if k == "unit"]
    overlap = sum(1 for i in range(len(mains)) for j in range(i + 1, len(mains)) if mains[i].intersection(mains[j]).area > 0.05)
    rec("door_swings_do_not_overlap", overlap == 0, "overlapping main-door swings=%d" % overlap)
    parts = [ln for u in pl.units if u.get("plan") for ln in u["plan"]["parts"]]
    part_u = unary_union([ln.buffer(0.05) for ln in parts]) if parts else None
    rec("partitions_clear_of_columns", part_u is None or part_u.intersection(col_u).area < 1e-4, "partitions=%d" % len(parts))
    on_wall = []
    wall_lines = unary_union([u["poly"].boundary for u in pl.units] + parts)
    for k, c, sw in doors:
        if Point(c).distance(wall_lines) > 0.12:
            on_wall.append((k, tuple(round(v, 1) for v in c)))
    rec("door_openings_on_walls", not on_wall, "doors off any wall line: %s" % on_wall[:3])
    cross = 0
    wall_poly = unary_union([ln.buffer(0.04) for ln in parts]) if parts else None
    if wall_poly is not None:
        for u in pl.units:
            for dr in (u["plan"]["doors"] if u.get("plan") else []):
                inner = dr["swing"].buffer(-0.06)
                if not inner.is_empty and inner.intersection(wall_poly).area > 0.02:
                    cross += 1
    rec("door_swings_do_not_cross_partitions", cross == 0, "swings crossing a partition=%d" % cross)
    # ---------------------------------------------------------------- route graph (from the written metadata)
    G = meta["design_proposed"]["circulation_graph"]
    nodes = {nd["id"]: nd for nd in G["nodes"]}
    parent = {k: k for k in nodes}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for e in G["edges"]:
        if e["a"] in parent and e["b"] in parent:
            parent[find(e["a"])] = find(e["b"])
    placed = [k for k, nd in nodes.items() if nd["status"] in ("ON_SLAB", "AT_OPENING_EDGE")]
    comps = {find(k) for k in placed}
    rec("route_graph_connected", len(comps) <= 1, "%d routed nodes in %d component(s), %d edges" % (len(placed), len(comps), len(G["edges"])))
    ends_ok = True
    for e in G["edges"]:
        for key, pt in (("a", e["coords"][0]), ("b", e["coords"][-1])):
            nd = nodes[e[key]]
            if nd.get("x") is not None and Point(nd["x"], nd["y"]).distance(Point(pt)) > 0.6:
                ends_ok = False
    rec("route_endpoints_match_nodes", ends_ok, "edge ends within 0.6 m of their nodes")
    unit_unreach = [u for u in G["unit_doors"] if not u["reachable"]]
    rec("unit_door_aprons_reachable", not unit_unreach, "doors=%d unreachable=%d" % (len(G["unit_doors"]), len(unit_unreach)))
    unres = list(G["unresolved"])
    rec("unresolved_items_have_decision_ids", all(u.get("decision") for u in unres if u["type"] in ("escalator", "elevator", "core", "fr")), "open items=%d" % len(unres))
    # ---------------------------------------------------------------- provenance
    lay = {}
    for it in d_.items:
        lay.setdefault(it.layer, set()).add(it.prov)
    bad_v = sorted(L for L in VERIFIED_ONLY if lay.get(L, set()) - {"MODEL_VERIFIED"})
    bad_p = sorted(L for L in PROPOSED_ONLY if "MODEL_VERIFIED" in lay.get(L, set()))
    rec("provenance_labels", not bad_v and not bad_p, "verified-only layers mislabelled=%s, proposed-only layers tagged verified=%s" % (bad_v, bad_p))
    return {"floor": f, "pass": ok, "checks": res, "unresolved": unres, "circulation_complete": not unres, "not_modeled": G.get("not_modeled", []),
            "decision_refs": sorted(meta["design_proposed"]["decision_refs"].keys())}


def Polygon_area(g):
    from shapely.geometry import Polygon
    return Polygon(g.coords).area if g.geom_type == "LineString" else g.area


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "outputs", "T14T"))
    ap.add_argument("--report", default=os.path.join(ROOT, "docs", "t14t_corrections", "build_test_report.json"))
    ap.add_argument("--floors", nargs="*", default=SRC.TARGET_FLOORS)
    a = ap.parse_args()
    report = {"schema": "C-T14T-BUILD-TEST-1.0",
              "scope": "deterministic technical-usability and route-geometry checks only; no architectural or visual review",
              "source_geometry": SRC.verify_sources(), "floors": []}
    man = json.load(open(os.path.join(a.out, "SHA256_MANIFEST.json"), encoding="utf-8"))["floors"]
    for f in a.floors:
        r = check_floor(a.out, f)
        fm = man.get(f, {})
        bad = [k for k, v in fm.items() if os.path.exists(os.path.join(a.out, f, k)) and SRC.sha256(os.path.join(a.out, f, k)) != v["sha256"]]
        r["checks"]["manifest_sha256"] = {"pass": bool(fm) and not bad, "detail": "files=%d mismatches=%s" % (len(fm), bad)}
        r["pass"] = r["pass"] and r["checks"]["manifest_sha256"]["pass"]
        report["floors"].append(r)
        fails = [k for k, v in r["checks"].items() if not v["pass"]]
        print("%-4s technical=%s circulation_complete=%s open_items=%d %s" % (f, "PASS" if r["pass"] else "FAIL", r["circulation_complete"], len(r["unresolved"]), fails or ""))
    open_items = {r["floor"]: r["unresolved"] for r in report["floors"] if r["unresolved"]}
    report["summary"] = {"floors_tested": len(report["floors"]), "floors_technical_pass": sum(1 for r in report["floors"] if r["pass"]),
                         "source_geometry_unchanged": report["source_geometry"]["ok"],
                         "floors_circulation_complete": [r["floor"] for r in report["floors"] if r["circulation_complete"]],
                         "floors_circulation_pending_decision": sorted(open_items),
                         "open_circulation_items": sum(len(v) for v in open_items.values())}
    os.makedirs(os.path.dirname(a.report), exist_ok=True)
    json.dump(report, open(a.report, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    s = report["summary"]
    print("source geometry unchanged:", s["source_geometry_unchanged"], "| technical pass %d/%d" % (s["floors_technical_pass"], s["floors_tested"]),
          "| circulation complete on %d floors, %d open items on %d floors" % (len(s["floors_circulation_complete"]), s["open_circulation_items"], len(open_items)))
    print("report:", os.path.abspath(a.report))
    sys.exit(0 if s["floors_technical_pass"] == s["floors_tested"] and s["source_geometry_unchanged"] else 1)


if __name__ == "__main__":
    main()

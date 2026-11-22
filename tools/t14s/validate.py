"""C-T14S deterministic build checks (technical usability only; this is NOT an architectural or visual review).

    python -I tools/t14s/validate.py [--out outputs/T14S] [--report docs/t14s_floor_plans/build_test_report.json]
"""
import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

import ezdxf  # noqa: E402
import fitz  # noqa: E402
from PIL import Image  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
from t14s import layout as LY  # noqa: E402
from t14s import source as SRC  # noqa: E402

A1_MM, A3_MM = (841.0, 594.0), (420.0, 297.0)
KINDS = ("svg", "dxf", "a1pdf", "a3pdf", "png", "json")


def names(f):
    s = "T14S_%s_plan" % f
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
        return {"floor": f, "pass": False, "checks": res}
    g = SRC.load_floor(f)
    svg_p = os.path.join(d, n["svg"])
    try:
        root = ET.parse(svg_p).getroot()
        txt = open(svg_p, encoding="utf-8").read()
        rec("svg_parses", True, "w=%s h=%s" % (root.get("width"), root.get("height")))
        rec("svg_sheet_A1", root.get("width") == "841mm" and root.get("height") == "594mm", "declared 841x594 mm")
        rec("svg_layers_present", all(('id="%s"' % L) in txt for L in ("A-COLS", "A-WALL-EXT", "A-WALL-CORE", "A-DOOR", "A-ANNO-SYMB")), "layer groups")
        rec("svg_declares_scale", "1:200" in txt, "title block text")
        rec("svg_has_provenance", 'data-prov="MODEL_VERIFIED"' in txt and 'data-prov="PROPOSED_DESIGN"' in txt, "data-prov groups")
    except Exception as e:  # noqa: BLE001
        rec("svg_parses", False, repr(e))
    try:
        with fitz.open(os.path.join(d, n["a1pdf"])) as pdf:
            pg = pdf[0]
            w, h = pg.rect.width / 72 * 25.4, pg.rect.height / 72 * 25.4
            rec("a1_pdf_size", len(pdf) == 1 and abs(w - A1_MM[0]) < 1.0 and abs(h - A1_MM[1]) < 1.0, "%.1f x %.1f mm" % (w, h))
            rec("a1_pdf_vector", len(pg.get_images()) == 0 and len(pg.get_drawings()) > 500, "images=%d drawings=%d" % (len(pg.get_images()), len(pg.get_drawings())))
            rec("a1_pdf_text", "1:200" in pg.get_text() and f in pg.get_text(), "scale + floor text extractable")
        with fitz.open(os.path.join(d, n["a3pdf"])) as pdf:
            sizes = [(p.rect.width / 72 * 25.4, p.rect.height / 72 * 25.4) for p in pdf]
            rec("a3_pdf_size", len(pdf) == 2 and all(abs(w - A3_MM[0]) < 1.0 and abs(h - A3_MM[1]) < 1.0 for w, h in sizes),
                "pages=%d %s" % (len(pdf), [(round(w, 1), round(h, 1)) for w, h in sizes]))
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
    except Exception as e:  # noqa: BLE001
        rec("dxf_opens_audits", False, repr(e))
    meta = json.load(open(os.path.join(d, n["json"]), encoding="utf-8"))
    gv = meta["geometry_verified"]
    rec("meta_state", meta["review_state"] == "READY_FOR_CHATGPT_INDEPENDENT_REVIEW" and meta["approval"] == "NOT_APPROVED" and meta["frozen"] is False, "review state / no approval claimed")
    rec("meta_geometry_matches_source", gv["columns"] == len(g.columns) and abs(gv["slab_net_m2"] - round(g.slab.area, 1)) < 0.06 and gv["cores"] == sorted(g.cores), "columns/slab/cores vs slice")
    rec("meta_source_hash", meta["source"]["slice_sha256"] == g.slice_sha256, "slice sha256")
    rec("rooms_present", len(meta["design_proposed"]["rooms"]) >= 5, "rooms=%d" % len(meta["design_proposed"]["rooms"]))
    rec("room_areas_positive", all(r["area_m2"] > 0 for r in meta["design_proposed"]["rooms"]), "areas computed from polygons")
    rec("proposed_flagged", meta["provenance_counts"].get("PROPOSED_DESIGN", 0) > 0 and meta["provenance_counts"].get("MODEL_VERIFIED", 0) > 0, str(meta["provenance_counts"]))
    # clipping: every drawn item must lie inside the A1 plan window
    d_ = LY.plan_floor(f)
    from t14s import sheets as SH
    wx0, wy0, wx1, wy1 = SH.window_full()
    bad = [it.ref for it in d_.items if it.geom.bounds[0] < wx0 - 1e-6 or it.geom.bounds[1] < wy0 - 1e-6 or it.geom.bounds[2] > wx1 + 1e-6 or it.geom.bounds[3] > wy1 + 1e-6]
    rec("no_geometry_outside_sheet_window", not bad, "outside: %s" % bad[:3])
    unl = sum(1 for r in d_.rooms if r.get("label") is None)
    rec("labels_placed", unl == 0, "unplaced labels=%d (listed in schedule)" % unl)
    return {"floor": f, "pass": ok, "checks": res}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "outputs", "T14S"))
    ap.add_argument("--report", default=os.path.join(ROOT, "docs", "t14s_floor_plans", "build_test_report.json"))
    ap.add_argument("--floors", nargs="*", default=SRC.TARGET_FLOORS)
    a = ap.parse_args()
    report = {"schema": "C-T14S-BUILD-TEST-1.0", "scope": "deterministic technical-usability checks only; no architectural/visual review",
              "source_geometry": SRC.verify_sources(), "floors": [], "manifest": {}}
    man_p = os.path.join(a.out, "SHA256_MANIFEST.json")
    man = json.load(open(man_p, encoding="utf-8"))["floors"]
    for f in a.floors:
        r = check_floor(a.out, f)
        fm = man.get(f, {})
        bad = [k for k, v in fm.items() if os.path.exists(os.path.join(a.out, f, k)) and SRC.sha256(os.path.join(a.out, f, k)) != v["sha256"]]
        r["checks"]["manifest_sha256"] = {"pass": bool(fm) and not bad, "detail": "files=%d mismatches=%s" % (len(fm), bad)}
        r["pass"] = r["pass"] and r["checks"]["manifest_sha256"]["pass"]
        report["floors"].append(r)
        fails = [k for k, v in r["checks"].items() if not v["pass"]]
        print("%-4s %s %s" % (f, "PASS" if r["pass"] else "FAIL", fails or ""))
    report["all_floors_produced"] = [r["floor"] for r in report["floors"] if r["checks"]["files_present"]["pass"]]
    report["summary"] = {"floors_tested": len(report["floors"]), "floors_passed": sum(1 for r in report["floors"] if r["pass"]),
                         "source_geometry_unchanged": report["source_geometry"]["ok"]}
    os.makedirs(os.path.dirname(a.report), exist_ok=True)
    json.dump(report, open(a.report, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("source geometry unchanged:", report["source_geometry"]["ok"], "| passed %d/%d" % (report["summary"]["floors_passed"], report["summary"]["floors_tested"]))
    print("report:", os.path.abspath(a.report))
    sys.exit(0 if report["summary"]["floors_passed"] == report["summary"]["floors_tested"] and report["source_geometry"]["ok"] else 1)


if __name__ == "__main__":
    main()

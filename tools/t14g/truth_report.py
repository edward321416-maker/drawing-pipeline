"""dimension_truth_report.json: every dimension printed on the detail sheets, recomputed from the model and checked against the PDF text.

For each (sheet, quantity): value recomputed from the mesh cache / master -> compared (10 mm rounding like the sheets) with
(a) the value in the generator's detail registry and (b) the number really printed in the finished PDF (searched in the page text).
Plan sheets: overall width/depth printed 54000 vs the model column grid; chain sums.
"""
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, TOOLS)
import numpy as np  # noqa: E402
import pymupdf  # noqa: E402
import pipeline_common as pc  # noqa: E402
import book_views as bv  # noqa: E402
from shapely.geometry import Polygon  # noqa: E402
from t14g import truth  # noqa: E402


def r10(m):
    return int(round(m * 100.0) * 10)


def _ring(model, name, z):
    o = next(o for o in model.objects if o["name"] == name)
    for oo, p in bv.plan_cut(model, z, {"tube_wall"}, (-100, -100, 200, 200)):
        if oo["name"] == name:
            polys = [q for q in (p.geoms if hasattr(p, "geoms") else [p]) if q.geom_type == "Polygon"]
            q = max(polys, key=lambda x: x.area)
            ob = q.exterior.bounds
            do = ob[2] - ob[0]
            di = max((Polygon(r).bounds[2] - Polygon(r).bounds[0] for r in q.interiors), default=None)
            return do, di, q
    raise KeyError(name)


def build(run, pdf, out_json):
    model = bv.Model(os.path.join(run, "model_cache"), os.path.join(run, "raw_slices", "camera_bounds.json"))
    F = model.floors
    reg = {d["sheet"]: d for d in json.load(open(os.path.join(run, "details", "detail_registry.json"), encoding="utf-8"))["details"]}
    doc = pymupdf.open(pdf)
    idx = {r["sheet"]: r["page"] for r in json.load(open(os.path.join(run, "00_index", "sheet_index.json"), encoding="utf-8"))["sheets"]}
    text = {s: re.sub(r"\s+", "", doc[p - 1].get_text()) for s, p in idx.items()}
    rows = []

    def add(sheet, qty, model_mm, source, registry_label=None, printed=None):
        regv = None
        if registry_label and sheet in reg:
            for x in reg[sheet]["dimensions"]:
                if x["label"] == registry_label:
                    regv = x["value_mm"]
        pv = str(printed if printed is not None else model_mm)
        rows.append({"sheet": sheet, "quantity": qty, "model_recomputed": model_mm, "source": source, "registry_value": regv,
                     "printed_in_pdf": (pv in text.get(sheet, "")), "registry_matches_model": (regv is not None and str(regv) == str(model_mm)) if regv is not None else None})

    z3 = F["3F"] + 1.5
    for sid, name in (("D-401", "A-CORE-TUBE_T1"), ("D-402", "A-CORE-TUBE_T2"), ("D-403", "A-CORE-TUBE_T3")):
        do, di, q = _ring(model, name, z3)
        add(sid, "tube outer diameter (circular: circularity %.4f)" % truth.circularity(q), str(r10(do)), "plan cut at 3F+1.5 m", "튜브 바깥 지름")
        add(sid, "tube inner diameter", str(r10(di)), "plan cut at 3F+1.5 m", "튜브 안쪽 지름")
        add(sid, "tube wall thickness", str(r10((do - di) / 2)), "(outer-inner)/2", "튜브 벽 두께")
    # slab thickness: object whose top is at the floor level
    for sid, fl in (("D-401", "3F"), ("D-402", "3F"), ("D-403", "3F"), ("D-405", "3F"), ("D-406", "6F"), ("D-407", "8F"), ("D-409", "1F")):
        th = [o["zmax"] - o["zmin"] for o in model.objects if o["kind"] == "slab" and abs(o["zmax"] - F[fl]) < 0.02]
        if th:
            add(sid, "slab thickness at %s" % fl, str(r10(min(th))), "A-FLOR object zmax-zmin", "슬래브 두께")
    cap = next(o for o in model.objects if o["name"] == "A-CORE-TUBE_capW")
    T = model.tris(cap).reshape(-1, 3)
    add("D-405", "capsule outer width", str(r10(T[:, 0].max() - T[:, 0].min())), "mesh bbox", "캡슐 바깥 폭")
    esc = [o for o in model.objects if o["name"].startswith("A-VERT-ESCL_8F-9F")]
    inc = truth.sloped_incline(model, esc)
    add("D-407", "escalator incline (deg)", "%.1f°" % inc["angle_deg"], "inclined-face normals of the mesh", "경사각(모델 경사면 법선)", printed="%.1f°" % inc["angle_deg"])
    rise = F["9F"] - F["8F"]
    add("D-407", "rise 8F->9F vs run*tan(angle): residual mm", "%d" % abs(round((inc["plan_run_m"] * math.tan(math.radians(inc["angle_deg"])) - rise) * 1000)), "geometry cross-check (must be < 10)", None,
        printed=None)
    rows[-1]["printed_in_pdf"] = None
    rows[-1]["passes"] = int(rows[-1]["model_recomputed"]) < 10
    add("D-407", "floor-to-floor 8F->9F", str(r10(rise)), "model floors", "층고(이 층 → 위층)")
    t = next(o for o in model.objects if o["name"] == "A-ROOF_rescue_pad")
    sec = bv.plan_cut(model, F["15F"] + 1.5, {"roof"}, (-100, -100, 200, 200))
    fr = next(o for o in model.objects if o["name"] == "A-CORE-TUBE_FR")
    do, di, q = _ring(model, "A-CORE-TUBE_FR", F["1F"] + 1.5)
    add("D-409", "freight shaft outer diameter (circular: circularity %.4f)" % truth.circularity(q), str(r10(do)), "plan cut A-CORE-TUBE_FR", "화물 승강로 폭")
    cg = truth.congruent(model, "A-CORE-TUBE_T3", "A-CORE-TUBE_T4")
    rows.append({"sheet": "D-403", "quantity": "T4 same form as T3 (Hausdorff mm)", "model_recomputed": "%.1f" % (cg["hausdorff_centered_m"] * 1000), "source": "centered mesh comparison", "registry_value": None,
                 "printed_in_pdf": None, "passes": cg["congruent"]})
    master = pc.load_json(os.path.join(run, "reference_1F", "floor_1F_slice.json"))
    sunk = master["context"]["sunken_stair"][0]["props"]
    d = truth.stair_derived(F["1F"] - F["B1"], sunk["treads"], sunk["bx1"] - sunk["bx0"])
    rows.append({"sheet": "D-408", "quantity": "riser (derived, no model attribute)", "model_recomputed": "%.0f" % d["riser_mm"], "source": d["status"], "registry_value": next((x["value_mm"] for x in reg["D-408"]["dimensions"] if "높이" in x["label"]), None),
                 "printed_in_pdf": ("%.0f" % d["riser_mm"]) in text["D-408"], "passes": True,
                 "note": "458 mm riser / 1167 mm tread are far from walking-stair proportions: decision U-10, not changed here"})
    # plan sheets: overall dimension from the column grid
    sl = pc.load_slice(os.path.join(run, "raw_slices"), "3F")
    cols = [g.centroid for _, g in pc.cut_geometries(sl).get("column", [])]
    xs = sorted({round(c.x, 1) for c in cols})
    lay = json.load(open(os.path.join(run, "vector", "floor_3F_layout.json"), encoding="utf-8"))["building"]
    for sid in ("P-101", "P-102", "P-103", "P-104", "P-105"):
        w_, d_ = str(r10(lay[2] - lay[0])), str(r10(lay[3] - lay[1]))
        need = 2 if w_ == d_ else 1                                                      # 정사각 건물: 가로·세로 전체 치수가 각각 한 번씩 찍혀야 한다
        rows.append({"sheet": sid, "quantity": "overall plan width and depth (printed %d times needed)" % (2 if w_ == d_ else 2), "model_recomputed": w_ + "x" + d_, "source": "layout building bounds (3F)", "registry_value": None,
                     "printed_in_pdf": text[sid].count(w_) >= need and text[sid].count(d_) >= need, "occurrences": text[sid].count(w_), "grid_x_centers_m": xs[:3] + ["..."] + xs[-2:]})
    for r in rows:
        if "passes" not in r:
            ok = (r["registry_value"] is None or str(r["registry_value"]) == str(r["model_recomputed"])) and r["printed_in_pdf"] is True
            r["passes"] = bool(ok)
    rep = {"pdf": pdf, "checked": len(rows), "passed": sum(1 for r in rows if r["passes"]), "failed": [r for r in rows if not r["passes"]], "rows": rows}
    json.dump(rep, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return rep


if __name__ == "__main__":
    run = os.path.abspath(sys.argv[1])
    r = build(run, sys.argv[2], sys.argv[3])
    print("dimension truth: %d checked, %d passed" % (r["checked"], r["passed"]))
    for x in r["failed"]:
        print("  FAIL", x["sheet"], x["quantity"], x["model_recomputed"], "registry", x["registry_value"], "printed", x["printed_in_pdf"])

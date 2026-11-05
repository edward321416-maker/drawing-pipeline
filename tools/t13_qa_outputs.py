"""C-T13 산출물 QA·manifest: 용지·레이어·중복(고스트)·기둥 34개 대조·출입구 상태·SHA-256.

    python tools/t13_qa_outputs.py --out outputs/T13 --geom tests/fixtures/t13_geom_1F.json --model engine/model/1F_master.model.json \
        --before-svg <기존 1F SVG> --blend <1F_master.blend> --slice <floor_1F_slice.json>

종료 코드 1 = 하나라도 기술 게이트 실패.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys

from shapely import wkt
from shapely.geometry import Point
from shapely.ops import unary_union

VARIANTS = ("A", "B")
NAME = "1F_Program_Concept_V2_%s"


def sha256(p):
    if not p or not os.path.exists(p):
        return None
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def group(svg, gid):
    m = re.search(r'<g id="%s">(.*?)</g>' % gid, svg, re.S)
    return m.group(1) if m else ""


def pdf_mm(path):
    from pypdf import PdfReader
    r = PdfReader(path)
    mb = r.pages[0].mediabox
    return (round(float(mb.width) * 25.4 / 72, 2), round(float(mb.height) * 25.4 / 72, 2)), len(r.pages)


def column_reconciliation(geom, model_path):
    """모델의 Col_* 34개 ↔ 도면에 그린 기둥. 안 그린 기둥은 가장 가까운 코어·튜브·화장실까지의 가장자리 거리와 함께 이유를 적는다."""
    model = json.load(open(model_path, encoding="utf-8"))
    src = []
    for o in model["objects"]:
        if o["name"].startswith("Col_"):
            xs = [v[0] for v in o["verts"]]
            ys = [v[1] for v in o["verts"]]
            src.append((o["name"], (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2))
    drawn = list(wkt.loads(geom["cols_drawn"]).geoms)
    struct = [(t["name"], wkt.loads(t["wkt"])) for t in geom["tubes"]] + [(z["name"], wkt.loads(z["wkt"])) for z in geom["zones"] if z["kind"] in ("core", "restroom")]
    rows = []
    for name, x, y in src:
        p = Point(x, y)
        hit = next((d for d in drawn if d.centroid.distance(p) < 0.05), None)
        near = min(struct, key=lambda s: s[1].distance(p))
        dist = near[1].distance(p)
        why = None
        if hit is None:
            why = ("화장실/코어 평면 안에 매입: 점 기둥이 벽체·칸막이 덩어리와 겹쳐 따로 그리지 않는다" if dist < 0.05 else
                   "코어·튜브·캡슐 외곽에서 기둥 가장자리까지 1.8 m 이내(렌더러 규칙 core_exclusion). 아래 center_distance_m 은 기둥 중심 기준")
        rows.append({"id": name, "x": round(x, 2), "y": round(y, 2), "drawn": hit is not None,
                     "nearest_core_or_tube": near[0], "center_distance_m": round(dist, 2), "reason": why})
    return {"source_columns": len(src), "drawn": sum(r["drawn"] for r in rows), "not_drawn": sum(not r["drawn"] for r in rows),
            "culled_min_center_distance_m": min((r["center_distance_m"] for r in rows if not r["drawn"]), default=None),
            "drawn_min_center_distance_m": min((r["center_distance_m"] for r in rows if r["drawn"]), default=None), "rows": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--geom", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--before-svg", default=None)
    ap.add_argument("--blend", default=None)
    ap.add_argument("--slice", default=None)
    ap.add_argument("--tests", default="")
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    geom = json.load(open(a.geom, encoding="utf-8"))
    fails = []
    report = {"gate_rules": "PASS 요건: 구획 중첩·부모 밖 유출·구조 침범·가구 중복·ID 칩 겹침·출입구 승격 모두 0", "variants": {}}
    before = open(a.before_svg, encoding="utf-8").read() if a.before_svg and os.path.exists(a.before_svg) else None
    layers_ref = None
    for v in VARIANTS:
        base = os.path.join(out, NAME % v)
        svg = open(base + ".svg", encoding="utf-8").read()
        chk = json.load(open(base + "_check.json", encoding="utf-8"))
        pr = chk["program"]
        row = {}
        row["sheet_mm_svg"] = bool(re.search(r'width="420mm" height="297mm"', svg))
        row["pdf_mm"], row["pdf_pages"] = pdf_mm(base + ".pdf")
        row["pdf_is_A3_420x297"] = abs(row["pdf_mm"][0] - 420) < 0.3 and abs(row["pdf_mm"][1] - 297) < 0.3 and row["pdf_pages"] == 1
        row["scale"] = chk["scale"]
        row["canvas_matches_A3"] = chk["canvas_matches_A3"]
        layers = re.findall(r'<g id="([a-z]+)">', svg)
        layers_ref = layers_ref or layers
        row["layers_same_as_variant_A"] = layers == layers_ref
        row["png_px"] = None
        try:
            from PIL import Image
            Image.MAX_IMAGE_PIXELS = None
            row["png_px"] = list(Image.open(base + ".png").size)
        except Exception:  # noqa: BLE001
            pass
        furn = group(svg, "furn")
        ds = re.findall(r'<path d="([^"]+)"[^>]*fill="#FFFFFF"', furn)
        dup = len(ds) - len(set(ds))
        row["furniture_body_paths"] = len(ds)
        row["furniture_duplicate_body_paths_ghost"] = dup
        env = group(svg, "envelope")
        arcs_env = re.findall(r'<polyline points="[^"]*"[^>]*stroke="#333"[^>]*/>', env)
        row["curtain_door_arc_paths"] = len(arcs_env)
        row["curtain_door_arc_paths_solid"] = sum(1 for e in arcs_env if "stroke-dasharray" not in e)
        doors = group(svg, "doors")
        row["dashed_paths_in_doors_layer"] = len(re.findall(r"stroke-dasharray", doors))
        if before is not None:
            for gid in ("cols",):
                row["structure_%s_identical_to_V1" % gid] = set(re.findall(r'<(?:path|polyline)[^>]*/>', group(svg, gid))) == set(re.findall(r'<(?:path|polyline)[^>]*/>', group(before, gid)))
            wv, wb = set(re.findall(r'<(?:path|polyline)[^>]*/>', group(svg, "walls"))), set(re.findall(r'<(?:path|polyline)[^>]*/>', group(before, "walls")))
            row["walls_paths_only_in_V2"] = len(wv - wb)
            row["walls_paths_only_in_V1"] = len(wb - wv)
        row["promoted_entries"] = [e["id"] for e in pr["proposed_entries"] if "PROPOSED_ONLY" not in e["status"]]
        qa = pr["qa"]
        hard = {"zone_overlap_m2_total": qa["zone_overlap_m2_total"], "zone_outside_parent_m2_max": qa["zone_outside_parent_m2_max"],
                "furniture_hits_structure": qa["furniture_hits_structure"], "furniture_outside_parent_zone": qa["furniture_outside_parent_zone"],
                "furniture_instance_overlaps": qa["furniture_instance_overlaps"], "furniture_in_entry_clearance": qa["furniture_in_entry_clearance"],
                "furniture_touching_column": chk["furniture_touching_column"], "furniture_touching_tube": chk["furniture_touching_tube"],
                "chips_overlapping_furniture": len(pr["zone_chips_overlapping_furniture"]), "ghost_duplicates": dup,
                "curtain_door_arcs_solid": row["curtain_door_arc_paths_solid"], "promoted_entries": len(row["promoted_entries"]),
                "door_swing_hits_wall": chk["door_swing_hits_wall"], "door_swing_hits_other_door": chk["door_swing_hits_other_door"],
                "unassigned_net_floor_m2": sum(qa["unassigned_net_floor_m2"].values())}
        row["hard_gates"] = hard
        bad = {k: x for k, x in hard.items() if x}
        if not (row["sheet_mm_svg"] and row["pdf_is_A3_420x297"] and row["canvas_matches_A3"] and row["layers_same_as_variant_A"]):
            bad["paper_scale_layers"] = False
        if bad:
            fails.append((v, bad))
        row["hard_gate_failures"] = bad
        row["output_sha256"] = {ext: sha256(base + ext) for ext in (".png", ".pdf", ".svg", "_check.json")}
        report["variants"][v] = row
    report["column_reconciliation"] = column_reconciliation(geom, a.model)
    report["input_sha256"] = {"source_blend_1F_master": sha256(a.blend), "slice_1F": sha256(a.slice), "master_model_json": sha256(a.model), "geom_dump": sha256(a.geom)}
    try:
        report["git_head"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))), text=True).strip()
    except Exception:  # noqa: BLE001
        report["git_head"] = None
    report["tests"] = a.tests
    report["technical_gate"] = "PASS" if not fails else "FAIL"
    report["gate"] = "HOLD" if not fails else "FAIL"
    report["gate_reason"] = "기술 QA 통과. 사용자 시각 승인·출입구 위치·법규 검토 전이라 HOLD" if not fails else str(fails)
    report["1F_FINAL_FROZEN"] = False
    p = os.path.join(out, "1F_Program_Concept_V2_QA.json")
    json.dump(report, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("QA gate:", report["gate"], "technical:", report["technical_gate"], os.path.abspath(p))
    for v, row in report["variants"].items():
        print(" ", v, "failures:", row["hard_gate_failures"] or "none")
    cr = report["column_reconciliation"]
    print("  columns: source %d drawn %d culled %d (culled min center dist %s m, drawn min %s m)" % (cr["source_columns"], cr["drawn"], cr["not_drawn"], cr["culled_min_center_distance_m"], cr["drawn_min_center_distance_m"]))
    man = {}
    for root, _, files in os.walk(out):
        for f in sorted(files):
            fp = os.path.join(root, f)
            if f != "1F_Program_Concept_V2_manifest.json":
                man[os.path.relpath(fp, out).replace("\\", "/")] = {"sha256": sha256(fp), "bytes": os.path.getsize(fp)}
    json.dump({"git_head": report["git_head"], "state": "PLAN_CANDIDATE_UNAPPROVED", "1F_FINAL_FROZEN": False, "inputs": report["input_sha256"], "files": man},
              open(os.path.join(out, "1F_Program_Concept_V2_manifest.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()

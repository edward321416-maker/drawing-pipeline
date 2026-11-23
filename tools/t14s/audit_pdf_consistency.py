"""Read-only cross-floor consistency check of the actual A1 and A3 PDF files of a C-T14T output folder.

    python -I tools/t14s/audit_pdf_consistency.py [--out outputs/T14T] [--report docs/t14t_audit_r1/evidence/pdf_consistency.json]

For every floor it opens the real PDF files (A1 1:200, A3 split) and checks, with explicit pass/fail criteria:
  P1 page count and physical page size (A1 841 x 594 mm, A3 two pages 420 x 297 mm)
  P2 vector content only (no embedded raster images)
  P3 the floor label, the scale text "1:200" and the level line "FFL +x.xxx (floor)" printed in the PDF equal the floor, the scale and level_ffl_m of the metadata
  P4 every unit, hall and garden room area in the metadata is printed in the PDF (formatted n,nnn.n㎡)
  F4 finding (not pass/fail): support rooms and restrooms whose area is not printed on the plan (room/area schedule coverage)
  P5 no internal identifier text (A-VERT, ESCL, _slice, source_id) in the printed text
  P6 the level-stack list printed on every floor is identical across floors
  P7 the title-block strings (project code, revision, date, review state) are identical across floors
The check says whether the PDFs agree with their own metadata and with each other. It does not review architecture, fire/egress or accessibility.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from t14s import source as SRC  # noqa: E402

A1_MM, A3_MM = (841.0, 594.0), (420.0, 297.0)
ID_PATTERN = re.compile(r"A-[A-Z]{3,}-[A-Z]|_car_\d|ESCL|_slice|source_id")
LEVEL = re.compile(r"FFL\s*([+-]\d+\.\d+)\s*\((\w+)\)")
AREA = re.compile(r"([\d,]+\.\d)㎡")
TITLE = re.compile(r"C-T14T[^\n]*|R1\b[^\n]*|2026-11-23[^\n]*|NOT APPROVED[^\n]*|PROPOSED_DESIGN[^\n]*")


def mm(r):
    return r.width / 72 * 25.4, r.height / 72 * 25.4


def names(f):
    s = "T14T_%s_plan" % f
    return s + "_A1_1to200.pdf", s + "_A3_split_1to200.pdf", s + "_metadata.json"


def check_floor(out: Path, f: str) -> dict:
    a1n, a3n, mn = names(f)
    meta = json.loads((out / f / mn).read_text(encoding="utf-8"))
    res = {}

    def rec(k, ok, detail):
        res[k] = {"pass": bool(ok), "detail": detail}
    a1 = fitz.open(str(out / f / a1n))
    a3 = fitz.open(str(out / f / a3n))
    w, h = mm(a1[0].rect)
    rec("P1_page_count_and_size", len(a1) == 1 and abs(w - A1_MM[0]) < 1 and abs(h - A1_MM[1]) < 1 and len(a3) == 2 and all(abs(mm(p.rect)[0] - A3_MM[0]) < 1 and abs(mm(p.rect)[1] - A3_MM[1]) < 1 for p in a3),
        "A1 %.1fx%.1f mm (%d page), A3 pages=%d" % (w, h, len(a1), len(a3)))
    rec("P2_vector_only", not a1[0].get_images() and all(not p.get_images() for p in a3), "images A1=%d A3=%d" % (len(a1[0].get_images()), sum(len(p.get_images()) for p in a3)))
    text = a1[0].get_text()
    a3text = "\n".join(p.get_text() for p in a3)
    lv = LEVEL.findall(text)
    ffl = meta["level_ffl_m"]
    rec("P3_label_scale_level", f in text and "1:200" in text and any(abs(float(v) - ffl) < 0.0006 and fl == f for v, fl in lv) and f in a3text and "1:200" in a3text,
        "level lines %s vs metadata %+.3f" % (lv[:2], ffl))
    printed = {}
    for a in AREA.findall(text):
        printed[a] = printed.get(a, 0) + 1
    main_rooms = [r for r in meta["design_proposed"]["rooms"] if r["kind"] not in ("support", "restroom")]
    small_rooms = [r for r in meta["design_proposed"]["rooms"] if r["kind"] in ("support", "restroom")]

    def shortfall(rooms):
        need = {}
        for r in rooms:
            k = "{:,.1f}".format(r["area_m2"])
            need[k] = need.get(k, 0) + 1
        return {k: n - printed.get(k, 0) for k, n in need.items() if printed.get(k, 0) < n}
    missing = shortfall(main_rooms)
    rec("P4_main_room_areas_printed", not missing, "unit/hall/garden rooms=%d, area values not printed as often as in metadata: %s" % (len(main_rooms), missing or "none"))
    unprinted_small = sum(shortfall(small_rooms).values())
    leaks = sorted({m.group(0) for t in (text, a3text) for m in ID_PATTERN.finditer(t)})
    rec("P5_no_internal_identifiers", not leaks, "leaks=%s" % leaks[:4])
    stack = re.search(r"LEVEL STACK[^\n]*\n(.*?)(?:\n[A-Z]{3,}[^\n]*\n|\Z)", text, re.S)
    levels = re.findall(r"\n((?:B\d|\d+F))\n([+-]?\d+\.\d)\n", "\n" + text)
    return {"floor": f, "checks": res, "finding_F4_support_or_restroom_area_not_printed": {"rooms": len(small_rooms), "area_not_printed": unprinted_small},
            "level_stack": levels, "title_strings": sorted(set(m.group(0).strip() for m in TITLE.finditer(text))), "pass": all(v["pass"] for v in res.values())}


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ROOT / "outputs" / "T14T"))
    ap.add_argument("--report", default=str(ROOT / "docs" / "t14t_audit_r1" / "evidence" / "pdf_consistency.json"))
    a = ap.parse_args(argv)
    out = Path(a.out)
    rows = [check_floor(out, f) for f in SRC.TARGET_FLOORS]
    stacks = {json.dumps(r["level_stack"]) for r in rows}
    titles = {json.dumps(r["title_strings"]) for r in rows}
    cross = {"P6_level_stack_identical_across_floors": {"pass": len(stacks) == 1 and len(rows[0]["level_stack"]) >= 16, "detail": "%d distinct level stacks, %d entries" % (len(stacks), len(rows[0]["level_stack"]))},
             "P7_title_strings_identical_across_floors": {"pass": len(titles) == 1, "detail": "%d distinct title-string sets: %s" % (len(titles), rows[0]["title_strings"][:6])}}
    report = {"schema": "C-T14T-AUDIT-PDF-CONSISTENCY-1.0", "scope": "agreement of the PDFs with their metadata and with each other; no architectural review", "folder": str(out),
              "source_geometry": SRC.verify_sources(), "floors": rows, "cross_floor": cross,
              "summary": {"floors": len(rows), "floors_all_pass": sum(r["pass"] for r in rows), "cross_floor_pass": all(v["pass"] for v in cross.values()),
                          "F4_support_or_restroom_rooms": sum(r["finding_F4_support_or_restroom_area_not_printed"]["rooms"] for r in rows),
                          "F4_area_not_printed": sum(r["finding_F4_support_or_restroom_area_not_printed"]["area_not_printed"] for r in rows)}}
    Path(a.report).parent.mkdir(parents=True, exist_ok=True)
    Path(a.report).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in rows:
        bad = [k for k, v in r["checks"].items() if not v["pass"]]
        print("%-4s %s %s" % (r["floor"], "PASS" if r["pass"] else "FAIL", bad or ""))
    for k, v in cross.items():
        print(k, "PASS" if v["pass"] else "FAIL", v["detail"])
    print("finding F4: %d support/restroom rooms, %d without a printed area" % (report["summary"]["F4_support_or_restroom_rooms"], report["summary"]["F4_area_not_printed"]))
    print("report:", Path(a.report).resolve())
    return 0 if report["summary"]["floors_all_pass"] == len(rows) and report["summary"]["cross_floor_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())

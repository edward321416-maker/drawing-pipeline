"""R10-B drawing cross-reference validation, read straight from the PDF vectors and text.

    python -I -X utf8 tools/r10b/validate_xref_r10b.py --build <dir> [--out review/wp0_r10_b/validation/R10B_XREF.json]
"""
from __future__ import annotations

import argparse
import json
import os
import re

import fitz

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
K = 72 / 25.4
# A-201 plan transform (paper mm = 49 + 5*(x+12), 67 + 5*(37-y)); identical to R10-A (checked against its record elsewhere)
PX = lambda x: 49 + 5 * (x + 12)   # noqa: E731
PY = lambda y: 67 + 5 * (37 - y)   # noqa: E731
EXISTING_R10A = {"A-501", "S-401"}


def segments(page):
    out = []
    for d in page.get_drawings():
        for it in d["items"]:
            if it[0] == "l":
                (x0, y0), (x1, y1) = it[1], it[2]
                out.append((x0 / K, y0 / K, x1 / K, y1 / K))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", required=True)
    ap.add_argument("--out", default=os.path.join(ROOT, "review", "wp0_r10_b", "validation", "R10B_XREF.json"))
    a = ap.parse_args()
    rec = json.load(open(os.path.join(a.build, "R10B_GEOMETRY.json"), encoding="utf-8"))
    ids = rec["page_order"]
    doc = fitz.open(os.path.join(a.build, "WP0_R10B_Representative_A2.pdf"))
    res = []

    def add(tid, title, ok, ev):
        res.append(dict(id=tid, title=title, status="PASS" if ok else "FAIL", evidence=ev))
        print(f"{tid} {'PASS' if ok else 'FAIL':4s} {title}", flush=True)

    texts = {sid: doc[i].get_text() for i, sid in enumerate(ids)}
    sec = rec["sheets"]["A-201"]["section"]
    # X1: recorded plane values agree between plan and section sheets
    add("X01", "A-201 section values equal the values the section sheets were cut at",
        abs(sec["A_A"]["x"] - rec["sheets"]["A-301"]["value"]) < 1e-9 and abs(sec["B_B"]["y"] - rec["sheets"]["A-302"]["value"]) < 1e-9,
        dict(plan=sec, A_301=rec["sheets"]["A-301"]["value"], A_302=rec["sheets"]["A-302"]["value"]))
    # X2/X3: the marks are really drawn at those plane positions on A-201 (vector measurement)
    segs = segments(doc[ids.index("A-201")])
    xa = PX(sec["A_A"]["x"])
    vert = [s for s in segs if abs(s[0] - xa) < 0.15 and abs(s[2] - xa) < 0.15]
    length_a = sum(abs(s[3] - s[1]) for s in vert)
    add("X02", "A-A mark: vector line drawn at the plan position of X = -4.200 and spanning the plan",
        length_a > 250, dict(expected_x_mm=round(xa, 3), segments=len(vert), total_length_mm=round(length_a, 1)))
    yb = PY(sec["B_B"]["y"])
    hor = [s for s in segs if abs(s[1] - yb) < 0.15 and abs(s[3] - yb) < 0.15]
    length_b = sum(abs(s[2] - s[0]) for s in hor)
    add("X03", "B-B mark: vector line drawn at the plan position of Y = +10.000 and spanning the plan",
        length_b > 250, dict(expected_y_mm=round(yb, 3), segments=len(hor), total_length_mm=round(length_b, 1)))
    # X4: sheet references resolve
    refs = {}
    unresolved = []
    for sid, t in texts.items():
        found = sorted(set(re.findall(r"\b([AS]-\d{3})\b", t)) - {sid})
        refs[sid] = found
        for r in found:
            if r not in ids and r not in EXISTING_R10A:
                unresolved.append((sid, r))
    add("X04", "Every sheet reference resolves to an R10-B sheet or an unchanged R10-A sheet (A-501, S-401)",
        not unresolved, dict(references=refs, unresolved=unresolved, r10a_carried=sorted(EXISTING_R10A)))
    # X5: A-201 refers to both sections, each section refers back to A-201
    add("X05", "A-201 refers to A-301 and A-302; both sections refer back to A-201",
        "A-301" in texts["A-201"] and "A-302" in texts["A-201"] and "A-201" in texts["A-301"] and "A-201" in texts["A-302"], dict())
    # X6: every callout string configured for the sections is present in the PDF text
    miss = []
    for sid in ("A-301", "A-302"):
        for c in rec["sheets"][sid].get("callouts", []):
            if c not in texts[sid]:
                miss.append((sid, c))
    add("X06", "Every callout of the section sheets is present in the PDF text layer", not miss, dict(missing=miss))
    # X7: level list = floors.json
    floors = json.load(open(os.path.join(ROOT, "data", "t14s", "source_slices", "floors.json"), encoding="utf-8"))["floors"]
    bad = [n for n, z in floors.items() if f"{n}  {z:+.3f}" not in texts["A-301"].replace("\xa0", " ") and f"{n} {z:+.3f}" not in re.sub(r"\s+", " ", texts["A-301"])]
    add("X07", "All 17 level labels of A-301 equal data/t14s/source_slices/floors.json", not bad, dict(levels=len(floors), missing=bad))
    # X8: room tags: every 2-01..2-26 appears on A-201 and in the schedule
    rooms = [r["id"] for r in rec["sheets"]["A-201"]["rooms"]]
    counts = {r: texts["A-201"].count(r) for r in rooms}
    add("X08", "All 26 room ids appear on A-201 at least twice (tag + schedule row)", len(rooms) == 26 and all(c >= 2 for c in counts.values()),
        dict(counts=counts))
    summary = dict(PASS=sum(r["status"] == "PASS" for r in res), FAIL=sum(r["status"] == "FAIL" for r in res))
    json.dump(dict(summary=summary, tests=res), open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2, default=str)
    print("SUMMARY", summary, "->", os.path.abspath(a.out))


if __name__ == "__main__":
    main()

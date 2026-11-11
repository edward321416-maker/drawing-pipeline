"""Single sheet registry reader (sheet number -> page, title, scale, grade).

Callout labels, scale bars and QA all read scale and page from here instead of hard-coding
numbers (audit finding F-01). The registry is docs/t14e_v2/sheet_index.json (V2) or the V3 index.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
V2_DIR = os.path.join(ROOT, "docs", "t14e_v2")
V2_PDF = os.path.join(V2_DIR, "drawing_set_candidate_v2.pdf")
V2_INDEX = os.path.join(V2_DIR, "sheet_index.json")
MM = 72.0 / 25.4          # PDF points per paper millimetre


def load(path=V2_INDEX):
    """Return {sheet_id: {...registry row..., 'scale_den': int | None}}."""
    data = json.load(open(path, encoding="utf-8"))
    out = {}
    for row in data["sheets"]:
        m = re.fullmatch(r"1:(\d+)", (row.get("scale") or "").strip())
        out[row["sheet"]] = dict(row, scale_den=int(m.group(1)) if m else None)
    return out


def by_page(reg):
    return {r["page"]: sid for sid, r in reg.items()}


def scale_of(reg, sheet_id):
    d = reg[sheet_id]["scale_den"]
    if d is None:
        raise KeyError("%s has no numeric scale in the registry" % sheet_id)
    return d

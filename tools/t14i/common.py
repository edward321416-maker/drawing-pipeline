"""Helpers shared by the C-T14I modules: run layout, model loading, status badge, registry rows."""
import hashlib
import json
import os

import t14i  # noqa: F401  (edition env, sys.path, text policy)
from t14i import config as cfg

RUN_DEFAULT = os.path.join(t14i.ROOT, "output", "C_T14I_run")


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def jl(p):
    return json.load(open(p, encoding="utf-8"))


def jd(obj, p):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(obj, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def v4_dir(run, *parts):
    """Every C-T14I output goes below <run>/v4/ (created on demand)."""
    d = os.path.join(run, "v4", *parts)
    os.makedirs(d, exist_ok=True)
    return d


def load_model(run):
    import book_views as bv
    return bv.Model(os.path.join(run, "model_cache"), os.path.join(run, "raw_slices", "camera_bounds.json"))


def badge(sh, x, y, kind, w=None, h=4.6, pt=6.0):
    """Status badge (text always spelled out, so it survives black-and-white printing). Returns right edge x."""
    col = cfg.CLASS_COLOR[kind]
    w = w or (len(kind) * pt * 0.3528 * 0.62 + 4.0)
    sh.path([[(x, y), (x + w, y), (x + w, y + h), (x, y + h)]], fill="#fff", stroke=col, w=0.3)
    sh.text(x + w / 2, y + h * 0.72, kind, pt, "bold", col, "middle")
    return x + w


def sheet_row(sh, base, title, grade, folder, scale=None, paper=None, status_class=None, extra=None):
    """Registry row for a saved sheet (the assembler reads these)."""
    row = {"sheet": sh.sid, "title": title, "scale": ("1:%d" % scale) if scale else "—", "grade": grade, "folder": folder,
           "paper": list(paper or sh.paper), "status_class": status_class,
           "scale_bars": getattr(sh, "bars", []),
           "files": {e: {"path": base + "." + e, "sha256": sha_file(base + "." + e)} for e in ("svg", "pdf", "png")}}
    if extra:
        row.update(extra)
    return row

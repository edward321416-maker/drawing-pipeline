"""Read-only geometry measurements for the open decisions D-01 (escalator landings), D-02 (cores without slab) and D-03 (lift entry rotations).

    python -I tools/t14s/audit_measurements.py [--out docs/t14t_audit_r1/measurements]

Everything is computed from the hash-pinned verified slices (data/t14s/source_slices) through src/t14s/source.py and from the decision records written
into the C-T14T metadata. Nothing is modified and nothing is drawn. The numbers describe how far verified geometry is from a usable landing, apron or
entry; they do not show that any alternative is valid. Parameters (stated in each output): landing depth 2.6 m and entry apron 2.6 m x 2.6 m are the values
the C-T14T builder used, not code requirements; the deck width equals the escalator width taken from the model.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from shapely import affinity  # noqa: E402
from shapely.geometry import LineString, Point, box  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

from t14s import source as SRC  # noqa: E402
from t14s import symbols as SY  # noqa: E402

LANDING_DEPTH = 2.6
STEP = 0.05
MAX_SHIFT = 15.0
METHOD = "MEASURED_FROM_VERIFIED_SLICE: geometry arithmetic only; no design validity, egress or code compliance is implied"


def meta_path(out_dir: Path, f: str) -> Path:
    return out_dir / f / ("T14T_%s_plan_metadata.json" % f)


def landing_rect(p, out, width, depth=LANDING_DEPTH):
    """Standing rectangle outward from escalator end p: `width` across the escalator, `depth` along the outward axis."""
    nx, ny = -out[1], out[0]
    hx, hy = width / 2.0, 0.0
    a = (p[0] - nx * hx, p[1] - ny * hx)
    b = (p[0] + nx * hx, p[1] + ny * hx)
    c = (b[0] + out[0] * depth, b[1] + out[1] * depth)
    d = (a[0] + out[0] * depth, a[1] + out[1] * depth)
    from shapely.geometry import Polygon
    return Polygon([a, b, c, d])


def walkable_slab(g):
    """Verified slab minus the verified solids standing on it (cores and non-capsule tubes). Capsule tubes are the openings themselves."""
    solids = [box(*b) for b in g.cores.values()] + [t.outer for k, t in g.tubes.items() if k not in ("capW", "capE")]
    return g.slab.difference(unary_union(solids)) if solids else g.slab


def ray_gap(slab, p, out, limit=30.0):
    """Distance along the outward axis from p to the first walkable verified slab, or None."""
    n = int(limit / STEP)
    for i in range(n + 1):
        q = Point(p[0] + out[0] * i * STEP, p[1] + out[1] * i * STEP)
        if slab.buffer(1e-6).contains(q):
            return round(i * STEP, 2)
    return None


def shift_to_slab(slab, p, out, width):
    """Smallest outward translation t so that the whole landing rectangle lies on verified slab."""
    s = slab.buffer(0.01)
    for i in range(int(MAX_SHIFT / STEP) + 1):
        t = i * STEP
        q = (p[0] + out[0] * t, p[1] + out[1] * t)
        if s.contains(landing_rect(q, out, width)):
            return round(t, 2)
    return None


def d01_rows(out_dir: Path) -> list[dict]:
    rows, decks = [], {}
    for f in SRC.TARGET_FLOORS:
        g = SRC.load_floor(f)
        meta = json.loads(meta_path(out_dir, f).read_text(encoding="utf-8"))
        d01 = {(r["source_id"], r["role"]): r for r in meta["design_proposed"]["decision_refs"].get("D-01", [])}
        cores = {k: box(*b) for k, b in g.cores.items()}
        core_u = unary_union(list(cores.values())) if cores else None
        walk = walkable_slab(g)
        for e in g.esc_ends:
            if e["role"] not in ("board", "arrive") or (e["source_id"], e["role"]) not in d01:
                continue
            p = e["low"] if e["role"] == "board" else e["high"]
            u = e["u"]
            out = (-u[0], -u[1]) if e["role"] == "board" else (u[0], u[1])
            w = e["width"]
            P = Point(p)
            hole = next((h for h in g.holes if h.buffer(0.01).contains(P)), None)
            in_core = core_u is not None and core_u.buffer(0.01).contains(P)
            lies = "core" if in_core else ("slab" if walk.buffer(0.01).contains(P) else ("opening" if hole is not None else "outside_slab_outline"))
            rect = landing_rect(p, out, w)
            gap = ray_gap(walk, p, out)
            strip = None
            if gap is not None:
                strip = LineString([p, (p[0] + out[0] * gap, p[1] + out[1] * gap)]).buffer(w / 2.0, cap_style=2)
            deck = unary_union([rect, strip]) if strip is not None else rect
            deck_new = deck.difference(walk)
            colu = unary_union([Point(c).buffer(SRC.COL_R) for c in g.columns])
            shift = shift_to_slab(walk, p, out, w)
            conflicts = None
            if shift is not None:
                q = (p[0] + out[0] * shift, p[1] + out[1] * shift)
                conflicts = sum(1 for c in g.columns if landing_rect(q, out, w).distance(Point(c)) < SRC.COL_R + 0.62)
            decks.setdefault(f, []).append(deck_new)
            rows.append({
                "id": "D01-%s-%s-%s" % (f, e["label"].replace("→", "to"), e["role"]),
                "floor": f, "escalator": e["label"].replace("→", "-"), "role": e["role"], "side": e["side"], "width_m": w, "escalator_length_m": round(e["length"], 1),
                "end_x_m": round(p[0], 2), "end_y_m": round(p[1], 2), "out_x": round(out[0], 3), "out_y": round(out[1], 3),
                "end_lies_in": lies,
                "opening_area_m2": round(hole.area, 1) if hole is not None else "",
                "gap_to_walkable_slab_along_axis_m": gap if gap is not None else "",
                "gap_to_walkable_slab_euclid_m": round(walk.distance(P), 2),
                "landing_rect_walkable_m2": round(rect.intersection(walk).area, 2),
                "landing_rect_m2": round(rect.area, 2),
                "altA_new_deck_m2": round(deck_new.area, 1),
                "altA_deck_pct_of_opening": round(100.0 * deck_new.area / hole.area, 1) if hole is not None else "",
                "altA_columns_within_deck_m": sum(1 for c in g.columns if deck.distance(Point(c)) < SRC.COL_R),
                "altC_shift_outward_to_slab_m": shift if shift is not None else "",
                "altC_columns_near_shifted_landing": conflicts if conflicts is not None else "",
                "source_id": e["source_id"], "slice_sha256": g.slice_sha256, "method": METHOD})
    for r in rows:                                          # landings of one floor share a capsule end: their decks overlap, so the combined area is smaller than the sum
        r["altA_floor_combined_deck_m2"] = round(unary_union(decks[r["floor"]]).area, 1)
    return rows


def d02_rows(out_dir: Path) -> list[dict]:
    rows = []
    for f in SRC.TARGET_FLOORS:
        meta = json.loads(meta_path(out_dir, f).read_text(encoding="utf-8"))
        for rec in meta["design_proposed"]["decision_refs"].get("D-02", []):
            g = SRC.load_floor(f)
            b = tuple(rec["core_bounds_m"])
            core = box(*b)
            sides = {}
            for name, (dx, dy) in {"S": (0, -1), "N": (0, 1), "W": (-1, 0), "E": (1, 0)}.items():
                if dx == 0:
                    ap = box(b[0], b[1] - LANDING_DEPTH if dy < 0 else b[3], b[2], b[1] if dy < 0 else b[3] + LANDING_DEPTH)
                else:
                    ap = box(b[0] - LANDING_DEPTH if dx < 0 else b[2], b[1], b[0] if dx < 0 else b[2] + LANDING_DEPTH, b[3])
                on = ap.intersection(g.slab).area
                sides[name] = {"apron_m2": round(ap.area, 1), "on_slab_m2": round(on, 2), "on_slab_pct": round(100.0 * on / ap.area, 1)}
            rows.append({"id": "D02-%s-core-%s" % (f, rec["core"]), "floor": f, "core": rec["core"], "bounds_m": list(b), "footprint_m2": round(core.area, 1),
                         "core_on_slab_m2": round(core.intersection(g.slab).area, 2), "nearest_slab_m": round(g.slab.distance(core), 2),
                         "apron_by_side": sides, "slice_sha256": g.slice_sha256, "method": METHOD})
    return rows


def d03_rows(out_dir: Path) -> list[dict]:
    rows = []
    for f in SRC.TARGET_FLOORS:
        meta = json.loads(meta_path(out_dir, f).read_text(encoding="utf-8"))
        g = SRC.load_floor(f)
        core_u = unary_union([box(*b) for b in g.cores.values()]) if g.cores else None
        wc_u = unary_union([box(*b) for b in SY.wc_bounds().values()])
        col_u = unary_union([Point(c).buffer(SRC.COL_R) for c in g.columns]).buffer(0.3)
        for rec in meta["design_proposed"]["decision_refs"].get("D-03", []):
            comps = {"core": core_u, "restroom": wc_u, "column": col_u}
            comps.update({"tube:" + k: x.outer for k, x in g.tubes.items() if k != rec["tube"]})
            tb = g.tubes[rec["tube"]]
            c = (round(tb.center[0], 2), round(tb.center[1], 2))
            r = SY._round_r(tb.r)
            cands = [0, 30, 45, 60, 75, 90] if rec["tube"] == "T3" else [0, -30, -45, -60, -75, -90]
            sweep = {}
            for deg in cands:
                ap = SY.entry_apron(c, r, deg)
                sweep[str(deg)] = {"on_slab_pct": round(100.0 * ap.intersection(g.slab).area / ap.area, 1),
                                   "blocked_by": sorted(k for k, v in comps.items() if v is not None and not v.is_empty and ap.intersection(v).area > 1e-6)}
            rows.append({"id": "D03-%s-%s" % (f, rec["tube"]), "floor": f, "tube": rec["tube"], "centre_m": list(c), "tube_radius_m": r, "proposed_turn_deg": rec["turn_deg"],
                         "unrotated_apron_on_slab_pct": sweep["0"]["on_slab_pct"], "unrotated_blocked_by": sweep["0"]["blocked_by"],
                         "proposed_apron_on_slab_pct": sweep[str(int(rec["turn_deg"]))]["on_slab_pct"], "proposed_blocked_by": sweep[str(int(rec["turn_deg"]))]["blocked_by"],
                         "sweep": sweep, "slice_sha256": g.slice_sha256, "method": METHOD,
                         "note": "apron = %.1f x %.1f m in front of the entry (builder value); blocked_by uses the builder's blocked set (cores, restrooms, columns +0.3 m, other tubes); door clear opening, lobby threshold and tube interior conflicts are NOT measured here" % (2.6, 2.6)})
    return rows


def write_csv(path: Path, rows: list[dict], skip=()):
    cols = [k for k in rows[0] if k not in skip]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v) for k, v in r.items() if k in cols})


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ROOT / "docs" / "t14t_audit_r1" / "measurements"))
    ap.add_argument("--metadata", default=str(ROOT / "outputs" / "T14T"), help="folder with the C-T14T per-floor metadata (read only)")
    a = ap.parse_args(argv)
    outdir = Path(a.out)
    outdir.mkdir(parents=True, exist_ok=True)
    mdir = Path(a.metadata)
    d01, d02, d03 = d01_rows(mdir), d02_rows(mdir), d03_rows(mdir)
    write_csv(outdir / "d01_escalator_landings.csv", d01)
    write_csv(outdir / "d02_cores_without_slab.csv", d02, skip=("apron_by_side",))
    write_csv(outdir / "d03_lift_entry_rotations.csv", d03, skip=("sweep",))
    doc = {"schema": "C-T14T-AUDIT-MEASUREMENTS-1.0", "method": METHOD,
           "parameters": {"landing_depth_m": LANDING_DEPTH, "entry_apron_m": 2.6, "deck_width": "escalator width from the model", "column_radius_m": SRC.COL_R, "search_step_m": STEP, "max_shift_m": MAX_SHIFT},
           "source_geometry": SRC.verify_sources(), "d01": d01, "d02": d02, "d03": d03}
    (outdir / "measurements.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("D-01 landings: %d | D-02 cores: %d | D-03 rotations: %d | source geometry unchanged: %s" % (len(d01), len(d02), len(d03), doc["source_geometry"]["ok"]))
    print("written:", outdir.resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())

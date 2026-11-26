# -*- coding: utf-8 -*-
"""Run: python -I -X utf8 tools/r10b/test_fitout_r10b.py   (exit code != 0 on any hard violation or if PR was mutated)

Loads the 2F PR plan, hashes it BEFORE and AFTER develop_fitout (room polygon WKT + per-layer item counts + every item's WKT),
runs the checks, prints a summary and writes a preview PNG (PR items gray, new items dark teal, 110 dpi) to the scratch dir.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for p in (str(HERE), str(ROOT / "src"), str(ROOT / "engine")):
    if p not in sys.path:
        sys.path.insert(0, p)

SCRATCH = Path(r"D:\Temp\claude\D--Users-admin-Desktop-2-----\331dbb83-783e-4e46-aa6c-a9c67d371b45\scratchpad\fitout")

from t14s.planner import plan_floor
from t14s.source import load_floor

import fitout_r10b as F
import fitout_checks_r10b as C


def snapshot(PR):
    rooms = [(r["id"], r["poly"].wkt) for r in PR.rooms]
    layers = {}
    for it in PR.items:
        layers[it.layer] = layers.get(it.layer, 0) + 1
    h_rooms = hashlib.sha256("\n".join("%s|%s" % x for x in rooms).encode("utf-8")).hexdigest()
    h_items = hashlib.sha256("\n".join("%s|%s|%s" % (it.layer, it.ref, it.geom.wkt) for it in PR.items).encode("utf-8")).hexdigest()
    return {"n_rooms": len(rooms), "room_wkt_sha256": h_rooms, "items_wkt_sha256": h_items, "layer_counts": dict(sorted(layers.items()))}


def preview(PR, items, path, dpi=110):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager as fm
    fm.fontManager.addfont("C:/Windows/Fonts/malgun.ttf")
    plt.rcParams["font.family"] = "Malgun Gothic"
    plt.rcParams["axes.unicode_minus"] = False
    teal, fill = "#0b4f5c", "#cfe8ec"
    fig, ax = plt.subplots(figsize=(14, 14))
    for it in PR.items:
        if it.layer in ("A-ANNO-DIMS", "A-ANNO-TAGS", "A-GRID", "A-ZONE", "A-FLOR-HATCH", "A-STAR-PROJ", "A-ANNO-SYMB"):
            continue
        for g in F._flat(it.geom):
            if g.geom_type == "Polygon":
                ax.plot(*g.exterior.xy, color="#9a9a9a", lw=0.5)
            elif g.geom_type == "LineString":
                ax.plot(*g.xy, color="#9a9a9a", lw=0.5)
    for it in items:
        for g in F._flat(it.geom):
            if g.geom_type != "Polygon":
                continue
            if it.draw == "dashed":
                ax.plot(*g.exterior.xy, color=teal, lw=0.8, ls="--")
            else:
                ax.fill(*g.exterior.xy, color=fill, ec=teal, lw=0.5)
    for r in PR.rooms:
        c = r["poly"].representative_point() if r["kind"] != "hall" else None
        if c is not None and r["kind"] in ("unit", "support"):
            ax.text(c.x, c.y, "2-" + r["id"], fontsize=6, color="#555555", ha="center", va="center")
    ax.set_aspect("equal")
    ax.set_xlim(-10, 46)
    ax.set_ylim(-19, 37)
    ax.set_title("2F A-201 fit-out development layer (FIT_OUT_DEVELOPMENT, not verified): new items dark teal", fontsize=10)
    SCRATCH.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi)
    plt.close(fig)


def main():
    t0 = time.time()
    PR = plan_floor("2F", seed=7)
    G = load_floor("2F")
    before = snapshot(PR)
    items = F.develop_fitout(PR, G)
    after = snapshot(PR)
    mutated = before != after
    print("PR snapshot BEFORE:", json.dumps(before, ensure_ascii=False))
    print("PR snapshot AFTER :", json.dumps(after, ensure_ascii=False))
    print("PR unchanged (rooms WKT sha256, all item WKT sha256, layer counts):", not mutated)
    print("  rooms sha256 :", before["room_wkt_sha256"])
    print("  items sha256 :", before["items_wkt_sha256"])
    rep = C.check_fitout(PR, G, items)
    print("\nfit-out items: %d   seats total: %d   develop+check %.1f s" % (len(items), rep["seats_total"], time.time() - t0))
    print("%-6s %-4s %-6s %-8s  %s" % ("room", "n", "seats", "m2/seat", "kinds"))
    for rid, d in sorted(rep["per_room"].items()):
        print("%-6s %-4d %-6d %-8s  %s" % (rid, d["items"], d["seats"], d["m2_per_seat"], json.dumps(d["by_kind"], ensure_ascii=False)))
    print("\nviolation counts:", json.dumps(rep["violation_counts"]))
    for k, v in rep["violations"].items():
        for x in v[:5]:
            print("  VIOLATION", k, json.dumps(x, ensure_ascii=False))
    fc = rep["f_hall_circulation"]
    print("\nhall circulation: min main-corridor clear width with fit-out %.2f m, PR only %.2f m; new items push width below 3 m at %d samples; floor >=1.2 m from furniture: %.3f (PR only %.3f)" % (
        fc["min_main_corridor_width_with_fitout_m"], fc["min_main_corridor_width_pr_only_m"], fc["samples_where_new_items_push_width_below_3m"],
        fc["floor_fraction_ge_1.2m_from_furniture_with_fitout"], fc["floor_fraction_ge_1.2m_from_furniture_pr_only"]))
    for x in fc["per_main_line"]:
        print("   line %d  %.1f m  min width PR-only %s  with fit-out %s  samples<3m %d" % (x["line"], x["length_m"], x["min_width_pr_only_m"], x["min_width_with_fitout_m"], x["samples_below_3m_with_fitout"]))
    print("\nrestrooms (existing items only, nothing added: %d new items):" % rep["g_restrooms"]["new_items_in_restrooms"])
    for rid, r in rep["g_restrooms"]["rooms"].items():
        for d in r["doors"]:
            print("  %s %s door '%s': clear depth inside %.2f m (>=1.2: %s), first obstacle: %s" % (rid, r["name"], d["door_ref"], d["clear_depth_inside_m"], d["ok_ge_1.2m"], d["first_obstacle"]))
        for c in r["cubicles"]:
            print("  %s cubicle %s: %s" % (rid, c["fixture"], c.get("size_m", c.get("status"))), "need", c["need_m"], "ok" if c.get("ok") else "")
    print("\ndropped candidates (%d):" % len(items.dropped))
    for d in items.dropped:
        print("  %s %s: %s" % (d["room"], d["kind"], d["reason"]))
    print("\ninfo:", json.dumps({k: v for k, v in items.info.items() if k not in ("lanes",)}, ensure_ascii=False, default=str)[:1500])
    out_json = SCRATCH / "fitout_report.json"
    SCRATCH.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps({"checks": rep, "dropped": items.dropped, "info": {k: v for k, v in items.info.items() if k != "lanes"},
                                    "pr_snapshot": before}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    png = SCRATCH / "fitout_preview_2F.png"
    preview(PR, items, png)
    print("\nwrote", os.path.abspath(out_json))
    print("wrote", os.path.abspath(png))
    bad = mutated or rep["n_violations"] > 0
    print("RESULT:", "FAIL" if bad else "PASS (0 hard violations, PR not mutated)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

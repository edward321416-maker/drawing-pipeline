"""Reproduce the R10-A A-A section cut (X = -4.200 m) from the GLB and compare with R10-A's record.

Usage:  python -I -X utf8 tools/r10b/validate_cut_vs_r10a.py
Prints absolute paths of everything it reads (project rule 0.3).
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glb_section as gs  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
R10A = os.path.join(ROOT, "review", "wp0_r10_a", "validation", "R10A_GEOMETRY.json")
print("GLB     :", os.path.abspath(gs.GLB_PATH))
print("R10-A   :", os.path.abspath(R10A))

with open(R10A, encoding="utf-8") as fh:
    rec = json.load(fh)["sheets"]["A-301"]
recorded = {c["name"]: c for c in rec["original_cuts"]}
print("recorded cuts:", len(recorded), " axis:", rec["cut_axis"], rec["value"])

t0 = time.time()
scene = gs.load_scene(verify_hash=True)
print(f"scene loaded in {time.time() - t0:.1f}s; GLB sha256 verified = {gs.GLB_SHA256[:16]}...")
t0 = time.time()
cut = gs.cut_at_x(scene, rec["value"])
print(f"cut computed in {time.time() - t0:.1f}s: intersected={len(cut.items)} untouched={len(cut.skipped)}")

mine = {i.node: i for i in cut.items}
tol = 0.02  # 20 mm: R10-A rounded to 0.1 mm but may have welded/simplified differently
rows, ok, bad = [], 0, []
for name, c in sorted(recorded.items()):
    if name not in mine:
        bad.append((name, "NOT CUT BY MY PLANE", c["section_bounds"], None))
        continue
    b = mine[name].bounds_hv
    d = max(abs(x - y) for x, y in zip(b, c["section_bounds"]))
    (ok := ok + 1) if d <= tol else bad.append((name, f"max dev {d:.4f} m", c["section_bounds"], b))
extra = sorted(set(mine) - set(recorded))
print(f"MATCH within {tol*1000:.0f} mm: {ok}/{len(recorded)}")
for n, why, rb, mb in bad:
    print("  MISMATCH", n, "|", why, "| R10-A", rb, "| mine", mb)
print(f"cut by me but absent from R10-A record: {len(extra)}")
for n in extra[:40]:
    i = mine[n]
    print("   +", n[:42], i.kind, i.bounds_hv, "closed" if i.watertight else "open-lines")

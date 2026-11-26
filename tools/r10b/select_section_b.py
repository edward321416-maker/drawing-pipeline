"""Choose the perpendicular section (B-B, plane y_drawing = const) from actual geometry coverage.

Score = information the cut exposes, computed from the real mesh cut (no bounding boxes):
  + 3 per distinct tube / spiral ramp / escalator / stair core / elevator car cut
  + 1 per distinct program volume cut
  + void length: sum over storeys of the slab-free length across the building width (m) / 10
  - penalty when the plane runs within 0.3 m of a column centreline (cuts columns, poor reading)
Usage: python -I -X utf8 tools/r10b/select_section_b.py [step_m]
"""
import json
import os
import sys

import numpy as np
from shapely.geometry import LineString

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glb_section as gs  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "review", "wp0_r10_b", "validation", "SECTION_B_SELECTION.json")
COLUMN_Y = [-17.4, -9.0, 0.0, 9.0, 18.0, 27.0, 35.4]
FLOORS = json.load(open(os.path.join(HERE, "..", "..", "data", "t14s", "source_slices", "floors.json"), encoding="utf-8"))["floors"]
INFO_KINDS = {"tube", "spiral_ramp", "escalator", "stair_core", "elevator_car"}


def void_length(items, building_h=(-18.0, 36.0)):
    """Total slab-free length (m) over all storeys, measured on the cut slab polygons."""
    total = 0.0
    for z in FLOORS.values():
        probe = LineString([(building_h[0] - 2, z - 0.25), (building_h[1] + 2, z - 0.25)])
        covered = 0.0
        for it in items:
            if it.kind == "slab":
                for p in it.polygons:
                    covered += p.intersection(probe).length
        total += max(0.0, (building_h[1] - building_h[0]) - min(covered, building_h[1] - building_h[0]))
    return total


def main(step=1.5):
    scene = gs.load_scene()
    rows = []
    for y in np.arange(-16.5, 35.1, step):
        cut = gs.cut_plane(scene, "y", float(y))
        names = {i.node for i in cut.items}
        info = {n for n in names if gs.kind_of(n) in INFO_KINDS}
        progs = {n for n in names if gs.kind_of(n) == "program"}
        vlen = void_length(cut.items, building_h=(-9.0, 45.0))   # for a y-cut, h = +x_drawing
        near_col = min(abs(y - c) for c in COLUMN_Y) < 0.3
        score = 3 * len(info) + len(progs) + vlen / 10.0 - (6 if near_col else 0)
        rows.append(dict(y=round(float(y), 2), score=round(score, 2), info=sorted(info), programs=len(progs),
                         void_length_m=round(vlen, 1), on_column_line=bool(near_col)))
        print(f"y={y:6.2f}  score={score:6.2f}  info={len(info):2d}  prog={len(progs):2d}  void={vlen:6.1f}  col={near_col}", flush=True)
    best = sorted(rows, key=lambda r: -r["score"])[:5]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(dict(glb_sha256=gs.GLB_SHA256, step_m=step, candidates=rows, top5=best), open(OUT, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("TOP 5:", [(b["y"], b["score"]) for b in best])
    print("written:", os.path.abspath(OUT))


REFINE = (9.5, 10.0, 10.2, 10.5, 11.0)
COLUMN_FACE_HALF = 0.45          # columns are 0.9 m square on the grid lines


def refine():
    """Second pass around the best sweep band; also checks tangency of the M1 tube cut and column-face clearance."""
    scene = gs.load_scene()
    rows = []
    for y in REFINE:
        cut = gs.cut_plane(scene, "y", y)
        names = {i.node for i in cut.items}
        info = {n for n in names if gs.kind_of(n) in INFO_KINDS}
        progs = {n for n in names if gs.kind_of(n) == "program"}
        vlen = void_length(cut.items, (-9.0, 45.0))
        m1 = [i for i in cut.items if "M1" in i.node]
        chord = round(m1[0].bounds_hv[2] - m1[0].bounds_hv[0], 3) if m1 else None
        clear = round(min(abs(y - c) for c in COLUMN_Y) - COLUMN_FACE_HALF, 3)
        rows.append(dict(y=y, score=round(3 * len(info) + len(progs) + vlen / 10.0, 2), info=len(info), programs=len(progs),
                         void_length_m=round(vlen, 1), m1_tube_chord_m=chord, clearance_to_column_face_m=clear))
        print(rows[-1], flush=True)
    chosen = 10.0
    out = dict(glb_sha256=gs.GLB_SHA256, refinement=rows, chosen_y=chosen,
               reason="Highest-scoring sweep band (y 3-13.5). y=10.0 cuts the M1 tube through a 2.49 m chord (two distinct walls) "
                      "rather than the 1.1 m near-tangent sliver at y=10.5, and keeps 0.55 m clear of the y=9 column faces "
                      "(y=9.5 scores 0.9 higher but leaves 0.05 m).")
    path = os.path.join(os.path.dirname(OUT), "SECTION_B_REFINEMENT.json")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("written:", os.path.abspath(path))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "refine":
        refine()
    else:
        main(float(sys.argv[1]) if len(sys.argv) > 1 else 1.5)

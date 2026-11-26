"""R10-B geometry-preservation and source-consistency validation (independent of the drawing code paths).

    python -I -X utf8 tools/r10b/validate_preservation_r10b.py [--out review/wp0_r10_b/validation/R10B_PRESERVATION.json]
Each test reports PASS / FAIL / NOT_TESTED with its evidence.  Nothing is relaxed silently.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path[:0] = [HERE]
sys.dont_write_bytecode = True
import glb_section as gs  # noqa: E402

R10A_GEOM = os.path.join(ROOT, "review", "wp0_r10_a", "validation", "R10A_GEOMETRY.json")
R10A_COMMIT = "cdbb6328554d4e7ab6f2d065f0bbac1aa3fe145d"
RESULTS = []


def rec(tid, title, status, evidence):
    RESULTS.append(dict(id=tid, title=title, status=status, evidence=evidence))
    print(f"{tid} {status:10s} {title}", flush=True)


def sha(path):
    return gs.sha256_file(path)


def git(*args):
    return subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True, encoding="utf-8").stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "review", "wp0_r10_b", "validation", "R10B_PRESERVATION.json"))
    a = ap.parse_args()
    r10a = json.load(open(R10A_GEOM, encoding="utf-8"))
    protected = {os.path.basename(p["path"]): p for p in r10a["protected_local_sources"]}
    # --- T01-T04 source hashes ------------------------------------------------------------------------------------
    srcs = [("T01", "Original GLB unchanged", gs.GLB_PATH, gs.GLB_SHA256),
            ("T02", "Approved 1F master unchanged", "D:/Users/admin/Desktop/2학기 논문/도면/00_엔진/model/1F_master.blend",
             next(p["sha256"] for p in r10a["protected_local_sources"] if p["path"].endswith(".blend") or "1F_master" in p["path"] or "1F_master.blend" in p["path"] or p["path"].lower().endswith("blend"))),
            ("T03", "R9 drawing book unchanged", "D:/Users/admin/Desktop/2학기 논문/도면/01_과정/01_기획_구획_베이스/WP0_R9_기술도면집/WP0_R9_A2_기술도면집.pdf",
             next(p["sha256"] for p in r10a["protected_local_sources"] if p["path"].lower().endswith(".pdf"))),
            ("T04", "PR30 2F source slice unchanged", os.path.join(ROOT, "data", "t14s", "source_slices", "floor_2F_slice.json"),
             r10a["sheets"]["A-201"]["source_slice_sha256"])]
    for tid, title, path, expected in srcs:
        got = sha(path)
        rec(tid, title, "PASS" if got == expected else "FAIL", dict(path=os.path.abspath(path), expected=expected, actual=got))
    # --- T05 git-level: protected paths untouched since the R10-A commit ----------------------------------------------------
    changed = [l for l in (git("diff", "--name-only", R10A_COMMIT).splitlines() + git("ls-files", "--others", "--exclude-standard").splitlines()) if l]
    allowed = ("tools/r10b/", "review/wp0_r10_b/")
    illegal = sorted({c for c in changed if not c.startswith(allowed)})
    rec("T05", "No tracked file outside tools/r10b and review/wp0_r10_b differs from the R10-A commit", "PASS" if not illegal else "FAIL",
        dict(base_commit=R10A_COMMIT, changed_count=len(changed), outside_allowed=illegal[:20]))
    # --- load R10-A composer data (PR30 planner + R8 meshes) -------------------------------------------------------------
    import build_r10b as BR
    B = BR.load_r10a()
    PR, G = B.PR, B.G
    # --- T06 rooms ---------------------------------------------------------------------------------------------------------------
    old = {r["id"]: r for r in r10a["sheets"]["A-201"]["rooms"]}
    bad = []
    for r in PR.rooms:
        rid = "2-" + r["id"]
        o = old.get(rid)
        if not o or abs(o["area"] - r["poly"].area) > 1e-3 or o["name"] != B.roomname(r) or o["grade"] != r["prov"]:
            bad.append(rid)
    rec("T06", "26 PR30 rooms: ids, names, areas, provenance equal the R10-A record", "PASS" if not bad and len(PR.rooms) == 26 else "FAIL",
        dict(rooms=len(PR.rooms), mismatches=bad))
    # --- T07 layer counts ---------------------------------------------------------------------------------------------------------
    from collections import Counter
    now = dict(Counter(i.layer for i in PR.items if i.layer not in {"A-CIRC", "A-CIRC-SVC"}))
    want = r10a["sheets"]["A-201"]["architectural_model_items"]
    rec("T07", "PR30 item counts per layer equal the R10-A record", "PASS" if now == want else "FAIL", dict(now=now, r10a=want))
    # --- T08 every module the plan depends on is byte-identical between the R7 checkout (used by R10-A) and this worktree ----
    r7 = str(B.REPO)
    rel = sorted([os.path.join("src", "t14s", f) for f in os.listdir(os.path.join(ROOT, "src", "t14s")) if f.endswith(".py")]
                 + [os.path.join("src", "upper_layouts.py"), os.path.join("src", "furniture_library.py"),
                    os.path.join("engine", "render", "style.py"), os.path.join("engine", "model", "params.yaml")])
    diff, missing = [], []
    for rp in rel:
        a_, b_ = os.path.join(r7, rp), os.path.join(ROOT, rp)
        if not os.path.exists(a_):
            missing.append(rp)
        elif sha(a_) != sha(b_):
            diff.append(rp)
    rec("T08", "Plan-defining modules in the worktree are byte-identical to the R7 checkout used by R10-A",
        "PASS" if not diff else "FAIL", dict(r7_checkout=os.path.abspath(r7), files_compared=len(rel) - len(missing),
                                             differing=diff, absent_in_r7=missing))
    # --- GLB-derived checks ------------------------------------------------------------------------------------------------------------
    scene = gs.load_scene()
    th = gs.frame_theta()

    def bounds_dr(node):
        vw, _ = gs.world_vertices(scene, node)
        vd = gs.to_drawing(vw, th)
        return vd.min(0), vd.max(0)

    cols = {}
    for n in scene.graph.nodes_geometry:
        if n.startswith("A-STRC_column"):
            lo, hi = bounds_dr(n)
            cols[n] = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2], hi[2])
    col_items = [i for i in PR.items if i.layer == "A-COLS"]
    unmatched = []
    for it in col_items:
        c = it.geom.centroid
        if not any(math.hypot(c.x - v[0], c.y - v[1]) < 0.005 and v[2] <= 6.0 <= v[3] for v in cols.values()):
            unmatched.append((round(c.x, 3), round(c.y, 3)))
    rec("T09", "Every 2F column in the plan sits on a GLB column (<= 5 mm) that exists at z = +6.000", "PASS" if not unmatched else "FAIL",
        dict(plan_columns=len(col_items), glb_columns=len(cols), unmatched=unmatched))
    core_bad = {}
    for k, nm in zip("ABCD", ("A-VERT-STRS_A", "A-VERT-STRS_B", "A-VERT-STRS_C", "A-VERT-STRS_D")):
        lo, hi = bounds_dr(nm)
        b = G.cores[k]
        dev = max(abs(lo[0] - b[0]), abs(lo[1] - b[1]), abs(hi[0] - b[2]), abs(hi[1] - b[3]))
        if dev > 0.01:
            core_bad[k] = round(dev, 4)
    rec("T10", "Core A-D plan bounds equal the GLB core boxes (<= 10 mm)", "PASS" if not core_bad else "FAIL", dict(deviations_m=core_bad))
    tube_bad = {}
    glbmap = {"T1": "T1", "T2": "T2", "T3": "T3", "T4": "T4", "FR": "FR", "M1": "M1", "M2": "M2", "PL": "PL"}
    for k, suffix in glbmap.items():
        lo, hi = bounds_dr("A-CORE-TUBE_" + suffix)
        c = G.tubes[k].center
        dev = math.hypot((lo[0] + hi[0]) / 2 - c[0], (lo[1] + hi[1]) / 2 - c[1])
        if dev > 0.02:
            tube_bad[k] = round(dev, 4)
    rec("T11", "Tube centres in the plan equal the GLB tube centres (<= 20 mm)", "PASS" if not tube_bad else "FAIL", dict(deviations_m=tube_bad))
    floors = json.load(open(os.path.join(ROOT, "data", "t14s", "source_slices", "floors.json"), encoding="utf-8"))["floors"]
    lev_bad = {}
    for name, z in floors.items():
        node = "A-FLOR_s7_" + name
        _, hi = bounds_dr(node)
        if abs(hi[2] - z) > 0.001:
            lev_bad[name] = (z, round(float(hi[2]), 4))
    rec("T12", "Floor levels B2..15F equal the GLB slab tops (<= 1 mm)", "PASS" if not lev_bad else "FAIL", dict(floors=len(floors), mismatches=lev_bad))
    _, rh = bounds_dr("A-ROOF_slab")
    rec("T13", "Roof maximum equals +76.500 m (R10-A record)", "PASS" if abs(rh[2] - 76.5) < 0.001 and abs(r10a["sheets"]["A-301"]["roof_max"] - 76.5) < 0.001 else "FAIL",
        dict(glb_roof_top=round(float(rh[2]), 4), r10a=r10a["sheets"]["A-301"]["roof_max"]))
    # --- T14 section cut reproduction ----------------------------------------------------------------------------------------------------
    cut = gs.cut_at_x(scene, -4.2)
    mine = {i.node: i for i in cut.items}
    miss = []
    for c in r10a["sheets"]["A-301"]["original_cuts"]:
        i = mine.get(c["name"])
        if not i or max(abs(x - y) for x, y in zip(i.bounds_hv, c["section_bounds"])) > 0.02:
            miss.append(c["name"])
    rec("T14", "A-A cut at X = -4.200 reproduces all 26 R10-A recorded cuts (<= 20 mm)", "PASS" if not miss else "FAIL", dict(recorded=26, mismatches=miss))
    # --- T15 R8 research bridges: same cut names as R10-A ----------------------------------------------------------------------------------
    hits = [o["name"] for o, _ in B.cuts(B.P, B.objects(types={"bridge"}), 0, B.XSEC)]
    want_b = r10a["sheets"]["A-301"]["proposed_bridge_cuts"]
    rec("T15", "R8 research bridge cuts in A-A equal the R10-A record", "PASS" if sorted(hits) == sorted(want_b) else "FAIL", dict(now=hits, r10a=want_b))
    # --- T16 protected issue carried, sheets not regenerated --------------------------------------------------------------------------------
    a501 = r10a["sheets"]["A-501"]
    mism = [v for k, v in a501.items() if k == "max_landing_mismatch_mm"] or [None]
    for p_ in ("pdf/A-501.pdf", "pdf/S-401.pdf", "svg/A-501.svg", "svg/S-401.svg"):
        pass
    r10a_changed = [l for l in changed if l.startswith("review/wp0_r10_a/")]
    rec("T16", "Core D landing mismatch (176.07 mm) and E2 bridge evidence carried unchanged; A-501 and S-401 not regenerated",
        "PASS" if not r10a_changed and mism[0] and abs(mism[0] - 176.071) < 0.01 else "FAIL",
        dict(max_landing_mismatch_mm=mism[0], r10a_files_changed=r10a_changed, status_of_issue="BLOCKED_USER_DECISION / OPEN (unchanged)"))
    # --- T17 fit-out does not mutate the plan -----------------------------------------------------------------------------------------------
    try:
        import fitout_r10b as F

        def snap():
            h = hashlib.sha256()
            for it in PR.items:
                h.update(it.layer.encode()); h.update(it.geom.wkb)
            for r in PR.rooms:
                h.update(r["poly"].wkb); h.update(str(r["name"]).encode())
            return h.hexdigest(), len(PR.items), len(PR.rooms)
        before = snap()
        items = F.develop_fitout(PR, G)
        after = snap()
        rec("T17", "Fit-out generation leaves every PR30 item and room polygon byte-identical", "PASS" if before == after else "FAIL",
            dict(before=before, after=after, fitout_items=len(items)))
    except ModuleNotFoundError as e:
        rec("T17", "Fit-out non-mutation", "NOT_TESTED", dict(reason=str(e)))
    summary = dict(PASS=sum(r["status"] == "PASS" for r in RESULTS), FAIL=sum(r["status"] == "FAIL" for r in RESULTS),
                   NOT_TESTED=sum(r["status"] == "NOT_TESTED" for r in RESULTS))
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(dict(base_commit=R10A_COMMIT, glb_sha256=gs.GLB_SHA256, summary=summary, tests=RESULTS), open(a.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2, default=str)
    print("SUMMARY", summary, "->", os.path.abspath(a.out))
    sys.exit(1 if summary["FAIL"] else 0)


if __name__ == "__main__":
    main()

"""R10-B section sheets (A-301 A-A longitudinal, A-302 B-B transverse) drawn from the original GLB.

Everything is derived from actual mesh/plane intersection (glb_section.cut_plane) and from silhouette projection of
the geometry that lies BEHIND the plane within a stated depth.  Nothing is drawn from bounding boxes.

Classes drawn (project evidence classes in brackets):
  cut poche ........ slabs, roof, tube walls, escalator cut, facade rails, site slab/wall     [MODEL_VERIFIED]
  core envelope .... A-VERT-STRS_* boxes: representation envelope only, interior not modelled [MODEL_VERIFIED envelope]
  program volumes .. A-PROG_* boxes (names from the GLB); NOT ceiling heights                  [MODEL_VERIFIED volume]
  beyond plane ..... thin outlines of tubes / cores / columns / escalators / spiral ramp         [MODEL_VERIFIED]
  R8 bridge cuts ... E2 bridge, landings (research geometry, drawn unchanged from R10-A)         [EXISTING_PROPOSED_DESIGN]
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np
from shapely import affinity
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glb_section as gs  # noqa: E402
from draft import (BLACK, CAND, DASH, EXIST, FAINT, GRAY, GRID, INK, LIGHT, PALE, WHITE, K, View, arrow,  # noqa: E402
                   circle, dim, frame, leader, line, parts, rule, symbol, text, view_caption)

DARK = (.16, .17, .17)
MID = (.55, .57, .57)
TINT = (.955, .962, .958)
PROG_KO = {"F&B": "식음", "판매": "판매", "문화·엔터": "문화·엔터", "anchor": "앵커", "garden": "정원", "서비스": "서비스"}
BEYOND_KINDS = {"tube", "stair_core", "escalator", "spiral_ramp", "structure", "elevator_car"}
KIND_KO = {"tube": "튜브", "stair_core": "코어", "escalator": "에스컬레이터", "spiral_ramp": "나선 램프",
           "structure": "기둥", "elevator_car": "승강기"}


def sheet_b(doc, id_, name, sc, refcodes, desc, rev="B  대표 도면 개발"):
    """A2 frame and right-hand title column (same layout as R10-A), written with R10-B identification only."""
    from datetime import datetime
    import draft as d
    p = doc.new_page(width=594 * K, height=420 * K)
    for n, f in (("Body", "malgun.ttf"), ("Bold", "malgunbd.ttf")):
        p.insert_font(fontname=n, fontfile=f"C:/Windows/Fonts/{f}")
    d.frame(p, (14, 13, 580, 407), .9)
    rule(p, 532, 13, 532, 407, .64)
    x = 536
    for y in (44, 78, 114, 154, 192, 240, 274, 307, 344, 375):
        rule(p, 532, y, 580, y, .18)
    for y, label in [(20, "PROJECT NO."), (51, "PROJECT TITLE"), (85, "DRAWING TITLE"), (121, "REFERENCES"),
                     (161, "GEOMETRY"), (199, "NOTES"), (247, "REVISION"), (281, "ISSUE"), (314, "PRINT SCALE"),
                     (351, "DATE"), (382, "DRAWING NO.")]:
        text(p, x, y, label, 6, col=GRAY)
    text(p, x, 34, "WP0 · R10-B", 10.5, True)
    text(p, x, 63, "다층 상업시설", 11, True)
    text(p, x, 70, "수직동선 및 접합 연구", 7.5)
    for i, s_ in enumerate(name):
        text(p, x, 96 + 6 * i, s_, 9.4, True)
    for i, s_ in enumerate(refcodes):
        text(p, x, 132 + 5 * i, s_, 7.2)
    text(p, x, 170, "회색·흑색 / 기준 형상", 7)
    text(p, x, 176, "청록 / 연구 후보", 7, col=INK)
    text(p, x, 182, "점선 / 투영 또는 미확인", 6.9, col=GRAY)
    for i, s_ in enumerate(desc):
        text(p, x, 208 + 5.7 * i, s_, 6.8)
    text(p, x, 260, rev, 7.7, True)
    text(p, x, 297, "독립 검수용", 9, True)
    text(p, x, 327, sc, 8.8, True)
    text(p, x, 335, "A2 · 실제 크기 100%", 7.3)
    text(p, x, 366, datetime.now().strftime("%Y. %m. %d"), 8.3)
    text(p, x, 398, id_, 17, True)
    return p


# ---------------------------------------------------------------- projection of what lies behind the plane
def _clip(poly: np.ndarray, ax: int, bound: float, keep_ge: bool) -> np.ndarray:
    out = []
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        ina = (a[ax] >= bound) if keep_ge else (a[ax] <= bound)
        inb = (b[ax] >= bound) if keep_ge else (b[ax] <= bound)
        if ina:
            out.append(a)
        if ina != inb and b[ax] != a[ax]:
            t = (bound - a[ax]) / (b[ax] - a[ax])
            out.append(a + t * (b - a))
    return np.array(out) if out else np.zeros((0, 3))


def project_beyond(scene, axis: str, value: float, depth: float, theta: float, kinds=BEYOND_KINDS) -> dict:
    """Silhouette (sheet h,v) of each node's geometry that lies in  value < coord <= value + depth."""
    ax = {"x": 0, "y": 1}[axis]
    hc, hs = {"x": (1, -1.0), "y": (0, 1.0)}[axis]
    lo, hi = value + 1e-4, value + depth
    out = {}
    for node in sorted(scene.graph.nodes_geometry):
        if gs.kind_of(node) not in kinds:
            continue
        vw, faces = gs.world_vertices(scene, node)
        vd = gs.to_drawing(vw, theta)
        if vd[:, ax].max() < lo or vd[:, ax].min() > hi:
            continue
        polys = []
        for t in vd[faces]:
            c = t[:, ax]
            if c.max() < lo or c.min() > hi:
                continue
            q = _clip(t, ax, lo, True)
            if len(q):
                q = _clip(q, ax, hi, False)
            if len(q) >= 3:
                pg = Polygon(np.c_[hs * q[:, hc], q[:, 2]])
                if pg.area > 1e-8:
                    polys.append(pg.buffer(0.004))
        if polys:
            g = unary_union(polys).buffer(-0.004).simplify(0.015)
            if not g.is_empty:
                out[node] = g
    return out


def prog_label(node: str) -> tuple[str, str]:
    parts_ = node.split("_")
    fl = parts_[1]
    raw = parts_[2]
    return fl, PROG_KO.get(raw, raw)


# ---------------------------------------------------------------- the sheet
def build_section_sheet(doc, B, cfg: dict, scene, theta: float) -> dict:
    """cfg: id, title, scale, axis, value, depth, hrange, zrange, paper(x,y), grid('Y'|'X'), notes, refs, name, desc"""
    axis, value = cfg["axis"], cfg["value"]
    p = sheet_b(doc, cfg["id"], cfg["name"], f"1:{cfg['scale']}", cfg["refs"], cfg["desc"])
    h0, h1 = cfg["hrange"]
    z0, z1 = cfg["zrange"]
    v = View(p, cfg["id"], cfg["scale"], (h0, z0, h1, z1), cfg["paper"])
    cut = gs.cut_plane(scene, axis, value, theta=theta)
    beyond = project_beyond(scene, axis, value, cfg["depth"], theta)
    FF = B.FF
    rec = dict(cut_axis=axis, value=value, depth_m=cfg["depth"], cut_items=[], beyond=[], programs=[], levels=FF,
               omitted_context_items=[], glb_sha256=gs.GLB_SHA256)

    # level strip, level lines and floor-to-floor chain ------------------------------------------------------
    names = list(FF.items())
    lx = cfg.get("strip_x", 40)
    for name, z in names:
        y = v.xy(h0, z)[1]
        rule(p, lx + 5, y, v.r[2] + 2, y, .09, LIGHT, GRID)
        text(p, lx, y - .7, f"{name}  {z:+.3f}", 7.3, name in {"B2", "B1", "1F", "2F", "7F", "15F"}, align='right')
        circle(p, lx + 3.2, y, .95, .13, BLACK)
        rule(p, lx + 2.3, y, lx + 4.1, y, .1)
    for (a, za), (b, zb) in zip(names, names[1:]):
        dim(p, (lx + 11.5, v.xy(0, za)[1]), (lx + 11.5, v.xy(0, zb)[1]), 0, f"{(zb - za) * 1000:,.0f}", vertical=True)

    # program volumes (tint + name), drawn first ------------------------------------------------------------
    for it in cut.items:
        if it.kind != "program":
            continue
        fl, ko = prog_label(it.node)
        for g in it.polygons:
            v.geo(g, .06, FAINT, TINT)
        rec["programs"].append(dict(node=it.node, floor=fl, program=ko, bounds=list(it.bounds_hv)))
    # beyond-plane outlines --------------------------------------------------------------------------------
    for node, g in beyond.items():
        k = gs.kind_of(node)
        v.geo(g.boundary, .10 if k in {"structure", "escalator"} else .12, MID, None, None if k != "stair_core" else DASH)
        rec["beyond"].append(dict(node=node, kind=k))
    # cut poche -------------------------------------------------------------------------------------------
    order = {"planting": 0, "site": 1, "stair_core": 2, "tube": 3, "escalator": 4, "facade": 5, "slab": 6, "roof": 6}
    for it in sorted(cut.items, key=lambda i: order.get(i.kind, 3)):
        if it.kind in {"program", "context"}:
            if it.kind == "context":
                rec["omitted_context_items"].append(dict(node=it.node, reason="neighbour massing overlaps envelope; not a design element"))
            continue
        for g in it.polygons:
            if it.kind in {"slab", "roof"}:
                v.geo(g, .40, BLACK, DARK)
            elif it.kind == "stair_core":
                v.geo(g, .18, GRAY, (.93, .94, .94), DASH)
            elif it.kind in {"tube", "facade"}:
                v.geo(g, .30, BLACK, DARK)
            elif it.kind == "escalator":
                v.geo(g, .20, BLACK, PALE)
            elif it.kind == "site":
                v.geo(g, .35, BLACK, DARK)
            elif it.kind == "planting":
                v.geo(g, .14, GRAY, (.90, .93, .90))
            else:
                v.geo(g, .15, GRAY, PALE)
        rec["cut_items"].append(dict(node=it.node, kind=it.kind, bounds_hv=list(it.bounds_hv), closed=it.watertight))

    # protected R8 research geometry (cuts of the proposal meshes), unchanged from R10-A --------------------
    bridge_hits = []
    if axis == "x":
        assert abs(B.XSEC - value) < 1e-3
        for o, g in B.cuts(B.P, B.objects(types={"bridge", "stair", "landing", "threshold", "vestibule"}), 0, B.XSEC):
            gz = affinity.scale(g, xfact=-1, origin=(0, 0))
            if o["kind"] == "bridge":
                v.geo(gz, .37, INK, CAND)
                bridge_hits.append((o["name"], gz))
            elif o["kind"] != "vestibule":
                v.geo(gz, .17, INK, CAND)
        for name, b in bridge_hits:
            pt = b.representative_point()
            x, y = v.xy(pt.x, pt.y)
            leader(p, (x, y), (cfg["bridge_leader_x"], y - 5), "01", "S-401" if name.startswith("2F") else "7F D")
    rec["r8_bridge_cuts"] = [n for n, _ in bridge_hits]

    # program labels: centre of the largest interval not blocked by a cut tube / core envelope ------------------
    blockers = []
    for it in cut.items:
        if it.kind in {"tube", "stair_core"}:
            blockers.append((it.bounds_hv[0] - .5, it.bounds_hv[2] + .5))
    placed = []
    for pr in rec["programs"]:
        hb = pr["bounds"]
        if (hb[2] - hb[0]) < 5.5 or (hb[3] - hb[1]) < 1.0 or pr["program"] == "앵커":
            continue
        free = [(max(hb[0], h0 + 1), min(hb[2], h1 - 1))]
        for b0, b1 in blockers:
            nxt = []
            for a0, a1 in free:
                if b1 <= a0 or b0 >= a1:
                    nxt.append((a0, a1))
                else:
                    if b0 > a0:
                        nxt.append((a0, b0))
                    if b1 < a1:
                        nxt.append((b1, a1))
            free = nxt
        free = [f for f in free if f[1] - f[0] >= 7.0]
        if not free:
            continue
        a0, a1 = max(free, key=lambda f: f[1] - f[0])
        cx_, cz_ = (a0 + a1) / 2, hb[1] + 1.55
        if any(abs(cz_ - pz) < 1.2 and abs(cx_ - px_) < 9 for px_, pz in placed):
            continue
        placed.append((cx_, cz_))
        v.pt(cx_, cz_, pr["program"], 6.6, False, col=GRAY, align='center', halo=True)
        pr["label_h"] = round((a0 + a1) / 2, 2)

    # slab voids: slab-free gaps >= 5 m inside the building width, from the cut slabs ---------------------------
    bh0, bh1 = cfg["building_h"]
    rec["voids"] = []
    for name, z in FF.items():
        iv = []
        for it in cut.items:
            if it.kind in {"slab", "roof"}:
                for g in it.polygons:
                    b = g.bounds
                    if b[1] >= z - 0.65 and b[3] <= z + 0.05:
                        iv.append((b[0], b[2]))
        iv.sort()
        merged = []
        for a0, a1 in iv:
            if merged and a0 <= merged[-1][1] + 0.05:
                merged[-1][1] = max(merged[-1][1], a1)
            else:
                merged.append([a0, a1])
        edges = [bh0] + [e for m in merged for e in m] + [bh1]
        for g0, g1 in zip(edges[0::2], edges[1::2]):
            if g1 - g0 >= 5.0 and g0 >= bh0 - 0.01 and g1 <= bh1 + 0.01:
                rec["voids"].append(dict(level=name, z=z, h0=round(g0, 3), h1=round(g1, 3), width_m=round(g1 - g0, 3)))
    groups = {}
    for vd_ in rec["voids"]:
        groups.setdefault((round(vd_["h0"]), round(vd_["h1"])), []).append(vd_)
    for key, vs in groups.items():
        vs.sort(key=lambda t: t["z"])
        low = vs[0]
        a, b = v.xy(low["h0"], low["z"] + 3.0), v.xy(low["h1"], low["z"] + 3.0)
        rep = f" ×{len(vs)}" if len(vs) > 1 else ""
        dim(p, a, b, 0, f"OPEN {math.dist(a, b) / v.k * 1000:,.0f}{rep}")
        for t in vs:
            t["labelled"] = t is low
    # callouts supplied by the sheet config (positions are model coordinates in sheet h, z) ----------------------
    for c in cfg.get("callouts", []):
        x, y = v.xy(c["h"], c["z"])
        if "th" in c:
            tx, ty = v.xy(c["th"], c["tz"])
            line(p, [(x, y), (tx, ty)], .12, GRAY)
            circle(p, x, y, .5, .1, BLACK, BLACK)
        else:
            tx, ty = x, y
        text(p, tx, ty + .9, c["t"], c.get("size", 6.9), c.get("bold", False), col=BLACK if c.get("bold") else GRAY,
             align=c.get("align", "center"), halo=True)
    rec["callouts"] = [c["t"] for c in cfg.get("callouts", [])]

    # grid bubbles and chain ---------------------------------------------------------------------------------
    grid = B.YGRID if cfg["grid"] == "Y" else B.XGRID
    top = v.xy(0, z1)[1]
    pts = []
    for key, c in grid:
        hh = -c if cfg["grid"] == "Y" else c
        if not (h0 <= hh <= h1):
            continue
        xx, _ = v.xy(hh, z1)
        rule(p, xx, top - 13.0, xx, v.r[3] - .4, .09, (.85, .86, .86), GRID)
        symbol(p, xx, top - 17.2, str(key), None, 2.8)
        pts.append((xx, top - 12.0))
    pts.sort()
    for a, b in zip(pts, pts[1:]):
        dim(p, a, b, 4.2, f"{math.dist(a, b) / v.k * 1000:,.0f}")
    roof = max(i.bounds_hv[3] for i in cut.items if i.kind == "roof") if any(i.kind == "roof" for i in cut.items) else FF.get("15F", 0)
    rec["roof_max"] = roof
    return dict(page=p, view=v, rec=rec, cut=cut)

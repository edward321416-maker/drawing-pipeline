"""R10-B A-201: 2F architectural plan, 1:200.

Ported from the R10-A composer (`plan()`), unchanged for every PR30 / R8 element, with these R10-B additions:
  * FIT_OUT_DEVELOPMENT layer (furniture / kitchen / storage equipment) drawn from fitout_r10b.develop_fitout()
  * room schedule with internal dimensions and an explicit CH 미확인 column
  * dimensions computed from the geometry: core sizes, tube diameters, void, E2 interface
  * section marks A-A (A-301) and B-B (A-302), key to tube / shaft functions as named in the model
Nothing here moves or edits a PR30 room, wall, door, column, core, tube or void.
"""
from __future__ import annotations

import math
import os
import re
import sys
from collections import Counter

import numpy as np
from shapely.geometry import LineString, Point, box
from shapely.ops import polylabel, unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import draft as D  # noqa: E402
from draft import (BLACK, CAND, DASH, EXIST, FAINT, GRAY, GRID, INK, LIGHT, PALE, WHITE, View, arrow, circle,  # noqa: E402
                   dim, frame, leader, line, parts, rule, symbol, tag, text)
import sheet_sections as S  # noqa: E402

FIT = (.26, .28, .29)          # FIT_OUT_DEVELOPMENT line colour (dark, thin)
FIT_LIGHT = (.55, .57, .57)    # chairs / stools


def room_dims(poly):
    """(W, D) in metres when the room is a rectangle (axis-aligned or rotated), else None.  From the polygon only."""
    if poly.area < 1e-6:
        return None
    mrr = poly.minimum_rotated_rectangle
    if poly.area / mrr.area < 0.985:
        return None
    c = list(mrr.exterior.coords)
    a = math.dist(c[0], c[1])
    b = math.dist(c[1], c[2])
    return (max(a, b), min(a, b))


def draw_fitout(v, items):
    for it in items:
        k = it.kind
        if "hood" in k:
            v.geo(it.geom, .10, FIT, None, DASH)
        elif any(w in k for w in ("chair", "stool")):
            v.geo(it.geom, .10, FIT_LIGHT, WHITE)
        else:
            v.geo(it.geom, .12, FIT, WHITE)


def build_a201(doc, B, fit_items, rec_in=None):
    G, PR, FF = B.G, B.PR, B.FF
    p = S.sheet_b(doc, B.IDS[0], ["2층 전체", "건축 평면도"], "1:200",
                  ["A-301  A–A 종단", "A-302  B–B 횡단", "A-501  코어 D", "S-401  E2 접합"],
                  ["기준 2F FFL +6.0004 m", "절단면 FFL +1.50 m", "실 구성·가구는 PR #30 검토", "가구·설비는 개발 후보", "CH는 전 실 미확인"])
    v = View(p, B.IDS[0], 200, (-12, -20, 48, 37), (49, 67))
    p.set_rotation(0)
    # ---- room schedule frame -------------------------------------------------------------------------------
    TX0, TX1 = 386, 526
    frame(p, (TX0, 39, TX1, 291), .17)
    text(p, TX0 + 4, 47, "2F 실 목록", 11, True)
    text(p, TX1 - 3, 47, "치수 m · 면적 ㎡ · CH 천장고", 6.6, align='right', col=GRAY)
    rule(p, TX0, 52, TX1, 52, .24)
    cols = dict(no=TX0 + 8, name=TX0 + 15, dim=TX0 + 80, area=TX0 + 103, ch=TX0 + 124)
    for x, c, al in [(cols["no"], "실번호", "center"), (cols["name"], "실명", "left"), (cols["dim"], "가로×세로", "right"),
                     (cols["area"], "면적", "right"), (cols["ch"], "CH", "center")]:
        text(p, x, 58, c, 7.0, True, align=al)
    for x in (TX0 + 14, TX0 + 81.5, TX0 + 104.5):
        rule(p, x, 52, x, 291, .11, LIGHT)
    # ---- base: slab, projections, voids -------------------------------------------------------------------------
    v.geo(G.slab, 0, BLACK, (.989, .990, .989))
    over = B.load_floor("3F").slab
    v.geo(over.boundary.difference(G.slab.boundary.buffer(.14)), .102, LIGHT, None, DASH)
    under = B.load_floor("1F").slab
    v.geo(under.boundary.difference(G.slab.buffer(.14)), .10, LIGHT, None, "[2 2] 0")
    h = G.outline.difference(G.slab)
    voids = []
    for g in sorted(parts(h, {"Polygon"}), key=lambda item: -item.area)[:9]:
        if g.area > 9:
            v.geo(g.boundary, .15, GRAY, None, DASH)
            if g.area > 55:
                clearance = g.difference(unary_union([t.outer for t in G.tubes.values()] + [B.DECK]).buffer(.48))
                areas = list(parts(clearance, {"Polygon"}))
                if areas:
                    pt = polylabel(max(areas, key=lambda x: x.area), tolerance=.18)
                    v.pt(pt.x, pt.y, "하부 OPEN", 7.8, True, col=GRAY, align='center', halo=True)
                voids.append(g)
    B.plan_grid(v)
    win = B.BOUND.buffer(.02)
    # ---- PR30 items, exactly as R10-A drew them ------------------------------------------------------------------
    from t14s.model import LAYER_ORDER
    for item in sorted(PR.items, key=lambda i: LAYER_ORDER[i.layer]):
        l, g = item.layer, item.geom
        if l in {"A-CIRC", "A-CIRC-SVC", "A-ZONE", "A-GRID", "A-FLOOR-HATCH", "A-RAIL", "A-ANNO-TAGS", "A-ANNO-DIMS",
                 "A-ANNO-SYMB", "A-ANNO-TEXT"}:
            continue
        if g.intersects(win) and l in {"A-WALL-CORE", "A-DOOR", "A-STAR", "A-WALL-EXT"}:
            g = g.difference(win)
        if l == "A-WALL-EXT":
            v.geo(g, .40, BLACK)
            continue
        if l == "A-COLS":
            v.geo(g, .40, BLACK, BLACK)
            continue
        if l == "A-WALL-PART":
            v.geo(g, .26 if 'cubicle' not in item.ref else .14, GRAY, EXIST if item.fill else None)
            continue
        if l == "A-WALL-CORE":
            fill = EXIST if item.fill and 'footprint' not in item.ref else None
            v.geo(g, .50 if 'footprint' in item.ref else .40, BLACK, fill)
            continue
        if l == "A-GLAZ":
            v.geo(g, .20, BLACK, EXIST if item.fill else None)
            continue
        pal = .11 if l in {"A-FURN", "A-FIXT", "A-STAR-PROJ"} else .15
        v.geo(g, pal, GRAY, PALE if item.fill and l in {"A-TUBE", "A-FURN", "A-FIXT"} else None,
              DASH if item.dash or l == "A-STAR-PROJ" else None)
    # ---- R10-B: fit-out development candidates (drawn after PR30 furniture, before research geometry) ---------------
    draw_fitout(v, fit_items)
    # ---- R8 research geometry, unchanged -------------------------------------------------------------------------------
    cands = B.objects(floor="2F")
    v.geo(B.DECK, .24, INK, CAND)
    land = [o for o in B.P.bld if o.get("floor") == "2F" and o.get("group", "").startswith("ESC ") and o["kind"] in {"escalator_deck", "guard"}]
    for o in land:
        v.geo(B.top_faces(o), .17, INK, CAND if o["kind"] == "escalator_deck" else None)
    for o in cands:
        if o["kind"] in {"guard", "threshold", "vestibule", "landing"}:
            v.geo(B.top_faces(o), .14, INK)
    low = FF["2F"]
    B.stairs_plan(v, "2F-3F", low + 1.5)
    B.core_shell_plan(v, cands, low + 1.5)
    B.core_doors(v, "2F")
    # ---- rooms: schedule rows and tags -------------------------------------------------------------------------------
    model_rooms = []
    for r in PR.rooms:
        n = int(r["id"])
        yy = 60 + n * 8.25
        rule(p, TX0, yy - 3.6, TX1, yy - 3.6, .1, LIGHT)
        name = B.roomname(r)
        text(p, cols["no"], yy + 1.5, "2-" + r["id"], 7.45, True, align='center')
        text(p, cols["name"], yy + 1.5, name, 7.75)
        dm = room_dims(r["poly"])
        text(p, cols["dim"], yy + 1.5, f"{dm[0]:.1f}×{dm[1]:.1f}" if dm else "비정형", 7.2, align='right', col=GRAY if dm else LIGHT)
        text(p, cols["area"], yy + 1.5, f"{r['poly'].area:,.1f}", 7.45, align='right')
        text(p, cols["ch"], yy + 1.5, "미확인", 6.8, align='center', col=GRAY)
        pos = r.get("label")
        if pos and r["poly"].covers(Point(pos["cx"], pos["cy"])):
            x, y = v.xy(pos["cx"], pos["cy"])
        else:
            pt = r["poly"].representative_point()
            x, y = v.xy(pt.x, pt.y)
        if n in {2, 3, 8, 10, 11, 16, 20, 25}:
            show = "객석" if n != 10 else r["name"]
            text(p, x, y - 3.55, show, 8 if n != 10 else 10, True, align='center', halo=True)
        tag(p, x, y, "2-" + r["id"], 5.45)
        model_rooms.append(dict(id="2-" + r["id"], name=name, area=round(r["poly"].area, 4), centre_paper_mm=(x, y),
                                dims_m=[round(dm[0], 3), round(dm[1], 3)] if dm else None, ceiling_height=None,
                                grade=r["prov"]))
    # ---- core, tube and shaft names, dimensions from geometry --------------------------------------------------------
    core_dims = {}
    for k in ("A", "B", "C", "D"):
        a = G.cores[k]
        cx = (a[0] + a[2]) / 2
        w, hh = a[2] - a[0], a[3] - a[1]
        core_dims[k] = [round(w, 3), round(hh, 3)]
        if k != "D":
            v.pt(cx, a[1] + .55 if k in "BC" else a[1] + .55, "코어 " + k, 6.6, True, align='center', halo=True)
            v.pt(cx, a[1] + 1.55, f"{w * 1000:,.0f}×{hh * 1000:,.0f}", 5.4, False, col=GRAY, align='center', halo=True)
    v.pt(-7.3, -17.1, "코어 D", 6.6, True, align='center', halo=True)
    v.pt(-6.28, -12.92, "UP", 5.9, True, align='right', halo=True)
    for txt in PR.texts:
        if txt.s in ("UP", "DN") and not win.covers(Point(txt.x, txt.y)):
            v.pt(txt.x, txt.y, txt.s, 5.5, True, align='center', halo=True)
    tube_dims = {}
    for k in ("T1", "T2", "T3", "T4", "FR"):
        t = G.tubes[k]
        v.pt(*t.center, k, 6.6, True, align='center', halo=True)
        d_ = 2 * t.r
        tube_dims[k] = round(d_, 3)
        a, b = v.xy(t.center[0] - t.r, t.center[1] - t.r), v.xy(t.center[0] + t.r, t.center[1] - t.r)
        dim(p, a, b, 2.6, f"Ø{d_ * 1000:,.0f}")
    doors_done, doors_skipped = door_dims(p, v, PR, p.number)
    for i, r in enumerate([a for a in B.WALK["escalators"] if a["floor"] == "2F"]):
        x, y = r["real_comb_edge_xy"]
        yy = y + 1.15 if i == 0 else y - 1.55
        v.pt(x, yy, "하차" if r['role'] == "arrive" else "승차", 6.3, True, align='center', halo=True)
    # ---- section marks: A-A (A-301) and B-B (A-302) --------------------------------------------------------------------
    sx, _ = v.xy(B.XSEC, 0)
    for y1, y2 in [(64.8, 76), (328, 347)]:
        rule(p, sx, y1, sx, y2, .22, BLACK, GRID)
    rule(p, sx, 76, sx, 328, .115, LIGHT, GRID)
    for yy in (64.8, 347):
        symbol(p, sx, yy, "A", "A-301", 4.75)
        arrow(p, (sx + 5, yy), (sx + 12, yy), BLACK, size=2.7)
    by = v.xy(0, 10.0)[1]
    bl, br = v.xy(-9, 0)[0] - 3, v.xy(45, 0)[0] + 3
    rule(p, v.xy(-11.5, 0)[0], by, bl, by, .22, BLACK, GRID)
    rule(p, bl, by, br, by, .115, LIGHT, GRID)
    rule(p, br, by, br + 9, by, .22, BLACK, GRID)
    symbol(p, v.xy(-11.5, 0)[0] - 4.8, by, "B", "A-302", 4.75)
    symbol(p, br + 14, by, "B", "A-302", 4.75)
    arrow(p, (br + 19.5, by - 0.0), (br + 19.5, by - 7.0), BLACK, size=2.7)
    leader(p, v.xy(-4.18, -2.4), (107, 268), "01", "S-401")
    leader(p, v.xy(-4.92, -14.8), (111, 326), "01", "A-501")
    D_north(p, G, 362, 73)
    text(p, 361, 89, "북각 " + str(G.north_deg) + "°", 6.3, col=GRAY, align='center')
    # ---- legend and notes ---------------------------------------------------------------------------------------------------
    rule(p, TX0, 296, TX1, 296, .23)
    text(p, TX0 + 2, 302, "표기 및 원본 구분", 8.8, True)
    sy = 308
    for kind, label in [("fit", "가구·설비: 개발 후보 (FIT_OUT_DEVELOPMENT) — 진한 회색 가는 선"),
                        ("pr30", "PR #30 설계 후보 (벽·문·가구·설비) — 연한 회색"),
                        ("r8", "코어 D · 브리지 · 랜딩: R8 연구 형상 — 청록"),
                        ("hid", "위·아래층 투영 경계 — 가는 점선")]:
        if kind == "fit":
            frame(p, (TX0 + 2, sy - 2.6, TX0 + 9, sy + .6), .12, WHITE, FIT)
        elif kind == "pr30":
            frame(p, (TX0 + 2, sy - 2.6, TX0 + 9, sy + .6), .11, PALE, GRAY)
        elif kind == "r8":
            frame(p, (TX0 + 2, sy - 2.6, TX0 + 9, sy + .6), .24, CAND, INK)
        else:
            rule(p, TX0 + 2, sy - 1, TX0 + 9, sy - 1, .10, LIGHT, DASH)
        text(p, TX0 + 12, sy, label, 6.7, col=GRAY)
        sy += 6.0
    for s_ in ["원형: 큰 원 T1–T4·FR = 튜브, 작은 원 ✕ = 샤프트(M1·M2·PL·EV1·EV2·W). 용도명은 모형 식별자.",
               "FR: PR #30에서 ‘반입 접점’으로 표기된 튜브. T2·PL의 용도는 미확인.",
               "치수 mm · 레벨 m. 가구 치수는 가정값(fitout_assumptions). 천장고 CH 미확인."]:
        text(p, TX0 + 2, sy, s_, 6.4, col=GRAY)
        sy += 5.6
    v.bar(10, 57, 378)
    D.view_caption(p, 326, 390, "01", "2층 건축 평면도", 200, 520)
    rec = dict(PR30_source_commit=B.PR30, source_slice_sha256=G.slice_sha256, rooms=model_rooms,
               grid={"x": B.XGRID, "y": B.YGRID}, section=dict(A_A=dict(x=B.XSEC, direction="+X", target="A-301"),
                                                               B_B=dict(y=10.0, direction="+Y", target="A-302")),
               architectural_model_items=dict(Counter(i.layer for i in PR.items if i.layer not in {"A-CIRC", "A-CIRC-SVC"})),
               removed_layers=["A-CIRC", "A-CIRC-SVC"], unknown_ceiling_count=len(model_rooms),
               core_dims_m=core_dims, tube_diameters_m=tube_dims, door_dims_annotated=doors_done, door_dims_skipped=doors_skipped,
               void_areas_m2=[round(g.area, 2) for g in voids], fitout_items=len(fit_items),
               fitout_register=[dict(id=i.id, room=i.room_id, kind=i.kind, dims_mm=list(i.dims_mm), basis=i.basis, prov=i.prov,
                                     bounds_m=[round(x, 3) for x in i.geom.bounds]) for i in fit_items])
    return p, v, rec


def door_dims(p, v, PR, page_no):
    """Opening-width dimension for every door that has a leaf + swing pair (28 doors: unit / internal / pass / service).
    Opening = leaf start (hinge) -> swing-arc start (closed leaf tip); width = their distance.  The dimension sits on the side
    away from the swing.  A label that would overlap an already placed text is NOT drawn (counted as skipped)."""
    leaves, swings = {}, {}
    key = lambda c: (round(c[0], 3), round(c[1], 3))   # noqa: E731
    for it in PR.items:
        if it.layer != "A-DOOR" or it.geom.geom_type != "MultiLineString":
            continue
        c = list(it.geom.geoms[0].coords)
        (leaves if "leaf" in it.ref else swings)[key(c[-1])] = (c, it.ref)
    done, skipped = [], []
    for tip, (lc, ref) in leaves.items():
        if tip not in swings:
            continue
        sc = swings[tip][0]
        H, C, T = np.array(lc[0]), np.array(sc[0]), np.array(lc[-1])
        width = float(np.linalg.norm(H - C))
        a, b = np.array(v.xy(*H)), np.array(v.xy(*C))
        dd = b - a
        L = float(np.linalg.norm(dd))
        if L < 1e-6:
            continue
        n = np.array([-dd[1], dd[0]]) / L
        sw = np.array(v.xy(*T)) - a
        if float(np.dot(n, sw)) > 0:
            n = -n
        off = 3.3
        u, z = a + n * off, b + n * off
        label = f"{width * 1000:,.0f}"
        cx, cy = (u + z) / 2
        horizontal = abs(dd[0]) >= abs(dd[1])
        tw = D.FONTS["Bold"].text_length(label, fontsize=5.25) / D.K
        if horizontal:
            bx = (cx - tw / 2, cy - 2.8, cx + tw / 2, cy - 0.4)
        else:
            sgn = 1 if n[0] > 0 else -1
            bx = (cx + sgn * 1.0 - (tw if sgn < 0 else 0), cy - 1.2, cx + sgn * 1.0 + (tw if sgn > 0 else 0), cy + 1.2)
        clash = any(b_[0] == page_no and not (bx[2] < b_[1] or bx[0] > b_[3] or bx[3] < b_[2] or bx[1] > b_[4]) for b_ in D.BBOX)
        rec_ = dict(door=ref.replace(" door leaf", ""), width_mm=round(width * 1000, 1), centre_m=[round(float((H[0] + C[0]) / 2), 3), round(float((H[1] + C[1]) / 2), 3)])
        if clash:
            skipped.append(rec_)
            continue
        rule(p, *a, *u, .08, GRAY)
        rule(p, *b, *z, .08, GRAY)
        line(p, [u, z], .10, BLACK)
        for e in (u, z):
            line(p, [e + np.array([-.6, .6]), e + np.array([.6, -.6])], .12, BLACK)
        if horizontal:
            text(p, cx, cy - 0.9, label, 5.25, True, align='center')
        else:
            text(p, cx + (1.0 if n[0] > 0 else -1.0), cy + .6, label, 5.25, True, align='left' if n[0] > 0 else 'right')
        done.append(rec_)
    return done, skipped


def D_north(p, G, x, y):
    rad = math.radians(G.north_deg)
    circle(p, x, y, 8.1, .14, BLACK)
    d = np.array([math.sin(rad), -math.cos(rad)])
    arrow(p, np.array([x, y]) - d * 5, np.array([x, y]) + d * 7, size=2.45)
    text(p, *(np.array([x, y]) + d * 11), "N", 10, True, align='center')

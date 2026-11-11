"""V2 입면 4 + 단면 4 + 키플랜: V1 엔진(book_views) 위에 치수·축선·호출·키플랜·높이표를 더한다.

    python -I tools/t14e_make_views.py --run <V2 루트> --glb <glb>
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import pipeline_common as pc  # noqa: E402
from shapely.geometry import box  # noqa: E402
import book_views as bv  # noqa: E402
import t14d_sheet as _ts  # noqa: E402
from t14g import config as cfg, modelsrc  # noqa: E402
cfg.apply(_ts)
from t14d_sheet import Sheet, geom_lines, geom_rings  # noqa: E402
import t14d_make_views as V1  # noqa: E402
import t14e_dims as dm  # noqa: E402


def r5(v):
    """모델 값을 5 mm 단위로 반올림(0.4~0.6 mm 수준 모델 노이즈를 라벨·치수에 싣지 않는다)."""
    return round(v / 0.005) * 0.005


def level_lines(sh, model, x_l, x_r, y_of, z_lo, z_hi, roof_z):
    ffl0 = model.floors["1F"]
    for name, z in sorted(model.floors.items(), key=lambda kv: kv[1]):
        if z < z_lo or z > z_hi:
            continue
        y = y_of(z)
        sh.line(x_l, y, x_r, y, 0.1, "#999", "2.2,1.6")
        lab = "%s  %+.3f" % (name, r5(z - ffl0))
        sh.text(x_l - 1, y - 0.8, lab, 6, "normal", "#444", "end")
        sh.text(x_r + 1, y - 0.8, lab, 6, "normal", "#444", "start")
    y = y_of(roof_z)
    sh.line(x_l, y, x_r, y, 0.1, "#999", "2.2,1.6")
    sh.text(x_l - 1, y - 0.8, "ROOF  %+.3f" % r5(roof_z - ffl0), 6, "bold", "#444", "end")
    sh.text(x_r + 1, y - 0.8, "ROOF  %+.3f" % r5(roof_z - ffl0), 6, "bold", "#444", "start")


def axes_of(run):
    sl = pc.load_slice(os.path.join(run, "raw_slices"), "3F")
    cols = [g.centroid for _, g in pc.cut_geometries(sl).get("column", [])]
    from t14e_plan_sheet import uniq
    return uniq([c.x for c in cols]), uniq([c.y for c in cols]), sl


def top_axes(sh, X, ytop, right, xs, ys, lo, hi, meta):
    """수평 방향에 걸리는 축선: 기호 + 그리드 체인 + 전체 폭."""
    xl, yl = dm.axis_labels(xs, ys)
    if abs(right[1]) > 0.5:                                                       # 화면 가로축 = y → 숫자 축선
        pos = {u: yl[round(y, 2)] for y in ys for u in [y * right[1]]}
    else:                                                                         # 화면 가로축 = x → 알파벳 축선
        pos = {u: xl[round(x, 2)] for x in xs for u in [x * right[0]]}
    us = sorted(pos)
    for u in us:
        sh.line(X(u), ytop + 1.0, X(u), ytop - 15.5, 0.1, "#888", "6,1.4,1,1.4")
        dm.bubble(sh, X(u), ytop - 19.0, pos[u], r=3.0)
        meta["axis_bubbles"] += 1
    edges = [lo] + [u for u in us if lo + 0.2 < u < hi - 0.2] + [hi]
    dm.chain_h(sh, [X(u) for u in edges], ytop - 6.0, [dm.fmt_mm(b - a) for a, b in zip(edges, edges[1:])], from_y=ytop + 1.0)
    meta["grid_chains"] += 1
    dm.dim_h(sh, X(lo), X(hi), ytop - 11.5, dm.fmt_mm(hi - lo), from_y=ytop + 1.0)
    meta["overall_chains"] += 1


def height_dims(sh, model, Y, x_left, x_right, roof_z, z_lo_draw, tops, meta):
    ffl0 = model.floors["1F"]
    zs = sorted([(n, z) for n, z in model.floors.items() if z >= z_lo_draw - 1e-6], key=lambda kv: kv[1]) + [("ROOF", roof_z)]
    chain = [Y(z) for _, z in zs]
    labels = [dm.fmt_mm(r5(b[1]) - r5(a[1])) for a, b in zip(zs, zs[1:])]
    dm.chain_v(sh, chain, x_left, labels, from_x=x_left + 24.0)                    # 층고 체인(왼쪽)
    meta["level_dims"] += 1
    dm.dim_v(sh, Y(roof_z), Y(ffl0), x_right, dm.fmt_mm(roof_z - ffl0), from_x=x_right - 24.0, left=False)    # GL~지붕 전체 높이
    meta["overall_chains"] += 1
    ex = sorted({round(t - ffl0, 2) for t in tops if t > ffl0 + 0.5})
    if ex:                                                                         # 주요 돌출부·튜브 상단 높이
        dm.chain_v(sh, [Y(ffl0 + v) for v in [0.0] + ex], x_right + 9.0, [dm.fmt_mm(b - a) for a, b in zip([0.0] + ex, ex)], from_x=x_right - 24.0, left=False)
        meta["major_dims"] += 1


def mini_keyplan(sh, run, x, y, size, cut=None, letter=None, north=None, label="키플랜 KEY PLAN"):
    """3F 절단 평면을 작게 그리고 절단선을 강조한다. (x,y) = 좌상단, size = 한 변(mm)."""
    sl = pc.load_slice(os.path.join(run, "raw_slices"), "3F")
    cuts = pc.cut_geometries(sl)
    slab = bv._union([pc.polygons_from_segments(p["segments"]) for p in sl["projection"]])
    x0, y0, x1, y1 = slab.bounds
    k = size / max(x1 - x0, y1 - y0)
    P = lambda a, b: (x + (a - x0) * k, y + (y1 - b) * k)
    sh.text(x, y - 3.0, label, 6.5, "bold", "#222")
    sh.path([[P(a, b) for a, b in r] for r in geom_rings(slab)], fill="#f4f4f4", stroke="#555", w=0.2)
    for kind, fill in (("core_wall", "#333"), ("tube_wall", "#fff")):
        for it, g in cuts.get(kind, []):
            sh.path([[P(a, b) for a, b in r] for r in geom_rings(g)], fill=fill, stroke="#222", w=0.12)
    if cut:
        (ax0, ay0), (ax1, ay1) = cut["line_drawing_frame"]
        p0, p1 = P(ax0, ay0), P(ax1, ay1)
        sh.line(p0[0], p0[1], p1[0], p1[1], 0.5, "#c00", "5,1.2,1,1.2")
        lk = cut["view_direction_drawing_frame"]
        mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
        sh.path([[mid, (mid[0] + lk[0] * 7, mid[1] - lk[1] * 7)]], stroke="#c00", w=0.5, closed=False)
        for p in (p0, p1):
            dm.bubble(sh, p[0], p[1], letter, r=2.4, pt=6.0, color="#c00")
    if north is not None:
        sh.north_arrow(x + size + 8, y + 8, north, r=4.0)


def height_table(sh, model, x, y, rows, title):
    ffl0 = model.floors["1F"]
    sh.text(x, y, title, 8, "bold", "#111")
    y += 5.0
    sh.line(x, y - 3.2, x + 98, y - 3.2, 0.2, "#555")
    sh.text(x, y, "요소", 6.2, "bold", "#222")
    sh.text(x + 62, y, "하단", 6.2, "bold", "#222", "end")
    sh.text(x + 80, y, "상단", 6.2, "bold", "#222", "end")
    sh.text(x + 98, y, "높이", 6.2, "bold", "#222", "end")
    y += 4.2
    for nm, lo, hi in rows:
        sh.text(x, y, nm[:22], 5.9, "normal", "#333")
        sh.text(x + 62, y, "%+.2f" % (lo - ffl0), 5.9, "normal", "#333", "end")
        sh.text(x + 80, y, "%+.2f" % (hi - ffl0), 5.9, "normal", "#333", "end")
        sh.text(x + 98, y, dm.fmt_mm(hi - lo), 5.9, "normal", "#333", "end")
        y += 4.0
    return y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--glb", default=None, help="원본 GLB(없어도 됨: 모델 캐시에서 생성하고 캐시 해시를 기록한다)")
    a = ap.parse_args()
    run = os.path.abspath(a.run)
    model = bv.Model(os.path.join(run, "model_cache"), os.path.join(run, "raw_slices", "camera_bounds.json"))
    bb = model.building
    ffl0 = model.floors["1F"]
    roof_z = max(o["zmax"] for o in model.objects if o["kind"] == "roof")
    xs, ys, sl3 = axes_of(run)
    regs = json.load(open(os.path.join(run, "qa", "ref_registries", "section_line_registry.json"), encoding="utf-8"))
    tops = sorted({o["zmax"] for o in model.objects if o["kind"] in ("tube_wall", "core_wall", "shaft", "ramp") and o["zmax"] > model.floors["15F"] + 0.5})
    ident = modelsrc.identity(run, a.glb)
    reg = {"book": "C_T14G", "model": {"path": os.path.abspath(a.glb) if a.glb else ident["glb_name"] + " (not present)", "sha256": modelsrc.model_sha(run, a.glb),
                                        "status": ident["status"], "cache_sha256": ident["cache_sha256"]}, "frame": {"theta_deg": math.degrees(model.theta), "north_deg": model.north_deg},
           "elevations": [], "sections": [], "dimension_meta": {}}
    scale, k, pad = 400, 2.5, 0.3
    fac6 = [o for o in model.objects if o["name"].startswith("A-FACD_valley_glass_6F")]
    pad_o = next(o for o in model.objects if o["name"] == "A-ROOF_rescue_pad")

    def center_of(o):
        T = model.tris(o).reshape(-1, 3)
        return (T[:, 0].min() + T[:, 0].max()) / 2, (T[:, 1].min() + T[:, 1].max()) / 2, (T[:, 2].min() + T[:, 2].max()) / 2

    for beta, sid in [(90.0, "E-201"), (180.0, "E-202"), (270.0, "E-203"), (0.0, "E-204")]:
        cb = (beta - model.north_deg) % 360
        card = V1.card4(cb)
        nm_en = {"N": "NORTH", "E": "EAST", "S": "SOUTH", "W": "WEST"}[card]
        el = bv.elevation(model, beta)
        x0, y0, x1, y1 = el["extent"]
        zlim = box(x0 - 1, ffl0, x1 + 1, roof_z + pad)
        meta = {"overall_chains": 0, "grid_chains": 0, "level_dims": 0, "major_dims": 0, "axis_bubbles": 0, "detail_callouts": 0, "level_labels": 0}
        sh = Sheet(sid, "%s측 입면도 (%s ELEVATION)" % (V1.CARD_KO[card], nm_en), scale, "MODEL_GEOMETRY · 외피 접합·재료 상세 미검증",
                   subtitle="정면 방위 %s %.1f° (면 법선, 진북 기준) · 건물 면에 수직 정투영 · 기준 GL = 1F FFL ±0.000 · 치수 mm" % (V1.compass_name(cb), cb),
                   extra_lines=["원천: A-FACD·A-STRC·A-FLOR·A-CORE-TUBE·A-VERT·A-ROOF 모델 객체. 3D에 없는 유리 패널·루버·출입구는 그리지 않음",
                                "가림 처리 벡터(숨은 선 제거). 대지 지형·지하 옹벽 미표시(모델에 없음) · 축선은 3F 모델 기둥 중심선"])
        ucen = (x0 + x1) / 2
        y_ground = 232.0
        X = lambda u: 190.0 + (u - ucen) * k
        Y = lambda z: y_ground - (z - ffl0) * k
        level_lines(sh, model, X(x0) - 6, X(x1) + 6, Y, ffl0 + 0.1, roof_z - 0.1, roof_z)
        meta["level_labels"] = 15
        drawn, drawq = [], []
        for o, vis, edge in el["items"]:
            lines = geom_lines(edge.intersection(zlim))
            if lines:
                drawn.append(o)
                drawq.append((V1.W_STRUCT.get(o["kind"], 0.15), lines))
        sh.path([[(X(u), Y(z)) for u, z in ln] for ln in geom_lines(el["silhouette"].intersection(zlim).boundary)], stroke="#000", w=0.45, closed=False)
        for w, lines in sorted(drawq, key=lambda t: -t[0]):
            sh.path([[(X(u), Y(z)) for u, z in ln] for ln in lines], stroke="#222", w=w, closed=False)
        sh.line(12, Y(ffl0), 300, Y(ffl0), 0.6, "#000")
        sh.text(X(x1) + 1, Y(ffl0) + 4.5, "GL ±0.000", 6.5, "bold", "#111")
        corners = [(bb["xmin"], bb["ymin"]), (bb["xmax"], bb["ymax"]), (bb["xmin"], bb["ymax"]), (bb["xmax"], bb["ymin"])]
        rr = el["right"]
        top_axes(sh, X, Y(roof_z), rr, xs, ys, min(p[0] * rr[0] + p[1] * rr[1] for p in corners), max(p[0] * rr[0] + p[1] * rr[1] for p in corners), meta)
        height_dims(sh, model, Y, X(x0) - 32.0, X(x1) + 30.0, roof_z, ffl0, tops, meta)
        # 상세 호출: 6F 외피(D-406), 지붕 구조(D-410)
        if fac6:
            fx, fy, fz = center_of(fac6[0])
            dm.detail_tag(sh, X(fx * el["right"][0] + fy * el["right"][1]), Y(fz), "D-406", dashed_r=6.0)           # 축척은 레지스트리에서
            meta["detail_callouts"] += 1
        px_, py_, pz_ = center_of(pad_o)
        dm.detail_tag(sh, X(px_ * el["right"][0] + py_ * el["right"][1]), Y(pz_), "D-410", dashed_r=5.0)
        meta["detail_callouts"] += 1
        # 오른쪽: 주요 높이표 + 방위 안내
        rows = [("15F → 지붕 상단", model.floors["15F"], roof_z)] + [(o["name_ko"], o["zmin"], o["zmax"]) for o in model.objects if o["kind"] in ("tube_wall",) and o["zmax"] > model.floors["15F"] + 0.5][:6]
        height_table(sh, model, 306, 20, rows, "주요 높이 (GL=±0)")
        sh.text(306, 80, "방위·투영", 8, "bold", "#111")
        for i, t in enumerate(["정면 방위 %s %.1f° (면 법선)" % (V1.compass_name(cb), cb), "건물 면에 수직인 정투영", "보는 사람: 건물 바깥에서 건물 쪽", "도면 위쪽에서 진북 %.1f° (1층 기준)" % model.north_deg]):
            sh.text(306, 86 + i * 4.6, t, 6.0, "normal", "#333")
        sh.north_arrow(380, 108, model.north_deg, r=5.5)
        sh.scale_bar(306, 150, meters=(0, 5, 10, 20))
        sh.title_block()
        base = sh.save(os.path.join(run, "elevations", "%s_%s_elevation" % (sid, {"N": "north", "E": "east", "S": "south", "W": "west"}[card])))
        reg["elevations"].append({"sheet": sid, "name": card, "compass_of_face_normal_deg": round(cb, 2), "compass16": V1.compass_name(cb), "drawing_bearing_of_view_deg": beta,
                                  "view_direction_in_drawing_frame": [round(float(v), 6) for v in el["depth"]], "projection": "orthographic, perpendicular to building face", "scale": "1:%d" % scale,
                                  "extent_m": [round(float(v), 3) for v in el["extent"]], "source_objects": sorted({o["name"] for o in drawn}), "source_count": len(drawn),
                                  "geometry_sha256": V1.obj_hash(model, drawn), "dimension_meta": meta, "files": {e: {"path": base + "." + e, "sha256": V1.sha_file(base + "." + e)} for e in ("svg", "pdf", "png")}})
        print("ELEV", sid, card, meta)

    cx_mid, cy_mid = (bb["xmin"] + bb["xmax"]) / 2, (bb["ymin"] + bb["ymax"]) / 2
    z_lo = min(o["zmin"] for o in model.bld)
    for s in regs["sections"]:
        ax, val, ls, nm, sid = s["plane"]["axis"], s["plane"]["value_drawing_frame"], s["plane"]["look_sign"], s["name"][0], s["sheet"]
        sec = bv.section(model, ax, val, ls)
        x0, y0, x1, y1 = sec["extent"]
        sc = 400
        kk = 1000.0 / sc
        ucen = (x0 + x1) / 2
        X = lambda u: 190.0 + (u - ucen) * kk
        Y = lambda z: 40.0 + (roof_z + 0.4 - z) * kk
        meta = {"overall_chains": 0, "grid_chains": 0, "level_dims": 0, "major_dims": 0, "axis_bubbles": 0, "detail_callouts": 0, "level_labels": 18}
        sh = Sheet(sid, "단면도 %s–%s (SECTION %s–%s)" % (nm, nm, nm, nm), sc, "MODEL_GEOMETRY · 실제 메시 절단",
                   subtitle="%s · 절단면 %s = %.3f (도면틀) · 바라보는 방향 %s · 치수 mm" % (s["description"], ax, val, ("+" if ls > 0 else "−") + ax),
                   extra_lines=["절단 포셰 = 모델 메시와 절단면의 교선(층 평면을 쌓은 가짜 단면 아님). 절단면 너머 객체는 가림 처리 윤곽선",
                                "층 레벨·슬래브 두께는 A-FLOR 층판에서 읽음. 접합·재료 상세 미검증. 지반·옹벽은 모델에 없어 표시하지 않음(UNVERIFIED)"])
        level_lines(sh, model, X(x0) - 6, X(x1) + 6, Y, z_lo, roof_z - 0.1, roof_z)
        drawn, drawq = [], []
        for o, vis, edge in sec["items"]:
            lines = geom_lines(edge)
            if lines:
                drawn.append(o)
                drawq.append((0.12 if o["kind"] in ("column", "facade") else 0.18, lines))
        for w, lines in sorted(drawq, key=lambda t: -t[0]):
            sh.path([[(X(u), Y(z)) for u, z in ln] for ln in lines], stroke="#444", w=w, closed=False)
        cut_objs = []
        for o, poly in sec["cuts"]:
            sh.path([[(X(u), Y(z)) for u, z in r] for r in geom_rings(poly)], fill="#111", stroke="#000", w=0.35)
            cut_objs.append(o)
        sh.line(12, Y(ffl0), 300, Y(ffl0), 0.35, "#555", "5,2")
        sh.text(X(x1) + 1, Y(ffl0) + 3.5, "GL ±0.000", 6, "bold", "#444")
        # 축선·그리드·전체 폭(위), 층고 체인·전체 높이(양옆)
        right = sec["right"]
        corners = [(bb["xmin"], bb["ymin"]), (bb["xmax"], bb["ymax"]), (bb["xmin"], bb["ymax"]), (bb["xmax"], bb["ymin"])]
        lo_u, hi_u = min(p[0] * right[0] + p[1] * right[1] for p in corners), max(p[0] * right[0] + p[1] * right[1] for p in corners)
        top_axes(sh, X, Y(roof_z), right, xs, ys, lo_u, hi_u, meta)
        height_dims(sh, model, Y, X(x0) - 32.0, X(x1) + 30.0, roof_z, z_lo, tops, meta)
        mini_keyplan(sh, run, 308, 24, 60, cut=s, letter=nm, north=model.north_deg)
        sh.text(308, 101, "절단선 %s–%s: %s = %.2f, 바라봄 %s" % (nm, nm, ax, val, ("+" if ls > 0 else "−") + ax), 6.0, "normal", "#c00")
        sh.text(308, 105.6, "키플랜 S-301 참조", 6.0, "normal", "#555")
        seen, rows = set(), []
        for o in cut_objs:
            if o["kind"] in ("tube_wall", "shaft", "ramp", "stair", "core_wall") and o["name"] not in seen:
                seen.add(o["name"])
                rows.append((o["name_ko"], o["zmin"], o["zmax"]))
        rows = sorted(rows, key=lambda r: -(r[2] - r[1]))[:14]
        height_table(sh, model, 308, 120, rows, "절단 통과 요소 높이")
        sh.scale_bar(308, 253 - 14, meters=(0, 5, 10, 20))
        sh.title_block()
        base = sh.save(os.path.join(run, "sections", "%s_section_%s-%s" % (sid, nm, nm)))
        reg["sections"].append({**{k_: v_ for k_, v_ in s.items() if k_ != "files"}, "scale": "1:%d" % sc, "dimension_meta": meta,
                                "cut_elements": [{"name": o["name"], "kind": o["kind"], "name_ko": o["name_ko"]} for o in cut_objs], "visible_source_count": len(drawn),
                                "visible_source_objects": sorted({o["name"] for o in drawn}), "files": {e: {"path": base + "." + e, "sha256": V1.sha_file(base + "." + e)} for e in ("svg", "pdf", "png")}})
        print("SEC", sid, nm, meta)

    # 키플랜 시트
    sh = Sheet("S-301", "단면 키플랜 (SECTION LOCATOR)", 400, "MODEL_GEOMETRY · 절단선은 모델 좌표에서 계산", subtitle="3F 절단 평면 위에 A–A ~ D–D 절단선 · 화살표 = 바라보는 방향 · 치수 mm",
               extra_lines=["절단선 좌표·방향·source 요소는 section_line_registry.json 에 기록", "1층 마스터와 같은 좌표틀(north_deg %.1f°)" % model.north_deg])
    kp = 2.5
    ox, oy = 150.0 - (bb["xmin"] + bb["xmax"]) / 2 * kp, 140.0 + (bb["ymin"] + bb["ymax"]) / 2 * kp
    P = lambda x_, y_: (ox + x_ * kp, oy - y_ * kp)
    cuts3 = pc.cut_geometries(sl3)
    slab = bv._union([pc.polygons_from_segments(p["segments"]) for p in sl3["projection"]])
    sh.path([[P(x_, y_) for x_, y_ in r] for r in geom_rings(slab)], fill="#f4f4f4", stroke="#555", w=0.3)
    for kind, fill, w in (("core_wall", "#222", 0.25), ("tube_wall", "#fff", 0.25), ("column", "#000", 0.1)):
        for it, g in cuts3.get(kind, []):
            sh.path([[P(x_, y_) for x_, y_ in r] for r in geom_rings(g)], fill=fill, stroke="#000", w=w)
    xl, yl = dm.axis_labels(xs, ys)
    for x_ in xs:
        p = P(x_, bb["ymax"])
        sh.line(p[0], p[1] - 1, p[0], p[1] - 9, 0.1, "#888", "6,1.4,1,1.4")
        dm.bubble(sh, p[0], p[1] - 12, xl[round(x_, 2)], r=2.6, pt=6.0)
    for y_ in ys:
        p = P(bb["xmin"], y_)
        sh.line(p[0] - 1, p[1], p[0] - 9, p[1], 0.1, "#888", "6,1.4,1,1.4")
        dm.bubble(sh, p[0] - 12, p[1], yl[round(y_, 2)], r=2.6, pt=6.0)
    for s in regs["sections"]:
        (ax0, ay0), (ax1, ay1) = s["line_drawing_frame"]
        p0, p1 = P(ax0, ay0), P(ax1, ay1)
        sh.line(p0[0], p0[1], p1[0], p1[1], 0.5, "#c00", "7,2,1.2,2")
        lk = s["view_direction_drawing_frame"]
        mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
        sh.path([[mid, (mid[0] + lk[0] * 12, mid[1] - lk[1] * 12)]], stroke="#c00", w=0.5, closed=False)
        for p in (p0, p1):
            dm.bubble(sh, p[0], p[1], s["name"][0], r=3.2, pt=7.5, color="#c00")
            sh.text(p[0], p[1] + 7.2 if p[1] > mid[1] else p[1] - 4.6, s["sheet"], 5.0, "normal", "#c00", "middle")
    sh.north_arrow(380, 60, model.north_deg)
    yy = 40.0
    sh.text(250, yy - 6, "절단선 (도면틀 좌표, m)", 8, "bold", "#222")
    for s in regs["sections"]:
        pl = s["plane"]
        sh.text(250, yy, "%s  %s = %.2f  바라봄 %s  (%s)" % (s["name"], pl["axis"], pl["value_drawing_frame"], ("+" if pl["look_sign"] > 0 else "−") + pl["axis"], s["sheet"]), 6.5, "normal", "#333")
        sh.text(254, yy + 4.2, s["description"], 5.6, "normal", "#666")
        yy += 11
    sh.scale_bar(300, 253 - 14)
    sh.title_block()
    base = sh.save(os.path.join(run, "sections", "S-301_section_locator_plan"))
    reg["section_locator"] = {"files": {e: {"path": base + "." + e, "sha256": V1.sha_file(base + "." + e)} for e in ("svg", "pdf", "png")}}
    json.dump(reg, open(os.path.join(run, "sections", "section_line_registry.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"elevations": reg["elevations"], "frame": reg["frame"], "model": reg["model"]}, open(os.path.join(run, "elevations", "elevation_registry.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("VIEWS %s DONE" % cfg.EDITION)


if __name__ == "__main__":
    main()

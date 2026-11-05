"""C-T14D 3·4단계: 4면 입면 + 단면 A~D + 단면 키플랜 (3D 모델에서 직접 생성).

    python -I tools/t14d_make_views.py --run <도면집 후보 폴더> --glb <전층.glb>

입면은 건물 면에 수직으로 정투영하고, 이름은 그 면 법선의 실제 방위(도면 north_deg 기준)에서 가장 가까운 방위로 붙인다.
단면 위치는 모델 객체(T1~T4, 캡슐)의 실제 위치에서 계산한다. 모든 시트는 SVG·PDF·PNG와 source 객체 목록·해시를 함께 낸다.
"""
import argparse
import hashlib
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
from t14d_sheet import Sheet, geom_lines, geom_rings  # noqa: E402

W_STRUCT = {"slab": 0.25, "roof": 0.25, "core_wall": 0.25, "tube_wall": 0.25}
COMPASS = [("N", 0), ("NE", 45), ("E", 90), ("SE", 135), ("S", 180), ("SW", 225), ("W", 270), ("NW", 315)]


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def compass_name(deg):
    deg %= 360
    names16 = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return names16[int((deg + 11.25) // 22.5) % 16]


def card4(deg):
    return ["N", "E", "S", "W"][int(((deg % 360) + 45) // 90) % 4]


CARD_KO = {"N": "북", "E": "동", "S": "남", "W": "서"}


def obj_center(model, name):
    o = next(o for o in model.objects if o["name"] == name)
    T = model.tris(o).reshape(-1, 3)
    return (T[:, 0].min() + T[:, 0].max()) / 2, (T[:, 1].min() + T[:, 1].max()) / 2


def obj_hash(model, objs):
    h = hashlib.sha256()
    for o in sorted(objs, key=lambda o: o["name"]):
        h.update(o["name"].encode("utf-8"))
        h.update(np.round(model.tris(o), 4).tobytes())
    return h.hexdigest()


def level_lines(sh, model, x_l, x_r, y_of, z_lo, z_hi, roof_z):
    ffl0 = model.floors["1F"]
    for name, z in sorted(model.floors.items(), key=lambda kv: kv[1]):
        if z < z_lo or z > z_hi:
            continue
        y = y_of(z)
        sh.line(x_l, y, x_r, y, 0.1, "#999", "2.2,1.6")
        lab = "%s  %+.3f" % (name, z - ffl0)
        sh.text(x_l - 1, y - 0.8, lab, 6, "normal", "#444", "end")
        sh.text(x_r + 1, y - 0.8, lab, 6, "normal", "#444", "start")
    y = y_of(roof_z)
    sh.line(x_l, y, x_r, y, 0.1, "#999", "2.2,1.6")
    sh.text(x_l - 1, y - 0.8, "ROOF  %+.3f" % (roof_z - ffl0), 6, "bold", "#444", "end")
    sh.text(x_r + 1, y - 0.8, "ROOF  %+.3f" % (roof_z - ffl0), 6, "bold", "#444", "start")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--glb", required=True)
    a = ap.parse_args()
    run = os.path.abspath(a.run)
    model = bv.Model(os.path.join(run, "model_cache"), os.path.join(run, "raw_slices", "camera_bounds.json"))
    bb = model.building
    ffl0 = model.floors["1F"]
    roof_z = max(o["zmax"] for o in model.objects if o["kind"] == "roof")
    reg = {"book": "C_T14D", "model": {"path": os.path.abspath(a.glb), "sha256": sha_file(a.glb)}, "frame": {"theta_deg": math.degrees(model.theta), "north_deg": model.north_deg},
           "gl": {"definition": "기준 GL = 1F FFL = ±0.000 (층판 윗면). 대지 지형·옹벽은 모델에 없음(UNVERIFIED)", "z_1F": ffl0}, "elevations": [], "sections": []}

    # ── 입면 4장 ──────────────────────────────────────────────────────────────────────────────
    ELEVS = [(90.0, "E-201"), (180.0, "E-202"), (270.0, "E-203"), (0.0, "E-204")]     # 도면틀의 건물 면 법선 방위(+x, −y, −x, +y)
    scale = 400
    k = 1000.0 / scale
    pad = 0.3
    for beta, sid in ELEVS:
        cb = (beta - model.north_deg) % 360
        card = card4(cb)
        el = bv.elevation(model, beta)
        x0, y0, x1, y1 = el["extent"]
        zlim = box(x0 - 1, ffl0, x1 + 1, roof_z + pad)
        sh = Sheet(sid, "%s측 입면도 (%s ELEVATION)" % (CARD_KO[card], {"N": "NORTH", "E": "EAST", "S": "SOUTH", "W": "WEST"}[card]), scale,
                   "MODEL_GEOMETRY · 외피 접합·재료 상세 미검증",
                   subtitle="정면 방위 %s %.1f° (면 법선, 진북 기준) · 건물 면에 수직 정투영 · 기준 GL = 1F FFL ±0.000" % (compass_name(cb), cb),
                   extra_lines=["원천: A-FACD·A-STRC·A-FLOR·A-CORE-TUBE·A-VERT·A-ROOF 모델 객체. 3D에 없는 유리 패널·루버·출입구는 그리지 않음",
                                "가림 처리 벡터(숨은 선 제거). 대지 지형·지하 옹벽 미표시(모델에 없음)"])
        ucen = (x0 + x1) / 2
        y_ground = 238.0
        X = lambda u: 215.0 + (u - ucen) * k
        Y = lambda z: y_ground - (z - ffl0) * k
        level_lines(sh, model, X(x0) - 6, X(x1) + 6, Y, ffl0 + 0.1, roof_z - 0.1, roof_z)
        drawn, drawq = [], []
        for o, vis, edge in el["items"]:
            e = edge.intersection(zlim)
            lines = geom_lines(e)
            if not lines:
                continue
            drawn.append(o)
            drawq.append((W_STRUCT.get(o["kind"], 0.15), lines))
        sil = el["silhouette"].intersection(zlim)
        sh.path([[(X(u), Y(z)) for u, z in ln] for ln in geom_lines(sil.boundary)], stroke="#000", w=0.45, closed=False)      # 굵은 선부터(같은 선분 중복 제거가 굵은 쪽을 남긴다)
        for w, lines in sorted(drawq, key=lambda t: -t[0]):
            sh.path([[(X(u), Y(z)) for u, z in ln] for ln in lines], stroke="#222", w=w, closed=False)
        sh.line(12, Y(ffl0), 408, Y(ffl0), 0.6, "#000")
        sh.text(X(x1) + 1, Y(ffl0) + 4.5, "GL ±0.000", 6.5, "bold", "#111")
        for i in range(0, int((X(x1) - X(x0)) // 3) + 6):                                # GL 아래 지반 표시선(해칭 아님, 지반은 모델에 없음)
            xx = X(x0) - 8 + i * 3
            sh.line(xx, Y(ffl0) + 0.4, xx - 2, Y(ffl0) + 2.4, 0.08, "#bbb")
        sh.scale_bar(300, 253)
        sh.title_block()
        base = sh.save(os.path.join(run, "02_elevations", "%s_%s_elevation" % (sid, {"N": "north", "E": "east", "S": "south", "W": "west"}[card])))
        reg["elevations"].append({"sheet": sid, "name": card, "compass_of_face_normal_deg": round(cb, 2), "compass16": compass_name(cb), "drawing_bearing_of_view_deg": beta,
                                  "view_direction_in_drawing_frame": [round(float(v), 6) for v in el["depth"]], "projection": "orthographic, perpendicular to building face",
                                  "scale": "1:%d" % scale, "extent_m": [round(float(v), 3) for v in el["extent"]],
                                  "source_objects": sorted({o["name"] for o in drawn}), "source_count": len(drawn),
                                  "geometry_sha256": obj_hash(model, drawn), "files": {e: {"path": base + "." + e, "sha256": sha_file(base + "." + e)} for e in ("svg", "pdf", "png")}})
        print("ELEV", sid, card, "%.1f°" % cb, "objects", len(drawn))

    # ── 단면 A~D ─────────────────────────────────────────────────────────────────────────────
    cx_mid, cy_mid = (bb["xmin"] + bb["xmax"]) / 2, (bb["ymin"] + bb["ymax"]) / 2
    t1x, _ = obj_center(model, "A-CORE-TUBE_T1")
    t3x, _ = obj_center(model, "A-CORE-TUBE_T3")
    capx, _ = obj_center(model, "A-CORE-TUBE_capW")
    t2x, _ = obj_center(model, "A-CORE-TUBE_T2")
    t4x, _ = obj_center(model, "A-CORE-TUBE_T4")
    SECS = [("A", "S-302", "x", cx_mid, +1, "건물 중앙 종단면 (층판·코어·튜브 관통)"),
            ("B", "S-303", "y", cy_mid, +1, "A–A와 직교하는 중앙 횡단면"),
            ("C", "S-304", "x", (t1x + t3x + capx) / 3, +1, "수직동선 특화: T1 나선 램프 + 서측 캡슐 + T3 승강기 튜브"),
            ("D", "S-305", "x", (t2x + t4x) / 2, +1, "튜브·보이드 특화: T2 빛 튜브 + T4 승강기 튜브")]
    z_lo = min(o["zmin"] for o in model.bld)
    for nm, sid, ax, val, ls, desc in SECS:
        sec = bv.section(model, ax, val, ls)
        x0, y0, x1, y1 = sec["extent"]
        hm = (roof_z + 0.4) - (z_lo - 0.2)
        sc = 400 if hm * 2.5 <= 236 else 500
        kk = 1000.0 / sc
        ucen = (x0 + x1) / 2
        X = lambda u: 215.0 + (u - ucen) * kk
        Y = lambda z: 8.0 + (roof_z + 0.4 - z) * kk
        sh = Sheet(sid, "단면도 %s–%s (SECTION %s–%s)" % (nm, nm, nm, nm), sc, "MODEL_GEOMETRY · 실제 메시 절단",
                   subtitle="%s · 절단면 %s = %.3f (도면틀) · 바라보는 방향 %s" % (desc, ax, val, ("+" if ls > 0 else "−") + ax),
                   extra_lines=["절단 포셰 = 모델 메시와 절단면의 교선(층 평면을 쌓은 가짜 단면 아님). 절단면 너머 객체는 가림 처리 윤곽선",
                                "층 레벨·슬래브 두께는 A-FLOR 층판에서 읽음. 접합·재료 상세 미검증. 지반·옹벽은 모델에 없어 표시하지 않음(UNVERIFIED)"])
        level_lines(sh, model, X(x0) - 6, X(x1) + 6, Y, z_lo, roof_z - 0.1, roof_z)
        drawn, drawq = [], []
        for o, vis, edge in sec["items"]:
            lines = geom_lines(edge)
            if not lines:
                continue
            drawn.append(o)
            drawq.append((0.12 if o["kind"] in ("column", "facade") else 0.18, lines))
        for w, lines in sorted(drawq, key=lambda t: -t[0]):
            sh.path([[(X(u), Y(z)) for u, z in ln] for ln in lines], stroke="#444", w=w, closed=False)
        cut_objs = []
        for o, poly in sec["cuts"]:
            sh.path([[(X(u), Y(z)) for u, z in r] for r in geom_rings(poly)], fill="#111", stroke="#000", w=0.35)
            cut_objs.append({"name": o["name"], "kind": o["kind"], "name_ko": o["name_ko"], "cut_area_m2": round(poly.area, 3)})
        sh.line(12, Y(ffl0), 408, Y(ffl0), 0.35, "#555", "5,2")
        sh.text(X(x1) + 1, Y(ffl0) + 3.5, "GL ±0.000", 6, "bold", "#444")
        sh.scale_bar(300, 253)
        sh.title_block()
        names = sorted({c["name_ko"] for c in cut_objs if c["kind"] in ("tube_wall", "core_wall", "shaft", "ramp", "stair")})
        sh.text(14, 20, "절단 통과 요소: " + ", ".join(names[:9]) + (" 외" if len(names) > 9 else ""), 6, "normal", "#555")
        base = sh.save(os.path.join(run, "03_sections", "%s_section_%s-%s" % (sid, nm, nm)))
        # 절단선을 월드 좌표로(키플랜·재현용)
        if ax == "x":
            p0, p1 = (val, bb["ymin"] - 6), (val, bb["ymax"] + 6)
        else:
            p0, p1 = (bb["xmin"] - 6, val), (bb["xmax"] + 6, val)
        c_, s_ = math.cos(model.theta), math.sin(model.theta)
        to_world = lambda p: (round(p[0] * c_ - p[1] * s_, 4), round(p[0] * s_ + p[1] * c_, 4))
        reg["sections"].append({"sheet": sid, "name": "%s–%s" % (nm, nm), "description": desc, "plane": {"axis": ax, "value_drawing_frame": round(val, 4), "look_sign": ls},
                                "line_drawing_frame": [list(map(lambda v: round(v, 3), p0)), list(map(lambda v: round(v, 3), p1))],
                                "line_world": [to_world(p0), to_world(p1)], "view_direction_drawing_frame": [float(v) for v in sec["look"]],
                                "view_compass_deg": round((math.degrees(math.atan2(sec["look"][0], sec["look"][1])) - model.north_deg) % 360, 2),
                                "scale": "1:%d" % sc, "cut_elements": cut_objs, "visible_source_count": len(drawn), "visible_source_objects": sorted({o["name"] for o in drawn}),
                                "geometry_sha256": obj_hash(model, [c for c in model.bld if c["name"] in {o["name"] for o in drawn} | {c_["name"] for c_ in cut_objs}]),
                                "files": {e: {"path": base + "." + e, "sha256": sha_file(base + "." + e)} for e in ("svg", "pdf", "png")}})
        print("SEC", sid, nm, "1:%d" % sc, "cut elements", len(cut_objs), "visible", len(drawn))

    # ── 키플랜 ───────────────────────────────────────────────────────────────────────────────
    sl = pc.load_slice(os.path.join(run, "raw_slices"), "3F")
    cuts = pc.cut_geometries(sl)
    sh = Sheet("S-301", "단면 키플랜 (SECTION LOCATOR)", 400, "MODEL_GEOMETRY · 절단선은 모델 좌표에서 계산", subtitle="3F 절단 평면 위에 A–A ~ D–D 절단선 표시 · 화살표 = 바라보는 방향",
               extra_lines=["절단선 좌표·방향·source 요소는 section_line_registry.json 에 기록", "1층 마스터와 같은 좌표틀(north_deg %.1f°)" % model.north_deg])
    kk = 2.5
    ox = 150.0 - (bb["xmin"] + bb["xmax"]) / 2 * kk
    oy = 150.0 + (bb["ymin"] + bb["ymax"]) / 2 * kk
    P = lambda x, y: (ox + x * kk, oy - y * kk)
    slab = bv._union([pc.polygons_from_segments(p["segments"]) for p in sl["projection"]])
    sh.path([[P(x, y) for x, y in r] for r in geom_rings(slab)], fill="#f4f4f4", stroke="#555", w=0.3)
    for kind, fill, w in (("core_wall", "#222", 0.25), ("tube_wall", "#fff", 0.25), ("column", "#000", 0.1)):
        for it, g in cuts.get(kind, []):
            sh.path([[P(x, y) for x, y in r] for r in geom_rings(g)], fill=fill, stroke="#000", w=w)
    for s_ in reg["sections"]:
        (ax0, ay0), (ax1, ay1) = s_["line_drawing_frame"]
        p0, p1 = P(ax0, ay0), P(ax1, ay1)
        sh.line(p0[0], p0[1], p1[0], p1[1], 0.5, "#c00", "7,2,1.2,2")
        lk = s_["view_direction_drawing_frame"]
        mid = ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2)
        arrow = (mid[0] + lk[0] * 12, mid[1] - lk[1] * 12)
        sh.path([[mid, arrow]], stroke="#c00", w=0.5, closed=False)
        nm = s_["name"][0]
        for p, _ in ((p0, 0), (p1, 1)):
            sh.path([[(p[0] - 3.2, p[1] - 3.2), (p[0] + 3.2, p[1] - 3.2), (p[0] + 3.2, p[1] + 3.2), (p[0] - 3.2, p[1] + 3.2)]], fill="#fff", stroke="#c00", w=0.3)
            sh.text(p[0], p[1] + 1.4, nm, 8, "bold", "#c00", "middle")
    sh.north_arrow(380, 60, model.north_deg)
    yy = 40.0
    sh.text(250, yy - 6, "절단선 (도면틀 좌표, m)", 8, "bold", "#222")
    for s_ in reg["sections"]:
        pl = s_["plane"]
        sh.text(250, yy, "%s  %s = %.2f  바라봄 %s  (방위 %.0f°)" % (s_["name"], pl["axis"], pl["value_drawing_frame"], ("+" if pl["look_sign"] > 0 else "−") + pl["axis"], s_["view_compass_deg"]), 6.5, "normal", "#333")
        sh.text(254, yy + 4.2, s_["description"], 5.5, "normal", "#666")
        yy += 11
    sh.scale_bar(300, 253)
    sh.title_block()
    base = sh.save(os.path.join(run, "03_sections", "S-301_section_locator_plan"))
    reg["section_locator"] = {"files": {e: {"path": base + "." + e, "sha256": sha_file(base + "." + e)} for e in ("svg", "pdf", "png")}}
    json.dump(reg, open(os.path.join(run, "03_sections", "section_line_registry.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"elevations": reg["elevations"], "frame": reg["frame"], "gl": reg["gl"], "model": reg["model"]}, open(os.path.join(run, "02_elevations", "elevation_registry.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("VIEWS DONE", run)


if __name__ == "__main__":
    main()

"""C-T14D 5단계: 확대 상세도 D-401 ~ D-410 (모델 기하 근거, 사실성 등급 명시).

각 시트 = 왼쪽 평면 절단 패널 + 오른쪽 단면 패널. 평면은 GLB(상층·튜브) 또는 1층 마스터 slice(코어 내부·선큰·화물)에서,
단면은 GLB 메시 절단(book_views.section)에서 가져와 창으로 잘라 확대한다. 재료·볼트·방수 등 모델에 없는 것은 그리지 않는다.

    python -I tools/t14d_make_details.py --run <도면집 후보 폴더> --glb <전층.glb>
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
from shapely.geometry import LineString, Point, box  # noqa: E402
from shapely.ops import unary_union  # noqa: E402
import book_views as bv  # noqa: E402
from t14d_sheet import Sheet, geom_lines, geom_rings  # noqa: E402

PLAN_KINDS = {"core_wall", "tube_wall", "shaft", "column", "stair", "ramp", "facade", "roof"}


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def obj(model, name):
    return next(o for o in model.objects if o["name"] == name)


def obj_bbox(model, o):
    T = model.tris(o).reshape(-1, 3)
    return T[:, 0].min(), T[:, 1].min(), T[:, 0].max(), T[:, 1].max()


def center(b):
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def top_outline(model, o):
    T = model.tris(o)
    tris = [bv.Polygon([(t[0][0], t[0][1]), (t[1][0], t[1][1]), (t[2][0], t[2][1])]) for t in T]
    tris = [t for t in tris if t.area > 1e-9]
    return unary_union(tris).buffer(0.001, join_style=2).buffer(-0.001, join_style=2)


class Detail:
    def __init__(self, sid, title, grade, scale, plan, section, notes):
        self.sid, self.title, self.grade, self.scale, self.plan, self.section, self.notes = sid, title, grade, scale, plan, section, notes


def draw_plan_panel(sh, run, model, spec, cx, cy, k, half, px, py, reg):
    """평면 패널. 창: 중심 (cx,cy)에서 ±half m. 화면 중심 (px,py)."""
    win = box(cx - half, cy - half, cx + half, cy + half)
    X = lambda x: px + (x - cx) * k
    Y = lambda y: py - (y - cy) * k
    sh.path([[(px - half * k, py - half * k), (px + half * k, py - half * k), (px + half * k, py + half * k), (px - half * k, py + half * k)]], stroke="#aaa", w=0.15)
    used = []
    labels = []
    if spec["source"] == "glb":
        z = spec["z"]
        ffl = spec["ffl"]
        slab = [(o, p) for o, p in bv.plan_cut(model, ffl - 0.05, {"slab"}, (cx - half, cy - half, cx + half, cy + half))]
        for o, p in slab:
            g = p.intersection(win)
            sh.path([[(X(x), Y(y)) for x, y in r] for r in geom_rings(g)], fill="#f1f1f1", stroke="#777", w=0.25)
            used.append(o["name"])
        cuts = bv.plan_cut(model, z, PLAN_KINDS, (cx - half, cy - half, cx + half, cy + half))
        for o, p in cuts:
            g = p.intersection(win)
            if g.is_empty:
                continue
            kind = o["kind"]
            if kind in ("stair", "ramp", "shaft"):                                       # 샤프트·에스컬레이터·램프는 벽이 아니라 윤곽선
                sh.path([[(X(x), Y(y)) for x, y in r] for r in geom_rings(g)], fill="#fff", stroke="#444", w=0.2)
            elif kind == "facade":
                sh.path([[(X(x), Y(y)) for x, y in r] for r in geom_rings(g)], fill="#555", stroke="#222", w=0.15)
            else:
                sh.path([[(X(x), Y(y)) for x, y in r] for r in geom_rings(g)], fill="#111", stroke="#000", w=0.45)
            used.append(o["name"])
            if kind in ("tube_wall", "shaft", "stair", "ramp", "core_wall"):
                c = g.representative_point() if g.geom_type != "Polygon" else g.centroid
                labels.append((c.x, c.y, o["name_ko"]))
        for o in model.bld:                                                           # 절단선 아래에 있는 요소(예: 지붕 구조 표식)의 윗면 윤곽
            if spec.get("top_kinds") and o["kind"] in spec["top_kinds"] and o["zmax"] < z + 0.01:
                bb = obj_bbox(model, o)
                if bb[2] < cx - half or bb[0] > cx + half or bb[3] < cy - half or bb[1] > cy + half:
                    continue
                g = top_outline(model, o).intersection(win)
                sh.path([[(X(x), Y(y)) for x, y in r] for r in geom_rings(g)], fill="#e6e6e6", stroke="#555", w=0.2)
                used.append(o["name"])
    else:                                                                             # 1층 마스터 slice(코어 내부·선큰·화물)
        sl = spec["slice"]
        cuts = pc.cut_geometries(sl)
        for kind in ("slab",):
            pass
        for it, g in cuts.get("column", []):
            sh.path([[(X(x), Y(y)) for x, y in r] for r in geom_rings(g.intersection(win))], fill="#111", stroke="#000", w=0.3)
        for kind, fill, w in (("core_wall", "#111", 0.45), ("tube_wall", "#111", 0.45), ("partition_wall", "#222", 0.25), ("shaft", "#fff", 0.2), ("stair", "#fff", 0.15)):
            for it, g in cuts.get(kind, []):
                gg = g.intersection(win)
                if gg.is_empty:
                    continue
                sh.path([[(X(x), Y(y)) for x, y in r] for r in geom_rings(gg)], fill=fill, stroke="#000", w=w)
                used.append(it["name"])
                if kind in ("shaft", "tube_wall", "core_wall") and spec.get("label_kinds") and kind in spec["label_kinds"]:
                    labels.append((gg.centroid.x, gg.centroid.y, it["name_ko"]))
        for s in sl.get("symbols", []):
            g = pc.polygons_from_segments(s.get("segments", [])).intersection(win)
            if not g.is_empty:
                sh.path([[(X(x), Y(y)) for x, y in r] for r in geom_rings(g)], fill="#fff", stroke="#444", w=0.12)
                used.append(s["name"])
        for s in sl["context"].get("sunken_stair", []):
            g = pc.polygons_from_segments(s["segments"])
            gg = g.intersection(win)
            if not gg.is_empty:
                sh.path([[(X(x), Y(y)) for x, y in r] for r in geom_rings(gg)], fill="#f7f7f7", stroke="#444", w=0.3)
                b = g.bounds
                n = int(s["props"].get("treads", 12))
                for i in range(1, n):
                    xx = b[0] + (b[2] - b[0]) * i / n
                    ln = LineString([(xx, b[1]), (xx, b[3])]).intersection(win)
                    for l2 in geom_lines(ln):
                        sh.path([[(X(x), Y(y)) for x, y in l2]], stroke="#777", w=0.12, closed=False)
                used.append(s["props"].get("name_ko", "선큰 계단"))
        for s in sl["context"].get("spaces", []):
            if s["props"].get("use") in spec.get("space_uses", ()):
                g = pc.polygons_from_segments(s["segments"]).intersection(win)
                for ln in geom_lines(g.boundary):
                    sh.path([[(X(x), Y(y)) for x, y in ln]], stroke="#555", w=0.2, closed=False, dash="3,2")
                used.append("space:" + s["props"].get("use"))
    for x, y, t in labels:
        if cx - half < x < cx + half and cy - half < y < cy + half:
            sh.text(X(x), Y(y) + 1.0, t, 6.5, "bold", "#222", "middle", bg=True)
    sh.north_arrow(px + half * k - 12, py - half * k + 14, model.north_deg, r=5.0)
    return sorted(set(used))


def draw_section_panel(sh, model, sec, uc, z0, z1, k, half, px, py_top):
    X = lambda u: px + (u - uc) * k
    Y = lambda z: py_top + (z1 - z) * k
    win = box(uc - half, z0, uc + half, z1)
    sh.path([[(X(uc - half), Y(z1)), (X(uc + half), Y(z1)), (X(uc + half), Y(z0)), (X(uc - half), Y(z0))]], stroke="#aaa", w=0.15)
    for name, z in sorted(model.floors.items(), key=lambda kv: kv[1]):
        if z0 < z < z1:
            sh.line(X(uc - half), Y(z), X(uc + half), Y(z), 0.1, "#999", "2.2,1.6")
            sh.text(X(uc - half) + 4.0, Y(z) - 0.8, "%s %+.3f" % (name, z - model.floors["1F"]), 6, "normal", "#444", bg=True)
    used = []
    for o, vis, edge in sec["items"]:
        e = edge.intersection(win)
        ls = geom_lines(e)
        if ls:
            used.append(o["name"])
            sh.path([[(X(u), Y(z)) for u, z in ln] for ln in ls], stroke="#444", w=0.12 if o["kind"] in ("column", "facade") else 0.2, closed=False)
    cut_names = []
    for o, poly in sec["cuts"]:
        g = poly.intersection(win)
        if g.is_empty or g.area < 1e-6:
            continue
        sh.path([[(X(u), Y(z)) for u, z in r] for r in geom_rings(g)], fill="#111", stroke="#000", w=0.3)
        used.append(o["name"])
        cut_names.append((o["name"], o["kind"], o["name_ko"]))
    return sorted(set(used)), cut_names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--glb", required=True)
    a = ap.parse_args()
    run = os.path.abspath(a.run)
    model = bv.Model(os.path.join(run, "model_cache"), os.path.join(run, "raw_slices", "camera_bounds.json"))
    master = pc.load_json(os.path.join(run, "reference_1F", "floor_1F_slice.json"))
    mb = pc.load_json(os.path.join(run, "reference_1F", "camera_bounds.json"))["building"]
    F = model.floors
    ffl1 = F["1F"]
    reg = {"book": "C_T14D", "details": [], "model_sha256": sha_file(a.glb)}

    def story(f):
        return F[f]

    bb = model.building
    # ── 상세 정의 (요소 위치는 모델에서 계산) ─────────────────────────────────────────────────────
    t1 = obj(model, "A-CORE-TUBE_T1"); t2 = obj(model, "A-CORE-TUBE_T2"); t3 = obj(model, "A-CORE-TUBE_T3"); capw = obj(model, "A-CORE-TUBE_capW"); fr = obj(model, "A-CORE-TUBE_FR")
    esc8 = [o for o in model.objects if o["name"].startswith("A-VERT-ESCL_8F-9F")]
    fac6 = [o for o in model.objects if o["name"].startswith("A-FACD_valley_glass_6F")]
    pad = obj(model, "A-ROOF_rescue_pad")
    slab_roof = obj(model, "A-ROOF_slab")
    capbb = obj_bbox(model, capw)
    sunk = master["context"]["sunken_stair"][0]
    sg = pc.polygons_from_segments(sunk["segments"]).bounds
    corerD = next(g for it, g in pc.cut_geometries(master)["core_wall"] if it["name_ko"].startswith("코어 D"))
    frm = next(g for it, g in pc.cut_geometries(master)["shaft"] if "FR" in it["name_ko"])

    def glb_spec(floor, center_xy, top_kinds=None):
        return {"source": "glb", "z": F[floor] + 1.5, "ffl": F[floor], "floor": floor, "center": center_xy, "top_kinds": top_kinds}

    T1c, T2c, T3c = center(obj_bbox(model, t1)), center(obj_bbox(model, t2)), center(obj_bbox(model, t3))
    esc_c = center(unary_bbox([obj_bbox(model, o) for o in esc8])) if False else None
    escb = [obj_bbox(model, o) for o in esc8]
    esc_c = ((min(b[0] for b in escb) + max(b[2] for b in escb)) / 2, (min(b[1] for b in escb) + max(b[3] for b in escb)) / 2)
    facb = obj_bbox(model, fac6[0]) if fac6 else None
    fac_c = center(facb)
    fac_axis = "x" if (facb[2] - facb[0]) > (facb[3] - facb[1]) else "y"                 # 외피가 뻗은 방향에 수직인 면으로 절단
    cap_c = ((capbb[0] + capbb[2]) / 2, capbb[3] - 3.0)                                   # 캡슐 끝단(+y) 근처
    pad_c = center(obj_bbox(model, pad))

    DET = [
        ("D-401", "T1 나선 램프 확대 (평면 + 단면)", "MODEL_GEOMETRY · 장비·난간 상세 미검증", 50, glb_spec("3F", T1c), ("x", T1c[0], "3F"), ["A-VERT-SPRL_B1-6F_T1_spiral, A-CORE-TUBE_T1 모델 메시", "램프 경사·폭은 모델 형상 그대로. 난간·마감·바닥재는 모델에 없어 그리지 않음"]),
        ("D-402", "T2 빛 튜브와 층판 관통 확대", "MODEL_GEOMETRY · T2는 승객 이동로 아님", 50, glb_spec("3F", T2c), ("x", T2c[0], "3F"), ["A-CORE-TUBE_T2 + A-FLOR_s7 층판 개구", "빛 튜브의 유리·마감은 모델에 없어 그리지 않음"]),
        ("D-403", "T3 파노라마 승강기 튜브 확대 (T4 동형)", "MODEL_GEOMETRY · 승강기 제조 상세 미검증", 50, glb_spec("3F", T3c), ("x", T3c[0], "3F"), ["A-CORE-TUBE_T3, A-VERT-ELEV 카·샤프트 모델 메시", "T4는 T3와 같은 형식(위치만 다름). 승강장 문·기계 상세는 모델에 없음"]),
        ("D-404", "코어 D 진입·부속실 확대 (1층 마스터)", "MODEL_GEOMETRY(1F 마스터) · 상층 코어 BLOCKED_MISSING_SOURCE", 50,
         {"source": "master", "slice": master, "center": center(corerD.bounds), "label_kinds": ("core_wall",), "space_uses": ()}, None,
         ["1층 마스터의 코어 D(벽·부속실 칸막이·문·계단 기호)", "상층 GLB는 코어 외곽 벽만 있어 상층 코어 내부 상세는 만들지 않음(BLOCKED_MISSING_SOURCE)"]),
        ("D-405", "캡슐과 층판 접속 확대", "MODEL_GEOMETRY · 출입문 미승인(그리지 않음)", 50, glb_spec("3F", cap_c), ("y", cap_c[1], "3F"), ["A-CORE-TUBE_capW + A-FLOR 층판", "캡슐 출입구는 모델에 없고 사용자 미승인이라 벽을 닫아 둠"]),
        ("D-406", "전형층 외피와 층판 가장자리 확대 (6F)", "MODEL_GEOMETRY · 방수·커튼월 접합 미검증", 50, glb_spec("6F", fac_c), (fac_axis, fac_c[0] if fac_axis == "x" else fac_c[1], "6F"), ["A-FACD_valley_* 외피 부재 + A-FLOR_s7_6F", "실제 조인트·재료 자료가 없어 모델 형상만 표시"]),
        ("D-407", "에스컬레이터 개구 확대 (8F–9F)", "MODEL_GEOMETRY · 난간·안전 규격 미검증", 50, glb_spec("8F", esc_c), ("x", esc_c[0], "8F"), ["A-VERT-ESCL_8F-9F_* 모델 메시 + 층판 개구", "에스컬레이터 기계·난간은 모델에 없음"]),
        ("D-408", "선큰 계단·마당 연결 확대 (1층 마스터)", "MODEL_GEOMETRY(1F 마스터) · 지반·옹벽 미검증", 100,
         {"source": "master", "slice": master, "center": ((sg[0] + sg[2]) / 2, (sg[1] + sg[3]) / 2), "label_kinds": (), "space_uses": ("sunken",)}, None,
         ["선큰 계단 %d단, 하향 방향 %s, FL -5.5 m (마스터 속성 그대로)" % (int(sunk["props"].get("treads", 12)), sunk["props"].get("down")), "계단 폭·단높이는 속성에 없어 단 수·하향 방향·윤곽만 표시. 1:50로는 창에 안 들어가 1:100"]),
        ("D-409", "화물 승강기·하역 동선 확대", "SCHEMATIC · 화물 기계·서비스 동선 미검증", 50,
         {"source": "master", "slice": master, "center": center(frm.bounds), "label_kinds": ("shaft",), "space_uses": ()}, ("x", center(obj_bbox(model, fr))[0], "1F", center(obj_bbox(model, fr))),
         ["1층 마스터 화물 승강기 FR 샤프트 + GLB A-CORE-TUBE_FR 단면(평면과 단면의 좌표틀이 다르므로 단면 창은 GLB 위치로)", "단면에는 GLB의 FR 샤프트 벽과 층판만 있고 승강 카·기계·승강장 문은 모델에 없음. 화물 기계·하역 동선은 SCHEMATIC"]),
        ("D-410", "지붕·상층 후퇴부 확대", "MODEL_GEOMETRY · 방수·지붕 마감 미검증", 50,
         {"source": "glb", "z": 71.5, "ffl": F["15F"], "floor": "15F", "center": pad_c, "top_kinds": {"roof"}}, ("x", pad_c[0], "15F"),
         ["A-ROOF_slab, A-ROOF_rescue_pad·mark 모델 메시", "방수층·지붕 마감·배수는 모델에 없어 그리지 않음"]),
    ]

    for sid, title, grade, scale, plan, section, notes in DET:
        k = 1000.0 / scale
        sh = Sheet(sid, title, scale, grade, subtitle="평면: %s 절단(%s)" % (plan.get("floor", "1F 마스터") + (" +1.5 m" if plan["source"] == "glb" else ""), plan["source"].upper()) + ("  ·  단면: 평면 위치를 지나는 수직 절단" if section else ""), extra_lines=notes[:2])
        half = 9.0 / 2 if scale == 50 else 18.0 / 2
        cx, cy = plan["center"]
        px, py = 104.0, 24.0 + 90.0
        sh.text(14, 20, "평면 PLAN", 8, "bold", "#222")
        used_plan = draw_plan_panel(sh, run, model, plan, cx, cy, k, half, px, py, reg)
        used_sec, cut_names = [], []
        sec_meta = None
        if section:
            ax, val, fl = section[:3]
            sc_center = section[3] if len(section) > 3 else (cx, cy)                      # 평면(1층 마스터 좌표)과 단면(GLB 도면틀)의 좌표가 다르면 단면 창은 GLB 위치로
            sec = bv.section(model, ax, val, +1)
            uc = cy if ax == "x" else cx                                                   # 단면 가로축 = 오른쪽 벡터 방향
            # right 벡터 기준 u 좌표 중심: 절단면 위 요소 중심을 오른쪽 벡터에 투영
            rt = sec["right"]
            uc = float(sc_center[0] * rt[0] + sc_center[1] * rt[1])
            z0 = F[fl] - 0.4 if sid != "D-409" else F["1F"] - 0.4
            hh = 11.6 if scale == 50 else 23.0
            z1 = z0 + hh
            sh.text(226, 20, "단면 SECTION  (%s = %.2f, 바라봄 +%s)" % (ax, val, ax), 8, "bold", "#222")
            used_sec, cut_names = draw_section_panel(sh, model, sec, uc, z0, z1, k, half if scale == 50 else half, 316.0, 24.0)
            sec_meta = {"axis": ax, "value_drawing_frame": round(val, 4), "look_sign": 1, "z_window": [round(z0, 3), round(z1, 3)]}
        else:
            sh.text(226, 20, "단면 SECTION", 8, "bold", "#222")
            sh.text(316, 120, "단면 없음", 12, "bold", "#999", "middle")
            sh.text(316, 128, "BLOCKED_MISSING_SOURCE", 8, "normal", "#999", "middle")
            sh.text(316, 136, "(상층 GLB에 코어·선큰 내부 단면 근거 없음)", 6.5, "normal", "#999", "middle")
        sh.scale_bar(24, 253, meters=(0, 1, 2, 5) if scale == 50 else (0, 2, 5, 10))
        sh.title_block()
        base = sh.save(os.path.join(run, "04_details", "%s_%s" % (sid, "".join(ch if ch.isalnum() else "_" for ch in title.split(" ")[0]))))
        names = sorted(set(used_plan) | set(used_sec))
        reg["details"].append({"sheet": sid, "title": title, "grade": grade, "scale": "1:%d" % scale, "plan": {"source": plan["source"], "center": [round(cx, 3), round(cy, 3)], "window_m": 2 * half,
                                "cut_height": (round(plan["z"], 3) if plan["source"] == "glb" else "1F master 1.5 m"), "source_objects": used_plan},
                               "section": sec_meta, "section_cut_elements": [{"name": n, "kind": kd, "name_ko": nk} for n, kd, nk in cut_names], "section_visible_objects": used_sec,
                               "notes": notes, "files": {e: {"path": base + "." + e, "sha256": sha_file(base + "." + e)} for e in ("svg", "pdf", "png")}})
        print("DETAIL", sid, "1:%d" % scale, "plan objs", len(used_plan), "sec objs", len(used_sec), "cut", len(cut_names))
    json.dump(reg, open(os.path.join(run, "04_details", "detail_registry.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("DETAILS DONE")


if __name__ == "__main__":
    main()

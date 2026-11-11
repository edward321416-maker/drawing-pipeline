"""V2 상세도 D-401 ~ D-410 (재설계).

각 시트 = 평면(왼쪽) + 단면(오른쪽) + 키플랜·근거 표(왼쪽 아래). 모든 치수는 모델에서 계산한다(숫자 직접 입력 없음).
절단 포셰는 해칭(재료 미확정 표시), 레벨 기호, 층고·슬래브 두께 치수, 요소 치수(지름·벽 두께·폭·경사), 호출 시트 참조를 가진다.
등급: MODEL DETAIL(모델 메시에서 직접) / CONCEPT DETAIL(제안) / UNRESOLVED DETAIL(근거 부재, 그리지 않음).

    python -I tools/t14e_make_details.py --run <V2 루트> --glb <glb>
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
from shapely import affinity  # noqa: E402
from shapely.geometry import LineString, Point, Polygon, box  # noqa: E402
from shapely.ops import unary_union  # noqa: E402
import book_views as bv  # noqa: E402
import t14d_sheet as _ts  # noqa: E402
from t14g import config as cfg, modelsrc, registry as sheetreg, truth  # noqa: E402
cfg.apply(_ts)
from t14d_sheet import Sheet, geom_lines, geom_rings  # noqa: E402
import t14d_make_views as V1  # noqa: E402
import t14e_dims as dm  # noqa: E402
from t14e_make_views import r5, level_lines  # noqa: E402

PLAN_KINDS = {"core_wall", "tube_wall", "shaft", "column", "stair", "ramp", "facade", "roof"}
PX, PY, PHALF_M = 104.0, 112.0, 4.5       # 평면 패널 중심(mm), 한 변 = 2×PHALF_M m (1:50 → 180 mm)
SX, STOP = 304.0, 22.0                    # 단면 패널 중심 x, 위 y


def hatch(sh, polys_mm, spacing=1.7, angle=45.0, w=0.05, color="#777"):
    """시트 좌표(mm) 폴리곤 안에 사선 해칭(재료 미확정을 뜻하는 일반 절단 표시)."""
    for g in polys_mm:
        if g.is_empty:
            continue
        x0, y0, x1, y1 = g.bounds
        r = math.hypot(x1 - x0, y1 - y0)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        n = int(r / spacing) + 2
        ln = []
        for i in range(-n, n + 1):
            base = LineString([(cx - r, cy + i * spacing), (cx + r, cy + i * spacing)])
            seg = affinity.rotate(base, angle, origin=(cx, cy))
            inter = seg.intersection(g)
            ln += geom_lines(inter)
        if ln:
            sh.path(ln, stroke=color, w=w, closed=False)


def poly_mm(g, X, Y):
    out = []
    for p in (g.geoms if hasattr(g, "geoms") else [g]):
        if p.geom_type != "Polygon" or p.is_empty:
            continue
        out.append(Polygon([(X(x), Y(y)) for x, y in p.exterior.coords], [[(X(x), Y(y)) for x, y in r.coords] for r in p.interiors]))
    return out


def obj_of(model, name):
    return next(o for o in model.objects if o["name"] == name)


def bbox_of(model, o):
    T = model.tris(o).reshape(-1, 3)
    return T[:, 0].min(), T[:, 1].min(), T[:, 0].max(), T[:, 1].max(), T[:, 2].min(), T[:, 2].max()


def top_outline(model, o):
    T = model.tris(o)
    tris = [Polygon([(t[0][0], t[0][1]), (t[1][0], t[1][1]), (t[2][0], t[2][1])]) for t in T]
    u = unary_union([t for t in tris if t.area > 1e-9])
    return u.buffer(0.001, join_style=2).buffer(-0.001, join_style=2)


def ring_dims(g):
    """고리(튜브 벽) 폴리곤 → (바깥 지름, 안쪽 지름, 벽 두께)."""
    ps = [p for p in (g.geoms if hasattr(g, "geoms") else [g]) if p.geom_type == "Polygon"]
    p = max(ps, key=lambda q: q.area)
    ob = p.exterior.bounds
    do = max(ob[2] - ob[0], ob[3] - ob[1])
    if not p.interiors:
        return do, None, None
    ib = max((Polygon(r).bounds for r in p.interiors), key=lambda b: (b[2] - b[0]))
    di = max(ib[2] - ib[0], ib[3] - ib[1])
    return do, di, (do - di) / 2


class Ctx:
    pass


def draw_plan(sh, model, spec, c):
    """평면 패널. 반환: (사용 객체 이름 목록, 치수 항목 목록)."""
    k = 1000.0 / spec["scale"]
    half = PHALF_M if spec["scale"] == 50 else PHALF_M * 2
    cx, cy = spec["center"]
    X = lambda x: PX + (x - cx) * k
    Y = lambda y: PY - (y - cy) * k
    c.PX_, c.PY_, c.k, c.half, c.cx, c.cy = X, Y, k, half, cx, cy
    win = box(cx - half, cy - half, cx + half, cy + half)
    sh.path([[(PX - half * k, PY - half * k), (PX + half * k, PY - half * k), (PX + half * k, PY + half * k), (PX - half * k, PY + half * k)]], stroke="#aaa", w=0.15)
    used, rows = [], []
    labels = []
    if spec["source"] == "glb":
        ffl, z = spec["ffl"], spec["ffl"] + 1.5
        w4 = (cx - half, cy - half, cx + half, cy + half)
        for o, p in bv.plan_cut(model, ffl - 0.05, {"slab"}, w4):                       # 층판 윗면 + 개구
            g = p.intersection(win)
            polys = poly_mm(g, X, Y)
            sh.path([[(X(x), Y(y)) for x, y in r] for r in geom_rings(g)], fill="#f1f1f1", stroke="#777", w=0.25)
            used.append(o["name"])
            c.slab_poly = g
        for o in spec.get("top_objs", []):                                                 # 절단선 아래의 요소 윗면(램프 등)
            g = top_outline(model, o).intersection(win)
            sh.path([[(X(x), Y(y)) for x, y in r] for r in geom_rings(g)], fill="#e2e2e2", stroke="#666", w=0.2)
            used.append(o["name"])
            c.top[o["name"]] = top_outline(model, o)
        cuts = bv.plan_cut(model, z, PLAN_KINDS, w4)
        for o, p in cuts:
            g = p.intersection(win)
            if g.is_empty:
                continue
            kind = o["kind"]
            if kind in ("stair", "ramp", "shaft"):
                sh.path([[(X(x), Y(y)) for x, y in r] for r in geom_rings(g)], fill="#fff", stroke="#444", w=0.2)
            elif kind == "facade":
                sh.path([[(X(x), Y(y)) for x, y in r] for r in geom_rings(g)], fill="#444", stroke="#222", w=0.15)
            else:
                sh.path([[(X(x), Y(y)) for x, y in r] for r in geom_rings(g)], fill="#fff", stroke="#000", w=0.45)
                hatch(sh, poly_mm(g, X, Y))
            c.cut[o["name"]] = p
            used.append(o["name"])
            if kind in ("tube_wall", "shaft", "stair", "ramp", "core_wall"):
                pt = g.representative_point() if g.geom_type != "Polygon" else g.centroid
                labels.append((pt.x, pt.y, o["name_ko"]))
    else:
        sl = spec["slice"]
        cuts = pc.cut_geometries(sl)
        for kind, fill, w in (("column", "#fff", 0.3), ("core_wall", "#fff", 0.45), ("tube_wall", "#fff", 0.45), ("partition_wall", "#fff", 0.3), ("shaft", "#fff", 0.2), ("stair", "#fff", 0.15)):
            for it, g in cuts.get(kind, []):
                gg = g.intersection(win)
                if gg.is_empty:
                    continue
                sh.path([[(X(x), Y(y)) for x, y in r] for r in geom_rings(gg)], fill=fill, stroke="#000", w=w)
                if kind in ("column", "core_wall", "tube_wall", "partition_wall"):
                    hatch(sh, poly_mm(gg, X, Y))
                c.cut[it["name"]] = g
                used.append(it["name"])
                if kind in ("shaft", "tube_wall") and spec.get("label_kinds") and kind in spec["label_kinds"]:
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
                    for l2 in geom_lines(LineString([(xx, b[1]), (xx, b[3])]).intersection(win)):
                        sh.path([[(X(x), Y(y)) for x, y in l2]], stroke="#777", w=0.12, closed=False)
                c.sunk = (g.bounds, n, s["props"])
                used.append("sunken_stair")
        for s in sl["context"].get("spaces", []):
            if s["props"].get("use") in spec.get("space_uses", ()):
                g = pc.polygons_from_segments(s["segments"]).intersection(win)
                for ln in geom_lines(g.boundary):
                    sh.path([[(X(x), Y(y)) for x, y in ln]], stroke="#555", w=0.2, closed=False, dash="3,2")
                used.append("space:" + s["props"].get("use"))
    for x, y, t in labels:
        if cx - half < x < cx + half and cy - half < y < cy + half:
            yy_ = Y(y) + (-9.0 if "튜브" in t and Y(y) - 9.0 > PY - half * k + 6 else 1.0)
            sh.text(X(x), yy_, t, 6.0, "bold", "#222", "middle", bg=True)
    sh.north_arrow(PX + half * k - 12, PY - half * k + 14, model.north_deg, r=5.0)
    sh.text(PX - half * k, PY - half * k - 3.0, "평면 PLAN — %s" % spec["plan_label"], 8, "bold", "#222")
    return sorted(set(used))


def draw_section(sh, model, spec, c):
    ax, val, fl = spec["section"][:3]
    cx, cy = spec["section"][3] if len(spec["section"]) > 3 else spec["center"]
    k = 1000.0 / spec["scale"]
    half = PHALF_M if spec["scale"] == 50 else PHALF_M * 2
    sec = bv.section(model, ax, val, +1)
    rt = sec["right"]
    uc = float(cx * rt[0] + cy * rt[1])
    F = model.floors
    z0 = F[fl] - 0.4
    hh = 11.6 if spec["scale"] == 50 else 23.0
    z1 = z0 + hh
    X = lambda u: SX + (u - uc) * k
    Y = lambda z: STOP + (z1 - z) * k
    c.SX_, c.SY_, c.uc, c.sk, c.sz1 = X, Y, uc, k, z1
    win = box(uc - half, z0, uc + half, z1)
    sh.path([[(X(uc - half), Y(z1)), (X(uc + half), Y(z1)), (X(uc + half), Y(z0)), (X(uc - half), Y(z0))]], stroke="#aaa", w=0.15)
    sh.text(X(uc - half), STOP - 3.0, "단면 SECTION — %s = %.2f, 바라봄 +%s" % (ax, val, ax), 8, "bold", "#222")
    fl_in = [(n, z) for n, z in sorted(F.items(), key=lambda kv: kv[1]) if z0 < z < z1]
    used = []
    items = []
    for o, vis, edge in sec["items"]:
        ls = geom_lines(edge.intersection(win))
        if ls:
            items.append((0.12 if o["kind"] in ("column", "facade") else 0.2, ls))
            used.append(o["name"])
    for w, ls in sorted(items, key=lambda t: -t[0]):
        sh.path([[(X(u), Y(z)) for u, z in ln] for ln in ls], stroke="#444", w=w, closed=False)
    cut_names = []
    for o, poly in sec["cuts"]:
        g = poly.intersection(win)
        if g.is_empty or g.area < 1e-6:
            continue
        sh.path([[(X(u), Y(z)) for u, z in r] for r in geom_rings(g)], fill="#fff", stroke="#000", w=0.35)
        hatch(sh, poly_mm(g, X, Y))
        used.append(o["name"])
        cut_names.append((o, g))
    c.sec_cuts = cut_names
    c.sec_cuts_raw = [(o, poly) for o, poly in sec["cuts"]]                  # 창(window)으로 자르기 전 절단 폴리곤: 두께 치수는 이것으로 잰다(감사 p19-01)
    for name, z in fl_in:
        sh.line(X(uc - half), Y(z), X(uc + half), Y(z), 0.1, "#999", "2.2,1.6")
        xx = X(uc - half) + 5
        sh.path([[(xx, Y(z)), (xx + 1.6, Y(z) - 2.4), (xx - 1.6, Y(z) - 2.4)]], fill="#000", stroke="#000", w=0.1, closed=True)             # 레벨 기호
        sh.text(xx + 3.0, Y(z) - 0.8, "%s  %+.3f" % (name, r5(z - F["1F"])), 6.0, "bold", "#333", bg=True)
    # 층고 체인(오른쪽 안쪽)
    zs = [z0 + 0.0] if False else []
    pts = [z for n, z in fl_in]
    if len(pts) >= 2:
        dm.chain_v(sh, [Y(z) for z in pts], X(uc + half) - 6.0, [dm.fmt_mm(r5(b) - r5(a)) for a, b in zip(pts, pts[1:])], pt=5.8)
    return sorted(set(used)), sec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--glb", default=None, help="원본 GLB(없어도 됨: 모델 캐시에서 생성하고 캐시 해시를 기록한다)")
    a = ap.parse_args()
    run = os.path.abspath(a.run)
    model = bv.Model(os.path.join(run, "model_cache"), os.path.join(run, "raw_slices", "camera_bounds.json"))
    master = pc.load_json(os.path.join(run, "reference_1F", "floor_1F_slice.json"))
    F = model.floors
    ident = modelsrc.identity(run, a.glb)
    reg = {"book": "C_T14G", "details": [], "model_sha256": modelsrc.model_sha(run, a.glb), "model_status": ident["status"], "model_cache_sha256": ident["cache_sha256"]}
    t1, t2, t3 = obj_of(model, "A-CORE-TUBE_T1"), obj_of(model, "A-CORE-TUBE_T2"), obj_of(model, "A-CORE-TUBE_T3")
    capw, fr = obj_of(model, "A-CORE-TUBE_capW"), obj_of(model, "A-CORE-TUBE_FR")
    sprl = obj_of(model, "A-VERT-SPRL_B1-6F_T1_spiral")
    esc8 = [o for o in model.objects if o["name"].startswith("A-VERT-ESCL_8F-9F")]
    fac6 = [o for o in model.objects if o["name"].startswith("A-FACD_valley_glass_6F")]
    pad_o, roof_o = obj_of(model, "A-ROOF_rescue_pad"), obj_of(model, "A-ROOF_slab")
    ctr = lambda o: ((bbox_of(model, o)[0] + bbox_of(model, o)[2]) / 2, (bbox_of(model, o)[1] + bbox_of(model, o)[3]) / 2)
    sunk = master["context"]["sunken_stair"][0]
    sg = pc.polygons_from_segments(sunk["segments"]).bounds
    cm = pc.cut_geometries(master)
    coreD = next(g for it, g in cm["core_wall"] if it["name_ko"].startswith("코어 D"))
    frm = next(g for it, g in cm["shaft"] if "FR" in it["name_ko"])
    eb = [bbox_of(model, o) for o in esc8]
    esc_c = ((min(b[0] for b in eb) + max(b[2] for b in eb)) / 2, (min(b[1] for b in eb) + max(b[3] for b in eb)) / 2)
    capb = bbox_of(model, capw)
    cap_c = ((capb[0] + capb[2]) / 2, capb[3] - 3.0)
    facb = bbox_of(model, fac6[0])
    fac_axis = "x" if (facb[2] - facb[0]) > (facb[3] - facb[1]) else "y"
    fac_c = ((facb[0] + facb[2]) / 2, (facb[1] + facb[3]) / 2)
    pad_c = ctr(pad_o)

    G = lambda fl, c, **kw: dict(source="glb", ffl=F[fl], floor=fl, center=c, **kw)
    DET = [
        dict(sid="D-401", title="T1 나선 램프 확대", grade="MODEL DETAIL", plan_label="3F 절단 +1.5 m · 램프 윗면", ref="P-101 (3F)", **G("3F", ctr(t1), top_objs=[sprl]),
             section=("x", ctr(t1)[0], "3F"), main=t1, ramp=sprl, notes=["A-VERT-SPRL_B1-6F_T1_spiral + A-CORE-TUBE_T1 모델 메시", "난간·마감·바닥재는 모델에 없어 그리지 않음"]),
        dict(sid="D-402", title="T2 빛 튜브와 층판 관통 확대", grade="MODEL DETAIL", plan_label="3F 절단 +1.5 m · 층판 개구", ref="P-101 (3F)", **G("3F", ctr(t2)),
             section=("x", ctr(t2)[0], "3F"), main=t2, notes=["A-CORE-TUBE_T2 + A-FLOR_s7 층판 개구", "T2는 승객 이동로가 아님(빛 튜브). 유리·마감은 모델에 없음"]),
        dict(sid="D-403", title="T3 파노라마 승강기 튜브 확대 (T4 동형)", grade="MODEL DETAIL", plan_label="3F 절단 +1.5 m", ref="P-101 (3F)", **G("3F", ctr(t3)),
             section=("x", ctr(t3)[0], "3F"), main=t3, notes=["A-CORE-TUBE_T3, A-VERT-ELEV 카·샤프트 모델 메시", "T4는 같은 형식(위치만 다름). 승강장 문·기계는 모델에 없음"]),
        dict(sid="D-404", title="코어 D 진입·부속실 확대 (1층 마스터)", grade="MODEL DETAIL (1F 마스터) · 상층 UNRESOLVED DETAIL", plan_label="1F 마스터 절단 +1.5 m", ref="A-003 (1층)", source="master", slice=master,
             center=((coreD.bounds[0] + coreD.bounds[2]) / 2, (coreD.bounds[1] + coreD.bounds[3]) / 2), section=None, main_poly=coreD, label_kinds=("shaft",),
             notes=["1층 마스터의 코어 D(벽·부속실 칸막이·문·기호)", "상층 GLB는 코어 외곽 벽만 있어 상층 코어 내부는 그리지 않음(UNRESOLVED DETAIL)"]),
        dict(sid="D-405", title="캡슐과 층판 접속 확대", grade="MODEL DETAIL · 출입문 미승인", plan_label="3F 절단 +1.5 m · 캡슐 끝단", ref="P-101 (3F)", **G("3F", cap_c),
             section=("y", cap_c[1], "3F"), main=capw, notes=["A-CORE-TUBE_capW + A-FLOR 층판", "캡슐 출입구는 모델에 없고 사용자 미승인이라 벽을 닫아 둠"]),
        dict(sid="D-406", title="전형층 외피·층판 가장자리와 입면 부재 모듈 (6F)", grade="MODEL DETAIL · 접합 UNRESOLVED", plan_label="6F 절단 +1.5 m", ref="E-201~204", **G("6F", fac_c),
             section=(fac_axis, fac_c[0] if fac_axis == "x" else fac_c[1], "6F"), main=fac6[0], notes=["A-FACD_valley_* 외피 부재 + A-FLOR_s7_6F", "실제 조인트·재료 자료가 없어 모델 형상만 표시(접합 UNRESOLVED DETAIL)"]),
        dict(sid="D-407", title="에스컬레이터 개구 확대 (8F–9F)", grade="MODEL DETAIL · 난간·안전 규격 미검증", plan_label="8F 절단 +1.5 m · 에스컬레이터 윗면", ref="P-102 (8F)", **G("8F", esc_c, top_objs=esc8),
             section=("x", esc_c[0], "8F"), main=esc8[0], notes=["A-VERT-ESCL_8F-9F_* 모델 메시 + 층판 개구", "에스컬레이터 기계·난간은 모델에 없음"]),
        dict(sid="D-408", title="선큰 계단·마당 연결 확대 (1층 마스터)", grade="MODEL DETAIL (1F 마스터) · 지반 UNRESOLVED DETAIL", plan_label="1F 마스터 · 선큰", ref="A-003 (1층)", source="master", slice=master,
             center=((sg[0] + sg[2]) / 2, (sg[1] + sg[3]) / 2), section=None, space_uses=("sunken",), label_kinds=(),
             notes=["선큰 계단 %d단, 하향 %s, FL -5.5 m (마스터 속성)" % (int(sunk["props"].get("treads", 12)), sunk["props"].get("down")), "계단 폭·단높이는 속성에 없어 단 수·방향·윤곽만. 1:50은 창에 안 들어가 1:100"]),
        dict(sid="D-409", title="화물 승강기·하역 동선 확대", grade="UNRESOLVED DETAIL · 형상만 MODEL", plan_label="1F 마스터 · FR 샤프트", ref="A-003 (1층)", source="master", slice=master,
             center=((frm.bounds[0] + frm.bounds[2]) / 2, (frm.bounds[1] + frm.bounds[3]) / 2), section=("x", ctr(fr)[0], "1F", ctr(fr)), main_poly=frm, label_kinds=("shaft",),
             notes=["단면은 GLB A-CORE-TUBE_FR 벽과 층판만(승강 카·기계·승강장 문은 모델에 없음)", "화물 기계·하역 차량 동선은 UNRESOLVED DETAIL"]),
        dict(sid="D-410", title="지붕·상층 후퇴부 확대", grade="MODEL DETAIL · 방수·마감 UNRESOLVED", plan_label="15F 절단 +1.5 m · 지붕 구조 표식", ref="E-201~204", **G("15F", pad_c, top_objs=[pad_o]),
             section=("x", pad_c[0], "15F"), main=pad_o, notes=["A-ROOF_slab, A-ROOF_rescue_pad·mark 모델 메시", "방수층·지붕 마감·배수는 모델에 없어 그리지 않음"]),
    ]
    for spec in DET:
        spec["scale"] = sheetreg.detail_scale(spec["sid"])                  # 축척의 유일한 출처: tools/t14g/registry.py (호출 기호도 같은 값을 읽는다)
    assert {s["sid"] for s in DET} == set(sheetreg.DETAIL_SCALE), "상세 사양표와 레지스트리의 상세 번호가 다르다"
    for spec in DET:
        sid, scale = spec["sid"], spec["scale"]
        k = 1000.0 / scale
        sh = Sheet(sid, spec["title"], scale, spec["grade"].replace(" · ", " · "), subtitle="%s · 평면 %s" % (spec["grade"], spec["plan_label"]),
                   extra_lines=spec["notes"][:2])
        c = Ctx()
        c.cut, c.top, c.sunk, c.slab_poly = {}, {}, None, None
        c.truth = {}
        used_plan = draw_plan(sh, model, spec, c)
        PXX, PYY = c.PX_, c.PY_
        dims = []
        meta = {"plan_dims": 0, "section_dims": 0, "level_tags": 0, "callouts": 0}
        # ── 평면 치수 ──
        half = c.half
        if spec.get("main") is not None and spec["source"] == "glb":
            o = spec["main"]
            bx0, by0, bx1, by1, bz0, bz1 = bbox_of(model, o)
            if o["kind"] == "tube_wall" and o["name"] == capw["name"]:
                p = c.cut.get(o["name"])
                if p is not None and not p.is_empty:
                    ps_ = [q for q in (p.geoms if hasattr(p, "geoms") else [p]) if q.geom_type == "Polygon"]
                    q0 = max(ps_, key=lambda q: q.area)
                    ob = q0.exterior.bounds
                    wd = ob[2] - ob[0]
                    ib = max((Polygon(r_).bounds for r_ in q0.interiors), key=lambda q: (q[2] - q[0]) * (q[3] - q[1])) if q0.interiors else None
                    yb = PY + half * k - 12.0
                    dm.dim_h(sh, PXX(ob[0]), PXX(ob[2]), yb, "캡슐 바깥 폭 %s" % dm.fmt_mm(wd), pt=6.0, color="#06a")
                    dims.append(("캡슐 바깥 폭", dm.fmt_mm(wd), "plan_cut A-CORE-TUBE_capW"))
                    meta["plan_dims"] += 1
                    if ib:
                        tw = (wd - (ib[2] - ib[0])) / 2
                        dims.append(("캡슐 벽 두께", dm.fmt_mm(tw), "plan_cut (바깥폭−안쪽폭)/2"))
                        sh.text(PXX(ob[0]) + 22.0, yb - 8.0, "벽 t=%s" % dm.fmt_mm(tw), 5.8, "normal", "#06a", bg=True)
                        meta["plan_dims"] += 1
            elif o["kind"] == "tube_wall":
                p = c.cut.get(o["name"])
                if p is not None and not p.is_empty:
                    do, di, tw = ring_dims(p)
                    b = p.bounds
                    ymid = (b[1] + b[3]) / 2
                    if spec["sid"] in ("D-402", "D-403"):
                        dm.dim_h(sh, PXX(b[0]), PXX(b[2]), PY + 12.0, truth.diameter_label(p, dm.fmt_mm(do)) + " (바깥)", pt=6.0, color="#06a", above=False)
                    else:
                        dm.dim_h(sh, PXX(b[0]), PXX(b[2]), PYY(b[1]) + 9.0, truth.diameter_label(p, dm.fmt_mm(do)) + " (바깥)", from_y=PYY(b[1]), above=False, pt=6.0, color="#06a")
                    dims.append(("튜브 바깥 지름", dm.fmt_mm(do), "plan_cut " + o["name"]))
                    if di:
                        dims.append(("튜브 안쪽 지름", dm.fmt_mm(di), "plan_cut"))
                        dims.append(("튜브 벽 두께", dm.fmt_mm(tw), "plan_cut (바깥−안쪽)/2"))
                        sh.text(PXX(b[0]) + 7, PYY(ymid) - 3.0, "벽 t=%s" % dm.fmt_mm(tw), 5.8, "normal", "#06a", bg=True)
                    meta["plan_dims"] += 2
        if spec.get("ramp") is not None and spec["ramp"]["name"] in c.top:
            g = c.top[spec["ramp"]["name"]]
            ps = [p for p in (g.geoms if hasattr(g, "geoms") else [g]) if p.geom_type == "Polygon"]
            p = max(ps, key=lambda q: q.area)
            ob = p.exterior.bounds
            Ro = (ob[2] - ob[0]) / 2
            if p.interiors:
                ib = max((Polygon(r).bounds for r in p.interiors), key=lambda b: b[2] - b[0])
                Ri = (ib[2] - ib[0]) / 2
                cxm, cym = (ob[0] + ob[2]) / 2, (ob[1] + ob[3]) / 2
                dm.dim_h(sh, PXX(cxm), PXX(cxm + Ro), PYY(cym) - 0.0 + 0.0, "R%s" % dm.fmt_mm(Ro), pt=5.6, color="#a60")
                dm.dim_h(sh, PXX(cxm), PXX(cxm + Ri), PYY(cym) + 5.0, "R%s" % dm.fmt_mm(Ri), pt=5.6, color="#a60", above=False)
                dims.append(("램프 바깥 반경", dm.fmt_mm(Ro), "top_outline " + spec["ramp"]["name"]))
                dims.append(("램프 안쪽 반경", dm.fmt_mm(Ri), "top_outline"))
                dims.append(("램프 폭(반경 방향)", dm.fmt_mm(Ro - Ri), "바깥−안쪽"))
                meta["plan_dims"] += 3
        if spec["id"] if False else False:
            pass
        if spec["sid"] == "D-402" and c.slab_poly is not None and not c.slab_poly.is_empty:
            for p in (c.slab_poly.geoms if hasattr(c.slab_poly, "geoms") else [c.slab_poly]):
                for r in p.interiors:
                    b = Polygon(r).bounds
                    tc = ctr(t2)
                    if b[0] < tc[0] < b[2] and b[1] < tc[1] < b[3]:
                        dm.dim_h(sh, PXX(b[0]), PXX(b[2]), PY + 24.0, "층판 개구 %s" % dm.fmt_mm(b[2] - b[0]), pt=5.8, color="#06a", above=False)
                        dims.append(("층판 개구 폭", dm.fmt_mm(b[2] - b[0]), "층판 구멍 bbox"))
                        meta["plan_dims"] += 1
        if spec["sid"] == "D-406":
            cols = [(n_, g_) for n_, g_ in c.cut.items() if "COLM" in n_.upper() or "COLUMN" in n_.upper() or n_.startswith("A-STRC")]
            cols = [(n_, g_) for n_, g_ in cols if g_.intersects(box(c.cx - half, c.cy - half, c.cx + half, c.cy + half))]
            if len(cols) >= 2:
                cc = sorted([g_.centroid for n_, g_ in cols], key=lambda q: q.x if fac_axis == "x" else q.y)
                p0, p1 = cc[0], cc[-1]
                d_ = abs(p1.x - p0.x) if fac_axis == "x" else abs(p1.y - p0.y)
                if fac_axis == "x":
                    dm.dim_h(sh, PXX(p0.x), PXX(p1.x), PYY(p0.y) + 22.0, "기둥 중심 %s" % dm.fmt_mm(d_), from_y=PYY(p0.y) + 6.0, pt=6.0, color="#06a", above=False)
                else:
                    dm.dim_v(sh, PYY(p0.y), PYY(p1.y), PXX(p0.x) + 22.0, "기둥 중심 %s" % dm.fmt_mm(d_), from_x=PXX(p0.x) + 6.0, pt=6.0, color="#06a", left=False)
                dims.append(("기둥 중심 간격", dm.fmt_mm(d_), "plan_cut 기둥 윤곽 중심"))
                meta["plan_dims"] += 1
        if spec["sid"] == "D-407":
            xs_ = [b[0] for b in eb] + [b[2] for b in eb]
            ys_ = [b[1] for b in eb] + [b[3] for b in eb]
            dm.dim_h(sh, PXX(min(xs_)), PXX(max(xs_)), PYY(max(ys_)) - 5.0, "폭 %s" % dm.fmt_mm(max(xs_) - min(xs_)), pt=6.0, color="#06a")
            dm.dim_v(sh, PYY(max(ys_)), PYY(min(ys_)), PXX(min(xs_)) - 5.0, "길이 %s" % dm.fmt_mm(max(ys_) - min(ys_)), pt=6.0, color="#06a")
            dims.append(("에스컬레이터 폭", dm.fmt_mm(max(xs_) - min(xs_)), "A-VERT-ESCL bbox"))
            dims.append(("에스컬레이터 길이", dm.fmt_mm(max(ys_) - min(ys_)), "A-VERT-ESCL bbox"))
            meta["plan_dims"] += 2
        if spec["sid"] == "D-404":
            b = coreD.bounds
            dm.dim_h(sh, PXX(b[0]), PXX(b[2]), PYY(b[3]) - 8.0, dm.fmt_mm(b[2] - b[0]), from_y=PYY(b[3]), pt=6.0, color="#06a")
            dm.dim_v(sh, PYY(b[3]), PYY(b[1]), PXX(b[0]) - 8.0, dm.fmt_mm(b[3] - b[1]), from_x=PXX(b[0]), pt=6.0, color="#06a")
            ray = LineString([(b[0] - 0.5, b[1] + 3.0), (b[2] + 0.5, b[1] + 3.0)]).intersection(coreD)
            segs = sorted([q for q in geom_lines(ray)], key=lambda q: q[0][0]) if not ray.is_empty else []
            if segs:
                tw = abs(segs[0][-1][0] - segs[0][0][0])
                dims.append(("코어 벽 두께(서측 벽, 레이 측정)", dm.fmt_mm(tw), "1F 마스터 core_wall, y=코어 중앙 레이"))
                sh.text(PXX(b[0]) + 10, PYY(b[1] + 3.0) - 2.5, "벽 t=%s" % dm.fmt_mm(tw), 5.8, "normal", "#06a", bg=True)
                meta["plan_dims"] += 1
            dims.append(("코어 D 바깥 치수", "%s × %s" % (dm.fmt_mm(b[2] - b[0]), dm.fmt_mm(b[3] - b[1])), "1F 마스터 core_wall"))
            meta["plan_dims"] += 2
        if spec["sid"] == "D-408" and c.sunk:
            b, n, props = c.sunk
            dm.dim_h(sh, PXX(b[0]), PXX(b[2]), PYY(b[3]) - 8.0, "폭 %s" % dm.fmt_mm(b[2] - b[0]), from_y=PYY(b[3]), pt=6.0, color="#06a")
            dm.dim_v(sh, PYY(b[3]), PYY(b[1]), PXX(b[0]) - 8.0, "길이 %s" % dm.fmt_mm(b[3] - b[1]), from_x=PXX(b[0]), pt=6.0, color="#06a")
            sh.text(PXX((b[0] + b[2]) / 2), PYY((b[1] + b[3]) / 2) + 2, "%d단 · 하향 %s · FL -5.5 m" % (n, props.get("down")), 7.0, "bold", "#333", "middle", bg=True)
            sh.text(PX + half * k - 3, PY + half * k - 3, "점선: 마스터 sunken 공간 경계", 5.6, "normal", "#555", "end", bg=True)
            dims += [("선큰 계단 폭", dm.fmt_mm(b[2] - b[0]), "마스터 sunken_stair"), ("선큰 계단 길이", dm.fmt_mm(b[3] - b[1]), "마스터 sunken_stair"), ("단 수", "%d" % n, "마스터 속성 treads")]
            meta["plan_dims"] += 2
        if spec["sid"] == "D-409":
            b = frm.bounds
            dm.dim_h(sh, PXX(b[0]), PXX(b[2]), PYY(b[1]) + 9.0, truth.diameter_label(frm, dm.fmt_mm(b[2] - b[0])), from_y=PYY(b[1]), pt=6.0, color="#06a", above=False)
            dims.append(("화물 승강로 폭", dm.fmt_mm(b[2] - b[0]), "1F 마스터 shaft FR"))
            meta["plan_dims"] += 1
        if spec["sid"] == "D-410":
            tp = c.top.get(pad_o["name"])
            if tp is not None:
                b = tp.bounds
                dm.dim_h(sh, PXX(b[0]), PXX(b[2]), PYY(b[3]) - 9.0, truth.diameter_label(tp, dm.fmt_mm(b[2] - b[0])), from_y=PYY(b[3]), pt=6.0, color="#06a")
                dims.append(("구조 표식 패드 지름", dm.fmt_mm(b[2] - b[0]), "A-ROOF_rescue_pad 윗면"))
                meta["plan_dims"] += 1
        if spec["sid"] == "D-403":                                              # T4가 T3와 같은 형상이라는 문구의 근거
            cg = truth.congruent(model, "A-CORE-TUBE_T3", "A-CORE-TUBE_T4")
            c.truth["t3_t4"] = cg
            dims.append(("T3·T4 형상 차이(최대, mm)", "%.0f" % (cg["hausdorff_centered_m"] * 1000.0), "벽 메시 중심 정렬 비교 · " + ("동형" if cg["congruent"] else "다름(문구 수정 필요)")))
        if spec["sid"] == "D-408" and c.sunk:
            b_, n_, props_ = c.sunk
            drop_ = -F["B1"] + F["1F"] if abs((F["1F"] - F["B1"]) - 5.5) < 0.01 else None      # 마스터 라벨 FL -5.5 m = 모델 B1 층고 차
            if drop_ is not None:
                dd_ = truth.stair_derived(drop_, n_, b_[2] - b_[0])
                c.truth["stair"] = dd_
                dims.append(("선큰 바닥 레벨", "-5500", "마스터 FL −5.5 m = 모델 B1 FFL"))
                dims.append(("단당 높이 (계산값)", "%.0f" % dd_["riser_mm"], "5500 ÷ %d단 · 마스터에 속성 없음" % n_))
                dims.append(("단당 수평 길이 (계산값)", "%.0f" % dd_["tread_mm"], "%s ÷ %d단 · 하향 %s" % (dm.fmt_mm(b_[2] - b_[0]), n_, props_.get("down"))))
        # ── 단면 ──
        used_sec, sec = [], None
        if spec.get("section"):
            used_sec, sec = draw_section(sh, model, spec, c)
            meta["level_tags"] = 1
            ffl = F[spec["section"][2]]
            # 슬래브 두께: 절단된 층판 중 이 층 FFL에 걸린 것
            slab_t = None
            full = {o["name"]: g for o, g in c.sec_cuts_raw}
            for o, g in c.sec_cuts:
                if o["kind"] == "slab":
                    b = g.bounds
                    if abs(b[3] - ffl) < 0.06:
                        bf = full[o["name"]].bounds                           # 두께 = 자르지 않은 절단 폴리곤의 높이(창 아래로 잘린 400이 아니라 모델의 500)
                        slab_t = bf[3] - bf[1]
                        dm.dim_v(sh, c.SY_(b[3]), c.SY_(b[3] - slab_t), c.SX_(b[2]) + 6.0 if b[2] < c.uc + c.half - 1.0 else c.SX_(b[0]) - 6.0, "t=%s" % dm.fmt_mm(slab_t), pt=5.8, color="#06a", left=False)
                        break
            if slab_t is None:
                for o, g in c.sec_cuts_raw:
                    if o["kind"] == "slab":
                        b = g.bounds
                        slab_t = b[3] - b[1]
                        break
            if slab_t:
                dims.append(("슬래브 두께", dm.fmt_mm(slab_t), "단면 절단 층판 폭"))
                meta["section_dims"] += 1
            if spec["section"][2] == "15F":
                dims.append(("15F FFL → 지붕 슬래브 윗면", dm.fmt_mm(bbox_of(model, roof_o)[5] - ffl), "A-ROOF_slab 윗면 − 15F 층판"))
                zr = bbox_of(model, roof_o)[5]
                sh.line(c.SX_(c.uc - c.half), c.SY_(zr), c.SX_(c.uc + c.half), c.SY_(zr), 0.1, "#999", "2.2,1.6")
                sh.text(c.SX_(c.uc - c.half) + 8, c.SY_(zr) - 0.8, "ROOF  %+.3f" % r5(zr - F["1F"]), 6.0, "bold", "#333", bg=True)
            else:
                dims.append(("층고(이 층 → 위층)", dm.fmt_mm(F[{"3F": "4F", "6F": "7F", "8F": "9F"}.get(spec["section"][2], "2F")] - ffl), "A-FLOR 층판 윗면 차"))
            meta["section_dims"] += 1
            # 경사: 절단 띠의 최소 회전 사각형(V2)은 착지판·판 두께가 섞인 겉보기 각도라 쓰지 않는다.
            # 에스컬레이터의 물리적 경사각은 3D 메시의 경사면 법선에서 구하고, 이 시트가 다루는 8F–9F 구간의 절단 띠에 표기한다.
            if spec["sid"] == "D-407":
                inc = truth.sloped_incline(model, esc8)
                ang = inc["angle_deg"]
                names8 = {e["name"] for e in esc8}
                tgt = next((g for o, g in c.sec_cuts if o["name"] in names8 and g.area > 0.05), None)
                dims.append(("경사각(모델 경사면 법선)", "%.1f°" % ang, "A-VERT-ESCL_8F-9F 경사면, 면적 가중"))
                dims.append(("경사 구간 수평 길이", dm.fmt_mm(inc["plan_run_m"]), "경사면 평면 투영 길이(모델)"))
                c.truth["incline"] = inc
                if tgt is not None:
                    bb_ = tgt.bounds
                    sh.text(c.SX_((bb_[0] + bb_[2]) / 2), c.SY_((bb_[1] + bb_[3]) / 2) - 6.0, "%.1f°" % ang, 6.5, "bold", "#06a", "middle", bg=True)
                    meta["section_dims"] += 1
        else:
            sh.text(SX, STOP - 3.0, "단면 SECTION", 8, "bold", "#222", "middle")
            sh.text(SX, 120, "단면 없음", 12, "bold", "#999", "middle")
            sh.text(SX, 128, "UNRESOLVED DETAIL", 8, "normal", "#999", "middle")
            sh.text(SX, 136, "(코어·선큰 내부 단면은 모델 근거 없음)", 6.5, "normal", "#999", "middle")
        # ── 키플랜(확대 위치) + 근거 표 ──
        from t14e_make_views import mini_keyplan
        mini_keyplan(sh, run, 14, 226, 32, cut=None, label="확대 위치")
        # 확대 위치 표시(원)
        sl3 = pc.load_slice(os.path.join(run, "raw_slices"), "3F")
        slab_ = bv._union([pc.polygons_from_segments(p["segments"]) for p in sl3["projection"]])
        bx0, by0, bx1, by1 = slab_.bounds
        kk_ = 32.0 / max(bx1 - bx0, by1 - by0)
        if True:                                                                  # 모든 상세 시트에 확대 위치 고리(마스터 출처 D-404·D-408 포함, 감사 p22-03/p26-04)
            wc = ctr(fr) if spec["sid"] == "D-409" else spec["center"]
            sh.path([[(14 + (wc[0] - bx0) * kk_ + 3.0 * math.cos(t / 20 * 2 * math.pi), 226 + (by1 - wc[1]) * kk_ + 3.0 * math.sin(t / 20 * 2 * math.pi)) for t in range(21)]], stroke="#a60", w=0.4, closed=True)
        sh.text(34, 222.0, "· 참조: %s" % spec["ref"], 6.0, "bold", "#a60")
        tx, ty = 56.0, 224.0
        sh.text(tx, ty, "치수·근거 (모델에서 읽음)", 8, "bold", "#111")
        ty += 4.0
        sh.line(tx, ty - 2.2, tx + 134, ty - 2.2, 0.2, "#555")
        for lab, val, src in dims[:9]:
            sh.text(tx, ty + 1.0, lab, 6.2, "normal", "#222")
            sh.text(tx + 62, ty + 1.0, val, 6.2, "bold", "#222", "end")
            sh.text(tx + 66, ty + 1.0, src[:34], 5.2, "normal", "#777")
            ty += 3.7
        # 그래픽 스케일바: 평면 패널 아래 · 키플랜 위의 빈 띠(y 203~219)에 둔다. 영역을 선언해 두므로 다른 요소와 겹치면 save()에서 빌드가 멈춘다.
        sh.claim("plan_panel", PX - half * k, PY - half * k - 3.5, PX + half * k, PY + half * k + 0.5)
        sh.claim("keyplan_refs", 14, 220.0, 54, 258)
        sh.claim("dim_table", tx, 222.0, tx + 134, ty + 0.5)
        if spec.get("section"):
            sh.claim("section_panel", SX - half * k, STOP - 4.0, SX + half * k, STOP + (11.6 if scale == 50 else 23.0) * k)
        sh.scale_bar(17.0, 212.0)                                                # 5 m = 100 mm (1:50) / 10 m = 100 mm (1:100)
        sh.title_block()
        base = sh.save(os.path.join(run, "details", "%s_%s" % (sid, "detail")))
        reg["details"].append({"sheet": sid, "title": spec["title"], "grade": spec["grade"], "scale": "1:%d" % scale, "scale_bars": sh.bars, "truth": c.truth, "ref_sheet": spec["ref"],
                               "plan": {"source": spec["source"], "center": [round(spec["center"][0], 3), round(spec["center"][1], 3)], "window_m": 2 * half, "source_objects": used_plan},
                               "section": None if not spec.get("section") else {"axis": spec["section"][0], "value_drawing_frame": round(spec["section"][1], 4)},
                               "section_cut_elements": [{"name": o["name"], "kind": o["kind"], "name_ko": o["name_ko"]} for o, g in getattr(c, "sec_cuts", [])], "section_visible_objects": used_sec,
                               "dimensions": [{"label": l_, "value_mm": v_, "source": s_} for l_, v_, s_ in dims], "dimension_meta": meta, "notes": spec["notes"],
                               "files": {e: {"path": base + "." + e, "sha256": V1.sha_file(base + "." + e)} for e in ("svg", "pdf", "png")}})
        print("DETAIL", sid, "1:%d" % scale, "dims", len(dims), meta)
    json.dump(reg, open(os.path.join(run, "details", "detail_registry.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    problems = sheetreg.verify_against_registry(os.path.join(run, "details", "detail_registry.json"))
    if problems:
        raise SystemExit("detail registry mismatch: " + "; ".join(problems))
    print("DETAILS %s DONE" % cfg.EDITION)


if __name__ == "__main__":
    main()

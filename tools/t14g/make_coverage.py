"""A-902 층별 구성 일람(B2~15F 17개 층) + typical_floor_coverage.json.

모든 층의 평면을 따로 그리지 않고(사용자 지시: 기준층만), 17개 층 전부의 슬래브·프로그램 구역·튜브·코어·기둥·개구를 모델 slice에서
같은 축척(1:1000)으로 작게 그린다. 9F·14F는 8F·13F와 다른 부분(수직동선 개구)을 붉게 칠해 차이를 보인다.
수치는 전부 slice 폴리곤에서 계산한다(숫자를 직접 쓰지 않는다).
"""
import csv
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, TOOLS)
import pipeline_common as pc  # noqa: E402
import book_views as bv  # noqa: E402
from shapely.geometry import Polygon  # noqa: E402
from shapely.ops import unary_union  # noqa: E402
import t14d_sheet as _ts  # noqa: E402
from t14g import config as cfg  # noqa: E402
cfg.apply(_ts)
from t14d_sheet import Sheet, geom_rings  # noqa: E402
from t14e_make_details import hatch, poly_mm  # noqa: E402

ORDER = ["B2", "B1"] + ["%dF" % i for i in range(1, 16)]
K = 1.0                                     # 1:1000 → 모델 1 m = 1 mm
CELL_W, CELL_H = 66.0, 80.0
X0, Y0 = 12.0, 12.0
STYLE = {"판매": (None, None, "#bbb"), "F&B": (45.0, 1.7, "#777"), "문화": (135.0, 1.7, "#777"), "garden": (90.0, 1.3, "#5a7"), "서비스": (0.0, 1.2, "#999")}


def _slab(sl):
    return bv._union([pc.polygons_from_segments(p["segments"]) for p in sl["projection"]])


def _holes(g):
    out = []
    for p in (g.geoms if hasattr(g, "geoms") else [g]):
        if p.geom_type == "Polygon":
            out += [Polygon(r) for r in p.interiors]
    return out


def floor_facts(run, f, ffl):
    sl = pc.load_slice(os.path.join(run, "raw_slices"), f)
    slab = _slab(sl)
    cuts = pc.cut_geometries(sl)
    zones = {}
    for z in sl["zones"]:
        g = pc.polygons_from_segments(z["segments"])
        zones[z["name_ko"]] = zones.get(z["name_ko"], 0.0) + g.area
    holes = _holes(slab)
    return {"floor": f, "ffl_m": round(ffl, 3), "slab_area_m2": round(slab.area, 1), "program_areas_m2": {k: round(v, 1) for k, v in zones.items()},
            "openings": {"count": len(holes), "area_m2": round(sum(h.area for h in holes), 1)},
            "tubes": len(cuts.get("tube_wall", [])), "cores": len(cuts.get("core_wall", [])), "columns": len(cuts.get("column", [])),
            "_slab": slab, "_sl": sl, "_cuts": cuts}


def build(run, out_base):
    ev = json.load(open(os.path.join(run, "00_index", "floor_equivalence_evidence.json"), encoding="utf-8"))
    floors_z = ev["floor_z_m"]
    ffl0 = floors_z["1F"]
    plans = json.load(open(os.path.join(run, "plans", "plan_sheets.json"), encoding="utf-8"))
    plan_of = {}
    for p in plans:
        for m in p["applies_to"]:
            plan_of[m] = (p["sheet"], "OWN_PLAN" if m == p["floor"] else "SHARED_PLAN_WITH_DELTA", p["floor"])
    group_of = {f: g for g in ev["groups"] for f in g["floors"]}
    facts = {f: floor_facts(run, f, floors_z[f] - ffl0) for f in ORDER}
    ref_of = {"9F": "8F", "14F": "13F"}
    gb = unary_union([facts[f]["_slab"] for f in ORDER]).bounds                 # 모든 층이 같은 중심·같은 틀(건물 전체 범위)

    sh = Sheet("A-902", "층별 구성 일람 — B2~15F 17개 층 (프로그램·개구·수직동선 차이)", 1000, "MODEL_DATA · LEVEL S · 가구 없음",
               subtitle="전 층을 같은 축척(1:1000)으로 비교 · 슬래브·프로그램 구역·튜브·코어·기둥·개구는 모델 slice에서 계산 · 붉은색 = 기준층 대비 다른 부분",
               extra_lines=["평면을 따로 발행한 층: 3F(P-101) · 8F+9F(P-102) · 10F(P-103) · 13F+14F(P-104) · 15F(P-105) · 1F(A-003). 나머지는 이 일람에서 확인",
                            "구역 해칭: 판매 = 무늬 없음 · F&B = 45° 사선 · 문화·엔터 = 135° 사선 · 정원 = 세로선 · 서비스 = 가는 가로선"])
    cov = []
    for i, f in enumerate(ORDER):
        col, row = i % 6, i // 6
        ox, oy = X0 + col * CELL_W, Y0 + row * CELL_H
        fa = facts[f]
        slab, sl, cuts = fa["_slab"], fa["_sl"], fa["_cuts"]
        cx, cy = (gb[0] + gb[2]) / 2, (gb[1] + gb[3]) / 2
        X = lambda x, ox=ox, cx=cx: ox + CELL_W / 2 + (x - cx) * K
        Y = lambda y, oy=oy, cy=cy: oy + 6.0 + 28.0 + (cy - y) * K
        sh.claim("cell_" + f, ox + 1.0, oy, ox + CELL_W - 1.0, oy + CELL_H - 1.0)
        sh.text(ox + 3.0, oy + 4.0, f, 8, "bold", "#111")
        sh.text(ox + 16.0, oy + 4.0, "FFL %+.3f" % fa["ffl_m"], 6, "normal", "#555")
        sh.path([[(X(x), Y(y)) for x, y in r] for r in geom_rings(slab)], fill="#f6f6f6", stroke="#555", w=0.15)
        for z in sl["zones"]:
            g = pc.polygons_from_segments(z["segments"])
            ang, sp, colr = STYLE.get(z["name_ko"], (None, None, "#bbb"))
            if ang is not None:
                hatch(sh, poly_mm(g, X, Y), spacing=sp, angle=ang, w=0.07, color=colr)
            sh.path([[(X(x), Y(y)) for x, y in r] for r in geom_rings(g)], stroke="#999", w=0.08)
        if f in ref_of:                                                       # 기준층 대비 차이(수직동선 개구)
            ref = facts[ref_of[f]]["_slab"]
            diff = slab.symmetric_difference(ref)
            fa["delta_vs_reference"] = {"reference": ref_of[f], "slab_symdiff_m2": round(diff.area, 1), "pieces": len([p for p in (diff.geoms if hasattr(diff, "geoms") else [diff]) if p.area > 0.5])}
            for p in (diff.geoms if hasattr(diff, "geoms") else [diff]):
                if p.geom_type == "Polygon" and p.area > 0.5:
                    sh.path([[(X(x), Y(y)) for x, y in r] for r in geom_rings(p)], fill="#c33", stroke="#a00", w=0.15, opacity=0.55)
        for kind, fill, w in (("core_wall", "#333", 0.1), ("tube_wall", "#fff", 0.12), ("column", "#000", 0.05)):
            for it, g in cuts.get(kind, []):
                sh.path([[(X(x), Y(y)) for x, y in r] for r in geom_rings(g)], fill=fill, stroke="#111", w=w)
        for h in _holes(slab):
            sh.path([[(X(x), Y(y)) for x, y in h.exterior.coords]], stroke="#c77", w=0.1, dash="1.2,0.8")
        prog = " · ".join("%s %s㎡" % (k, format(int(round(v)), ",")) for k, v in fa["program_areas_m2"].items())
        sh.text(ox + 3.0, oy + 68.0, prog[:46], 5.5, "normal", "#333")
        ps = plan_of.get(f, ("A-003", "OWN_PLAN", "1F") if f == "1F" else (None, "OVERVIEW_ONLY", None))
        sh.text(ox + 3.0, oy + 72.0, "개구 %d개 %s㎡ · 슬래브 %s㎡" % (fa["openings"]["count"], format(int(round(fa["openings"]["area_m2"])), ","), format(int(round(fa["slab_area_m2"])), ",")), 5.5, "normal", "#555")
        tag = {"OWN_PLAN": "평면: %s" % ps[0], "SHARED_PLAN_WITH_DELTA": "평면: %s(공통) · %s 대비 차이 붉게" % (ps[0], ref_of.get(f, "")), "OVERVIEW_ONLY": "이 일람으로 확인(별도 평면 없음)"}[ps[1]]
        sh.text(ox + 3.0, oy + 76.0, tag, 5.5, "bold", "#a33" if ps[1] == "OVERVIEW_ONLY" else "#06a")
        g_ = group_of.get(f, {})
        entry = {k: v for k, v in fa.items() if not k.startswith("_")}
        entry.update({"plan_sheet": ps[0], "publication_status": ps[1], "equivalence_group": g_.get("id"), "equivalence_kind": g_.get("kind"), "also_in": "A-902"})
        cov.append(entry)
    # 18번째 칸: 범례·방위·스케일
    ox, oy = X0 + 5 * CELL_W, Y0 + 2 * CELL_H
    sh.claim("legend", ox + 1.0, oy, ox + CELL_W - 1.0, oy + CELL_H - 1.0)
    sh.text(ox + 3.0, oy + 5.0, "범례", 8, "bold", "#111")
    items = [("판매", "무늬 없음"), ("F&B", "45° 사선"), ("문화", "135° 사선"), ("garden", "세로선"), ("서비스", "가는 가로선")]
    for j, (k, t) in enumerate(items):
        yy = oy + 11.0 + j * 5.2
        ang, sp, colr = STYLE[k]
        if ang is not None:
            hatch(sh, [Polygon([(ox + 3, yy - 3), (ox + 12, yy - 3), (ox + 12, yy + 1), (ox + 3, yy + 1)])], spacing=1.0, angle=ang, w=0.07, color=colr)
        sh.path([[(ox + 3, yy - 3), (ox + 12, yy - 3), (ox + 12, yy + 1), (ox + 3, yy + 1)]], stroke="#999", w=0.1)
        sh.text(ox + 14, yy, "%s (%s)" % (k, t), 5.5, "normal", "#333")
    sh.path([[(ox + 3, oy + 38), (ox + 12, oy + 38), (ox + 12, oy + 42), (ox + 3, oy + 42)]], fill="#c33", stroke="#a00", w=0.15, opacity=0.55)
    sh.text(ox + 14, oy + 41.2, "기준층과 다른 부분", 5.5, "normal", "#333")
    sh.text(ox + 3, oy + 47, "점선 = 슬래브 개구(수직동선)", 5.5, "normal", "#333")
    sh.text(ox + 3, oy + 52, "검정 사각 = 코어 · 흰 원 = 튜브 · 점 = 기둥", 5.5, "normal", "#333")
    nd = 63.2
    try:
        nd = json.load(open(os.path.join(run, "elevations", "elevation_registry.json"), encoding="utf-8"))["frame"]["north_deg"]
    except (OSError, KeyError):
        pass
    sh.north_arrow(ox + 12, oy + 66, nd, r=4.0)
    sh.scale_bar(ox + 28, oy + 67.0, meters=(0, 10, 20))
    sh.title_block()
    os.makedirs(os.path.dirname(out_base), exist_ok=True)
    sh.save(out_base, allow=(("legend", "scale_bar"),))
    cov_path = os.path.join(os.path.dirname(out_base), "typical_floor_coverage.json")
    json.dump({"scale": "1:1000", "sheet": "A-902", "floors": cov,
               "note": "B2~15F 17개 층 모두 A-902에 그려진다. 별도 평면이 없는 층은 publication_status=OVERVIEW_ONLY. STRICT 동등 쌍 0건(증거: floor_equivalence_evidence.json)이라 층을 합치지 않았다."},
              open(cov_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return out_base + ".pdf", cov_path, cov


if __name__ == "__main__":
    run = os.path.abspath(sys.argv[1])
    print(build(run, os.path.join(run, "appendix", "A-902_floor_overview"))[:2])

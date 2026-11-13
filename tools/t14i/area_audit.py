"""A-903 면적 데이터 재검증 + area_reconciliation.json/.md + typical_floor_coverage_v2.json + area_facts.json.

모든 값은 두 길로 따로 잰다.
  (1) raw_slices의 폴리곤(tools/t14g/make_coverage.floor_facts와 같은 방식)
  (2) 모델 메시(model_objects.json의 A-PROG_* 볼륨, A-FLOR_* 층판)를 src/book_views.py로 직접 자른 값
두 길이 같으면 기록하고, 다르면 issues에 숫자로 적는다. 숫자를 맞추려고 고치지 않는다(모델·slice는 읽기 전용).
"""
import os
import sys

_T = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # REPO\tools (이 파일을 직접 실행할 때 t14i를 찾게 한다)
if _T not in sys.path:
    sys.path.insert(0, _T)

import t14i  # noqa: F401,E402  (edition env, sys.path, text policy)

import datetime  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import re  # noqa: E402

import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

import pipeline_common as pc
import book_views as bv
from t14i import common
from t14g import make_coverage as mc

ORDER = mc.ORDER
PROG_RE = re.compile(r"^A-PROG_(?P<floor>[^_]+)_(?P<prog>.+)_(?P<id>\d{3})(?P<suf>\.\d{3})?$")
MIN_PAIR_M2 = 0.05            # 이보다 작은 겹침은 그리기 오차로 보고 쌍 목록에 넣지 않는다
EPS = 1e-6

# ── 정의(한 곳). meaning은 시트·JSON·MD가 같이 쓴다 ───────────────────────────────────────────────
DEFS = {
    "slab_gross_m2": ("층판 외곽 면적", "층판(A-FLOR_*) 외곽선 안쪽 전체 면적(개구를 메운 값). 구조 슬래브 판이 차지하는 윤곽이며 사용 면적이 아님.", "area(fill(slab))", "MODEL VERIFIED"),
    "opening_m2": ("층판 개구 면적", "층판 안에 완전히 둘러싸인 구멍(튜브·승강로·에스컬레이터·캡슐·아트리움 등)의 합. 외곽선으로 터진 홈은 포함하지 않음.", "Σ area(interior rings of slab)", "MODEL VERIFIED"),
    "slab_net_m2": ("층판 순면적", "층판 외곽 − 개구. 구조 슬래브 판 면적. 코어·기둥 면적을 빼지 않았고 벽·실 구분이 모델에 없어 '사용(전용) 면적'이 아님.", "slab_gross − opening", "MODEL VERIFIED"),
    "core_footprint_m2": ("코어 단면 면적", "바닥 위 1.5 m 절단에서 코어 벽 객체(A-VERT-STRS_*)가 차지하는 면적(모델에서 속이 찬 상자).", "area(∪ core_wall cut)", "MODEL VERIFIED"),
    "slab_net_minus_core_m2": ("층판 순면적 − 코어", "층판 순면적에서 코어 단면을 뺀 값. 계산값이며 전용 면적 정의가 아님.", "slab_net − core_footprint∩slab", "DERIVED"),
    "program_sum_legacy_m2": ("프로그램 투영 단순합(구 A-902 표기)", "slice가 그 층 절단면(바닥+1.5 m)에서 잡은 A-PROG_* 볼륨 단면 면적을 이름별로 더한 값. 타층 볼륨·중복·개구 위·층판 밖 면적을 모두 포함. 사용 면적이 아님.", "Σ area(slice zone)", "MODEL VERIFIED"),
    "program_union_m2": ("프로그램 투영 합집합", "slice에 잡힌 모든 프로그램 볼륨 단면의 합집합(겹침 제거). 볼륨의 평면 투영 넓이이지 바닥 면적이 아님.", "area(∪ slice zones)", "MODEL VERIFIED"),
    "program_union_own_m2": ("자층 프로그램 투영 합집합", "program_floor가 이 층인 볼륨만의 합집합.", "area(∪ own zones)", "MODEL VERIFIED"),
    "borrowed_union_m2": ("타층 볼륨이 더한 투영", "다른 층 소속(program_floor ≠ 이 층)이지만 이 층 절단면을 지나가서 slice 합에 들어온 볼륨이 자층 합집합에 더한 면적.", "program_union − program_union_own", "DERIVED"),
    "overlap_double_count_m2": ("겹침 이중계산", "단순합 − 합집합. 서로 겹친 구역이 두 번 더해진 양.", "program_sum_legacy − program_union", "DERIVED"),
    "program_over_slab_m2": ("프로그램 투영 중 층판 위", "프로그램 투영 합집합 ∩ 층판 순면적.", "area(U ∩ slab)", "MODEL VERIFIED"),
    "program_over_opening_m2": ("프로그램 투영 중 개구 위", "프로그램 투영이 층판 개구(바닥이 없는 곳) 위에 걸친 면적. 볼륨은 개구를 빼지 않았다.", "area(U ∩ openings)", "MODEL VERIFIED"),
    "program_outside_slab_m2": ("프로그램 투영 중 층판 밖", "프로그램 투영이 층판 외곽선 바깥에 놓인 면적.", "area(U − fill(slab))", "MODEL VERIFIED"),
    "slab_uncovered_by_program_m2": ("층판 중 프로그램 미피복", "층판 순면적에서 프로그램 투영이 덮지 않은 면적(외곽 둘레 띠·튜브 둘레 틈·프로그램 없는 구역).", "area(slab − U)", "MODEL VERIFIED"),
    "slab_uncovered_outside_outline_m2": ("미피복 중 프로그램 외곽 밖", "미피복 층판 중 프로그램 볼륨 외곽선 바깥(둘레 띠 등).", "area(slab − fill(zones))", "MODEL VERIFIED"),
    "slab_uncovered_inside_outline_m2": ("미피복 중 프로그램 외곽 안", "미피복 층판 중 프로그램 볼륨 구멍 안(튜브 둘레 틈·프로그램이 없는 구역).", "미피복 − 외곽 밖", "DERIVED"),
    "program_over_core_m2": ("프로그램 투영 중 코어 위", "프로그램 투영이 코어 단면과 겹친 면적(볼륨은 코어를 빼지 않았다).", "area(U ∩ core)", "MODEL VERIFIED"),
    "excess_legacy_sum_minus_slab_m2": ("단순합 − 층판 순면적", "구 표기 단순합이 층판 순면적을 넘는 양(음수면 모자람). 아래 항으로 분해된다.", "S − N = 겹침 + 개구 위 + 층판 밖 − 미피복", "DERIVED"),
    "program_volume_footprint_m2": ("프로그램 볼륨 투영(메시)", "모델 메시 A-PROG_*(앵커판 제외)를 수직 투영한 합집합. slice와 독립한 값. 볼륨은 바닥에서 4~5.5 m 솟은 덩어리이므로 면적이 아니라 투영 넓이.", "area(∪ vertical projection of mesh)", "MODEL VERIFIED"),
    "program_volume_m3": ("프로그램 볼륨 체적(메시)", "A-PROG_* 메시(앵커판 제외)의 닫힌 체적 합. 계산값.", "Σ |mesh volume|", "DERIVED"),
    "building_envelope_m2": ("건물 외곽 상자", "전 층 층판 외곽의 도면틀 바운딩 상자 면적(54×54 m).", "bbox(∪ all slab outlines)", "MODEL VERIFIED"),
    "outline_deficit_vs_envelope_m2": ("외곽 상자 대비 모자람", "건물 외곽 상자 − 이 층 층판 외곽. 2F·7F처럼 층판이 외곽 상자를 다 채우지 않는 층에서 양수.", "envelope − slab_gross", "DERIVED"),
}
USABLE_BASIS = ("UNRESOLVED: 모델에 벽·실·전용/공용 구분이 없어 사용(전용) 면적을 정의할 수 없다. 모델로 검증되는 층 면적 기준은 "
                "slab_net_m2(층판 순면적)이며 이는 코어·기둥을 포함한 참고 상한이다. 프로그램 투영 면적은 사용 면적으로 쓰지 않는다.")
LEGACY_KEY_MAP = {
    "slab_area_m2": "= slab_net_m2 (같은 값, 구 이름 유지)",
    "program_areas_m2": "삭제(오해 소지) → program_volume_footprint_by_program_m2 (slice 볼륨 단면, 이름별 합; 사용 면적 아님)",
    "openings.count/area_m2": "= opening_count / opening_m2 (같은 값, 구 이름 유지)",
}


# ── 도형 보조 ────────────────────────────────────────────────────────────────────────────────────
def parts(g):
    if g is None or g.is_empty:
        return []
    return [p for p in (g.geoms if hasattr(g, "geoms") else [g]) if p.geom_type == "Polygon" and not p.is_empty]


def holes_of(g):
    out = []
    for p in parts(g):
        out += [Polygon(r) for r in p.interiors]
    return out


def fill(g):
    ps = parts(g)
    return unary_union([Polygon(p.exterior) for p in ps]) if ps else Polygon()


def A(g):
    return 0.0 if g is None or g.is_empty else float(g.area)


def uni(gs):
    gs = [g for g in gs if g is not None and not g.is_empty]
    return unary_union(gs) if gs else Polygon()


def r2(v):
    return round(float(v), 2)


def r1(v):
    return round(float(v), 1)


def fmt(v, d=1):
    return format(round(v, d), ",.%df" % d)


# ── 모델 메시 보조(book_views.plan_cut 재사용; 모델은 읽기 전용) ───────────────────────────────────
class _Shim:
    """book_views.plan_cut은 model.bld만 돈다. A-PROG(kind=zone)는 bld(DRAWN_KINDS)에 없으므로 한 객체만 든 껍데기를 건넨다."""

    def __init__(self, model, o):
        self.bld = [o]
        self.tris = model.tris


def mesh_cut(model, o, z):
    r = bv.plan_cut(_Shim(model, o), z, {o["kind"]}, None)
    return r[0][1] if r else Polygon()


def mesh_footprint(model, o):
    polys = []
    for t in model.tris(o):
        p = Polygon(t[:, :2])
        if p.area > 1e-9:
            polys.append(p)
    return unary_union(polys) if polys else Polygon()


def mesh_volume(model, o):
    T = model.tris(o)
    return abs(float(np.einsum("ij,ij->i", T[:, 0], np.cross(T[:, 1], T[:, 2])).sum()) / 6.0)


def slab_objs_of(model, F, fz):
    out = []
    for o in model.objects:
        if o["kind"] != "slab":
            continue
        if str(o["floor"]) == F or (o["floor"] is None and abs(o["zmax"] - fz) < 0.05):
            out.append(o)
    return out


def _centroid(g):
    c = g.centroid
    return [r1(c.x), r1(c.y)]


# ── 수집 ────────────────────────────────────────────────────────────────────────────────────────
def collect(run):
    raw = os.path.join(run, "raw_slices")
    model = common.load_model(run)
    ev = common.jl(os.path.join(run, "00_index", "floor_equivalence_evidence.json"))
    ffl0 = ev["floor_z_m"]["1F"]
    by_name = {o["name"]: o for o in model.objects}
    all_zone_objs = [o for o in model.objects if o["name"].startswith("A-PROG_")]

    sl_of = {f: pc.load_slice(raw, f) for f in ORDER}
    slab_of = {f: bv._union([pc.polygons_from_segments(p["segments"]) for p in sl_of[f]["projection"]]) for f in ORDER}
    gross_of = {f: fill(slab_of[f]) for f in ORDER}
    env = uni(list(gross_of.values())).bounds
    envelope = (env[2] - env[0]) * (env[3] - env[1])

    # 지붕 슬래브(15F 위): 메시 투영
    roof_o = by_name.get("A-ROOF_slab")
    roof_poly = mesh_footprint(model, roof_o) if roof_o else Polygon()

    floors, issues_global = [], []
    zone_cache = {}
    max_dev = {"slab_net_slice_vs_mesh": 0.0, "slab_gross_slice_vs_mesh": 0.0, "zone_cut_slice_vs_mesh": 0.0, "zone_cut_vs_projection": 0.0,
               "legacy_make_coverage_slab": 0.0, "legacy_make_coverage_program": 0.0}

    for f in ORDER:
        sl = sl_of[f]
        fz, cut_z = sl["floor_z"], sl["cut_z"]
        slab, gross = slab_of[f], gross_of[f]
        open_polys = holes_of(slab)
        open_u = uni(open_polys)
        cuts = pc.cut_geometries(sl)
        core_u = uni([g for _, g in cuts.get("core_wall", [])])
        legacy = mc.floor_facts(run, f, fz - ffl0)

        # --- 층판: 메시로 독립 계산 ---
        sobjs = slab_objs_of(model, f, fz)
        slab_mesh = uni([mesh_footprint(model, o) for o in sobjs])
        slab_cut_mesh = uni([mesh_cut(model, o, (o["zmin"] + o["zmax"]) / 2) for o in sobjs])
        slab_info = {
            "objects": [{"name": o["name"], "zmin": r2(o["zmin"]), "zmax": r2(o["zmax"]), "thickness_m": r2(o["zmax"] - o["zmin"]),
                         "projection_m2": r2(A(mesh_footprint(model, o))), "mid_cut_m2": r2(A(mesh_cut(model, o, (o["zmin"] + o["zmax"]) / 2)))} for o in sobjs],
            "net_m2_mesh_projection": r2(A(slab_mesh)), "net_m2_mesh_cut": r2(A(slab_cut_mesh)),
            "gross_m2_mesh_projection": r2(A(fill(slab_mesh))),
        }
        max_dev["slab_net_slice_vs_mesh"] = max(max_dev["slab_net_slice_vs_mesh"], abs(A(slab) - A(slab_mesh)))
        max_dev["slab_gross_slice_vs_mesh"] = max(max_dev["slab_gross_slice_vs_mesh"], abs(A(gross) - A(fill(slab_mesh))))
        max_dev["legacy_make_coverage_slab"] = max(max_dev["legacy_make_coverage_slab"], abs(round(A(slab), 1) - legacy["slab_area_m2"]))

        # --- 프로그램 구역: slice(그 층 절단) ---
        zones = []
        for z in sl["zones"]:
            g = pc.polygons_from_segments(z["segments"])
            o = by_name.get(z["name"])
            crosses = o["zmin"] - EPS <= cut_z <= o["zmax"] + EPS
            cz = cut_z if crosses else (o["zmin"] + o["zmax"]) / 2
            mc_poly = mesh_cut(model, o, cz)
            fp = zone_cache.get(z["name"]) or mesh_footprint(model, o)
            zone_cache[z["name"]] = fp
            h = o["zmax"] - o["zmin"]
            max_dev["zone_cut_slice_vs_mesh"] = max(max_dev["zone_cut_slice_vs_mesh"], abs(A(g) - A(mc_poly)))
            max_dev["zone_cut_vs_projection"] = max(max_dev["zone_cut_vs_projection"], abs(A(g) - A(fp)))
            zones.append({"name": z["name"], "program": z["name_ko"], "program_floor": z["program_floor"], "own": z["program_floor"] == f,
                          "geom": g, "area": A(g), "cut_mode": "floor+1.5m" if crosses else "mid-height(볼륨이 절단면 아래에서 끝남)",
                          "cut_z": r2(cz), "zmin": r2(o["zmin"]), "zmax": r2(o["zmax"]), "height_m": r2(h),
                          "rel_zmin_m": r2(o["zmin"] - fz), "rel_zmax_m": r2(o["zmax"] - fz),
                          "shape_class": "plane(0.5 m 얇은 판: 정원 바닥면)" if h < 1.0 else "volume",
                          "area_mesh_cut": A(mc_poly), "area_mesh_projection": A(fp), "volume_m3": mesh_volume(model, o),
                          "suffix": (PROG_RE.match(z["name"]).group("suf") if PROG_RE.match(z["name"]) else None)})
        S = sum(z["area"] for z in zones)
        by_prog = {}
        for z in zones:
            by_prog.setdefault(z["program"], []).append(z)
        legacy_by_prog = {k: r1(sum(z["area"] for z in v)) for k, v in by_prog.items()}
        max_dev["legacy_make_coverage_program"] = max([max_dev["legacy_make_coverage_program"]] + [abs(legacy_by_prog.get(k, 0) - v) for k, v in legacy["program_areas_m2"].items()])
        U = uni([z["geom"] for z in zones])
        Uo = uni([z["geom"] for z in zones if z["own"]])
        Zf = uni([fill(z["geom"]) for z in zones])
        U_cov, U_open, U_out = U.intersection(slab), U.intersection(open_u), U.difference(gross)
        N_unc = slab.difference(U)
        N_unc_out = slab.difference(Zf)
        U_core = U.intersection(core_u)
        N = A(slab)

        # 겹침 쌍
        pairs = []
        for i in range(len(zones)):
            for j in range(i + 1, len(zones)):
                a, b = zones[i], zones[j]
                ov = A(a["geom"].intersection(b["geom"]))
                if ov > MIN_PAIR_M2:
                    iou = ov / max(A(a["geom"].union(b["geom"])), 1e-9)
                    pairs.append({"a": a["name"], "b": b["name"], "overlap_m2": r2(ov), "same_program": a["program"] == b["program"], "iou": r2(iou),
                                  "kind": "DUPLICATE_POLYGON" if iou > 0.99 else "PARTIAL_OVERLAP"})

        # 개구별 분해(이름 붙이기)
        named = [(it["name"], g) for k, v in cuts.items() if k not in ("column", "facade", "core_wall") for it, g in v]
        openings = []
        open_sorted = sorted(open_polys, key=lambda p: -p.area)
        borrowed_u = uni([z["geom"] for z in zones if not z["own"]])
        for h in open_sorted:
            labels = sorted({n for n, g in named if h.buffer(0.35).intersects(g)})
            openings.append({"area_m2": r2(h.area), "centroid_m": _centroid(h), "elements": labels,
                             "program_over_m2": r2(A(U.intersection(h))), "own_floor_program_over_m2": r2(A(Uo.intersection(h))),
                             "borrowed_program_over_m2": r2(A(borrowed_u.intersection(h))), "zone_hole_nearby": None})
        # 프로그램 볼륨 구멍과 개구의 정렬(튜브 구멍 위치 어긋남 검출): 같은 이름의 요소를 가진 개구와 비교한다
        zhole_rows = []
        for z in zones:
            for h in holes_of(z["geom"]):
                c = h.centroid
                names = {n for n, g in named if h.buffer(0.2).intersects(g)}
                cands = [p for p, o_ in zip(open_sorted, openings) if names & set(o_["elements"])] or open_sorted
                best = min(cands, key=lambda p: p.centroid.distance(c), default=None)
                d = best.centroid.distance(c) if best is not None else None
                zhole_rows.append({"zone": z["name"], "area_m2": r2(h.area), "centroid_m": _centroid(h), "nearest_slab_opening_m2": r2(best.area) if best is not None else None,
                                   "nearest_slab_opening_centroid_m": _centroid(best) if best is not None else None,
                                   "offset_m": r2(d) if d is not None else None, "elements": sorted(names)})
        for o_ in openings:
            near = [zr for zr in zhole_rows if zr["offset_m"] is not None and math.dist(zr["centroid_m"], o_["centroid_m"]) < 1.0]
            o_["zone_hole_nearby"] = bool(near)

        # --- 메시 쪽 A-PROG 볼륨(이 층 소속, 앵커판 분리) ---
        own_objs = [o for o in all_zone_objs if o["floor"] == f]
        vols, plates = [], []
        for o in own_objs:
            fp = zone_cache.get(o["name"]) or mesh_footprint(model, o)
            zone_cache[o["name"]] = fp
            row = {"name": o["name"], "program": o["name_ko"], "zmin": r2(o["zmin"]), "zmax": r2(o["zmax"]), "height_m": r2(o["zmax"] - o["zmin"]),
                   "projection_m2": r2(A(fp)), "volume_m3": r2(mesh_volume(model, o)), "in_slice_zones": o["name"] in {z["name"] for z in zones}}
            (plates if o["name_ko"] == "anchor" else vols).append((row, fp, o))
        vol_u = uni([fp for _, fp, _ in vols])
        mesh_pairs = []
        allm = vols + plates
        for i in range(len(allm)):
            for j in range(i + 1, len(allm)):
                (ra, fa, oa), (rb, fb, ob) = allm[i], allm[j]
                ov = A(fa.intersection(fb))
                if ov > MIN_PAIR_M2:
                    za, zb = (oa["zmin"], oa["zmax"]), (ob["zmin"], ob["zmax"])
                    inside = (za[0] >= zb[0] - 1e-3 and za[1] <= zb[1] + 1e-3) or (zb[0] >= za[0] - 1e-3 and zb[1] <= za[1] + 1e-3)
                    plate = oa["name_ko"] == "anchor" or ob["name_ko"] == "anchor"
                    mesh_pairs.append({"a": ra["name"], "b": rb["name"], "overlap_m2": r2(ov), "z_ranges_nested": inside, "involves_anchor_plate": plate,
                                       "kind": "ANCHOR_PLATE_INSIDE_VOLUME(높이 방향으로 포함)" if plate and inside else ("OVERLAP_3D" if not plate else "ANCHOR_PLATE_OVERLAP")})

        # --- 정원(외부 성격) 위 덮임 ---
        gardens = []
        for z in zones:
            if z["program"] != "garden":
                continue
            rem = z["geom"]
            stack = []
            above = [g for g in ORDER if M_Z(model, g) > M_Z(model, f) + 0.01]
            for g in above:
                sg = slab_of[g]
                zb = min((o["zmin"] for o in slab_objs_of(model, g, sl_of[g]["floor_z"])), default=sl_of[g]["floor_z"])
                c = rem.intersection(sg)
                if A(c) > 0.05:
                    stack.append({"above": g + " 층판", "bottom_z_above_garden_m": r2(zb - z["zmax"]), "area_m2": r2(A(c))})
                rem = rem.difference(sg)
            if roof_o is not None and roof_o["zmin"] > z["zmin"]:
                c = rem.intersection(roof_poly)
                if A(c) > 0.05:
                    stack.append({"above": "A-ROOF_slab(지붕)", "bottom_z_above_garden_m": r2(roof_o["zmin"] - z["zmax"]), "area_m2": r2(A(c))})
                rem = rem.difference(roof_poly)
            gardens.append({"zone": z["name"], "area_m2": r2(z["area"]), "thickness_m": z["height_m"], "over_slab_m2": r2(A(z["geom"].intersection(slab))),
                            "over_opening_m2": r2(A(z["geom"].intersection(open_u))), "outside_slab_m2": r2(A(z["geom"].difference(gross))),
                            "covered_by_what_is_above": stack, "no_slab_or_roof_above_m2": r2(A(rem)),
                            "meaning": "모델 객체 위치만으로 센 값: 위층 층판·지붕이 위에 있는지. 외벽·유리·난간이 모델/결정에 없어 '외부 공간'인지는 UNRESOLVED."})

        floors.append({
            "floor": f, "ffl_m": r2(fz - ffl0), "ffl_abs_m": r2(fz), "cut_z_m": r2(cut_z),
            "_geom": {"slab": slab, "gross": gross, "open": open_u, "U": U, "zones": zones, "core": core_u},
            "slab": slab_info, "slab_objects": len(sobjs),
            "q": {
                "slab_gross_m2": A(gross), "opening_m2": A(open_u), "slab_net_m2": N, "core_footprint_m2": A(core_u.intersection(slab)),
                "slab_net_minus_core_m2": N - A(core_u.intersection(slab)),
                "program_sum_legacy_m2": S, "program_union_m2": A(U), "program_union_own_m2": A(Uo), "borrowed_union_m2": A(U) - A(Uo),
                "overlap_double_count_m2": S - A(U), "program_over_slab_m2": A(U_cov), "program_over_opening_m2": A(U_open), "program_outside_slab_m2": A(U_out),
                "slab_uncovered_by_program_m2": A(N_unc), "slab_uncovered_outside_outline_m2": A(N_unc_out), "slab_uncovered_inside_outline_m2": A(N_unc) - A(N_unc_out),
                "program_over_core_m2": A(U_core), "excess_legacy_sum_minus_slab_m2": S - N,
                "program_volume_footprint_m2": A(vol_u), "program_volume_m3": sum(r["volume_m3"] for r, _, _ in vols),
                "building_envelope_m2": envelope, "outline_deficit_vs_envelope_m2": envelope - A(gross),
            },
            "identity_residual_m2": (S - N) - ((S - A(U)) + A(U_open) + A(U_out) - A(N_unc)),
            "opening_count": len(open_polys), "openings": openings,
            "zones": [{k: (r2(v) if isinstance(v, float) else v) for k, v in z.items() if k != "geom"} for z in zones],
            "legacy_program_sum_by_program_m2": legacy_by_prog,
            "program_volume_footprint_by_program_m2": {k: r1(sum(z["area"] for z in v)) for k, v in by_prog.items()},
            "program_union_by_program_m2": {k: r1(A(uni([z["geom"] for z in v]))) for k, v in by_prog.items()},
            "overlap_pairs_slice_zones": pairs, "mesh_volumes": [r for r, _, _ in vols], "mesh_anchor_plates": [r for r, _, _ in plates], "mesh_overlap_pairs": mesh_pairs,
            "zone_holes": zhole_rows, "gardens": gardens, "legacy_facts": {k: v for k, v in legacy.items() if not k.startswith("_")},
        })
    return {"model": model, "floors": floors, "envelope": envelope, "max_dev": max_dev, "sl_of": sl_of, "ev": ev, "run": run}


def M_Z(model, f):
    return model.floors[f]


# ── 해석: 표준 다각형(2526.0), 층별 분해 문장, 문제 목록 ────────────────────────────────────────────
def explain_standard_polygon(d):
    """같은 값 2526.0이 무엇인지: 어느 층·어느 구역이 같은 다각형인지, 구멍은 무엇인지."""
    F = {f["floor"]: f for f in d["floors"]}
    ref = F["8F"]["_geom"]["zones"][0]
    std = ref["geom"]
    same = []
    for f in ORDER:
        for z in F[f]["_geom"]["zones"]:
            if abs(z["area"] - std.area) < 0.05:
                same.append({"floor": f, "zone": z["name"], "program": z["program"], "symdiff_vs_8F_m2": round(z["geom"].symmetric_difference(std).area, 4),
                             "height_m": z["height_m"], "slab_net_m2": r1(F[f]["q"]["slab_net_m2"]), "opening_m2": r1(F[f]["q"]["opening_m2"])})
    cuts = pc.cut_geometries(d["sl_of"]["8F"])
    named = [(it["name"], g) for k, v in cuts.items() if k in ("tube_wall", "shaft") for it, g in v]
    holes = []
    for h in sorted(holes_of(std), key=lambda p: -p.area):
        names = sorted({n for n, g in named if h.buffer(0.2).intersects(g)})
        offs = [h.centroid.distance(g.centroid) for n, g in named if n in names]
        holes.append({"area_m2": r2(h.area), "centroid_m": _centroid(h), "elements": names, "offset_to_element_centroid_m": r2(min(offs)) if offs else None})
    ext = fill(std)
    return {
        "value_m2": r2(std.area),
        "what": "프로그램 볼륨 하나(A-PROG_<층>_<프로그램>_<번호>)를 바닥 위 1.5 m에서 자른 단면. 외곽 정사각형에서 튜브·승강로 원통 구멍만 뺀 '표준 다각형'.",
        "exterior_m2": r2(ext.area), "exterior_bounds_m": [r2(b) for b in ext.bounds],
        "exterior_side_m": r2(ext.bounds[2] - ext.bounds[0]),
        "holes_total_m2": r2(sum(h.area for h in holes_of(std))), "holes": holes,
        "identical_on": same,
        "why_identical": "층마다 개구(에스컬레이터·캡슐·아트리움 보이드)가 달라도 이 볼륨은 개구를 빼지 않고 튜브 구멍만 뺀다. 그래서 같은 다각형이 층마다 반복된다(대칭차 ≤ 0.004 ㎡). 층판과 무관한 값이다.",
        "meaning": "프로그램 볼륨의 투영 넓이. 층판 면적도 사용 면적도 아니다.",
    }


def build_findings(d):
    F = {f["floor"]: f for f in d["floors"]}
    for fl in d["floors"]:
        q, f = fl["q"], fl["floor"]
        iss = []
        S, N = q["program_sum_legacy_m2"], q["slab_net_m2"]
        if S > N + 0.05:
            iss.append({"code": "SUM_EXCEEDS_SLAB", "text": "구 단순합 %s ㎡ > 층판 순면적 %s ㎡ (+%s ㎡)." % (fmt(S), fmt(N), fmt(S - N))})
        if q["program_over_opening_m2"] > 0.5:
            br = ["%s ㎡ %s%s" % (fmt(o["program_over_m2"]), ("[" + " / ".join(x.replace("A-CORE-TUBE_", "").replace("A-VERT-", "") for x in o["elements"]) + "]") if o["elements"] else "[이름 없는 개구]",
                                  (" (타층 볼륨분 %s)" % fmt(o["borrowed_program_over_m2"])) if o["borrowed_program_over_m2"] > 0.05 else "")
                  for o in sorted(fl["openings"], key=lambda o: -o["program_over_m2"]) if o["program_over_m2"] > 0.5]
            iss.append({"code": "PROGRAM_OVER_OPENING", "text": "프로그램 투영 %s ㎡가 층판 개구(바닥 없음) 위에 걸친다. 볼륨이 개구를 빼지 않았다. 내역: %s." % (fmt(q["program_over_opening_m2"]), "; ".join(br))})
        if q["program_outside_slab_m2"] > 0.5:
            iss.append({"code": "PROGRAM_OUTSIDE_SLAB", "text": "프로그램 투영 %s ㎡가 층판 외곽선 밖에 있다." % fmt(q["program_outside_slab_m2"])})
        for z in fl["zones"]:
            if not z["own"]:
                zg = [g for g in fl["_geom"]["zones"] if g["name"] == z["name"]][0]["geom"]
                iss.append({"code": "BORROWED_ZONE", "text": "%s(소속 %s, 높이 %s~%s m, %s ㎡)가 이 층 절단면을 지나 합에 들어왔다. 그 중 개구 위 %s ㎡, 층판 위 %s ㎡." % (
                    z["name"], z["program_floor"], fmt(z["zmin"], 2), fmt(z["zmax"], 2), fmt(z["area"]), fmt(A(zg.intersection(fl["_geom"]["open"]))), fmt(A(zg.intersection(fl["_geom"]["slab"]))))})
        for z in fl["zones"]:
            if z["suffix"]:
                iss.append({"code": "SUFFIX_OBJECT", "text": "%s(%s ㎡)는 접미사 %s 객체. 다른 구역과 겹치지 않고(구멍을 채움) 같은 이름 '%s'로 합산된다." % (z["name"], fmt(z["area"], 2), z["suffix"], z["program"])})
            if z["shape_class"].startswith("plane"):
                iss.append({"code": "PLANE_IN_SUM", "text": "%s(%s ㎡)는 두께 %s m의 바닥면(정원)이다. 실내 볼륨과 같은 합에 더해졌다." % (z["name"], fmt(z["area"]), fmt(z["height_m"], 2))})
        for p in fl["overlap_pairs_slice_zones"]:
            iss.append({"code": p["kind"], "text": "%s와 %s가 %s ㎡ 겹친다(같은 프로그램: %s)." % (p["a"], p["b"], fmt(p["overlap_m2"], 2), p["same_program"])})
        for zr in fl["zone_holes"]:
            if zr["offset_m"] is not None and zr["offset_m"] > 1.0:
                iss.append({"code": "ZONE_HOLE_MISALIGNED", "text": "프로그램 구멍 %s ㎡ (중심 %s)이 같은 이름(%s)의 층판 개구 중심 %s에서 %s m 어긋나 있다. 구멍 %s ㎡만큼의 바닥이 프로그램에 안 덮이고, 개구 위 %s ㎡가 프로그램에 덮인다." % (
                    fmt(zr["area_m2"]), zr["centroid_m"], ", ".join(zr["elements"]) or "없음", zr["nearest_slab_opening_centroid_m"], fmt(zr["offset_m"]), fmt(zr["area_m2"]), fmt(zr["nearest_slab_opening_m2"]))})
        if q["program_over_core_m2"] > 0.5:
            iss.append({"code": "PROGRAM_OVER_CORE", "text": "프로그램 투영 %s ㎡가 코어 단면과 겹친다(코어는 모델에서 속이 찬 상자)." % fmt(q["program_over_core_m2"])})
        if q["outline_deficit_vs_envelope_m2"] > 1.0:
            iss.append({"code": "SLAB_PARTIAL_OUTLINE", "text": "층판 외곽이 건물 외곽 상자보다 %s ㎡ 작다(층판이 외곽 상자를 다 채우지 않음)." % fmt(q["outline_deficit_vs_envelope_m2"])})
        if fl["mesh_anchor_plates"]:
            iss.append({"code": "ANCHOR_PLATES", "text": "앵커판 %d개(두께 0.30 m, 볼륨 최상부)가 있다. slice 합에는 들어오지 않고 메시 겹침 목록에는 '볼륨 안에 포함'으로만 나온다." % len(fl["mesh_anchor_plates"])})
        if abs(S - q["program_union_m2"]) < 0.05 and S > 0:
            pass
        for g in fl["gardens"]:
            n = g["no_slab_or_roof_above_m2"]
            iss.append({"code": "GARDEN_ABOVE_STACK", "text": "정원 %s ㎡: 위에 층판·지붕이 없는 면적 %s ㎡. 나머지는 위층 층판 아래다. 외부 공간 여부는 UNRESOLVED." % (fmt(g["area_m2"]), fmt(n))})
        fl["issues"] = iss
        fl["explanation_ko"] = (
            "%s: 단순합 %s ㎡ − 층판 순면적 %s ㎡ = %s ㎡ = 겹침 %s + 개구 위 %s + 층판 밖 %s − 층판 미피복 %s (㎡, 계산값)." % (
                f, fmt(S), fmt(N), fmt(S - N, 1), fmt(q["overlap_double_count_m2"]), fmt(q["program_over_opening_m2"]), fmt(q["program_outside_slab_m2"]), fmt(q["slab_uncovered_by_program_m2"])))
    std = explain_standard_polygon(d)
    mx = d["max_dev"]
    gl = [
        {"code": "STANDARD_POLYGON", "text": "%s ㎡는 %s에서 같은 다각형(외곽 %s × %s m = %s ㎡ − 구멍 %d개 %s ㎡)이다. 층판 면적이 아니다." % (
            fmt(std["value_m2"]), ", ".join(x["floor"] for x in std["identical_on"]), fmt(std["exterior_side_m"]), fmt(std["exterior_side_m"]), fmt(std["exterior_m2"]), len(std["holes"]), fmt(std["holes_total_m2"]))},
        {"code": "SLICE_VS_MESH", "text": "slice와 모델 메시를 따로 재어 비교: 층판 순면적 최대 차 %.3f ㎡, 구역 단면 최대 차 %.3f ㎡, 구역 단면 대 수직 투영 최대 차 %.3f ㎡. 구역은 모두 같은 단면이 높이 전체에 이어지는 각기둥." % (
            mx["slab_net_slice_vs_mesh"], mx["zone_cut_slice_vs_mesh"], mx["zone_cut_vs_projection"])},
        {"code": "NO_DUPLICATES", "text": "slice 구역 사이 겹침(≥ %.2f ㎡) %d쌍. .001 접미사 객체는 겹침 없이 같은 구역의 구멍을 채운다." % (MIN_PAIR_M2, sum(len(f["overlap_pairs_slice_zones"]) for f in d["floors"]))},
        {"code": "FLOOR_HEIGHT_NOT_FLOOR_TO_FLOOR", "text": "A-PROG 볼륨은 바닥에서 4.05~10.05 m 솟은 덩어리(앵커판 0.30 m, 정원 0.50 m 제외). 투영하면 한 층의 평면처럼 보이지만 층고 전체를 채우는 값이 아니다."},
        {"code": "USABLE_AREA", "text": USABLE_BASIS},
    ]
    return gl, std


def _q_entry(key, v):
    lab, mean, formula, cls = DEFS[key]
    return {"value": r2(v), "unit": "m2", "label_ko": lab, "meaning": mean, "class": cls}


def to_json(d, gl, std):
    floors = []
    for fl in d["floors"]:
        floors.append({
            "floor": fl["floor"], "ffl_m": fl["ffl_m"], "ffl_abs_m": fl["ffl_abs_m"], "cut_z_m": fl["cut_z_m"],
            "quantities": {k: _q_entry(k, v) for k, v in fl["q"].items()},
            "slab": fl["slab"], "opening_count": fl["opening_count"], "openings": fl["openings"], "zones_in_slice": fl["zones"],
            "legacy_program_sum_by_program_m2": fl["legacy_program_sum_by_program_m2"],
            "program_union_by_program_m2": fl["program_union_by_program_m2"],
            "overlap_pairs_slice_zones": fl["overlap_pairs_slice_zones"], "mesh_volumes": fl["mesh_volumes"], "mesh_anchor_plates": fl["mesh_anchor_plates"],
            "mesh_overlap_pairs": fl["mesh_overlap_pairs"], "zone_holes": fl["zone_holes"], "gardens": fl["gardens"],
            "accounting_identity_residual_m2": r2(fl["identity_residual_m2"]), "explanation_ko": fl["explanation_ko"], "issues": fl["issues"],
        })
    return {
        "sheet": "A-903", "kind": "AREA_RECONCILIATION", "units": "m2 (㎡) unless the key says m / m3",
        "issue_date": common.cfg.ISSUE_DATE, "edition": common.cfg.EDITION,
        "sources": {"slices": os.path.join(d["run"], "raw_slices"), "model_objects": os.path.join(d["run"], "model_cache", "model_objects.json"),
                    "model_mesh": os.path.join(d["run"], "model_cache", "model_world.npz"), "tool": "tools/t14i/area_audit.py"},
        "model_unchanged": True, "usable_area_basis": USABLE_BASIS,
        "definitions": {k: {"label_ko": v[0], "meaning": v[1], "formula": v[2], "class": v[3]} for k, v in DEFS.items()},
        "accounting_identity": "단순합 − 층판 순면적 = 겹침 + 개구 위 + 층판 밖 − 층판 미피복 (모든 층 잔차 ≤ 0.001 ㎡)",
        "explain_2526": std, "cross_checks": {k: round(v, 4) for k, v in d["max_dev"].items()},
        "issues": gl, "legacy_key_map": LEGACY_KEY_MAP, "building_envelope_m2": r2(d["envelope"]), "floors": floors,
    }


def to_coverage_v2(d, gl, std):
    """typical_floor_coverage.json과 같은 구조(floors 목록 + note)에 모호하지 않은 이름. 구 키 중 해가 없는 것은 유지."""
    ev = d["ev"]
    plans = common.jl(os.path.join(d["run"], "plans", "plan_sheets.json"))
    plan_of = {}
    for p in plans:
        for m in p["applies_to"]:
            plan_of[m] = (p["sheet"], "OWN_PLAN" if m == p["floor"] else "SHARED_PLAN_WITH_DELTA")
    group_of = {f: g for g in ev["groups"] for f in g["floors"]}
    out = []
    for fl in d["floors"]:
        q = fl["q"]
        f = fl["floor"]
        ps = plan_of.get(f, ("A-003", "OWN_PLAN") if f == "1F" else (None, "OVERVIEW_ONLY"))
        g_ = group_of.get(f, {})
        lg = fl["legacy_facts"]
        out.append({
            "floor": f, "ffl_m": fl["ffl_m"],
            "slab_gross_m2": r1(q["slab_gross_m2"]), "slab_net_m2": r1(q["slab_net_m2"]), "opening_m2": r1(q["opening_m2"]), "opening_count": fl["opening_count"],
            "slab_area_m2": r1(q["slab_net_m2"]), "openings": {"count": fl["opening_count"], "area_m2": r1(q["opening_m2"])},
            "program_volume_footprint_by_program_m2": fl["program_union_by_program_m2"],
            "program_volume_footprint_sum_naive_m2": r1(q["program_sum_legacy_m2"]),
            "program_volume_footprint_union_m2": r1(q["program_union_m2"]), "program_volume_footprint_union_own_floor_m2": r1(q["program_union_own_m2"]),
            "program_volume_footprint_mesh_m2": r1(q["program_volume_footprint_m2"]), "program_volume_m3": r1(q["program_volume_m3"]),
            "program_over_slab_m2": r1(q["program_over_slab_m2"]), "program_over_opening_m2": r1(q["program_over_opening_m2"]),
            "program_outside_slab_m2": r1(q["program_outside_slab_m2"]), "slab_uncovered_by_program_m2": r1(q["slab_uncovered_by_program_m2"]),
            "borrowed_zones": [{"zone": z["name"], "program_floor": z["program_floor"], "area_m2": r1(z["area"])} for z in fl["zones"] if not z["own"]],
            "excess_naive_sum_minus_slab_net_m2": r1(q["excess_legacy_sum_minus_slab_m2"]),
            "usable_area_basis": USABLE_BASIS,
            "tubes": lg["tubes"], "cores": lg["cores"], "columns": lg["columns"],
            **({"delta_vs_reference": {"reference": "8F" if f == "9F" else "13F", "slab_symdiff_m2": None}} if f in ("9F", "14F") else {}),
            "plan_sheet": ps[0], "publication_status": ps[1], "equivalence_group": g_.get("id"), "equivalence_kind": g_.get("kind"), "also_in": "A-902 · A-903",
        })
    # delta_vs_reference는 A-902 그림에서 계산한 값을 옮긴다(여기서는 다시 재지 않고 같은 식으로 계산)
    F = {fl["floor"]: fl for fl in d["floors"]}
    for e in out:
        if "delta_vs_reference" in e:
            ref = e["delta_vs_reference"]["reference"]
            diff = F[e["floor"]]["_geom"]["slab"].symmetric_difference(F[ref]["_geom"]["slab"])
            e["delta_vs_reference"]["slab_symdiff_m2"] = r1(diff.area)
            e["delta_vs_reference"]["pieces"] = len([p for p in parts(diff) if p.area > 0.5])
    return {"scale": "1:1000", "sheet": "A-902", "also_in": "A-903", "floors": out,
            "definitions": {k: {"label_ko": v[0], "meaning": v[1], "formula": v[2], "class": v[3]} for k, v in DEFS.items()},
            "legacy_key_map": LEGACY_KEY_MAP, "usable_area_basis": USABLE_BASIS,
            "note": "B2~15F 17개 층 모두 A-902에 그려진다. 면적 숫자는 전부 '프로그램 볼륨 투영' 또는 '층판' 라벨이 붙은 값이며 사용 면적이 아니다(정의·분해는 A-903, area_reconciliation.json). "
                    "별도 평면이 없는 층은 publication_status=OVERVIEW_ONLY. STRICT 동등 쌍 0건(증거: floor_equivalence_evidence.json)이라 층을 합치지 않았다."}


def write_md(R, path):
    L = ["# 면적 데이터 재검증 (A-903)", "",
         "대상: `typical_floor_coverage.json`(V3). 모델·slice는 읽기 전용이며 숫자를 맞추려고 고치지 않았다. 단위 ㎡.", "",
         "## 한 줄 결론", "",
         "- 구 A-902의 '프로그램 합'은 **프로그램 볼륨(바닥에서 4~10 m 솟은 덩어리)을 바닥 위 1.5 m에서 자른 단면의 단순 합**이다. 층판 면적도 사용 면적도 아니다.",
         "- %s" % R["issues"][0]["text"], "- 사용(전용) 면적: %s" % USABLE_BASIS, "",
         "## 정의", "", "| 키 | 이름 | 뜻 | 구분 |", "|---|---|---|---|"]
    for k, v in R["definitions"].items():
        L.append("| `%s` | %s | %s | %s |" % (k, v["label_ko"], v["meaning"], v["class"]))
    L += ["", "## 층별 수치 (㎡)", "",
          "| 층 | 층판 외곽 | 개구 | 층판 순 | 단순합(구) | 합집합 | 개구 위 | 층판 밖 | 미피복 | 단순합−순 |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for fl in R["floors"]:
        q = {k: v["value"] for k, v in fl["quantities"].items()}
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            fl["floor"], fmt(q["slab_gross_m2"]), fmt(q["opening_m2"]), fmt(q["slab_net_m2"]), fmt(q["program_sum_legacy_m2"]), fmt(q["program_union_m2"]),
            fmt(q["program_over_opening_m2"]), fmt(q["program_outside_slab_m2"]), fmt(q["slab_uncovered_by_program_m2"]), fmt(q["excess_legacy_sum_minus_slab_m2"])))
    e = R["explain_2526"]
    L += ["", "## 2526.0은 무엇인가", "", e["what"], "",
          "- 외곽 %s × %s m = %s ㎡, 구멍 %d개 합 %s ㎡ → %s ㎡." % (fmt(e["exterior_side_m"]), fmt(e["exterior_side_m"]), fmt(e["exterior_m2"]), len(e["holes"]), fmt(e["holes_total_m2"]), fmt(e["value_m2"])),
          "- 같은 다각형인 층: " + ", ".join("%s(%s)" % (x["floor"], x["program"]) for x in e["identical_on"]) + ".", "- " + e["why_identical"], "", "| 구멍 ㎡ | 중심(도면틀 m) | 겹치는 이름 | 이름 요소 중심과의 거리 m |", "|---:|---|---|---:|"]
    for h in e["holes"]:
        L.append("| %s | %s | %s | %s |" % (fmt(h["area_m2"]), h["centroid_m"], ", ".join(h["elements"]) or "이름 없음", fmt(h["offset_to_element_centroid_m"]) if h["offset_to_element_centroid_m"] is not None else "—"))
    for f in ("8F", "12F"):
        fl = [x for x in R["floors"] if x["floor"] == f][0]
        L += ["", "## %s 분해" % f, "", fl["explanation_ko"], ""]
        for it in fl["issues"]:
            L.append("- `%s` %s" % (it["code"], it["text"]))
    L += ["", "## 전 층 문제 목록", ""]
    for fl in R["floors"]:
        L.append("### %s" % fl["floor"])
        L.append(fl["explanation_ko"])
        for it in fl["issues"]:
            L.append("- `%s` %s" % (it["code"], it["text"]))
        L.append("")
    L += ["## 교차 확인(slice 대 모델 메시)", "", "```", json.dumps(R["cross_checks"], ensure_ascii=False, indent=1), "```", "",
          "## 구 키 처리", ""] + ["- `%s`: %s" % (k, v) for k, v in R["legacy_key_map"].items()]
    open(path, "w", encoding="utf-8").write("\n".join(L) + "\n")


def run_data(run):
    """데이터만 만들고 JSON·MD 세 개를 쓴다(시트 제외). 반환 (collect 결과, R, V2, 출력 폴더)."""
    out = common.v4_dir(run, "area")
    d = collect(run)
    gl, std = build_findings(d)
    R = to_json(d, gl, std)
    V2 = to_coverage_v2(d, gl, std)
    common.jd(R, os.path.join(out, "area_reconciliation.json"))
    common.jd(V2, os.path.join(out, "typical_floor_coverage_v2.json"))
    write_md(R, os.path.join(out, "area_reconciliation.md"))
    return d, R, V2, out


if __name__ == "__main__":
    _run = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else common.RUN_DEFAULT
    _d, _R, _V2, _out = run_data(_run)
    print(os.path.abspath(os.path.join(_out, "area_reconciliation.json")))

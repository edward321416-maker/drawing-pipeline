"""고정된 중간발표 1층 데이터(model\\m_1f_source.json)에서 태그된 1F 마스터 모델을 만든다.

출력: model\\1F_master.model.json  (엔진이 읽는 형식 — 월드 좌표 m, 원점 = X1·A 교점, x 동, y 북)
Blender 파일은 master\\make_blend.py가 이 JSON에서 만든다.

대지 좌표 (u, v) -> 마스터 좌표 (x, y) = (u + 9, v + 18).
이 모듈은 중간발표 폴더를 읽지 않는다. 입력은 고정된 JSON뿐이다.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent
if str(ENGINE) not in sys.path:  # 스크립트로 직접 실행해도 엔진 패키지를 찾도록
    sys.path.insert(0, str(ENGINE))

import numpy as np  # noqa: E402
import shapely  # noqa: E402
from shapely import wkt  # noqa: E402
from shapely.affinity import translate  # noqa: E402
from shapely.geometry import LineString, Point, Polygon, box  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

from engine_params import load_params  # noqa: E402
from extract.schema import Model, ModelObject  # noqa: E402
from symbols.restroom import PROGRAM_BY_ROOM, all_doors, build_restroom  # noqa: E402
from symbols.stair_core import CORE_VES_SIDE, DOOR_HEIGHT_M, build_stair_core, flight_blocks  # noqa: E402

SOURCE = ENGINE / "model" / "m_1f_source.json"
ADJUST = ENGINE / "model" / "design_adjustments.json"   # 사용자가 승인한 설계 조정(원본 데이터는 건드리지 않는다)
GROVE_DESIGN = ENGINE / "model" / "grove_design.json"   # 공원(숲 마당) 설계안 (master\design_grove.py, 사용자 승인 대상)
SITE_SOURCE = ENGINE / "model" / "m_site_source.json"   # 대지·도로·이웃 건물 (master\extract_site_source.py가 고정)
OUT_MODEL = ENGINE / "model" / "1F_master.model.json"

DU, DV = 9.0, 18.0          # 대지 좌표 -> X1·A 원점
GROUND_Z = -0.6             # 대지 맥락의 지면 높이: 1층 바닥판(z -0.5 ~ 0) 바로 아래
SIDEWALK_W_M = 3.5          # 차도를 따라 두르는 보도 폭(실측 폭이 아니다)
FLAT_T = 0.05               # 대지·도로·보도·건축한계선은 얇은 판으로만 둔다(평면은 바닥 윤곽으로 그린다)
CONTEXT_H = 12.0            # 이웃 건물의 자리표시 높이(평면 도면에서는 쓰지 않는다. 실제 층수는 이름에 적혀 있다)
SLAB_T = 0.5                # s7.py: 층판 z0 = ZF - 0.5
GLASS_T = 0.15              # 유리 튜브 벽 두께
ZONE_T = 0.05
SANITARY_H = {"wc": 0.4, "urinal": 0.6, "basin": 0.85}   # 위생도기 높이(3D 검토용)
QUAD_SEGS = 12              # 원을 48각형으로

TUBE_NAMES = {
    "T1": "T1 나선 램프",
    "T2": "T2 빛 튜브",
    "T3": "T3 전망 승강기",
    "T4": "T4 전망 승강기",
}
SHAFT_NAMES = {
    "EV1": "비상용 승강기 EV1",
    "EV2": "비상용 승강기 EV2",
    "M1": "설비 샤프트 M1",
    "M2": "설비 샤프트 M2",
    "FR": "화물 승강기 FR",
    "PL": "광장 승강기 PL",
}


def _parts(geom):
    if geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    return [g for g in geom.geoms if g.geom_type == "Polygon" and g.area > 1e-6]


def prism(geom, z0: float, z1: float):
    """구멍이 있는 다각형도 닫힌 각기둥 메시로 만든다(캡은 제약 들로네 삼각분할)."""
    verts, tris = [], []

    def add(*pts):
        base = len(verts)
        verts.extend(pts)
        return base

    for poly in _parts(geom):
        for tri in shapely.constrained_delaunay_triangles(poly).geoms:
            (a, b, c) = list(tri.exterior.coords)[:3]
            for z in (z0, z1):
                base = add((a[0], a[1], z), (b[0], b[1], z), (c[0], c[1], z))
                tris.append((base, base + 1, base + 2))
        for ring in [poly.exterior, *poly.interiors]:
            pts = list(ring.coords)
            for p, q in zip(pts[:-1], pts[1:]):
                base = add((p[0], p[1], z0), (q[0], q[1], z0), (q[0], q[1], z1), (p[0], p[1], z1))
                tris += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
    return np.array(verts, dtype=float), np.array(tris, dtype=int)


def _obj(name, kind, name_ko, geom, z0, z1, **props) -> ModelObject:
    verts, tris = prism(geom, z0, z1)
    return ModelObject(name, {"kind": kind, "name_ko": name_ko, **props}, verts, tris)


def load_adjustments(path=ADJUST) -> dict:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def load_site_source(path=SITE_SOURCE, design_path=GROVE_DESIGN) -> dict | None:
    """대지 원천. 공원(그늘 숲 마당) 설계안 파일이 있으면 grove_design 키로 붙인다."""
    p = Path(path)
    if not p.exists():
        return None
    data = json.loads(p.read_text(encoding="utf-8"))
    d = Path(design_path)
    if d.exists():
        data["grove_design"] = json.loads(d.read_text(encoding="utf-8"))
    return data


def _entrance_mark(start, end, length=4.0, thick=0.7):
    """출입구 표시: 동선이 건물·계단에 닿는 자리(end)에 동선과 직각인 짧은 굵은 막대(대지 좌표). start는 방향만 정한다.
    사용자 지시(2026-11-02): 큰 화살표는 그리지 않는다."""
    (x0, y0), (x1, y1) = start, end
    L = math.hypot(x1 - x0, y1 - y0)
    ux, uy = (x1 - x0) / L, (y1 - y0) / L
    nx, ny = -uy, ux
    hl, ht = length / 2, thick / 2
    return Polygon([(x1 + nx * hl - ux * ht, y1 + ny * hl - uy * ht), (x1 + nx * hl + ux * ht, y1 + ny * hl + uy * ht),
                    (x1 - nx * hl + ux * ht, y1 - ny * hl + uy * ht), (x1 - nx * hl - ux * ht, y1 - ny * hl - uy * ht)])

def _dashes(line, on=3.0, off=3.0, width=0.25):
    from shapely.ops import substring
    out, s = [], 0.0
    while s < line.length:
        out.append(substring(line, s, min(s + on, line.length)).buffer(width / 2, cap_style=2))
        s += on + off
    return out


def build_context_objects(site_src: dict) -> list[ModelObject]:
    """대지 경계, 건축한계선, 차도(하나로 합친 면)·보도 띠·중앙 차선, 이웃 건물, 외부공간(공원 설계안 포함), 수목,
    선큰 계단, 출입구 화살표, 지하철 출구. 겹치는 면은 우선순위(이웃 건물 > 차도 > 보도, 모두 대지 바깥)로 빼서 겹침이 없게 한다.
    건물 도면(1:200)에서는 그리지 않고 대지 도면(1:400)에서만 그린다."""
    def multi(rings):
        # 항목은 {"shell", "holes"}(구멍 보존) 또는 옛 형식의 고리 하나
        parts = [translate(Polygon(r["shell"], r.get("holes", [])) if isinstance(r, dict) else Polygon(r), DU, DV).buffer(0)
                 for r in rings]
        return unary_union(parts) if parts else Polygon()

    lot, buildable = multi(site_src["site"]["rings"]), multi(site_src["buildable"]["rings"])
    z0, z1 = GROUND_Z - FLAT_T, GROUND_Z
    objs = [
        _obj("Site_Lot", "site", "대지", lot, z0, z1, label_text="대지", label_role="room"),
        _obj("Setback_Line", "setback", "건축한계선", buildable, z0, z1, label=False),
    ]
    ctx = [(b, multi(b["rings"])) for b in site_src["context_buildings"]]
    ctx_all = unary_union([g for _b, g in ctx]) if ctx else Polygon()
    taken = unary_union([lot, ctx_all])
    carriage = multi(site_src["carriageway"]["rings"]).difference(taken)
    objs.append(_obj("Road_Carriageway", "road", site_src["carriageway"]["name_ko"], carriage, z0, z1, label=False))
    verge = carriage.buffer(SIDEWALK_W_M).difference(carriage).difference(taken)
    verge = unary_union([g for g in getattr(verge, "geoms", [verge]) if g.geom_type == "Polygon" and g.area > 20.0])
    if not verge.is_empty:
        objs.append(_obj("Sidewalk_Verge", "sidewalk", "보도", verge, z0, z1, label=False))
    # 도로 이름 글자 자리: 그리지 않는 방(room). 도면 창 안에서만 라벨이 붙는다(context=1)
    for key, v in site_src["road_names"].items():
        geom = multi(v["rings"]).difference(taken)
        if not geom.is_empty:
            objs.append(_obj(f"Room_Road_{key}", "room", v["name_ko"], geom, z0, z1, label_text=v["name_ko"],
                             label_role="sub", no_area=1, context=1))
    dashes = []
    for pts in site_src["road_centerlines"]:
        line = translate(LineString(pts), DU, DV)
        dashes += [d.intersection(carriage) for d in _dashes(line)]
    dashes = unary_union([d for d in dashes if not d.is_empty])
    if not dashes.is_empty:
        objs.append(_obj("Road_Markings", "road_marking", "중앙 차선", dashes, z0, z1, label=False))
    for i, (b, g) in enumerate(ctx):
        props = {"label_text": b["name_ko"], "label_role": "sub"} if b["label"] else {"label": False}
        objs.append(_obj(f"Ctx_{i:02d}", "context_building", b["name_ko"], g, GROUND_Z, GROUND_Z + CONTEXT_H, **props))

    # 외부공간. 공원 설계안(산책로·잔디 마당·수목)이 있으면 숲 마당·광장에서 그 면을 빼 겹치지 않게 한다
    gd = site_src.get("grove_design")
    carve = Polygon()
    ext = {k: multi(v["rings"]) for k, v in site_src["exterior_spaces"].items()}
    if gd:
        path_g, lawn_g = multi(gd["path"]["rings"]), multi(gd["lawn"]["rings"])
        carve = unary_union([path_g, lawn_g])
        ext["Plaza"], ext["Grove"] = ext["Plaza"].difference(path_g), ext["Grove"].difference(carve)
    for key, v in site_src["exterior_spaces"].items():
        objs.append(_obj(f"Ext_{key}", "exterior_space", v["name_ko"], ext[key], z0, z1, use=v["use"],
                         label_text=v["name_ko"], label_role="sub"))
    if gd:
        objs.append(_obj("Ext_GrovePath", "exterior_space", gd["path"]["name_ko"], path_g, z0, z1, use="path", label=False))
        objs.append(_obj("Ext_GroveLawn", "exterior_space", gd["lawn"]["name_ko"], lawn_g, z0, z1, use="lawn",
                         label_text=gd["lawn"]["name_ko"], label_role="sub"))
    grove_full = multi(site_src["exterior_spaces"]["Grove"]["rings"])
    kept = [(u, v, r) for u, v, r in site_src["trees"] if not (gd and grove_full.contains(Point(u + DU, v + DV)))]
    all_trees = kept + ([tuple(t) for t in gd["trees"]] if gd else [])
    trees = unary_union([Point(u + DU, v + DV).buffer(r, quad_segs=8) for u, v, r in all_trees])
    objs.append(_obj("Trees", "tree", "수목", trees, z0, z1, label=False))

    st = site_src["sunken_stair"]
    bx = (st["bounds"][0] + DU, st["bounds"][1] + DV, st["bounds"][2] + DU, st["bounds"][3] + DV)
    objs.append(_obj("Sunken_Stair", "sunken_stair", "선큰 계단", box(*bx), z0, z1, treads=st["treads"], down=st["down"],
                     bx0=bx[0], by0=bx[1], bx1=bx[2], by1=bx[3], label_text=st["label"], label_role="sub"))
    for e in site_src["entrances"]:
        arrow = translate(_entrance_mark(e["start"], e["end"]), DU, DV)
        objs.append(_obj(f"Entrance_{e['key']}", "entrance", e["name_ko"], arrow, z0, z1, label_text=e["name_ko"],
                         label_role="sub"))
    for i, e in enumerate(site_src["subway_exits"]):
        u, v = e["center"]
        objs.append(_obj(f"Subway_{i}", "subway_exit", e["name_ko"], translate(box(u - 1.6, v - 3.2, u + 1.6, v + 3.2), DU, DV),
                         z0, z1, label_text=e["name_ko"], label_role="sub"))
    return objs

def restroom_world_bounds(src: dict, adjustments: dict | None = None) -> dict:
    """화장실 방 외곽(벽 중심선)의 월드 좌표 {방 이름: (x0, y0, x1, y1)}. 승인된 이동(restroom_shift)이 있으면 반영한다.
    마스터 빌더, 시트 빌더, 테스트가 모두 이 함수로 같은 위치를 쓴다."""
    adjustments = load_adjustments() if adjustments is None else adjustments
    shift = adjustments.get("restroom_shift", {})
    out = {}
    for wid, b in src["wc"].items():
        dy = shift.get(wid, {}).get("dy_m", 0.0)
        out[wid] = (b[0] + DU, b[1] + DV + dy, b[2] + DU, b[3] + DV + dy)
    return out


def build_objects(src: dict, adjustments: dict | None = None, site_src: dict | None = None) -> list[ModelObject]:
    adjustments = load_adjustments() if adjustments is None else adjustments

    def T(g):
        return translate(g, DU, DV)

    floor_h = src["floor_z"]["2F"] - src["floor_z"]["1F"]
    plate = T(wkt.loads(src["wkt"]["plate_1f"]))
    piloti_raw = T(wkt.loads(src["wkt"]["piloti"]))
    service_raw = T(wkt.loads(src["wkt"]["service"]))
    cap_outer = T(wkt.loads(src["wkt"]["cap_w"]))

    def circle(c, r):
        return Point(c[0] + DU, c[1] + DV).buffer(r, quad_segs=QUAD_SEGS)

    small_polys = {n: circle(src["tubes"][n]["c"], src["tubes"][n]["r"]) for n in src["small"]}
    small_union = unary_union(list(small_polys.values()))

    # 층판의 구멍 중 튜브가 아닌 것(선큰 연결 개구부). 승인된 설계 조정이 있으면 개구부를 줄이고 남는 면은 바닥으로 메운다.
    tube_union = unary_union([circle(t["c"], t["r"]) for k, t in src["tubes"].items() if k in TUBE_NAMES])
    link_voids = []
    for ring in list(plate.interiors):
        hp = shapely.Polygon(ring)
        if hp.intersection(tube_union).area / hp.area >= 0.5:
            continue
        clip = adjustments.get("sunken_link_clip")
        new = hp.intersection(box(*clip["box"])) if clip else hp
        plate = plate.union(hp.difference(new))
        link_voids.append(new)

    slab = plate.difference(small_union)
    enclosed = plate.difference(piloti_raw).difference(small_union)
    zone_piloti = piloti_raw.intersection(plate).difference(small_union)
    zone_service = service_raw.intersection(enclosed)
    zone_market = enclosed.difference(service_raw)

    objs: list[ModelObject] = []
    objs.append(_obj("Slab_1F", "slab", "1층 바닥판", slab, -SLAB_T, 0.0))
    objs.append(_obj("Zone_Market", "zone", "시장 홀", zone_market, 0.0, ZONE_T, use="market_hall"))
    objs.append(_obj("Zone_Service", "zone", "하역·서비스", zone_service, 0.0, ZONE_T, use="service"))
    objs.append(_obj("Zone_Piloti", "zone", "필로티 광장", zone_piloti, 0.0, ZONE_T, use="piloti_plaza"))

    r_col = src["col_r"]
    for u, v, _z0, _z1 in src["columns"]:
        x, y = u + DU, v + DV
        objs.append(_obj(f"Col_{x:g}_{y:g}", "column", f"기둥 ({x:g}, {y:g})",
                         Point(x, y).buffer(r_col, quad_segs=QUAD_SEGS), 0.0, floor_h, label=False))

    for tid, label in TUBE_NAMES.items():
        t = src["tubes"][tid]
        ring = circle(t["c"], t["r"]).difference(circle(t["c"], t["r"] - GLASS_T))
        objs.append(_obj(f"Tube_{tid}", "tube_wall", label, ring, 0.0, floor_h, tube_id=tid))
    cap_ring = cap_outer.difference(cap_outer.buffer(-GLASS_T))
    objs.append(_obj("Capsule_W", "tube_wall", "서측 캡슐", cap_ring, 0.0, floor_h, tube_id="CAP_W"))

    for sid in src["small"]:
        objs.append(_obj(f"Shaft_{sid}", "shaft", SHAFT_NAMES[sid], small_polys[sid], 0.0, floor_h,
                         shaft_id=sid, label_text=sid))

    for i, hp in enumerate(link_voids):
        name = "Void_SunkenLink" if i == 0 else f"Void_SunkenLink_{i}"
        objs.append(_obj(name, "void", "선큰 연결 개구부", hp, -SLAB_T, floor_h, label_text="개구부"))

    # 코어: 승인된 코어 심볼(symbols\stair_core.py)에서 벽·칸막이·계단 갈래·문 스윙을 만든다
    stair_p = load_params().stair
    for cid, b in src["stairs"].items():
        bx = (b[0] + DU, b[1] + DV, b[2] + DU, b[3] + DV)
        off = adjustments.get("core_hall_door_offset", {}).get(cid, {}).get("offset_m", 0.0)
        core = build_stair_core(cid, bx, CORE_VES_SIDE[cid], stair_p, hall_door_offset=off)
        objs.append(_obj(f"Core_{cid}_wall", "core_wall", f"코어 {cid} 벽", core.walls, 0.0, floor_h, core_id=cid))
        objs.append(_obj(f"Core_{cid}_partition", "partition_wall", f"코어 {cid} 부속실 칸막이", core.partition,
                         0.0, floor_h, core_id=cid, grid_exempt=1))
        for fl, top in flight_blocks(core, stair_p):
            objs.append(_obj(f"Core_{cid}_flight{fl.index}", "stair", f"코어 {cid} 계단 {fl.index}갈래", fl.polygon,
                             0.0, top, core_id=cid, flight=fl.index, treads=fl.treads))
        for door, tag in zip(core.doors, ("hall", "stair")):
            objs.append(_obj(f"Core_{cid}_door_{tag}", "door", f"코어 {cid} {door.name}", door.swing,
                             0.0, DOOR_HEIGHT_M, core_id=cid, width_m=door.width))
        objs.append(_obj(f"Room_Core_{cid}", "room", f"코어 {cid}", box(*bx), ZONE_T, 2 * ZONE_T,
                         label_text=f"코어 {cid}", core_id=cid, symbol="stair_core", ves_side=CORE_VES_SIDE[cid],
                         bx0=bx[0], by0=bx[1], bx1=bx[2], by1=bx[3], hall_door_offset=off))
    # 화장실: 승인된 화장실 심볼(symbols\restroom.py)에서 벽·칸막이·위생도기·문 스윙·방을 만든다.
    # 기둥은 모델의 기둥 객체가 따로 있으므로 심볼에 넘기지 않는다(기둥과의 겹침은 모델 검사 G1이 본다).
    rest_p = load_params().restroom
    for wid, bx in restroom_world_bounds(src, adjustments).items():
        program = PROGRAM_BY_ROOM[wid]
        rr = build_restroom(wid, bx, program, rest_p)
        objs.append(_obj(f"WC_{wid}_wall", "partition_wall", f"화장실 {wid} 벽", rr.walls, 0.0, floor_h, wc_id=wid))
        if not rr.inner_walls.is_empty:
            objs.append(_obj(f"WC_{wid}_inner", "partition_wall", f"화장실 {wid} 방 사이 벽", rr.inner_walls,
                             0.0, floor_h, wc_id=wid))
        for i, g in enumerate(rr.thin, 1):
            objs.append(_obj(f"WC_{wid}_thin{i}", "partition_wall", f"화장실 {wid} 칸막이 {i}", g, 0.0, DOOR_HEIGHT_M,
                             wc_id=wid, thin=1, grid_exempt=1))
        for f in rr.fixtures:
            objs.append(_obj(f"WC_{wid}_{f.name}", "sanitary", f.name, f.polygon, 0.0, SANITARY_H[f.kind],
                             wc_id=wid, sanitary=f.kind))
        for d in all_doors(rr):
            if d.swing is not None:
                objs.append(_obj(f"WC_{wid}_door_{d.name}", "door", f"화장실 {wid} {d.name}", d.swing,
                                 0.0, DOOR_HEIGHT_M, wc_id=wid, width_m=d.width))
        single = len(rr.units) == 1
        for u in rr.units:
            objs.append(_obj(f"Room_WC_{wid}_{u.name}", "room", f"화장실 {wid} {u.label}", u.interior,
                             ZONE_T, 2 * ZONE_T, wc_id=wid, symbol="restroom", program=program, unit=u.name,
                             label_text="화장실" if single else u.name, label_role="room" if single else "sub",
                             bx0=bx[0], by0=bx[1], bx1=bx[2], by1=bx[3]))
    if site_src is not None:
        objs += build_context_objects(site_src)
    return objs


def load_source(path=SOURCE) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_master(path=SOURCE, adjustments: dict | None = None, site_path=SITE_SOURCE) -> Model:
    src = load_source(path)
    nu, nv = src["north_vec"]  # 대지 축(u 오른쪽, v 위)에서의 진북 방향
    meta = {"north_angle_deg": round(math.degrees(math.atan2(nu, nv)), 3)}  # 도면 위쪽에서 시계 방향
    return Model(build_objects(src, adjustments, load_site_source(site_path)), meta)


def write_model_json(model: Model, path=OUT_MODEL) -> Path:
    data = {
        "schema": 1,
        "units": "m",
        "meta": model.meta,
        "objects": [
            {"name": o.name, "props": o.props, "verts": o.verts.round(6).tolist(), "tris": o.tris.tolist()}
            for o in model.objects
        ],
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def main() -> int:
    import os

    model = build_master()
    out = write_model_json(model)
    kinds: dict[str, int] = {}
    for o in model.objects:
        kinds[o.kind] = kinds.get(o.kind, 0) + 1
    print(f"마스터 모델 JSON: {os.path.abspath(out)}")
    print("객체 수:", dict(sorted(kinds.items())), "합계", len(model.objects))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

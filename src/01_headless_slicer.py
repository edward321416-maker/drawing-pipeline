"""STEP 1 — 헤드리스 수평 절단 + 정사영 렌더 (Blender 안에서 실행).

    blender -b --factory-startup -P src/01_headless_slicer.py -- --input <model.glb|.blend> --out output/drawing_pipeline [--cut 1.5] [--floors 1F,2F] [--phase slice|render|both]
    blender -b <model.blend> -P src/01_headless_slicer.py -- --out ...

산출물 (out/raw_slices/):
    camera_bounds.json      모든 하위 단계가 공유하는 단 하나의 좌표 경계 (정사각, 건물 + 15 % 여백)
    floors.json             층 이름 → 마감 바닥 z (층판 윗면에서 읽음, 하드코딩 없음)
    floor_<층>_slice.json   절단 선분, 투영 윤곽, 변환 메타데이터, 방/영역
    floor_<층>_ao.png       점토 + AO 정사영 렌더 (render 단계)
    floor_<층>_cutmask.png  절단 요소만 검은색인 정렬 검증용 마스크 (render 단계)

좌표는 모델의 월드 좌표(미터)를 그대로 쓴다. 숫자 좌표를 이 파일에 직접 쓰지 않는다 (AGENTS.md §6.1).
"""
import argparse
import json
import math
import os
import re
import sys

import bmesh
import bpy
from mathutils import Vector

# ── 분류 규칙: 이름 접두어 → (kind, 한글 이름 서식). 맞는 규칙이 없고 태그도 없으면 빌드를 거부한다 (AGENTS.md §6.2) ──
NAME_RULES = [
    (r"^A-STRC_column", "column", lambda m, n: "기둥"),
    (r"^A-CORE-TUBE_EV(\d*)", "shaft", lambda m, n: "승강기 샤프트 EV" + m.group(1)),
    (r"^A-CORE-TUBE_cap([EW])", "tube_wall", lambda m, n: "캡슐 " + ("동" if m.group(1) == "E" else "서")),
    (r"^A-CORE-TUBE_([A-Za-z]+\d*)", "tube_wall", lambda m, n: "튜브 " + m.group(1)),
    (r"^A-FLOR_s7_(\w+)", "slab", lambda m, n: "층판 " + m.group(1)),
    (r"^A-FLOR_", "slab", lambda m, n: "유리 바닥"),
    (r"^A-PROG_([^_]+)_(.+?)(?:_\d+)?(?:\.\d+)?$", "zone", lambda m, n: m.group(2)),
    (r"^A-VERT-ESCL_(\S+?)_", "stair", lambda m, n: "에스컬레이터 " + m.group(1)),
    (r"^A-VERT-ELEV", "shaft", lambda m, n: "승강기 카"),
    (r"^A-VERT-SPRL_(\S+?)_(T\d)", "ramp", lambda m, n: "나선 램프 " + m.group(2) + " (" + m.group(1) + ")"),
    (r"^A-VERT-STRS_(\w)", "core_wall", lambda m, n: "코어 " + m.group(1)),
    (r"^X-CTXT_", "context_building", lambda m, n: "주변 건물"),
    (r"^A-FACD_", "facade", lambda m, n: "입면 부재"),
    (r"^(A-SITE_|C-SITE_|L-PLNT_)", "site", lambda m, n: "대지 요소"),
    (r"^A-ROOF_", "roof", lambda m, n: "지붕"),
    (r"^(Icosphere|Cylinder)", "tree", lambda m, n: "수목"),
]
CUT_KINDS = {"column", "exterior_wall", "core_wall", "partition_wall", "tube_wall", "shaft", "stair", "ramp", "facade"}
META_KINDS = {"door", "window", "fixture", "sanitary"}      # 메시를 자르지 않고 변환 정보만 뽑는다
ZONE_KINDS = {"zone", "room", "void"}                       # void = 개구부(층판의 뚫린 부분)
MIN_FLOOR_AREA_LABEL = None


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help=".glb 또는 .blend (.blend는 blender -b 로 먼저 열었으면 생략)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--cut", type=float, default=1.5, help="바닥 위 절단 높이(m). AGENTS.md §6.1 = 1.5")
    ap.add_argument("--floors", default="", help="쉼표로 구분한 층 이름. 비우면 전체")
    ap.add_argument("--size", type=int, default=4096)
    ap.add_argument("--samples", type=int, default=24)
    ap.add_argument("--threads", type=int, default=8, help="AGENTS: 시뮬레이션 자원 제한 ≤ 8 코어")
    ap.add_argument("--phase", choices=("slice", "render", "both"), default="both")
    ap.add_argument("--margin", type=float, default=0.15)
    ap.add_argument("--frame-ref", default=None, help="기준 층(1층 마스터)의 camera_bounds.json. 도면 방향을 그 진북각(north_deg)에 맞춘다")
    return ap.parse_args(argv)


def align_theta_to_reference(theta, ref_path):
    """detect_theta는 건물 축을 |θ| ≤ 45°로 정규화해 90° 단위 정보를 버린다. GLB에는 마스터 .blend의 north_angle_deg도 없어서,
    그대로 쓰면 1층 마스터와 90° 어긋난 도면 방향이 나온다. 기준 층의 north_deg와 90°의 배수만큼만 달라지도록 θ를 옮긴다.
    기준과 90° 배수로 맞지 않으면(같은 건물이 아니거나 축이 다름) 빌드를 거부한다."""
    ref = json.load(open(ref_path, encoding="utf-8"))["frame"]["north_deg"]
    th = math.degrees(theta)
    k = round((ref - th) / 90.0)
    th2 = th + 90.0 * k
    if abs(ref - th2) > 1.0:
        raise SystemExit("도면 방향 기준 불일치: 기준 north_deg=%.3f, 이 모델 건물축 θ=%.3f (90° 배수로 맞지 않음). 같은 건물인지 확인" % (ref, th))
    print("FRAME_REF north_deg=%.3f  detect_theta=%.3f  → 90°×%d 보정 → theta=%.3f" % (ref, th, k, th2))
    return round(math.radians(th2), 7)


def load_scene(path):
    if not path:
        return
    ext = os.path.splitext(path)[1].lower()
    if ext == ".glb" or ext == ".gltf":
        bpy.ops.wm.read_factory_settings(use_empty=True)        # 기본 큐브·카메라·조명이 모델로 섞이지 않게 비운다
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".blend":
        bpy.ops.wm.open_mainfile(filepath=path)
    else:
        raise SystemExit("지원하지 않는 입력: " + path)


def classify(obj):
    """(kind, name_ko, floor_tag, source). 태그가 있으면 태그를, 없으면 이름 규칙을 쓴다."""
    kind = obj.get("kind")
    if kind:
        return kind, obj.get("name_ko") or obj.name, obj.get("floor"), "tag"
    for pat, k, fmt in NAME_RULES:
        m = re.match(pat, obj.name)
        if m:
            floor = None
            fm = re.match(r"^A-PROG_([^_]+)_", obj.name) or re.match(r"^A-FLOR_s7_(\w+)", obj.name)
            if fm:
                floor = fm.group(1)
            return k, fmt(m, obj.name), floor, "name"
    return None, None, None, None


def world_bmesh(obj, deps):
    ev = obj.evaluated_get(deps)
    mesh = ev.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.transform(obj.matrix_world)
    ev.to_mesh_clear()
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)   # glb는 면마다 꼭짓점이 갈라져 있어 윤곽이 조각난다
    return bm


# 도면 좌표계: 건물 축에 맞춰 월드 좌표를 -THETA 만큼 돌린다. 이후 모든 산출물(SVG·DXF·카메라 경계)이 이 좌표계를 쓴다.
FRAME = {"theta": 0.0}


def rot(x, y):
    c, s = math.cos(FRAME["theta"]), math.sin(FRAME["theta"])
    return (x * c + y * s, -x * s + y * c)


def unrot(x, y):
    c, s = math.cos(FRAME["theta"]), math.sin(FRAME["theta"])
    return (x * c - y * s, x * s + y * c)


def _hull(points):
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def detect_theta(recs):
    """층판 꼭짓점의 최소 면적 외접 직사각형 각도 (|θ| ≤ 45°). 건물이 월드 축과 나란하면 0."""
    pts = [(v.co.x, v.co.y) for r in recs if r["kind"] == "slab" and r["floor"] for v in r["bm"].verts]
    if not pts:
        return 0.0
    hull = _hull(pts)
    best_a, best = 0.0, float("inf")
    for i in range(0, 9000):
        a = math.radians(i * 0.01)
        c, s = math.cos(a), math.sin(a)
        us = [x * c + y * s for x, y in hull]
        vs = [-x * s + y * c for x, y in hull]
        area = (max(us) - min(us)) * (max(vs) - min(vs))
        if area < best - 1e-9:
            best, best_a = area, a
    def area_at(a):
        c, s = math.cos(a), math.sin(a)
        us = [x * c + y * s for x, y in hull]
        vs = [-x * s + y * c for x, y in hull]
        return (max(us) - min(us)) * (max(vs) - min(vs))
    lo, hi = best_a - math.radians(0.012), best_a + math.radians(0.012)      # 0.01° 격자 오차를 정밀화 (치수가 mm 단위로 맞도록)
    for _ in range(60):
        m1, m2 = lo + (hi - lo) / 3, hi - (hi - lo) / 3
        if area_at(m1) < area_at(m2):
            hi = m2
        else:
            lo = m1
    best_a = (lo + hi) / 2
    if best_a > math.pi / 4:
        best_a -= math.pi / 2
    return round(best_a, 7)


def cut_segments(bm_src, z):
    bm = bm_src.copy()
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0.0, 0.0, z), plane_no=(0.0, 0.0, 1.0), dist=1e-7)
    segs = []
    for e in res["geom_cut"]:
        if isinstance(e, bmesh.types.BMEdge):
            a, b = e.verts
            ax, ay = rot(a.co.x, a.co.y)
            bx, by = rot(b.co.x, b.co.y)
            p = (round(ax, 5), round(ay, 5))
            q = (round(bx, 5), round(by, 5))
            if p != q:
                segs.append([p[0], p[1], q[0], q[1]])
    bm.free()
    return segs


def range_up(name):
    """에스컬레이터 이름 'A-VERT-ESCL_1F-2F_W_1F' → ('1F','2F'). 아니면 None."""
    m = re.match(r"^A-VERT-ESCL_([^-_]+)-([^_X]+)", name)
    return (m.group(1), m.group(2)) if m else None


def endpoints_xy(bm):
    """낮은 쪽/높은 쪽 끝의 평면 중심 — 화살표 방향(UP)을 모델에서 읽는다."""
    zs = [v.co.z for v in bm.verts]
    lo, hi = min(zs), max(zs)
    span = hi - lo
    if span < 1e-6:
        return None
    low = [v.co for v in bm.verts if v.co.z <= lo + 0.2 * span]
    high = [v.co for v in bm.verts if v.co.z >= hi - 0.2 * span]
    c = lambda pts: list(rot(sum(p.x for p in pts) / len(pts), sum(p.y for p in pts) / len(pts)))
    return {"low_xy": c(low), "high_xy": c(high), "z_low": lo, "z_high": hi}


def transform_meta(rec, bm):
    """문·창·가구: 변환 정보만. 폭/깊이는 PCA 주축 기준 바운딩 박스에서 구한다."""
    pts = [rot(v.co.x, v.co.y) for v in bm.verts]
    n = len(pts)
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - cx) ** 2 for p in pts)
    syy = sum((p[1] - cy) ** 2 for p in pts)
    sxy = sum((p[0] - cx) * (p[1] - cy) for p in pts)
    ang = 0.5 * math.atan2(2 * sxy, sxx - syy)
    ca, sa = math.cos(ang), math.sin(ang)
    u = [(p[0] - cx) * ca + (p[1] - cy) * sa for p in pts]
    v = [-(p[0] - cx) * sa + (p[1] - cy) * ca for p in pts]
    return {"category": rec["kind"], "name": rec["name"], "name_ko": rec["name_ko"],
            "center_xy": [round(cx, 4), round(cy, 4)], "rotation_rad": round(ang, 6),
            "width": round(max(u) - min(u), 4), "depth": round(max(v) - min(v), 4),
            "z_min": rec["zmin"], "z_max": rec["zmax"], "props": rec["props"],
            # 문 스윙 부채꼴·위생도기 윤곽: 객체 자신의 높이 중간에서 자른 선분 (메시 전체를 그리지 않고 평면 윤곽만)
            "segments": cut_segments(bm, (rec["zmin"] + rec["zmax"]) / 2)}


def simple_props(obj):
    out = {}
    for k in obj.keys():
        if not str(k).startswith("_") and isinstance(obj[k], (str, int, float, bool)):
            out[k] = obj[k]
    return out


def collect(deps):
    recs, bad = [], []
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        kind, name_ko, floor, src = classify(obj)
        if kind is None:
            bad.append(obj.name)
            continue
        bm = world_bmesh(obj, deps)
        if not bm.verts:
            bm.free()
            continue
        zs = [v.co.z for v in bm.verts]
        xs = [v.co.x for v in bm.verts]
        ys = [v.co.y for v in bm.verts]
        mats = [s.material.name for s in obj.material_slots if s.material]
        recs.append({"obj": obj, "bm": bm, "name": obj.name, "kind": kind, "name_ko": name_ko, "floor": floor,
                     "source": src, "material": mats[0] if mats else None, "props": simple_props(obj),
                     "zmin": min(zs), "zmax": max(zs), "bbox": [min(xs), min(ys), max(xs), max(ys)]})
    if bad:
        raise SystemExit("태그도 이름 규칙도 없는 객체가 있어 빌드를 거부한다 (%d개): %s" % (len(bad), ", ".join(sorted(bad)[:20])))
    return recs


def floors_from(recs):
    """층판(A-FLOR_s7_<층> 또는 kind=slab+floor 속성)의 윗면 z가 마감 바닥."""
    floors = {}
    for r in recs:
        if r["kind"] == "slab" and r["floor"]:
            floors[str(r["floor"])] = round(r["zmax"], 4)
    if not floors:
        slabs = [r for r in recs if r["kind"] == "slab"]
        if slabs:
            floors["1F"] = round(slabs[0]["zmax"], 4)
    return dict(sorted(floors.items(), key=lambda kv: kv[1]))


def building_bounds(recs, margin):
    """건물 바운딩 박스(층판들의 합) + 15 % 여백 → 정사각으로 맞춘다."""
    slabs = [r for r in recs if r["kind"] == "slab" and r["floor"]] or [r for r in recs if r["kind"] == "slab"]
    pts = [rot(v.co.x, v.co.y) for r in slabs for v in r["bm"].verts]       # 도면 좌표계에서의 바운딩 박스
    xmin = min(p[0] for p in pts); ymin = min(p[1] for p in pts)
    xmax = max(p[0] for p in pts); ymax = max(p[1] for p in pts)
    side = max(xmax - xmin, ymax - ymin) * (1 + 2 * margin)
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    theta = FRAME["theta"]
    return {"xmin": cx - side / 2, "ymin": cy - side / 2, "xmax": cx + side / 2, "ymax": cy + side / 2,
            "building": {"xmin": xmin, "ymin": ymin, "xmax": xmax, "ymax": ymax}, "margin": margin, "side": side,
            "frame": {"theta_rad": theta, "theta_deg": math.degrees(theta),
                      # 진북: 도면 위쪽에서 시계 방향으로 잰 각. 모델이 north_angle_deg를 갖고 있으면 그것을, 없으면 도면 회전각을 쓴다
                      "north_deg": bpy.context.scene.get("north_angle_deg", math.degrees(theta)),
                      "note": "도면좌표 = R(-theta) · 월드좌표. 월드 +Y가 진북. 진북 화살표는 도면에서 위쪽으로부터 시계 방향 theta_deg.",
                      "center_world": list(unrot(cx, cy))}}


def slice_floor(label, fz, cut, recs, floors):
    cut_z = fz + cut
    # 이 층에서 위층 바닥까지의 범위: 층판 투영은 이 층 것만
    elements, projection, zones, metas = [], [], [], []
    for r in recs:
        k = r["kind"]
        crosses = r["zmin"] - 1e-6 <= cut_z <= r["zmax"] + 1e-6
        if k in CUT_KINDS and crosses:
            seg = cut_segments(r["bm"], cut_z)
            if seg:
                item = {"name": r["name"], "kind": k, "name_ko": r["name_ko"], "material": r["material"], "source": r["source"],
                        "segments": seg}
                if k == "stair":
                    ep = endpoints_xy(r["bm"])
                    rg = range_up(r["name"])
                    if ep:
                        item["axis"] = ep
                    if rg:
                        item["escalator_range"] = list(rg)
                elements.append(item)
        elif k == "slab" and (str(r["floor"]) == label or (r["floor"] is None and abs(r["zmax"] - fz) < 0.05)):   # 층 속성이 없는 층판은 윗면 높이로 층을 정한다
            mid = (r["zmin"] + r["zmax"]) / 2
            projection.append({"name": r["name"], "kind": "slab", "name_ko": r["name_ko"], "segments": cut_segments(r["bm"], mid)})
        elif k in ZONE_KINDS and (crosses or (r["zmin"] <= cut_z + 1.0 and r["zmax"] >= fz - 1e-6)):
            # 방·영역 볼륨은 얇은 바닥 판일 수 있어 절단면을 가로지르지 않으면 객체 자신의 높이 중간에서 자른다
            seg = cut_segments(r["bm"], cut_z if crosses else (r["zmin"] + r["zmax"]) / 2)
            if seg:
                zones.append({"name": r["name"], "kind": k, "name_ko": r["name_ko"], "program_floor": r["floor"],
                              "segments": seg, "props": r["props"]})
        elif k in META_KINDS and r["zmin"] <= cut_z + 1.0 and r["zmax"] >= fz - 1e-6:
            metas.append(transform_meta(r, r["bm"]))
    return {"floor": label, "floor_z": fz, "cut_z": cut_z, "cut_height": cut, "elements": elements,
            "projection": projection, "zones": zones, "symbols": metas, "context": context_items(recs)}


def tree_components(bm):
    """합쳐진 수목 메시를 연결 요소로 나눠 (중심 x, y, 반경, 높이)를 구한다."""
    seen, out = set(), []
    for v0 in bm.verts:
        if v0 in seen:
            continue
        stack, comp = [v0], []
        seen.add(v0)
        while stack:
            a = stack.pop()
            comp.append(a)
            for e in a.link_edges:
                b = e.other_vert(a)
                if b not in seen:
                    seen.add(b)
                    stack.append(b)
        xs = [p.co.x for p in comp]; ys = [p.co.y for p in comp]; zs = [p.co.z for p in comp]
        x, y = rot((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
        out.append([round(x, 3), round(y, 3), round(max(max(xs) - min(xs), max(ys) - min(ys)) / 2, 3), round(max(zs) - min(zs), 2)])
    return out


def context_items(recs):
    """도면 표현(수목·외부공간·선큰 계단·출입구)에 쓰는 대지 맥락. 모델의 태그 객체에서 그대로 뽑는다."""
    ctx = {"trees": [], "spaces": [], "sunken_stair": [], "entrance": [], "site": [], "setback": [], "road": [], "sidewalk": [],
           "context_building": [], "road_marking": [], "subway_exit": []}
    for r in recs:
        k = r["kind"]
        if k == "tree":
            ctx["trees"] += tree_components(r["bm"])
        elif k in ctx and k != "trees":
            seg = cut_segments(r["bm"], (r["zmin"] + r["zmax"]) / 2)
            item = {"name": r["name"], "name_ko": r["name_ko"], "props": r["props"], "segments": seg}
            ctx["spaces" if k == "exterior_space" else k].append(item)
        elif k == "exterior_space":
            seg = cut_segments(r["bm"], (r["zmin"] + r["zmax"]) / 2)
            ctx["spaces"].append({"name": r["name"], "name_ko": r["name_ko"], "props": r["props"], "segments": seg})
    return ctx


# ── 정사영 렌더 ────────────────────────────────────────────────────────────────────────────────
# 단면 표현: 정사영 카메라의 근접 클립면을 절단 높이에 맞춘다. 클립면 아래만 렌더되므로 절단면은 메시 "안쪽(뒷면)"이 드러난 곳이다.
# 재질을 (앞면, 뒷면)으로 나눠 뒷면 = 절단면으로 칠한다. 면을 메우지 않으므로 구멍 있는 단면(유리 튜브 링)도 짝수-홀수 규칙으로 정확하다.
def _mat(name, front, back, front_emission):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    geom = nt.nodes.new("ShaderNodeNewGeometry")
    mix = nt.nodes.new("ShaderNodeMixShader")
    if front_emission:
        f = nt.nodes.new("ShaderNodeEmission")
        f.inputs["Color"].default_value = front
    else:
        f = nt.nodes.new("ShaderNodeBsdfDiffuse")
        f.inputs["Color"].default_value = front
        f.inputs["Roughness"].default_value = 1.0
    b = nt.nodes.new("ShaderNodeEmission")
    b.inputs["Color"].default_value = back
    nt.links.new(geom.outputs["Backfacing"], mix.inputs[0])
    nt.links.new(f.outputs[0], mix.inputs[1])
    nt.links.new(b.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    return m


NOT_BUILDING = ("site", "tree", "context_building", "zone", "room", "void", "setback", "road", "sidewalk", "exterior_space",
                "subway_exit", "sunken_stair", "entrance", "road_marking")


def orient_normals(recs):
    """뒷면 판정에 쓰려고 모든 건물 객체의 면을 일관된 바깥 방향으로 맞춘다.
    glb는 면마다 꼭짓점이 갈라져 있어 먼저 합친 뒤 법선을 재계산한다. 렌더용 임시 장면에서만 하며 모델 파일에는 저장하지 않는다."""
    for r in recs:
        if r["kind"] in NOT_BUILDING or r.get("fixed"):
            continue
        ob = r["obj"]
        if ob.data.users > 1:
            ob.data = ob.data.copy()
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-5)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.to_mesh(ob.data)
        bm.free()
        r["fixed"] = True


def _assign(recs, cut_z, mat_cut, mat_rest, only_cut=False):
    """절단면 위쪽 객체와 건물이 아닌 객체는 숨기고, 나머지에 절단/일반 재질을 입힌다.
    only_cut: 절단 요소만 남긴다. 이 모델은 층판이 기둥·코어 내부를 가로질러(합쳐져 있지 않다) 광선이 층판 앞면을 먼저 맞히므로,
    정렬 마스크에는 층판 등 절단되지 않는 객체를 넣지 않는다."""
    for r in recs:
        ob = r["obj"]
        if r["kind"] in NOT_BUILDING or r["zmin"] >= cut_z - 1e-6 or (only_cut and r["kind"] not in CUT_KINDS):
            ob.hide_render = True
            continue
        ob.hide_render = False
        if r["kind"] == "slab" and not r.get("lowered"):
            ob.location.z -= 0.01          # 기둥·코어 바닥면이 층판 윗면과 같은 높이라 광선이 층판 앞면을 먼저 맞힌다. 렌더용으로만 1 cm 내린다
            r["lowered"] = True
        ob.data.materials.clear()
        ob.data.materials.append(mat_cut if r["kind"] in CUT_KINDS else mat_rest)


def render_floor(label, cut_z, recs, bounds, out_ao, out_mask, size, samples, threads):
    scene = bpy.context.scene
    orient_normals(recs)
    paper = (1, 1, 1, 1)
    # 정렬 마스크: 절단면 = 검정, 그 밖은 흰색(발광). 앤티에일리어싱 없음
    mask_cut = _mat("mask_cut", paper, (0, 0, 0, 1), True)
    mask_rest = _mat("mask_rest", paper, paper, True)
    # 점토 + AO: 앞면은 확산 점토, 절단면(뒷면)은 밝은 단색으로 눌러 "속이 찬 단면"처럼 보이게
    clay_cut = _mat("clay_cut", (0.85, 0.85, 0.85, 1), (0.30, 0.30, 0.30, 1), False)
    clay_rest = _mat("clay_rest", (0.85, 0.85, 0.85, 1), (0.85, 0.85, 0.85, 1), False)

    cam_data = bpy.data.cameras.new("ortho")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = bounds["xmax"] - bounds["xmin"]
    height = 200.0
    cam_data.clip_start = height                                      # 클립면 = 절단면 (카메라 z = cut_z + height)
    cam_data.clip_end = height + 400.0
    cam = bpy.data.objects.new("ortho", cam_data)
    scene.collection.objects.link(cam)
    cx, cy = (bounds["xmin"] + bounds["xmax"]) / 2, (bounds["ymin"] + bounds["ymax"]) / 2
    wx, wy = unrot(cx, cy)                                            # 도면 좌표계 중심의 월드 위치
    cam.location = (wx, wy, cut_z + height)
    cam.rotation_euler = (0, 0, FRAME["theta"])                       # 아래를 본다. 이미지 위쪽 = 도면 +Y
    scene.camera = cam
    scene.render.resolution_x = scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.threads_mode = "FIXED"
    scene.render.threads = threads
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.world = scene.world or bpy.data.worlds.new("w")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (1, 1, 1, 1)
    bg.inputs["Strength"].default_value = 1.0

    _assign(recs, cut_z, mask_cut, mask_rest, only_cut=True)
    scene.cycles.samples = 1
    scene.cycles.use_denoising = False
    scene.cycles.filter_width = 0.01
    scene.render.filepath = out_mask
    bpy.ops.render.render(write_still=True)

    _assign(recs, cut_z, clay_cut, clay_rest)
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.filter_width = 1.5
    scene.render.filepath = out_ao
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam, do_unlink=True)


def main():
    a = parse_args()
    load_scene(a.input)
    deps = bpy.context.evaluated_depsgraph_get()
    out = os.path.join(os.path.abspath(a.out), "raw_slices")
    os.makedirs(out, exist_ok=True)
    recs = collect(deps)
    FRAME["theta"] = detect_theta(recs)
    if a.frame_ref:
        FRAME["theta"] = align_theta_to_reference(FRAME["theta"], a.frame_ref)
    print("FRAME theta_deg=%.3f" % math.degrees(FRAME["theta"]))
    floors = floors_from(recs)
    all_floors = dict(floors)                                          # floors.json에는 항상 전체 층을 쓴다 (--floors는 처리 대상만 거른다)
    if a.floors:
        want = [f.strip() for f in a.floors.split(",") if f.strip()]
        floors = {k: v for k, v in floors.items() if k in want}
    bounds = building_bounds(recs, a.margin)
    with open(os.path.join(out, "camera_bounds.json"), "w", encoding="utf-8") as fh:
        json.dump(bounds, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(out, "floors.json"), "w", encoding="utf-8") as fh:
        json.dump({"floors": all_floors, "cut_height": a.cut}, fh, ensure_ascii=False, indent=1)
    meta = {"north_angle_deg": bpy.context.scene.get("north_angle_deg")}
    for label, fz in floors.items():
        if a.phase in ("slice", "both"):
            data = slice_floor(label, fz, a.cut, recs, floors)
            data["meta"] = meta
            p = os.path.join(out, "floor_%s_slice.json" % label)
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False)
            print("SLICE", label, "cut_z=%.2f" % data["cut_z"], "elements=%d zones=%d symbols=%d" % (
                len(data["elements"]), len(data["zones"]), len(data["symbols"])), os.path.abspath(p))
        if a.phase in ("render", "both"):
            render_floor(label, fz + a.cut, recs, bounds, os.path.join(out, "floor_%s_ao.png" % label),
                         os.path.join(out, "floor_%s_cutmask.png" % label), a.size, a.samples, a.threads)
            print("RENDER", label, os.path.abspath(os.path.join(out, "floor_%s_ao.png" % label)))
    print("DONE_SLICER", out)


main()

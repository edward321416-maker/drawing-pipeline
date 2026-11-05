"""도면집 입면·단면 엔진 (순수 Python, shapely).

3D 모델(05_extract_model.py가 만든 model_world.npz)에서
  - 정투영 입면: 객체별 실루엣을 만들고, 가까운 객체부터 처리하며 이미 가려진 영역을 빼서 '보이는 윤곽선'만 남긴다(가림 처리).
  - 단면: 수직 절단면으로 삼각형을 잘라 절단 단면(포셰)을 만들고, 절단면 너머의 객체를 같은 방식으로 투영한다.
그림 코드에 숫자 좌표는 없다. 모든 좌표는 모델에서 나온다.

좌표틀: 도면좌표 = R(-theta)·월드좌표 (1층 마스터와 같은 틀, camera_bounds.json의 theta).
방위: 도면 위쪽(+y)에서 시계 방향 north_deg가 북쪽. 입면 d(방위 b)는 건물의 d쪽 면을 d쪽에서 본 그림이고 화면 오른쪽 = 방위 b−90°.
"""
import json
import math
import os

import numpy as np
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Polygon
from shapely.ops import unary_union

DRAWN_KINDS = {"column", "slab", "stair", "tube_wall", "shaft", "core_wall", "ramp", "facade", "roof"}
SKIP_KINDS = {"tree", "site", "context_building", "zone", "room", "void"}
KIND_RANK = {"slab": 0, "roof": 0, "core_wall": 1, "tube_wall": 1, "shaft": 2, "stair": 2, "ramp": 2, "column": 3, "facade": 3}


class Model:
    def __init__(self, cache_dir, camera_bounds):
        d = np.load(os.path.join(cache_dir, "model_world.npz"))
        self.V, self.F = d["V"], d["F"]
        meta = json.load(open(os.path.join(cache_dir, "model_objects.json"), encoding="utf-8"))
        self.floors = meta["floors"]
        self.objects = meta["objects"]
        fr = json.load(open(camera_bounds, encoding="utf-8"))
        self.theta = fr["frame"]["theta_rad"]
        self.north_deg = fr["frame"]["north_deg"]
        self.building = fr["building"]                                           # 도면틀에서의 건물 범위(xmin..ymax)
        c, s = math.cos(self.theta), math.sin(self.theta)
        x, y = self.V[:, 0], self.V[:, 1]
        self.P = np.column_stack([x * c + y * s, -x * s + y * c, self.V[:, 2]])      # 도면틀 좌표
        self.bld = [o for o in self.objects if o["kind"] in DRAWN_KINDS]

    def tris(self, o):
        f = self.F[o["f0"]:o["f0"] + o["nf"]]
        return self.P[f]                                                          # (n, 3, 3)


def bearing_vec(b_deg):
    b = math.radians(b_deg)
    return np.array([math.sin(b), math.cos(b)])


def _union(polys):
    polys = [p for p in polys if p is not None and not p.is_empty and p.area > 1e-9]
    return unary_union(polys) if polys else Polygon()


def _project_tris(T, right, depth_dir):
    """삼각형 (n,3,3) → 화면 삼각형 폴리곤 목록. 화면 x = P·right, 화면 y = z."""
    sx = T[:, :, 0] * right[0] + T[:, :, 1] * right[1]
    sy = T[:, :, 2]
    out = []
    for i in range(len(T)):
        pts = [(sx[i, 0], sy[i, 0]), (sx[i, 1], sy[i, 1]), (sx[i, 2], sy[i, 2])]
        a = (pts[1][0] - pts[0][0]) * (pts[2][1] - pts[0][1]) - (pts[1][1] - pts[0][1]) * (pts[2][0] - pts[0][0])
        if abs(a) < 1e-9:
            continue
        out.append(Polygon(pts))
    return out


def silhouette(T, right, depth_dir, grid=0.001):
    polys = _project_tris(T, right, depth_dir)
    u = _union(polys)
    if u.is_empty:
        return u
    u = u.buffer(grid, join_style=2).buffer(-grid, join_style=2)               # 삼각형 이음새의 가는 틈 제거(모서리를 둥글리지 않는 mitre)
    return u.simplify(0.002)


def visible_outlines(items, occluded=None):
    """items: [(obj, silhouette, depth_near)] 가까운(depth_near 큰) 것부터. 반환 [(obj, 보이는 면, 보이는 경계선)]."""
    occ = occluded if occluded is not None else Polygon()
    out = []
    for o, sil, dn in sorted(items, key=lambda t: -t[2]):
        if sil.is_empty:
            continue
        vis = sil.difference(occ) if not occ.is_empty else sil
        if vis.is_empty or vis.area < 1e-6:
            occ = occ.union(sil) if not occ.is_empty else sil
            continue
        edge = vis.boundary
        if not occ.is_empty:
            edge = edge.difference(occ.boundary.buffer(1e-5))                      # 가린 객체와 맞닿은 경계는 가린 객체의 윤곽선이 이미 있다
        out.append((o, vis, edge))
        occ = occ.union(sil) if not occ.is_empty else sil
    return out, occ


def elevation(model, bearing_deg, include=None):
    """건물의 방위 bearing_deg쪽 입면. 반환 dict(items=[(obj, vis, edge)], extent=(x0,y0,x1,y1), right=벡터, depth=벡터)."""
    d = bearing_vec(bearing_deg)                                                  # 보는 사람 쪽(건물 바깥)
    right = bearing_vec(bearing_deg - 90.0)
    items = []
    for o in model.bld:
        if include is not None and not include(o):
            continue
        T = model.tris(o)
        if len(T) == 0:
            continue
        sil = silhouette(T, right, d)
        depth_near = float((T[:, :, 0] * d[0] + T[:, :, 1] * d[1]).max())
        items.append((o, sil, depth_near))
    vis, occ = visible_outlines(items)
    ext = occ.bounds if not occ.is_empty else (0, 0, 1, 1)
    return {"items": vis, "extent": ext, "right": right, "depth": d, "bearing": bearing_deg, "silhouette": occ}


# ── 단면 ──────────────────────────────────────────────────────────────────────────────────────────
def _evenodd(faces):
    """polygonize 면들 → 짝수-홀수 규칙 영역(pipeline_common.polygons_from_segments와 같은 규칙). 중첩된 고리(튜브 벽)는 고리로, 구멍은 구멍으로."""
    if not faces:
        return Polygon()
    shells = [Polygon(f.exterior) for f in faces]
    inside = [f for f in faces if sum(1 for sh in shells if sh.contains(f.representative_point())) % 2 == 1]
    return unary_union(inside) if inside else Polygon()


def _clip_half(T, n, c):
    """삼각형들을 반공간 {p: n·p >= c}로 자른다(Sutherland–Hodgman). 반환: 삼각형 리스트(각 (3,3))."""
    out = []
    d = T @ n - c
    for i in range(len(T)):
        di = d[i]
        if (di >= -1e-9).all():
            out.append(T[i])
            continue
        if (di < -1e-9).all():
            continue
        poly = []
        for j in range(3):
            a, b = T[i][j], T[i][(j + 1) % 3]
            da, db = di[j], di[(j + 1) % 3]
            if da >= -1e-9:
                poly.append(a)
            if (da >= -1e-9) != (db >= -1e-9):
                t = da / (da - db)
                poly.append(a + t * (b - a))
        for k in range(1, len(poly) - 1):
            out.append(np.array([poly[0], poly[k], poly[k + 1]]))
    return np.array(out) if out else np.zeros((0, 3, 3))


def _cut_polygon(T, n, c, u, label=None):
    """평면 n·p = c로 삼각형 메시를 잘라 단면 폴리곤을 만든다. 평면 좌표: 가로 = u 방향, 세로 = z."""
    d = T @ n - c
    segs = []
    for i in range(len(T)):
        di = d[i]
        pos, neg = (di > 1e-9), (di < -1e-9)
        if not (pos.any() and neg.any()) and not (np.abs(di) <= 1e-9).any():
            continue
        pts = []
        for j in range(3):
            a, b = T[i][j], T[i][(j + 1) % 3]
            da, db = di[j], di[(j + 1) % 3]
            if abs(da) <= 1e-9:
                pts.append(a)
            if (da > 1e-9 and db < -1e-9) or (da < -1e-9 and db > 1e-9):
                pts.append(a + (da / (da - db)) * (b - a))
        if len(pts) >= 2:
            p, q = pts[0], pts[1]
            if np.linalg.norm(p - q) > 1e-7:
                segs.append(((p[0] * u[0] + p[1] * u[1], p[2]), (q[0] * u[0] + q[1] * u[1], q[2])))
    if not segs:
        return Polygon()
    from shapely.ops import polygonize
    snap = lambda v: (round(v[0], 4), round(v[1], 4))
    lines = unary_union([LineString([snap(a_), snap(b_)]) for a_, b_ in segs])
    polys = list(polygonize(lines))
    return _evenodd(polys)


def section(model, plane_axis, plane_value, look_sign, include=None):
    """도면틀에서 plane_axis('x' 또는 'y') = plane_value 인 수직 절단면. look_sign=+1이면 +축 방향을 바라본다.
    반환: items(투영, 절단면 너머), cuts([(obj, polygon)]), extent, right, look."""
    ax = 0 if plane_axis == "x" else 1
    look = np.zeros(2)
    look[ax] = look_sign
    right = np.array([look[1], -look[0]])                                        # 바라보는 방향의 오른쪽
    n = np.zeros(3)
    n[ax] = look_sign                                                           # 절단면 너머(바라보는 쪽) 반공간
    c = look_sign * plane_value
    cuts, items = [], []
    for o in model.bld:
        if include is not None and not include(o):
            continue
        T = model.tris(o)
        if len(T) == 0:
            continue
        pv = T[:, :, ax]
        if (pv * look_sign).max() < c - 1e-9:
            continue                                                            # 절단면 앞쪽(보는 사람 쪽)에만 있는 객체는 그리지 않는다
        crossing = ((pv.min(axis=1) < plane_value) & (pv.max(axis=1) > plane_value)).any()
        if crossing:
            poly = _cut_polygon(T, n, c, right)
            if not poly.is_empty and poly.area > 1e-6:
                cuts.append((o, poly))
        beyond = _clip_half(T, n, c)
        if len(beyond) == 0:
            continue
        sil = silhouette(beyond, right, look)
        dn = float((beyond[:, :, ax] * look_sign).min())                         # 절단면에 가까울수록 가깝다 → 깊이 = −(절단면에서의 거리)
        items.append((o, sil, -dn))
    cut_union = _union([p for _, p in cuts])
    vis, occ = visible_outlines(items, occluded=cut_union)
    ext_polys = [cut_union] + [v for _, v, _ in vis]
    ext = _union(ext_polys).bounds if any(not p.is_empty for p in ext_polys) else (0, 0, 1, 1)
    return {"items": vis, "cuts": cuts, "extent": ext, "right": right, "look": look, "plane": (plane_axis, plane_value, look_sign), "cut_union": cut_union}


# ── 평면 절단(상세용) ────────────────────────────────────────────────────────────────────────────
def plan_cut(model, z, kinds, window=None):
    """수평면 z에서 객체를 잘라 평면 단면 폴리곤을 만든다. window=(x0,y0,x1,y1)이면 그 안에 걸린 객체만. 반환 [(obj, polygon)]."""
    from shapely.ops import polygonize
    out = []
    for o in model.bld:
        if o["kind"] not in kinds or not (o["zmin"] - 1e-6 <= z <= o["zmax"] + 1e-6):
            continue
        T = model.tris(o)
        if len(T) == 0:
            continue
        if window is not None:
            xs, ys = T[:, :, 0], T[:, :, 1]
            if xs.max() < window[0] or xs.min() > window[2] or ys.max() < window[1] or ys.min() > window[3]:
                continue
        d = T[:, :, 2] - z
        segs = []
        for i in range(len(T)):
            di = d[i]
            if not ((di > 1e-9).any() and (di < -1e-9).any()):
                continue
            pts = []
            for j in range(3):
                a, b = T[i][j], T[i][(j + 1) % 3]
                da, db = di[j], di[(j + 1) % 3]
                if (da > 1e-9 and db < -1e-9) or (da < -1e-9 and db > 1e-9):
                    pts.append(a + (da / (da - db)) * (b - a))
            if len(pts) >= 2 and np.linalg.norm(pts[0] - pts[1]) > 1e-7:
                segs.append(LineString([(round(pts[0][0], 4), round(pts[0][1], 4)), (round(pts[1][0], 4), round(pts[1][1], 4))]))
        if not segs:
            continue
        acc = _evenodd(list(polygonize(unary_union(segs))))
        if not acc.is_empty and acc.area > 1e-6:
            out.append((o, acc))
    return out

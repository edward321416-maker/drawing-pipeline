# FILE: extract/slicer.py
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from shapely.geometry import LineString, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import polygonize, unary_union

from extract.schema import Model, ModelObject

_EPS = 1e-9


def _segments_at(verts: np.ndarray, tris: np.ndarray, z: float) -> list[LineString]:
    corners = verts[tris]                       # (m, 3, 3)
    dist = corners[:, :, 2] - z                 # 절단면까지의 부호 거리
    dist = np.where(np.abs(dist) < _EPS, _EPS, dist)  # 정점이 평면 위에 있으면 위쪽으로 취급
    segments = []
    for tri, d in zip(corners, dist):
        above = d > 0
        if above.all() or (~above).all():
            continue
        pts = []
        for a, b in ((0, 1), (1, 2), (2, 0)):
            if above[a] != above[b]:
                # 변의 두 끝점을 항상 같은 순서로 놓고 보간한다. 사각 옆면은 대각선을 공유하는 두 삼각형이 같은 변을 서로 반대
                # 방향으로 계산하는데, 그러면 부동소수 오차 때문에 6자리 반올림이 어긋나 윤곽이 닫히지 않는다(D-014 근본 원인)
                if tuple(tri[a]) > tuple(tri[b]):
                    a, b = b, a
                s = d[a] / (d[a] - d[b])
                p = tri[a] + s * (tri[b] - tri[a])
                pts.append((round(float(p[0]), 6), round(float(p[1]), 6)))
        if len(pts) == 2 and pts[0] != pts[1]:
            segments.append(LineString(pts))
    return segments


def section(obj: ModelObject, z: float) -> BaseGeometry:
    """메시를 수평면 z에서 자른 단면(내부 영역). 닫힌 메시의 짝수-홀수 규칙으로 구멍을 처리한다."""
    segments = _segments_at(obj.verts, obj.tris, z)
    if not segments:
        return Polygon()
    faces = list(polygonize(unary_union(segments)))
    if not faces:
        return Polygon()
    shells = [Polygon(f.exterior) for f in faces]
    inside = []
    for f in faces:
        p = f.representative_point()
        if sum(1 for s in shells if s.contains(p)) % 2 == 1:
            inside.append(f)
    return unary_union(inside) if inside else Polygon()


def filled_shell(geom: BaseGeometry) -> BaseGeometry:
    """링(튜브벽 등)의 내부 구멍을 메운 영역."""
    if geom.is_empty:
        return geom
    polys = [geom] if geom.geom_type == "Polygon" else [g for g in geom.geoms if g.geom_type == "Polygon"]
    return unary_union([Polygon(p.exterior) for p in polys])


@dataclass
class Sections:
    model: Model
    heights: tuple[float, ...]
    _at: dict
    _footprints: dict
    _objects: dict

    def at(self, h: float) -> dict:
        return self._at[h]

    def footprint(self, name: str) -> BaseGeometry:
        return self._footprints[name]

    def obj(self, name: str) -> ModelObject:
        return self._objects[name]

    def kind(self, name: str):
        return self._objects[name].kind


def slice_model(model: Model, heights) -> Sections:
    heights = tuple(heights)
    at = {h: {} for h in heights}
    footprints = {}
    objects = {}
    for o in model.objects:
        if len(o.verts) == 0:
            continue
        objects[o.name] = o
        footprints[o.name] = section(o, o.zmid)
        for h in heights:
            if o.zmin - _EPS <= h <= o.zmax + _EPS:
                g = section(o, h)
                if not g.is_empty:
                    at[h][o.name] = g
    return Sections(model, heights, at, footprints, objects)

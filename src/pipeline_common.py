"""파이프라인 공통: 슬라이스 읽기, 폐곡선 복원(shapely), 좌표↔픽셀 변환, 마스크 래스터화.

좌표계는 STEP 1이 정한 도면 좌표계(건물 축 정렬, 미터)이며 camera_bounds.json 하나에 고정된다.
SVG·DXF·AO 렌더·합성·테스트는 모두 여기의 변환을 쓴다. 변환을 따로 구현하지 않는다.
"""
from __future__ import annotations

import json
import os

from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import polygonize, unary_union

SNAP = 1e-4   # 끝점 스냅 허용오차 (m)


def load_json(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_bounds(raw_dir: str) -> dict:
    return load_json(os.path.join(raw_dir, "camera_bounds.json"))


def load_slice(raw_dir: str, floor: str) -> dict:
    return load_json(os.path.join(raw_dir, "floor_%s_slice.json" % floor))


def list_floors(raw_dir: str) -> list[str]:
    return list(load_json(os.path.join(raw_dir, "floors.json"))["floors"].keys())


def world_to_px(x: float, y: float, bounds: dict, size: int) -> tuple[float, float]:
    """도면 좌표 → 이미지 픽셀(u 오른쪽, v 아래쪽). CAD의 +Y(위)가 이미지에서는 v 감소(위)이다."""
    u = (x - bounds["xmin"]) / (bounds["xmax"] - bounds["xmin"]) * size
    v = (bounds["ymax"] - y) / (bounds["ymax"] - bounds["ymin"]) * size
    return u, v


def snap(v: float) -> float:
    return round(v / SNAP) * SNAP


def polygons_from_segments(segs) -> BaseGeometry:
    """절단 선분 → 닫힌 영역. 끝점을 스냅하고 polygonize한 뒤 짝수-홀수 규칙으로 구멍을 처리한다 (닫힌 메시 단면)."""
    lines = []
    for x1, y1, x2, y2 in segs:
        a, b = (snap(x1), snap(y1)), (snap(x2), snap(y2))
        if a != b:
            lines.append(LineString([a, b]))
    if not lines:
        return Polygon()
    faces = list(polygonize(unary_union(lines)))
    if not faces:
        return Polygon()
    shells = [Polygon(f.exterior) for f in faces]
    inside = [f for f in faces
              if sum(1 for s in shells if s.contains(f.representative_point())) % 2 == 1]
    return unary_union(inside) if inside else Polygon()


def iter_polygons(geom: BaseGeometry):
    if geom.is_empty:
        return
    if isinstance(geom, Polygon):
        yield geom
    elif isinstance(geom, MultiPolygon) or hasattr(geom, "geoms"):
        for g in geom.geoms:
            yield from iter_polygons(g)


def rasterize(geoms, bounds: dict, size: int):
    """도형(들)을 size×size 흑백 마스크(PIL 'L', 도형 안 = 0, 밖 = 255)로 그린다. 구멍은 흰색으로 되돌린다."""
    from PIL import Image, ImageDraw
    img = Image.new("L", (size, size), 255)
    dr = ImageDraw.Draw(img)
    for g in geoms:
        for p in iter_polygons(g):
            dr.polygon([world_to_px(x, y, bounds, size) for x, y in p.exterior.coords], fill=0)
            for hole in p.interiors:
                dr.polygon([world_to_px(x, y, bounds, size) for x, y in hole.coords], fill=255)
    return img


def cut_geometries(slice_data: dict) -> dict:
    """slice JSON의 절단 요소를 kind별 shapely 도형으로 복원한다. {kind: [(item, geom), ...]}"""
    out: dict = {}
    for it in slice_data["elements"]:
        g = polygons_from_segments(it["segments"])
        if not g.is_empty:
            out.setdefault(it["kind"], []).append((it, g))
    return out

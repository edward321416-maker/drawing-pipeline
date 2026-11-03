"""그늘 숲 마당(공원) 설계안: 산책로 + 잔디 마당 + 수목. 이 엔진이 만든 설계 제안이며 사용자 승인 대상이다.

입력: model\\m_site_source.json (숲 마당 폴리곤, 광장, 산책로 중심선, 중간발표 수목)
출력: model\\grove_design.json  (대지 좌표 u, v)
규칙(모두 매개변수): 산책로 폭 3 m, 잔디 마당은 숲 마당 안쪽 타원, 수목은 수관이 약간 겹치며(중심 거리 >= 반지름 합의 75 %)
산책로·잔디 마당을 피하고, 고정 시드로 항상 같은 결과를 낸다.
사용: python master\\design_grove.py
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

ENGINE = Path(__file__).resolve().parent.parent
SOURCE = ENGINE / "model" / "m_site_source.json"
OUT = ENGINE / "model" / "grove_design.json"

PATH_W_M = 3.0
LAWN_CENTER, LAWN_RADII, LAWN_ROT_DEG = (-37.0, 22.5), (8.5, 4.5), 14.0
TREE_R_RANGE = (1.8, 3.0)
TREE_COUNT = 34
EDGE_MARGIN_M = 1.8        # 수목 중심은 숲 마당 경계에서 이만큼 안쪽
LAWN_CLEAR_M = 0.3         # 수관 가장자리와 잔디 마당 사이 최소 간격
PATH_CLEAR_M = 1.0         # 수관 가장자리와 산책로 가장자리 사이 최소 간격
CANOPY_OVERLAP = 0.75      # 이웃 수목 중심 거리 >= (r1 + r2) * 0.75
SEED = 7
BUILDING_UV = Polygon([(-9, -18), (45, -18), (45, 36), (-9, 36)])   # 1층 바닥판(대지 좌표)


def _ring(r):
    return [[round(x, 3), round(y, 3)] for x, y in list(r.coords)[:-1]]


def _rings(geom):
    polys = [geom] if geom.geom_type == "Polygon" else [g for g in getattr(geom, "geoms", []) if g.geom_type == "Polygon"]
    return [{"shell": _ring(p.exterior), "holes": [_ring(h) for h in p.interiors if Polygon(h).area > 0.5]}
            for p in polys if p.area > 0.5]


def _poly(r):
    return Polygon(r["shell"], r.get("holes", [])) if isinstance(r, dict) else Polygon(r)


def design(src: dict) -> dict:
    grove = unary_union([_poly(r) for r in src["exterior_spaces"]["Grove"]["rings"]])
    plaza = unary_union([_poly(r) for r in src["exterior_spaces"]["Plaza"]["rings"]])
    path = LineString(src["grove_path_centerline"]).buffer(PATH_W_M / 2, cap_style=2).intersection(unary_union([grove, plaza]))
    path = path.difference(BUILDING_UV)
    lawn = affinity.rotate(
        affinity.scale(Point(*LAWN_CENTER).buffer(1.0, quad_segs=24), LAWN_RADII[0], LAWN_RADII[1]), LAWN_ROT_DEG,
        origin=LAWN_CENTER)
    lawn = lawn.intersection(grove.buffer(-3.0)).difference(path.buffer(1.0))

    rng = random.Random(SEED)
    inner = grove.buffer(-EDGE_MARGIN_M)
    x0, y0, x1, y1 = inner.bounds
    trees = []
    for _ in range(4000):
        if len(trees) >= TREE_COUNT:
            break
        r = round(rng.uniform(*TREE_R_RANGE), 2)
        p = Point(rng.uniform(x0, x1), rng.uniform(y0, y1))
        if not grove.buffer(-r).contains(p) or p.distance(lawn) < r + LAWN_CLEAR_M or p.distance(path) < r + PATH_CLEAR_M:
            continue
        if any(math.hypot(p.x - u, p.y - v) < (r + rr) * CANOPY_OVERLAP for u, v, rr in trees):
            continue
        trees.append((round(p.x, 3), round(p.y, 3), r))
    return {
        "note": "엔진이 만든 설계 제안(사용자 승인 대기). 규칙은 master\\design_grove.py 상단 상수.",
        "seed": SEED,
        "path": {"name_ko": "숲 마당 산책로", "rings": _rings(path)},
        "lawn": {"name_ko": "숲 마당 잔디 마당", "rings": _rings(lawn)},
        "trees": [list(t) for t in trees],
        "areas_m2": {"path": round(path.area, 1), "lawn": round(lawn.area, 1), "grove": round(grove.area, 1)},
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    d = design(json.loads(SOURCE.read_text(encoding="utf-8")))
    OUT.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"숲 마당 설계 고정: {OUT.resolve()}")
    print(f"수목 {len(d['trees'])}그루, 면적(㎡) {d['areas_m2']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

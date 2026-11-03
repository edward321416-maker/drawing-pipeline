# FILE: extract/schema.py
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

KINDS = frozenset({
    "column", "exterior_wall", "core_wall", "partition_wall", "tube_wall",
    "stair", "shaft", "fixture", "void", "zone", "slab",
    "room",  # 이름과 면적 라벨만 붙는 방(코어·화장실). 그리지 않고 구획존 검사(G4)에도 넣지 않는다
    "door",  # 문이 쓸고 지나가는 부채꼴(스윙 영역). 평면에서는 심볼이 문 호와 문짝으로 그린다
    "sanitary",  # 위생도기(양변기·소변기·세면대). 가구(fixture)의 기둥 이격 1.2 m 규칙은 적용하지 않고 겹침만 검사한다
    # 대지 맥락 (사용자 지시 2026-11-01: 1층 평면도는 주변 대지까지 보인다). 건물 도면(1:200)에서는 그리지 않고 대지 도면(1:400)에서만 그린다
    "site",              # 대지 경계 안쪽 영역
    "setback",           # 건축한계선 안쪽(건축 가능) 영역
    "road",              # 차도
    "sidewalk",          # 보도 (대지 바깥 부분만)
    "context_building",  # 이웃 건물 (실측 OSM)
    "exterior_space",    # 외부공간: 광장·숲 마당·선큰·소방차 구획 (props use)
    "tree",              # 수목 (원형 수관)
    "subway_exit",       # 지하철 출구 캐노피
    "road_marking",      # 중앙 차선(점선 조각)
    "sunken_stair",      # 선큰 광장으로 내려가는 계단(단 수, 방향 props)
    "entrance",          # 출입구·동선 화살표(보행·차량 진입)
})
CONTEXT_KINDS = frozenset({"site", "setback", "road", "sidewalk", "context_building", "exterior_space", "tree", "subway_exit",
                           "road_marking", "sunken_stair", "entrance"})
WALL_KINDS = frozenset({"exterior_wall", "core_wall", "partition_wall"})
REQUIRED_TAGS = ("kind", "name_ko")


@dataclass(frozen=True, eq=False)
class ModelObject:
    name: str
    props: dict
    verts: np.ndarray  # (n, 3) 월드 좌표, 미터
    tris: np.ndarray   # (m, 3) 정점 인덱스

    @property
    def kind(self):
        return self.props.get("kind")

    @property
    def name_ko(self):
        return self.props.get("name_ko")

    @property
    def zmin(self) -> float:
        return float(self.verts[:, 2].min())

    @property
    def zmax(self) -> float:
        return float(self.verts[:, 2].max())

    @property
    def zmid(self) -> float:
        return (self.zmin + self.zmax) / 2.0

    @property
    def center_xy(self) -> tuple[float, float]:
        lo = self.verts[:, :2].min(axis=0)
        hi = self.verts[:, :2].max(axis=0)
        return (round(float((lo[0] + hi[0]) / 2), 2), round(float((lo[1] + hi[1]) / 2), 2))


@dataclass
class Model:
    objects: list[ModelObject] = field(default_factory=list)
    meta: dict = field(default_factory=dict)  # 모델 전체 정보(예: 진북 각도 north_angle_deg)

    def by_kind(self, *kinds: str) -> list[ModelObject]:
        return [o for o in self.objects if o.kind in kinds]

    def get(self, name: str) -> ModelObject:
        for o in self.objects:
            if o.name == name:
                return o
        raise KeyError(name)

# FILE: render/style.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LineClass:
    name: str
    lw: float
    lw_min: float
    lw_max: float
    color: str
    linestyle: object


@dataclass(frozen=True)
class TextRole:
    name: str
    size: float
    size_min: float
    size_max: float
    weight: str
    color: str


# AGENTS.md §3.1 선 두께 위계 (유일한 출처)
LINE_CLASSES = {
    "cut_heavy": LineClass("cut_heavy", 1.7, 1.6, 1.8, "#000000", "-"),
    "cut_medium": LineClass("cut_medium", 1.1, 1.0, 1.2, "#222222", "-"),
    "projection_light": LineClass("projection_light", 0.55, 0.5, 0.6, "#444444", "-"),
    "detail": LineClass("detail", 0.38, 0.35, 0.4, "#aaaaaa", "--"),
    "grid": LineClass("grid", 0.4, 0.4, 0.4, "#dcdcdc", (0, (6, 3, 1, 3))),
    # 대지경계선: AGENTS.md §3.1 표에 없던 선종이라 대지 도면을 위해 더했다(사용자 검토 대상). 긴 1점 쇄선, 구획벽보다 가늘게
    "boundary": LineClass("boundary", 0.8, 0.7, 0.9, "#222222", (0, (10, 3, 2, 3))),
    # 대지 맥락(도로·이웃 건물·수목 등): 참고 도면처럼 건물보다 훨씬 옅고 가는 실선. 건물만 진하게 남아 위계가 선다
    "context": LineClass("context", 0.35, 0.3, 0.4, "#b4b4b4", "-"),
}

# AGENTS.md §3.1 텍스트 위계 (유일한 출처)
TEXT_ROLES = {
    "title": TextRole("title", 12.0, 11.0, 13.0, "bold", "#111111"),
    "room": TextRole("room", 8.0, 7.5, 8.5, "bold", "#222222"),
    "sub": TextRole("sub", 6.25, 6.0, 6.5, "normal", "#555555"),
    "micro": TextRole("micro", 5.25, 5.0, 5.5, "bold", "#333333"),
}

FONT_FAMILY = ["Malgun Gothic", "Arial", "DejaVu Sans"]

# kind -> (선종, 채움색). 채움이 None이면 윤곽선만 그린다.
KIND_STYLE = {
    "column": ("cut_heavy", "#000000"),
    "exterior_wall": ("cut_heavy", "#111111"),
    "core_wall": ("cut_heavy", "#1a1a1a"),
    "partition_wall": ("cut_medium", "#666666"),
    "tube_wall": ("cut_medium", None),
    "stair": ("projection_light", None),
    "shaft": ("projection_light", None),
    "fixture": ("projection_light", None),
    "sanitary": ("projection_light", None),   # 위생도기(양변기·소변기·세면대) — AGENTS.md §3.2 위생도기 외곽선 0.5
    "void": ("detail", None),
    "zone": ("detail", None),
    # 대지 맥락(대지 도면에서만 그린다). 채움은 무채색으로 절제한다
    "site": ("boundary", None),
    "setback": ("detail", None),
    "road": ("context", None),
    "sidewalk": ("context", None),
    "context_building": ("context", None),
    "exterior_space": ("context", None),
    "tree": ("context", None),
    "subway_exit": ("context", None),
    "road_marking": ("context", None),
    "sunken_stair": ("projection_light", None),   # 단 선과 하향 화살표는 렌더러가 props(treads, down)로 그린다
    "entrance": ("projection_light", "#666666"),
}
# 대지 도면(1:400): 참고 도면처럼 해치는 중심 열린 공간(광장) 한 곳에만 쓴다. 나머지는 흰 바탕 + 옅은 선. 값 = (패턴, 해치색, 투명도)
HATCH = {
    "use:plaza": ("..", "#8c8c8c", 0.75),
}
HATCH_LINEWIDTH = 0.25  # pt

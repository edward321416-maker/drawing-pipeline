from __future__ import annotations

from itertools import combinations

from shapely.ops import unary_union

from checks.base import Violation, dedupe
from extract.slicer import filled_shell

AREA_EPS = 1e-6
G6_KINDS = ("tube_wall", "void", "shaft", "core_wall", "partition_wall")
ENCLOSING = ("tube_wall", "core_wall", "partition_wall")  # 닫힌 벽은 안쪽 공간까지 점유 영역으로 본다
DOOR_OBSTACLES = ("core_wall", "partition_wall", "exterior_wall", "column", "shaft", "tube_wall", "void", "fixture", "stair",
                  "sanitary")


def _group_key(obj) -> str:
    """코어·화장실은 벽·칸막이·방을 한 덩어리로 묶는다(같은 코어의 벽끼리 모서리에서 겹치는 것은 위반이 아니다)."""
    core_id, wc_id = obj.props.get("core_id"), obj.props.get("wc_id")
    if obj.kind in ("core_wall", "partition_wall", "room") and core_id:
        return f"core:{core_id}"
    if obj.kind in ("partition_wall", "room") and wc_id:
        return f"wc:{wc_id}"
    return obj.name


def check_g6_overlaps(sections, params) -> list[Violation]:
    """튜브·보이드·샤프트·코어·화장실 같은 점유 영역끼리 겹치면 위반(어느 검사 높이에서든).

    코어·화장실은 문 개구 때문에 벽만으로는 닫히지 않으므로, 같은 묶음의 방(room) 바닥 영역을 함께 넣어 안쪽까지 점유로 본다."""
    out = []
    room_groups: dict[str, list] = {}
    for o in sections.model.by_kind("room"):
        key = _group_key(o)
        if key != o.name and len(o.verts):
            room_groups.setdefault(key, []).append(sections.footprint(o.name))
    for h in sections.heights:
        groups: dict[str, list] = {}
        for name, geom in sections.at(h).items():
            obj = sections.obj(name)
            if obj.kind in G6_KINDS:
                groups.setdefault(_group_key(obj), []).append((obj.kind, geom))
        for key, footprints in room_groups.items():
            if key in groups:
                groups[key] += [(groups[key][0][0], g) for g in footprints]
        shells = {}
        for key, items in groups.items():
            union = unary_union([g for _k, g in items])
            shells[key] = filled_shell(union) if items[0][0] in ENCLOSING else union
        for a, b in combinations(shells, 2):
            inter = shells[a].intersection(shells[b])
            if inter.area > AREA_EPS:
                c = inter.centroid
                out.append(Violation(
                    "G6", f"'{a}'와 '{b}' 점유 영역이 겹침 (높이 {h} m, {inter.area:.2f} ㎡)",
                    (round(c.x, 2), round(c.y, 2)), (a, b)))
    return dedupe(out)


def check_g3_model_doors(sections, params) -> list[Violation]:
    """모델의 문(kind=door) 스윙 영역이 벽·기둥·샤프트·튜브·계단·기물·다른 문과 겹치면 위반."""
    out = []
    for h in sections.heights:
        at = sections.at(h)
        doors = {n: g for n, g in at.items() if sections.kind(n) == "door"}
        for n_d, g_d in doors.items():
            for n_o, g_o in at.items():
                kind = sections.kind(n_o)
                if kind not in DOOR_OBSTACLES:
                    continue
                inter = g_d.intersection(filled_shell(g_o) if kind == "tube_wall" else g_o)
                if inter.area > AREA_EPS:
                    c = inter.centroid
                    out.append(Violation(
                        "G3", f"문 '{n_d}' 스윙이 {kind} '{n_o}'와 {inter.area:.2f} ㎡ 겹침 (높이 {h} m)",
                        (round(c.x, 2), round(c.y, 2)), (n_d, n_o)))
        for (a, ga), (b, gb) in combinations(doors.items(), 2):
            inter = ga.intersection(gb)
            if inter.area > AREA_EPS:
                c = inter.centroid
                out.append(Violation("G3", f"문 '{a}'와 '{b}' 스윙이 {inter.area:.2f} ㎡ 겹침 (높이 {h} m)",
                                     (round(c.x, 2), round(c.y, 2)), (a, b)))
    return dedupe(out)

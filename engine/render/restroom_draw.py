"""화장실 심볼을 pen으로 그린다(AGENTS.md §3.2 선 두께: 방 벽 구획벽, 큐비클 칸막이 0.6, 위생도기 외곽선 0.5)."""
from __future__ import annotations

from symbols.restroom import all_doors


def draw_restroom(pen, rr, only_details: bool = False) -> list:
    """그린 기하 중 라벨이 피해야 할 것(선 띠, 위생도기, 문 호 등)을 돌려준다.

    only_details=True이면 벽·칸막이·위생도기·기둥은 그리지 않는다. 상세 평면에서는 이것들이 모델의 객체로 이미 그려지므로,
    심볼은 세면대 볼, 회전 원, 문 호와 문짝만 더한다."""
    rid = rr.room_id
    obstacles = []

    if not only_details:
        pen.polygon(f"{rid}:wall", rr.walls, "cut_medium", "#666666", 3.0)
        if not rr.inner_walls.is_empty:
            pen.polygon(f"{rid}:inner", rr.inner_walls, "cut_medium", "#666666", 3.0)
        for i, g in enumerate(rr.thin):
            pen.polygon(f"{rid}:thin{i}", g, "projection_light", "#444444", 3.2)
            obstacles.append(g.buffer(0.04))
        for f in rr.fixtures:
            pen.polygon(f"{rid}:{f.name}", f.polygon, "projection_light", None, 2.6)
            obstacles.append(f.polygon.buffer(0.04))
    for i, g in enumerate(rr.details):
        pen.polygon(f"{rid}:bowl{i}", g, "projection_light", None, 2.6)
    if not only_details:
        for i, g in enumerate(rr.columns):  # 방 안(벽가)의 구조 기둥
            pen.polygon(f"{rid}:column{i}", g, "cut_heavy", "#000000", 5.0)
            obstacles.append(g.buffer(0.04))
    for u in rr.units:
        if u.turning is not None:
            pen.polygon(f"{rid}:{u.name}:turning", u.turning, "detail", None, 2.0)
            obstacles.append(u.turning)        # 휠체어 회전 원 안에는 글자를 두지 않는다
    for d in all_doors(rr):
        owner = f"{rid}:{d.name}"
        if d.kind == "swing":
            pen.line(f"{owner}:leaf", d.leaf, "cut_medium", 4.0)
            pen.line(f"{owner}:arc", d.arc, "projection_light", 4.0)
            obstacles += [d.leaf.buffer(0.05), d.arc.buffer(0.05)]
        else:
            pen.line(f"{owner}:leaf", d.leaf, "cut_medium", 4.0)
            pen.line(f"{owner}:travel", d.travel, "detail", 4.0)
            obstacles += [d.leaf.buffer(0.05), d.travel.buffer(0.05)]
    if not only_details:
        obstacles.append(rr.walls)
        if not rr.inner_walls.is_empty:
            obstacles.append(rr.inner_walls)
    return obstacles

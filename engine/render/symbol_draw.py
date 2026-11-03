"""코어 심볼의 상세선(계단 갈래·디딤판·절단선·문 호·오름 화살표)을 pen으로 그린다. 심볼 시트와 상세 평면이 같이 쓴다."""
from __future__ import annotations

from shapely.geometry import LineString


def draw_stair_details(pen, c) -> list:
    """벽·칸막이는 그리지 않는다(시트는 직접, 평면은 모델의 벽 객체로 그린다). 라벨이 피해야 할 기하 목록을 돌려준다."""
    cid = c.core_id
    obstacles = []

    def outline(owner, geom, klass, z):
        pen.polygon(owner, geom, klass, None, z)
        obstacles.append(geom.boundary.buffer(0.05))

    for f in c.flights:
        outline(f"{cid}:flight{f.index}", f.polygon, "projection_light", 2.0)
    for i, g in enumerate(c.landings):
        outline(f"{cid}:landing{i + 1}", g, "projection_light", 2.0)
    outline(f"{cid}:opening", c.opening, "detail", 2.0)
    for f in c.flights:
        for line, solid in f.tread_lines:
            pen.line(f"{cid}:tread{f.index}", line, "projection_light" if solid else "detail", 2.5)
            obstacles.append(line.buffer(0.05))
    if c.break_line is not None:
        pen.line(f"{cid}:break", c.break_line, "cut_medium", 4.0)
        obstacles.append(c.break_line.buffer(0.05))
    for d in c.doors:
        leaf = LineString([d.hinge, d.open_end])
        pen.line(f"{cid}:{d.name}:leaf", leaf, "cut_medium", 4.0)
        pen.line(f"{cid}:{d.name}:arc", d.arc, "projection_light", 4.0)
        obstacles += [leaf.buffer(0.05), d.arc.buffer(0.05)]
    pen.line(f"{cid}:arrow", c.arrow, "cut_medium", 5.0)
    pen.polygon(f"{cid}:arrow_head", c.arrow_head, "cut_heavy", "#000000", 5.0)
    obstacles += [c.arrow.buffer(0.05), c.arrow_head]
    return obstacles

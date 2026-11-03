"""튜브 심볼을 pen으로 그린다(AGENTS.md §3.1: 유리 벽·승강로 벽 cut_medium, 문·X선 projection_light, 나선 화살표 cut_medium/heavy)."""
from __future__ import annotations


def draw_tube(pen, t) -> None:
    """모든 owner는 '{튜브 id}:'로 시작한다(시트가 이 접두어로 라벨 장애물을 모은다)."""
    tid = t.tube_id
    pen.polygon(f"{tid}:ring", t.ring, "cut_medium", None, 3.0)
    if t.inner_ring is not None:
        pen.polygon(f"{tid}:inner_rim", t.inner_ring, "cut_medium", None, 3.0)
    if t.spiral is not None:
        pen.line(f"{tid}:spiral", t.spiral, "cut_medium", 5.0)
        pen.polygon(f"{tid}:spiral_head", t.arrow_head, "cut_heavy", "#000000", 5.0)
    for s in t.shafts:
        pen.polygon(f"{tid}:{s.name}:wall", s.walls, "cut_medium", None, 3.2)
        for i, d in enumerate(s.diagonals):
            pen.line(f"{tid}:{s.name}:x{i}", d, "projection_light", 3.2)
        pen.line(f"{tid}:{s.name}:door", s.door.leaf, "projection_light", 4.0)
    for d in t.doors:
        pen.line(f"{tid}:{d.name}", d.leaf, "projection_light", 4.0)
    for i, c in enumerate(t.columns):
        pen.polygon(f"{tid}:column{i}", c, "cut_heavy", "#000000", 5.0)

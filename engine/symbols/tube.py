"""튜브 심볼. AGENTS.md §3의 표준을 파라미터화한 것.

  - T1 나선 램프: 바깥 림과 안쪽 림의 2중 동심원, 두 림 사이가 램프 통로. 매끄러운 나선 회전 화살표 하나(방사형 해치 없음).
  - T3·T4 전망 승강기: 원형 유리 원통. 안에 독립 승강로 2개(정사각형 + X), 앞(남쪽, -y)에 승강 로비와 슬라이딩 출입구.
  - T2 빛 튜브·서측 캡슐: 유리 링 하나.
튜브는 월드(또는 시트) 좌표의 중심에 바로 만든다. 모든 치수는 TubeParams에서 오고 면적·깊이는 기하에서 계산한다.
주변 기둥은 월드 좌표 폴리곤으로 받아 검사(R3)가 실제 구조와 대조한다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.base import BaseGeometry

from symbols.stair_core import ARROW_HEAD_HALF_W_M, ARROW_HEAD_LEN_M

QUAD_SEGS = 32
SPIRAL_STEPS = 120


@dataclass
class TDoor:
    name: str
    kind: str                  # 'sliding'
    width: float
    leaf: LineString


@dataclass
class Shaft:
    name: str
    outer: Polygon             # 벽 바깥 정사각형
    clear: Polygon             # 승강로 안쪽 (순폭)
    walls: BaseGeometry        # 벽(문 개구 제외)
    diagonals: list            # X 표시 두 선
    door: TDoor                # 승강기 문 (승강 로비 쪽)


@dataclass
class Tube:
    tube_id: str
    kind: str                  # 'ramp' | 'light' | 'elevator' | 'capsule'
    label: str
    center: tuple
    outer: Polygon             # 유리 벽 바깥 윤곽
    inner: Polygon             # 유리 벽 안쪽 윤곽
    ring: BaseGeometry         # 유리 벽 (출입구 개구 제외)
    rims: list                 # [(이름, 바깥 윤곽, 안쪽 윤곽)] 림 두께 검사용
    void: Polygon              # 라벨을 둘 수 있는 가운데 빈 곳
    inner_ring: BaseGeometry | None = None   # T1 안쪽 림
    band: Polygon | None = None              # T1 램프 통로
    spiral: LineString | None = None
    arrow_head: Polygon | None = None
    shafts: list = field(default_factory=list)
    lobby: Polygon | None = None
    lobby_zones: list = field(default_factory=list)   # 승강로 문 앞 유효 영역
    doors: list = field(default_factory=list)         # 유리 원통 출입구
    entry_zone: Polygon | None = None                 # 출입구 바깥 유효 통로
    columns: list = field(default_factory=list)
    envelope: BaseGeometry | None = None              # 건물 외곽(외벽 안쪽)


def _disc(cx, cy, r) -> Polygon:
    return Point(cx, cy).buffer(r, quad_segs=QUAD_SEGS)


def _ring(cx, cy, r_out, t) -> Polygon:
    return _disc(cx, cy, r_out).difference(_disc(cx, cy, r_out - t))


def _spiral(cx, cy, r0, r1, start_deg, turn_deg):
    """아르키메데스 나선(반시계)과 끝의 화살촉."""
    pts = []
    for i in range(SPIRAL_STEPS + 1):
        s = i / SPIRAL_STEPS
        a = math.radians(start_deg + turn_deg * s)
        r = r0 + (r1 - r0) * s
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    line = LineString(pts)
    (x0, y0), (x1, y1) = pts[-2], pts[-1]
    d = math.hypot(x1 - x0, y1 - y0)
    ux, uy = (x1 - x0) / d, (y1 - y0) / d
    tip = (x1 + ux * ARROW_HEAD_LEN_M, y1 + uy * ARROW_HEAD_LEN_M)
    nx, ny = -uy, ux
    head = Polygon([tip, (x1 + nx * ARROW_HEAD_HALF_W_M, y1 + ny * ARROW_HEAD_HALF_W_M),
                    (x1 - nx * ARROW_HEAD_HALF_W_M, y1 - ny * ARROW_HEAD_HALF_W_M)])
    return line, head


def build_ramp(tube_id, label, center, radius, p, columns=(), envelope=None) -> Tube:
    cx, cy = center
    t = p.glass_t_m
    outer, inner = _disc(cx, cy, radius), _disc(cx, cy, radius - t)
    r_rim = radius - t - p.ramp_w_m                      # 안쪽 림의 바깥 반지름
    rim_out, rim_in = _disc(cx, cy, r_rim), _disc(cx, cy, r_rim - t)
    band = inner.difference(rim_out)
    spiral, head = _spiral(cx, cy, r_rim + p.spiral_margin_m, radius - t - p.spiral_margin_m,
                           p.spiral_start_deg, p.spiral_turn_deg)
    return Tube(tube_id, "ramp", label, (cx, cy), outer, inner, outer.difference(inner),
                [("바깥 림", outer, inner), ("안쪽 림", rim_out, rim_in)], rim_in,
                inner_ring=rim_out.difference(rim_in), band=band, spiral=spiral, arrow_head=head,
                columns=list(columns), envelope=envelope)


def build_light(tube_id, label, center, radius, p, columns=(), envelope=None) -> Tube:
    cx, cy = center
    outer, inner = _disc(cx, cy, radius), _disc(cx, cy, radius - p.glass_t_m)
    return Tube(tube_id, "light", label, (cx, cy), outer, inner, outer.difference(inner),
                [("유리 링", outer, inner)], inner, columns=list(columns), envelope=envelope)


def build_capsule(tube_id, label, outer_poly, p, columns=(), envelope=None) -> Tube:
    outer = outer_poly
    inner = outer.buffer(-p.glass_t_m)
    c = outer.centroid
    return Tube(tube_id, "capsule", label, (c.x, c.y), outer, inner, outer.difference(inner),
                [("유리 링", outer, inner)], inner, columns=list(columns), envelope=envelope)


def build_elevator(tube_id, label, center, radius, p, columns=(), envelope=None) -> Tube:
    """승강로 2개는 원통 뒤쪽(북쪽)에, 로비는 앞쪽(남쪽)에 둔다. 승강로의 바깥 두 모서리가 유리 벽 안쪽에서 shaft_to_glass_m 떨어지도록 y를 계산한다."""
    cx, cy = center
    t, s = p.glass_t_m, p.shaft_outer_m
    r_in = radius - t
    outer, inner = _disc(cx, cy, radius), _disc(cx, cy, r_in)
    half = p.shaft_gap_m / 2 + s
    reach = r_in - p.shaft_to_glass_m
    y_top = math.sqrt(reach ** 2 - half ** 2)
    y0 = y_top - s                                       # 승강로 앞면(문 쪽)의 y (중심 기준)

    shafts = []
    for i, (xa, xb) in enumerate(((-half, -p.shaft_gap_m / 2), (p.shaft_gap_m / 2, half))):
        o = box(cx + xa, cy + y0, cx + xb, cy + y0 + s)
        clear = o.buffer(-p.shaft_wall_t_m, join_style=2)
        mx = (xa + xb) / 2
        door_gap = box(cx + mx - p.car_door_w_m / 2, cy + y0 - 0.01, cx + mx + p.car_door_w_m / 2, cy + y0 + p.shaft_wall_t_m + 0.01)
        cx0, cy0, cx1, cy1 = clear.bounds
        diag = [LineString([(cx0, cy0), (cx1, cy1)]), LineString([(cx0, cy1), (cx1, cy0)])]
        yd = cy + y0 + p.shaft_wall_t_m / 2
        door = TDoor(f"승강기 문 {i + 1}", "sliding", p.car_door_w_m,
                     LineString([(cx + mx - p.car_door_w_m / 2, yd), (cx + mx + p.car_door_w_m / 2, yd)]))
        shafts.append(Shaft(f"승강로 {i + 1}", o, clear, o.difference(clear).difference(door_gap), diag, door))

    lobby = inner.intersection(box(cx - radius, cy - radius, cx + radius, cy + y0))
    zones = []
    for sh in shafts:
        x0, x1 = sh.door.leaf.bounds[0], sh.door.leaf.bounds[2]
        zones.append(box(x0, cy + y0 - p.lobby_min_depth_m, x1, cy + y0))

    gap = box(cx - p.entry_w_m / 2, cy - radius - 1.0, cx + p.entry_w_m / 2, cy - r_in + 0.5)
    ring = outer.difference(inner).difference(gap)
    ymid = cy - radius + t / 2
    entry = TDoor("출입구", "sliding", p.entry_w_m, LineString([(cx - p.entry_w_m / 2, ymid), (cx + p.entry_w_m / 2, ymid)]))
    zone = box(cx - p.entry_w_m / 2, cy - radius - p.entry_clear_m, cx + p.entry_w_m / 2, cy - radius)
    return Tube(tube_id, "elevator", label, (cx, cy), outer, inner, ring, [("유리 원통", outer, inner)],
                inner.difference(lobby), shafts=shafts, lobby=lobby, lobby_zones=zones, doors=[entry], entry_zone=zone,
                columns=list(columns), envelope=envelope)


def move_tube(tube: Tube, dx: float, dy: float) -> Tube:
    """튜브를 통째로 옮긴다(시트 배치용). 모든 기하를 같은 만큼 옮긴다."""
    def mv(g):
        return None if g is None else affinity.translate(g, dx, dy)

    def mvd(d):
        return TDoor(d.name, d.kind, d.width, mv(d.leaf))

    return Tube(
        tube.tube_id, tube.kind, tube.label, (tube.center[0] + dx, tube.center[1] + dy), mv(tube.outer), mv(tube.inner),
        mv(tube.ring), [(n, mv(a), mv(b)) for n, a, b in tube.rims], mv(tube.void), mv(tube.inner_ring), mv(tube.band),
        mv(tube.spiral), mv(tube.arrow_head),
        [Shaft(s.name, mv(s.outer), mv(s.clear), mv(s.walls), [mv(d) for d in s.diagonals], mvd(s.door)) for s in tube.shafts],
        mv(tube.lobby), [mv(z) for z in tube.lobby_zones], [mvd(d) for d in tube.doors], mv(tube.entry_zone),
        [mv(c) for c in tube.columns], mv(tube.envelope))

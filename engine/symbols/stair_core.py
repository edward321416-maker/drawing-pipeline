"""특별피난계단 코어 심볼 (4갈래 ㅁ자). 중간발표 s7.py·plans_s7.py의 코어 구성을 파라미터화한 것.

구성(로컬 좌표, 부속실이 남쪽 띠인 A·B 형태를 기준으로 만들고 C·D는 회전·거울로 배치한다):
  - 바깥 벽(0.25 m) + 남쪽 벽 가운데의 방화문 개구(홀 ↔ 부속실)
  - 부속실(깊이 1.6 m)과 칸막이(0.15 m), 칸막이의 방화문 개구(부속실 ↔ 계단실, 주 계단참 폭)
  - 계단실: 4갈래 유효폭 1.2 m 계단이 가운데 빈 곳을 돈다. 시작점은 부속실 쪽 모서리의 주 계단참
  - 문은 피난 방향으로 열린다: 홀 쪽 문은 홀로, 계단실 쪽 문은 부속실로
  - 평면 절단(1.5 m) 아래 디딤판은 실선, 위는 점선, 절단선은 Z자 45° 선
모든 길이는 파라미터(StairParams)에서 오고, 개수·위치·면적은 기하에서 계산한다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

EPS = 1e-9
ARROW_HEAD_LEN_M = 0.3
ARROW_HEAD_HALF_W_M = 0.13


@dataclass
class Door:
    name: str
    width: float
    hinge: tuple
    closed_end: tuple
    open_end: tuple
    swing: Polygon      # 문이 쓸고 지나가는 부채꼴(열림 90°)
    arc: LineString     # 문 끝이 그리는 호


@dataclass
class Flight:
    index: int
    polygon: Polygon
    start: tuple
    direction: tuple
    length: float
    treads: int
    tread_lines: list   # [(LineString, solid: bool)]


@dataclass
class StairCore:
    core_id: str
    bounds: tuple
    ves_side: str
    walls: BaseGeometry
    partition: BaseGeometry
    vestibule: Polygon
    well: Polygon
    opening: Polygon
    flights: list
    landings: list
    doors: list
    break_line: LineString | None
    break_flight: int | None
    break_dist: float | None
    arrow: LineString
    arrow_head: Polygon
    steps_provided: int
    steps_required: int


def _sector(hinge, radius, step_deg=5.0):
    """hinge를 중심으로 0°에서 -90°까지 도는 부채꼴 (닫힌 문은 +x 방향, 90° 열리면 -y 방향)."""
    n = int(round(90.0 / step_deg))
    pts = [(hinge[0] + radius * math.cos(math.radians(-90.0 * i / n)),
            hinge[1] + radius * math.sin(math.radians(-90.0 * i / n))) for i in range(n + 1)]
    return Polygon([hinge, *pts]), LineString(pts)


def build_stair_core(core_id: str, bounds, ves_side: str, p, hall_door_offset: float = 0.0) -> StairCore:
    """bounds = 코어 바깥 치수 (x0, y0, x1, y1). ves_side: 'S' 부속실이 남쪽 띠(A·B), 'W' 서쪽 띠(C), 'E' 동쪽 띠(D).

    hall_door_offset: 홀 쪽 문 중심을 벽 가운데에서 옮기는 거리(로컬 x 방향 m). 주변 시설을 비킬 때 쓴다."""
    if ves_side not in ("S", "W", "E"):
        raise ValueError(f"ves_side는 S·W·E 중 하나여야 한다: {ves_side!r}")
    x0, y0, x1, y1 = bounds
    width, depth = (x1 - x0, y1 - y0) if ves_side == "S" else (y1 - y0, x1 - x0)
    t, fw, vd, pt, dw = p.wall_t_m, p.flight_w_m, p.vestibule_depth_m, p.partition_t_m, p.door_w_m
    yp = t + vd                                        # 칸막이 중심선
    a0, b0, a1, b1 = t, yp + pt / 2, width - t, depth - t   # 계단실
    if (a1 - a0) < 2 * fw + 0.01 or (b1 - b0) < 2 * fw + 0.01:
        raise ValueError(f"코어 {core_id}: 계단실 {a1 - a0:.2f} × {b1 - b0:.2f} m에 유효폭 {fw} m 4갈래가 들어가지 않는다")

    # --- 로컬 좌표 기하 ---
    ox0, ox1 = width / 2 + hall_door_offset - dw / 2, width / 2 + hall_door_offset + dw / 2
    if ox0 < t + 0.05 or ox1 > width - t - 0.05:
        raise ValueError(f"코어 {core_id}: 홀 쪽 문 이동량 {hall_door_offset} m가 벽 모서리를 침범한다")
    walls = box(0, 0, width, depth).difference(box(t, t, width - t, depth - t)).difference(
        box(ox0, -0.01, ox1, t + 0.01))
    partition = box(t, yp - pt / 2, width - t, yp + pt / 2).difference(box(t - 0.01, yp - pt, t + dw, yp + pt))
    vestibule = box(t, t, width - t, yp - pt / 2)
    well = box(a0, b0, a1, b1)
    opening = box(a0 + fw, b0 + fw, a1 - fw, b1 - fw)
    landings = [box(a0, b0, a0 + fw, b0 + fw), box(a0, b1 - fw, a0 + fw, b1),
                box(a1 - fw, b1 - fw, a1, b1), box(a1 - fw, b0, a1, b0 + fw)]
    run_v, run_h = (b1 - b0) - 2 * fw, (a1 - a0) - 2 * fw
    specs = [  # 폴리곤, 시작점(오르는 쪽 아래 끝의 중심선), 오르는 방향, 길이
        (box(a0, b0 + fw, a0 + fw, b1 - fw), (a0 + fw / 2, b0 + fw), (0.0, 1.0), run_v),
        (box(a0 + fw, b1 - fw, a1 - fw, b1), (a0 + fw, b1 - fw / 2), (1.0, 0.0), run_h),
        (box(a1 - fw, b0 + fw, a1, b1 - fw), (a1 - fw / 2, b1 - fw), (0.0, -1.0), run_v),
        (box(a0 + fw, b0, a1 - fw, b0 + fw), (a1 - fw, b0 + fw / 2), (-1.0, 0.0), run_h),
    ]

    def across(d):
        return (-d[1], d[0])

    # 디딤판 수: 한 갈래에 들어가는 디딤판 수 = 길이 // 디딤판 + 1 (중간발표 stair_capacity와 같은 계산)
    treads = [int(length // p.tread_m + EPS) + 1 for *_rest, length in specs]
    steps_required = math.ceil(p.floor_height_m / p.riser_m - 1e-9)
    # 평면 절단(1.5 m)이 지나는 디딤판 번호: 윗면이 절단 높이를 처음 넘는 단
    k_cut = int(p.cut_height_m // p.riser_m + EPS) + 1
    remaining, break_flight, break_dist = k_cut - 1, None, None
    for i, n in enumerate(treads):
        if remaining < n:
            break_flight, break_dist = i, (remaining + 0.5) * p.tread_m
            break
        remaining -= n

    flights = []
    for i, ((poly, start, d, length), n) in enumerate(zip(specs, treads)):
        lines, nh, k = [], across(d), 1
        while k * p.tread_m < length - 0.01:
            dist = k * p.tread_m
            c = (start[0] + dist * d[0], start[1] + dist * d[1])
            line = LineString([(c[0] - fw / 2 * nh[0], c[1] - fw / 2 * nh[1]), (c[0] + fw / 2 * nh[0], c[1] + fw / 2 * nh[1])])
            solid = break_flight is None or i < break_flight or (i == break_flight and dist <= (k_cut - 1) * p.tread_m + EPS)
            lines.append((line, solid))
            k += 1
        flights.append(Flight(i + 1, poly, start, d, length, n, lines))

    break_line = None
    if break_flight is not None:
        f = flights[break_flight]
        nh = across(f.direction)

        def bp(a, c):
            return (f.start[0] + a * f.direction[0] + c * nh[0], f.start[1] + a * f.direction[1] + c * nh[1])

        break_line = LineString([bp(break_dist - 0.15, -fw / 2), bp(break_dist - 0.15, -0.15),
                                 bp(break_dist + 0.15, 0.15), bp(break_dist + 0.15, fw / 2)])

    # 오름 화살표: 주 계단참 중심에서 첫 갈래 중심선을 따라 절단선 앞까지
    f1 = flights[0]
    reach = break_dist if break_flight == 0 else f1.length
    land_c = (a0 + fw / 2, b0 + fw / 2)
    tip = (land_c[0], b0 + fw + max(0.5, min(reach, f1.length) - 0.4))
    base = (tip[0], tip[1] - ARROW_HEAD_LEN_M)
    arrow = LineString([land_c, base])
    head = Polygon([tip, (base[0] + ARROW_HEAD_HALF_W_M, base[1]), (base[0] - ARROW_HEAD_HALF_W_M, base[1])])

    # 문: 홀 쪽 문은 홀(바깥)로, 계단실 쪽 문은 부속실로 90° 열린다
    outer_hinge = (ox0, 0.0)
    sec_o, arc_o = _sector(outer_hinge, dw)
    inner_hinge = (t, yp)
    sec_i, arc_i = _sector(inner_hinge, dw)
    doors = [
        Door("홀문", dw, outer_hinge, (ox1, 0.0), (ox0, -dw), sec_o, arc_o),
        Door("계단실문", dw, inner_hinge, (t + dw, yp), (t, yp - dw), sec_i, arc_i),
    ]

    # --- 월드 좌표로 배치 ---
    def W(g):
        if ves_side == "S":
            return affinity.translate(g, x0, y0)
        g = affinity.translate(affinity.rotate(g, -90, origin=(0, 0)), x0, y1)
        if ves_side == "E":
            g = affinity.scale(g, xfact=-1, yfact=1, origin=((x0 + x1) / 2, 0))
        return g

    def Wp(pt_):
        g = W(Point(pt_))
        return (g.x, g.y)

    def Wv(origin, vec):
        a, b = Wp(origin), Wp((origin[0] + vec[0], origin[1] + vec[1]))
        return (b[0] - a[0], b[1] - a[1])

    w_flights = [
        Flight(f.index, W(f.polygon), Wp(f.start), Wv(f.start, f.direction), f.length, f.treads,
               [(W(line), solid) for line, solid in f.tread_lines])
        for f in flights
    ]
    w_doors = [Door(d.name, d.width, Wp(d.hinge), Wp(d.closed_end), Wp(d.open_end), W(d.swing), W(d.arc)) for d in doors]
    return StairCore(
        core_id=core_id, bounds=tuple(bounds), ves_side=ves_side,
        walls=W(walls), partition=W(partition), vestibule=W(vestibule), well=W(well), opening=W(opening),
        flights=w_flights, landings=[W(g) for g in landings], doors=w_doors,
        break_line=W(break_line) if break_line is not None else None,
        break_flight=break_flight, break_dist=break_dist,
        arrow=W(arrow), arrow_head=W(head),
        steps_provided=sum(treads), steps_required=steps_required,
    )


CORE_VES_SIDE = {"A": "S", "B": "S", "C": "W", "D": "E"}   # 부속실이 붙는 변 (중간발표 plans_s7.stair)
DOOR_HEIGHT_M = 2.1


def flight_blocks(core: StairCore, p) -> list:
    """3D에서 계단 갈래를 단순한 덩어리로 만들 때의 (갈래, 높이). 한 바퀴가 층고를 오르도록 갈래 끝까지의 누적 높이를 쓴다."""
    riser = p.floor_height_m / core.steps_required
    out, cum = [], 0
    for f in core.flights:
        cum += f.treads
        out.append((f, min(cum * riser, p.floor_height_m)))
    return out


def core_footprint(core: StairCore) -> Polygon:
    return box(*core.bounds)


def all_geometry(core: StairCore) -> BaseGeometry:
    parts = [core.walls, core.partition, core.vestibule, core.well, *[f.polygon for f in core.flights],
             *core.landings, *[d.swing for d in core.doors]]
    return unary_union(parts)

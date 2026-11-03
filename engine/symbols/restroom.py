"""화장실 심볼. AGENTS.md §3.2의 구성을 따른다: 출입문 앞 유효 통로, 전면 세면대 카운터, 중면 소변기(스크린 뒤), 후면 큐비클.

두 가지 구성:
  - 'unisex' (화장실 B, 4.5 x 5.3 m): 공용·장애인 겸용 1실. 일반 큐비클 1 + 장애인 큐비클 1 + 세면대 2.
  - 'split'  (화장실 C, 5.5 x 5.8 m): 남 / 여 / 장애인 세 방. 남(소변기 2, 큐비클 1, 세면대 2), 여(큐비클 2, 세면대 2), 장애인(양변기, 세면대, 회전 원 Ø1.5 m).
방의 외곽(벽 중심선) bounds에서 로컬 좌표(원점 = 남서 모서리)로 배치한 뒤 월드로 옮긴다. 방 안의 기둥은 위치를 피해 배치했고 검사(R2)가 확인한다.
치수는 모두 RestroomParams에서 온다.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

PROGRAM_BY_ROOM = {"B": "unisex", "C": "split"}


@dataclass
class RDoor:
    name: str
    kind: str                  # 'swing' | 'sliding'
    width: float
    hinge: tuple
    closed_end: tuple
    leaf: LineString           # 스윙: 90° 연 위치의 문짝, 슬라이딩: 닫힌 위치
    swing: Polygon | None      # 스윙 문이 쓸고 지나가는 부채꼴
    arc: LineString | None
    travel: LineString | None  # 슬라이딩 문짝이 열릴 때 지나가는 자리


@dataclass
class Fixture:
    name: str
    kind: str                  # 'wc' | 'urinal' | 'basin'
    polygon: Polygon


@dataclass
class Cubicle:
    name: str
    kind: str                  # 'general' | 'accessible'
    clear: Polygon             # 안쪽 유효 영역


@dataclass
class Unit:
    name: str
    label: str
    interior: Polygon
    door: RDoor
    clear_zone: Polygon        # 출입문 앞 유효 통로(문 폭 x 1.2 m)
    clear_depth: float
    corridor: Polygon | None   # 출입구에서 큐비클까지 이어지는 통로
    turning: Polygon | None    # 장애인 회전 원
    extra_doors: list = field(default_factory=list)   # 방 안쪽의 문(예: 장애인 큐비클 슬라이딩 문)


@dataclass
class Restroom:
    room_id: str
    bounds: tuple
    program: str
    walls: BaseGeometry
    inner_walls: BaseGeometry
    thin: list
    fixtures: list
    details: list              # 세면대 볼 같은 장식(검사 제외)
    cubicles: list
    units: list
    columns: list = field(default_factory=list)


def R(x0, y0, x1, y1) -> Polygon:
    return box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _bowl(x0, y0, x1, y1) -> Polygon:
    return R(x0 + 0.05, y0 + 0.05, x1 - 0.05, y1 - 0.05).buffer(0.05)   # 모서리가 둥근 양변기


def _swing_door(name, hinge, along, out, width) -> RDoor:
    """along: 벽을 따라 닫힌 끝으로 가는 단위벡터, out: 벽에 수직으로 열리는 쪽 단위벡터."""
    pts = []
    for i in range(19):
        t = (math.pi / 2) * i / 18
        c, s = math.cos(t), math.sin(t)
        pts.append((hinge[0] + width * (c * along[0] + s * out[0]), hinge[1] + width * (c * along[1] + s * out[1])))
    open_end = (hinge[0] + out[0] * width, hinge[1] + out[1] * width)
    closed_end = (hinge[0] + along[0] * width, hinge[1] + along[1] * width)
    return RDoor(name, "swing", width, hinge, closed_end, LineString([hinge, open_end]),
                 Polygon([hinge, *pts]), LineString(pts), None)


def _sliding_door(name, p0, p1, travel_dx, travel_dy) -> RDoor:
    width = math.dist(p0, p1)
    shift = (travel_dx, travel_dy)
    travel = LineString([(p0[0] + shift[0], p0[1] + shift[1]), (p1[0] + shift[0], p1[1] + shift[1])])
    return RDoor(name, "sliding", width, p0, p1, LineString([p0, p1]), None, None, travel)


def _unisex(W, D, p):
    tw, th = p.wall_t_m, p.thin_t_m
    h = tw / 2
    dw, ex0 = p.door_w_m, 0.5
    if W < 4.4 or D < 5.2:
        raise ValueError(f"공용·장애인 겸용 배치는 4.4 x 5.2 m 이상의 방이 필요하다: {W} x {D}")
    ring = R(-h, -h, W + h, D + h).difference(R(h, h, W - h, D - h))
    walls = ring.difference(R(ex0, -tw, ex0 + dw, tw))
    interior = R(h, h, W - h, D - h)
    door = _swing_door("공용문", (ex0, 0.0), (1, 0), (0, -1), dw)
    clear = R(ex0, h, ex0 + dw, h + p.entry_clear_m)

    fixtures, details, thin = [], [], []
    for j in range(2):  # 전면: 동쪽 벽의 세면대 카운터
        y = 0.3 + j * p.basin_w_m
        fixtures.append(Fixture(f"세면대 {j + 1}", "basin", R(W - h - p.basin_d_m, y, W - h, y + p.basin_w_m)))
        details.append(Point(W - h - p.basin_d_m / 2, y + p.basin_w_m / 2).buffer(0.17))

    gw, gd, bw, bd = p.cubicle_general_m[0], p.stall_depth_m, p.bowl_w_m, p.bowl_d_m
    g_clear = R(h, D - h - gd, h + gw, D - h)                       # 후면: 일반 큐비클
    thin += [R(h + gw, D - h - gd - th, h + gw + th, D - h), R(h, D - h - gd - th, h + gw, D - h - gd)]
    gcx = h + gw / 2
    fixtures.append(Fixture("양변기 1", "wc", _bowl(gcx - bw / 2, D - h - bd, gcx + bw / 2, D - h)))

    ax0, aw, ad = h + gw + th, p.cubicle_accessible_m[0], p.accessible_depth_m   # 후면: 장애인 큐비클
    a_clear = R(ax0, D - h - ad, ax0 + aw, D - h)
    sd = p.sliding_door_w_m
    sx0, sx1 = ax0 + (aw - sd) / 2, ax0 + (aw + sd) / 2
    fy = D - h - ad
    thin += [R(ax0 + aw, fy - th, ax0 + aw + th, D - h), R(ax0, fy - th, sx0, fy), R(sx1, fy - th, ax0 + aw, fy)]
    sliding = _sliding_door("장애인 큐비클문", (sx0, fy - th / 2), (sx1, fy - th / 2), sd, 0.0)
    acx = ax0 + aw / 2
    fixtures.append(Fixture("양변기 2(장애인)", "wc", _bowl(acx - bw / 2, D - h - bd, acx + bw / 2, D - h)))
    turning = Point(acx, fy + p.turning_circle_d_m / 2).buffer(p.turning_circle_d_m / 2, quad_segs=32)

    # 진입 통로: 출입구 앞에서 장애인 큐비클 문까지의 동선. 슬라이딩 문이 열리는 자리(sx1 ~ sx1+sd) 끝에서 0.3 m까지만 두고,
    # 그 동쪽(세면대 카운터 쪽 구석)은 동선이 이어지지 않는 자리라 통로로 보지 않는다.
    corridor = R(h, h + p.entry_clear_m, min(W - h - p.basin_d_m, sx1 + sd + 0.3), fy - th)
    unit = Unit("공용", "공용·장애인 겸용", interior, door, clear, p.entry_clear_m, corridor, turning, [sliding])
    return dict(walls=walls, inner=Polygon(), thin=thin, fixtures=fixtures, details=details,
                cubicles=[Cubicle("일반 큐비클", "general", g_clear), Cubicle("장애인 큐비클", "accessible", a_clear)],
                units=[unit])


def _split(W, D, p):
    tw, th = p.wall_t_m, p.thin_t_m
    h = tw / 2
    dw = p.door_w_m
    if W < 5.4 or D < 5.7:
        raise ValueError(f"남/여/장애인 분리 배치는 5.4 x 5.7 m 이상의 방이 필요하다: {W} x {D}")
    mid_y, vx = 2.65, 2.8
    ring = R(-h, -h, W + h, D + h).difference(R(h, h, W - h, D - h))
    walls = ring.difference(R(-tw, 0.725, tw, 0.725 + dw)).difference(R(0.9, D - tw, 0.9 + dw, D + tw)).difference(
        R(3.3, D - tw, 3.3 + p.sliding_door_w_m, D + tw))
    inner = unary_union([R(h, mid_y - h, W - h, mid_y + h), R(vx - h, mid_y + h, vx + h, D - h)])
    bw, bd, bwid, bdep = p.basin_w_m, p.basin_d_m, p.bowl_w_m, p.bowl_d_m
    gw, gd = p.cubicle_general_m[0], p.stall_depth_m

    # ---- 남 (남쪽 띠, 서쪽 벽에 문) ----
    men_in = R(h, h, W - h, mid_y - h)
    men_door = _swing_door("남자문", (0.0, 0.725), (0, 1), (-1, 0), dw)
    men_clear = R(h, 0.725, h + p.entry_clear_m, 0.725 + dw)
    fixtures, details, thin = [], [], []
    for j in range(2):  # 전면: 북쪽(칸막이) 벽 세면대
        x = 1.3 + j * bw
        fixtures.append(Fixture(f"남 세면대 {j + 1}", "basin", R(x, mid_y - h - bd, x + bw, mid_y - h)))
        details.append(Point(x + bw / 2, mid_y - h - bd / 2).buffer(0.17))
    for i in range(2):  # 중면: 남쪽 벽 소변기, 스크린 뒤
        x = 2.7 + i * p.urinal_pitch_m
        fixtures.append(Fixture(f"소변기 {i + 1}", "urinal",
                                R(x + 0.03, h + 0.03, x + p.urinal_w_m - 0.03, h + p.urinal_d_m - 0.03).buffer(0.03)))
    thin.append(R(2.55, h, 2.55 + th, 0.775))                                  # 스크린
    sx = W - h - gw                                                             # 후면: 동쪽 끝 큐비클
    m_clear = R(sx, h, sx + gw, h + gd)
    thin += [R(sx - th, h, sx, h + gd + th), R(sx, h + gd, sx + gw, h + gd + th)]
    fixtures.append(Fixture("남 양변기", "wc", _bowl(sx + 0.25, h, sx + 0.25 + bwid, h + bdep)))
    men_corr = R(1.3, 0.775, sx - th, 2.075)
    men = Unit("남", "남자 화장실", men_in, men_door, men_clear, p.entry_clear_m, men_corr, None)

    # ---- 여 (북서, 북쪽 벽에 문) ----
    wom_in = R(h, mid_y + h, vx - h, D - h)
    wom_door = _swing_door("여자문", (0.9, D), (1, 0), (0, 1), dw)
    wom_clear = R(0.9, D - h - p.entry_clear_m, 0.9 + dw, D - h)
    for j in range(2):  # 전면: 서쪽 벽 세면대
        y = 4.2 + j * bw
        fixtures.append(Fixture(f"여 세면대 {j + 1}", "basin", R(h, y, h + bd, y + bw)))
        details.append(Point(h + bd / 2, y + bw / 2).buffer(0.17))
    y0s, y1s = mid_y + h, mid_y + h + gd
    w_clears = []
    for k in range(2):  # 후면: 큐비클 2
        x0s = h + k * (gw + th)
        w_clears.append(Cubicle(f"여 큐비클 {k + 1}", "general", R(x0s, y0s, x0s + gw, y1s)))
        thin += [R(x0s + gw, y0s, x0s + gw + th, y1s + th), R(x0s, y1s, x0s + gw, y1s + th)]
        cx = x0s + gw / 2
        fixtures.append(Fixture(f"여 양변기 {k + 1}", "wc", _bowl(cx - bwid / 2, y0s, cx + bwid / 2, y0s + bdep)))
    wom_corr = R(h + bd, y1s + th, vx - h, D - h)
    wom = Unit("여", "여자 화장실", wom_in, wom_door, wom_clear, p.entry_clear_m, wom_corr, None)

    # ---- 장애인 (북동, 북쪽 벽에 슬라이딩 문) ----
    acc_in = R(vx + h, mid_y + h, W - h, D - h)
    sd = p.sliding_door_w_m
    acc_door = _sliding_door("장애인문", (3.3, D), (3.3 + sd, D), sd, 0.0)
    acc_door.travel = LineString([(3.3 + sd, D - h - 0.05), (3.3 + 2 * sd, D - h - 0.05)])
    acc_clear = R(3.3, D - h - p.entry_clear_m, 3.3 + sd, D - h)
    fixtures.append(Fixture("장애인 양변기", "wc", _bowl(3.3, mid_y + h, 3.3 + bwid, mid_y + h + bdep)))
    fixtures.append(Fixture("장애인 세면대", "basin", R(vx + h, 3.6, vx + h + bd, 3.6 + bw)))
    details.append(Point(vx + h + bd / 2, 3.6 + bw / 2).buffer(0.17))
    turning = Point(4.15, 4.2).buffer(p.turning_circle_d_m / 2, quad_segs=32)
    acc = Unit("장애인", "장애인 화장실", acc_in, acc_door, acc_clear, p.entry_clear_m, None, turning)

    cubicles = [Cubicle("남 큐비클", "general", m_clear), *w_clears, Cubicle("장애인 화장실", "accessible", acc_in)]
    return dict(walls=walls, inner=inner, thin=thin, fixtures=fixtures, details=details, cubicles=cubicles,
                units=[men, wom, acc])


def _move_door(d: RDoor, dx, dy) -> RDoor:
    def pt(q):
        return (q[0] + dx, q[1] + dy)

    def mv(g):
        return None if g is None else affinity.translate(g, dx, dy)

    return RDoor(d.name, d.kind, d.width, pt(d.hinge), pt(d.closed_end), mv(d.leaf), mv(d.swing), mv(d.arc), mv(d.travel))


def build_restroom(room_id: str, bounds, program: str, p, columns=()) -> Restroom:
    """bounds = 방의 외곽(벽 중심선) (x0, y0, x1, y1). columns = 월드 좌표의 기둥 폴리곤."""
    x0, y0, x1, y1 = bounds
    W, D = x1 - x0, y1 - y0
    data = {"unisex": _unisex, "split": _split}[program](W, D, p)

    def T(g):
        return affinity.translate(g, x0, y0)

    units = []
    for u in data["units"]:
        units.append(Unit(
            u.name, u.label, T(u.interior), _move_door(u.door, x0, y0), T(u.clear_zone), u.clear_depth,
            T(u.corridor) if u.corridor is not None else None, T(u.turning) if u.turning is not None else None,
            [_move_door(d, x0, y0) for d in u.extra_doors]))
    return Restroom(
        room_id=room_id, bounds=tuple(bounds), program=program,
        walls=T(data["walls"]), inner_walls=T(data["inner"]) if not data["inner"].is_empty else data["inner"],
        thin=[T(g) for g in data["thin"]],
        fixtures=[Fixture(f.name, f.kind, T(f.polygon)) for f in data["fixtures"]],
        details=[T(g) for g in data["details"]],
        cubicles=[Cubicle(c.name, c.kind, T(c.clear)) for c in data["cubicles"]],
        units=units, columns=list(columns),
    )


def all_doors(rr: Restroom) -> list:
    out = []
    for u in rr.units:
        out.append(u.door)
        out += u.extra_doors
    return out

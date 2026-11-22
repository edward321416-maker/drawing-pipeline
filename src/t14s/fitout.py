"""Tenant-unit fit-out (PROPOSED_DESIGN furniture). Works in a door-aligned local frame so layouts are axis-aligned.

Local frame: origin at the door centre, +y points into the room, +x along the wall. Items are returned as
[(geometry, 'body'|'line'|'foliage')] in world coordinates, like upper_layouts.layout().
"""
from __future__ import annotations

import math

import shapely
from shapely import affinity
from shapely.geometry import LineString, Point, box
from shapely.ops import substring, unary_union
from shapely.geometry.polygon import orient

COL_CLEAR = 1.2        # params.yaml clearance.furniture_to_column_m


def polys(g):
    if g is None or g.is_empty:
        return []
    return [p for p in getattr(g, "geoms", [g]) if p.geom_type == "Polygon" and not p.is_empty]


class Frame:
    def __init__(self, c, inward):
        self.c = c
        vx, vy = inward
        n = math.hypot(vx, vy) or 1.0
        vx, vy = vx / n, vy / n
        tx, ty = vy, -vx                                    # t = rot(-90) of inward -> rot90(t) == inward
        self.theta = math.degrees(math.atan2(ty, tx))

    def to_local(self, g):
        return affinity.rotate(affinity.translate(g, -self.c[0], -self.c[1]), -self.theta, origin=(0, 0))

    def to_world(self, g):
        return affinity.translate(affinity.rotate(g, self.theta, origin=(0, 0)), self.c[0], self.c[1])


def rect(cx, cy, w, h):
    return box(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def wall_strips(usable, rng, depth=0.45, seg=(1.8, 4.2), gap=(0.8, 1.3)):
    """Shelving / banquette strips just inside the walls of `usable` (works on any polygon)."""
    out = []
    for poly in polys(usable):
        poly = orient(poly, 1.0)
        ring = LineString(poly.exterior.coords)
        t = rng.uniform(0.4, 1.2)
        while t < ring.length - 1.2:
            L = min(rng.uniform(*seg), ring.length - t)
            part = substring(ring, t, t + L)
            if part.length >= 1.2 and part.length - Point(part.coords[0]).distance(Point(part.coords[-1])) < 0.05:
                strip = shapely.offset_curve(part, depth / 2).buffer(depth / 2, cap_style=2)
                if poly.contains(strip):
                    out.append((strip, part))
            t += L + rng.uniform(*gap)
    return out


def grid_fill(inner, w, h, px, py, make):
    """Place `make(cx, cy)` -> [(geom, kind)] on a grid inside `inner` if its first body fits."""
    out = []
    if inner.is_empty:
        return out
    x0, y0, x1, y1 = inner.bounds
    j = 0
    y = y0 + h / 2 + 0.05
    while y < y1 - h / 2:
        x = x0 + w / 2 + 0.05 + (px / 2 if j % 2 else 0.0) * 0.0
        while x < x1 - w / 2:
            items = make(x, y)
            if items and inner.contains(items[0][0]):
                out += items
            x += px
        y += py
        j += 1
    return out


def fit(room, program, use, door, columns, reserved, rng):
    """room: world polygon of the unit; door: dict(center, inward(v), swing); columns/reserved: world geometries."""
    fr = Frame(door["center"], door["inward"])
    L = fr.to_local
    swing = L(door["swing"]).buffer(0.25) if door.get("swing") is not None and not door["swing"].is_empty else None
    blocks = [L(columns).buffer(0.0)] if columns is not None and not columns.is_empty else []
    if reserved is not None and not reserved.is_empty:
        blocks.append(L(reserved))
    block = unary_union(blocks) if blocks else None
    usable = L(room).buffer(-0.22, join_style=2)
    if swing is not None:
        usable = usable.difference(swing).difference(rect(0, 1.0, door["width"] + 1.0, 2.0))
    if block is not None:
        usable = usable.difference(block)
    col_l = L(columns) if columns is not None and not columns.is_empty else None
    items = []
    if program == "retail":
        items = _retail(usable, col_l, rng)
    elif program == "fnb":
        items = _fnb(usable, col_l, rng)
    elif program == "culture":
        items = _culture(usable, col_l, use, rng)
    return [(fr.to_world(g), k) for g, k in items]


def _near_col(g, col_l, d):
    return col_l is not None and not col_l.is_empty and g.distance(col_l) < d


def _retail(usable, col_l, rng):
    items = []
    for strip, part in wall_strips(usable.difference(col_l.buffer(0.35)) if col_l is not None else usable, rng):
        items.append((strip, "body"))
        items.append((substring(part, 0.1, part.length - 0.1), "line"))
    inner = usable.buffer(-(0.45 + 1.2), join_style=2)
    if inner.is_empty:
        return items
    items += grid_fill(inner, 1.6, 0.8, 3.2, 2.6,
                       lambda x, y: [] if _near_col(rect(x, y, 1.6, 0.8), col_l, COL_CLEAR) else
                       [(rect(x, y, 1.6, 0.8), "body"), (LineString([(x - 0.65, y), (x + 0.65, y)]), "line")])
    for g in polys(usable):                                   # cash counter: first free spot near the door side
        c = rect(1.9, 1.1, 1.5, 0.55)
        if g.contains(c) and not _near_col(c, col_l, 0.6):
            items.append((c, "body"))
            break
    return items


def _fnb(usable, col_l, rng):
    items = []
    for strip, part in wall_strips(usable.difference(col_l.buffer(0.35)) if col_l is not None else usable, rng,
                                   depth=0.55, seg=(2.4, 4.8), gap=(1.0, 1.6)):
        items.append((strip, "body"))                         # banquette / service counter
    inner = usable.buffer(-(0.55 + 0.6), join_style=2)
    if inner.is_empty:
        return items

    def table(x, y):
        t = rect(x, y, 0.9, 0.9)
        if _near_col(t, col_l, COL_CLEAR):
            return []
        out = [(t, "body")]
        for dx, dy in ((-0.7, 0), (0.7, 0), (0, -0.7), (0, 0.7)):
            out.append((rect(x + dx, y + dy, 0.42, 0.42), "body"))
        return out
    return items + grid_fill(inner, 1.8, 1.8, 2.5, 2.5, table)


def _culture(usable, col_l, use, rng):
    items = []
    inner = usable.buffer(-0.9, join_style=2)
    if inner.is_empty:
        return items
    x0, y0, x1, y1 = inner.bounds
    cx = (x0 + x1) / 2
    if use == "다목적 홀":
        stage = rect(cx, y1 - 1.3, min(7.0, (x1 - x0) * 0.6), 2.4)
        if inner.contains(stage):
            items += [(stage, "body"), (LineString([(stage.bounds[0] + 0.2, stage.bounds[1] + 0.2), (stage.bounds[2] - 0.2, stage.bounds[1] + 0.2)]), "line")]
        y = y0 + 1.6
        while y < y1 - 4.2:
            for a, b in ((x0 + 0.6, cx - 0.7), (cx + 0.7, x1 - 0.6)):
                row = box(a, y, b, y + 0.5)
                if inner.contains(row) and not _near_col(row, col_l, 0.5):
                    items.append((row, "body"))
            y += 0.95
    elif use == "전시 갤러리":
        y = y0 + 1.8
        k = 0
        while y < y1 - 1.5:
            x = x0 + 1.2 + (2.2 if k % 2 else 0.0)
            while x < x1 - 3.0:
                p = box(x, y, x + 3.0, y + 0.12)
                if inner.contains(p) and not _near_col(p, col_l, 0.8):
                    items.append((p, "body"))
                    pl = rect(x + 1.5, y + 1.2, 0.9, 0.9)
                    if inner.contains(pl) and not _near_col(pl, col_l, 0.8):
                        items.append((pl, "body"))
                x += 6.0
            y += 3.2
            k += 1
    elif use in ("스튜디오", "체험 공방", "미디어랩"):
        def bench(x, y):
            t = rect(x, y, 2.4, 0.9)
            if _near_col(t, col_l, COL_CLEAR):
                return []
            out = [(t, "body")]
            for i in range(3):
                out.append((rect(x - 0.8 + 0.8 * i, y - 0.72, 0.4, 0.4), "body"))
                out.append((rect(x - 0.8 + 0.8 * i, y + 0.72, 0.4, 0.4), "body"))
            return out
        items += grid_fill(inner, 2.4, 2.0, 3.4, 3.0, bench)
    else:                                                     # 라운지
        for strip, _ in wall_strips(usable, rng, depth=0.85, seg=(2.0, 2.6), gap=(1.5, 2.5)):
            items.append((strip, "body"))
        items += grid_fill(inner.buffer(-1.2, join_style=2), 1.2, 1.2, 3.4, 3.4,
                           lambda x, y: [] if _near_col(Point(x, y).buffer(0.6), col_l, COL_CLEAR) else
                           [(Point(x, y).buffer(0.55, quad_segs=8), "body")])
    return items

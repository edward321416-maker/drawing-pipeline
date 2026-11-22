"""Floor layout generator (PROPOSED_DESIGN) on top of verified geometry.

Method (all shapely booleans on the verified slab; no hand-typed coordinates):
  free   = slab - cores - restroom blocks          (openings/tubes are already holes of the slab)
  units  = free ∩ perimeter strips cut on the column grid, minus door aprons, morphologically cleaned
  hall   = free - units (split by program zone)
  walls  = unit boundaries not on the slab edge / openings / cores, 150 mm, cut by door openings
  doors  = one per unit on its longest hall-facing edge, away from columns
  routes = shortest paths hall-wise between core doors, tube entries, restrooms and escalator voids (MST)
"""
from __future__ import annotations

import heapq
import math
import random

import numpy as np
import shapely
from shapely import affinity
from shapely.geometry import LineString, MultiLineString, Point, Polygon, box
from shapely.ops import linemerge, nearest_points, polylabel, unary_union

from . import annotate as AN
from . import fitout as FO
from . import source as SRC
from . import structure as ST
from . import symbols as SY
from .model import MODEL_VERIFIED, PROPOSED, SYMBOL_REUSE, Drawing, text_extent_m

import upper_layouts as UL
from symbols.stair_core import CORE_VES_SIDE

PROG = {"판매": "retail", "F&B": "fnb", "문화·엔터": "culture", "garden": "garden", "서비스": "service"}
PROG_KO = {"retail": "판매", "fnb": "식음(F&B)", "culture": "문화·엔터", "garden": "정원", "service": "서비스",
           "restroom": "화장실", "core": "코어"}
UL_NAME = {"retail": "판매", "fnb": "F&B", "culture": "문화·엔터", "garden": "garden", "service": "서비스"}
HALL_NAME = {"retail": "판매 홀", "fnb": "식음 홀", "culture": "문화 로비·포이어", "garden": "정원 마당", "service": "서비스 홀"}
UNIT_NAME = {"retail": "판매 점포", "fnb": "식음 점포"}
CULTURE_USES = ["다목적 홀", "전시 갤러리", "스튜디오", "체험 공방", "라운지", "미디어랩"]
TINT = {"retail": "#f9f9f9", "fnb": "#f1f1f1", "culture": "#e9e9e9", "garden": "#f4f4f4", "service": "#efefef"}
TUBE_KO = {"T1": "T1 나선 램프", "T2": "T2 빛 튜브", "T3": "T3 전망 승강기", "T4": "T4 전망 승강기",
           "capW": "서측 캡슐", "capE": "동측 캡슐", "EV1": "비상용 승강기 EV1", "EV2": "비상용 승강기 EV2",
           "M1": "설비 샤프트 M1", "M2": "설비 샤프트 M2", "FR": "화물 승강기 FR", "PL": "광장 승강기 PL"}
MIN_UNIT_W, MIN_UNIT_AREA = 3.6, 30.0
APRON_DIR = {"S": (0.0, -1.0), "W": (-1.0, 0.0), "E": (1.0, 0.0)}


def polys(g, min_area=0.0):
    if g is None or g.is_empty:
        return []
    return [p for p in getattr(g, "geoms", [g]) if p.geom_type == "Polygon" and p.area > min_area]


def lines(g):
    if g is None or g.is_empty:
        return []
    out = []
    for p in getattr(g, "geoms", [g]):
        if p.geom_type == "LineString":
            out.append(p)
        elif p.geom_type in ("MultiLineString", "GeometryCollection"):
            out += lines(p)
    return out


def oriented_rect(c, n, w, depth):
    t = (-n[1], n[0])
    a = (c[0] - t[0] * w / 2, c[1] - t[1] * w / 2)
    b = (c[0] + t[0] * w / 2, c[1] + t[1] * w / 2)
    return Polygon([a, b, (b[0] + n[0] * depth, b[1] + n[1] * depth), (a[0] + n[0] * depth, a[1] + n[1] * depth)])


def sector(hinge, start_vec, end_vec, r, n=10):
    a0 = math.atan2(start_vec[1], start_vec[0])
    a1 = math.atan2(end_vec[1], end_vec[0])
    da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
    pts = [(hinge[0] + r * math.cos(a0 + da * i / n), hinge[1] + r * math.sin(a0 + da * i / n)) for i in range(n + 1)]
    return LineString(pts), Polygon([hinge] + pts)


def door_symbol(c, t, n, w):
    """Single (w < 1.6) or double leaf door in a wall: opening centre c, wall tangent t, swing side normal n."""
    leaves, arcs, swings = [], [], []
    if w < 1.6:
        h = (c[0] - t[0] * w / 2, c[1] - t[1] * w / 2)
        leaves.append(LineString([h, (h[0] + n[0] * w, h[1] + n[1] * w)]))
        arc, sw = sector(h, t, n, w)
        arcs.append(arc)
        swings.append(sw)
    else:
        hw = w / 2
        for s in (-1, 1):
            h = (c[0] + s * t[0] * hw, c[1] + s * t[1] * hw)
            leaves.append(LineString([h, (h[0] + n[0] * hw, h[1] + n[1] * hw)]))
            arc, sw = sector(h, (-s * t[0], -s * t[1]), n, hw)
            arcs.append(arc)
            swings.append(sw)
    return leaves, arcs, unary_union(swings)


class Planner:
    def __init__(self, g: SRC.FloorGeometry, seed=7):
        self.g = g
        self.rng = random.Random(seed * 1000 + SRC.FLOORS.index(g.floor))
        self.d = Drawing(g.floor)
        self.rooms = []
        self.vertical = []
        self.doors = []
        self.cols = [Point(x, y).buffer(SRC.COL_R, quad_segs=12) for x, y in g.columns]
        self.col_u = unary_union(self.cols)
        self.swing_u = Polygon()

    # ------------------------------------------------------------------ structure & symbols
    def structure_and_symbols(self):
        g, d = self.g, self.d
        ST.add_structure(d, g)
        self.core_info, self.wc_info, self.tube_info = {}, {}, {}
        for cid, b in sorted(g.cores.items()):
            served = g.slab.intersection(box(*b).buffer(2.0).difference(box(*b))).area > 6.0
            self.core_info[cid] = SY.add_core(d, cid, b, served)
            name = "코어 %s (특별피난계단)" % cid
            self.vertical.append({"id": "코어 " + cid, "name": name, "status": "MODEL_VERIFIED footprint / " + (
                "interior = 1F symbol reuse (PROPOSED)" if served else "no floor slab at this level (model); shaft continues")})
            if not served:
                d.notes.append("CORE_%s_NO_SLAB_AT_LEVEL: core walls exist in model, no floor slab around the hall door" % cid)
        for wid, b in SY.wc_bounds().items():
            fp = box(*b)
            if wid in g.cores and self.core_info[wid]["served"] and g.slab.buffer(0.06).contains(fp):
                self.wc_info[wid] = SY.add_restroom(d, wid, b)
            else:
                d.notes.append("RESTROOM_%s_OMITTED: adjacent core absent/unserved or footprint not on the slab at this level" % wid)
        for n, t in sorted(g.tubes.items()):
            self.tube_info[n] = SY.add_tube(d, n, t, bool(g.ramps), self.cols, g.outline)
            nm = TUBE_KO.get(n, n)
            if n == "T1" and not g.ramps:
                nm = "T1 빛 튜브 (램프 없음)"
            self.vertical.append({"id": n, "name": nm, "status": "MODEL_VERIFIED opening / content = 1F symbol reuse (PROPOSED)"})
            cx, cy = self.tube_info[n]["center"]
            ly = cy - 0.2 - (self.tube_info[n]["r"] * 0.62 if n in ("T3", "T4") else 0.0)
            d.text(cx, ly, n if n[0] != "c" else ("W" if n == "capW" else "E"), "micro", prov=SYMBOL_REUSE, box=True)
        for n, s in sorted(g.shafts.items()):
            SY.add_ev_shaft(d, n, s)
            self.vertical.append({"id": n, "name": TUBE_KO.get(n, n), "status": "MODEL_VERIFIED opening / content = symbol (PROPOSED)"})
            d.text(s.centroid.x, s.centroid.y - 0.2, n, "micro", prov=SYMBOL_REUSE, box=True)
        for e in g.escalators:
            d.vertical_note = True
            c = e["poly"].centroid
            self.vertical.append({"id": "ESC", "name": "에스컬레이터 절단부 " + e["name"], "status": "MODEL_VERIFIED cut (1.5 m)"})
        for e in g.escalators:                                       # chevrons across the verified escalator cut
            x0, y0, x1, y1 = e["poly"].bounds
            long_x = (x1 - x0) > (y1 - y0)
            n = 6
            for i in range(1, n):
                f = i / n
                seg = LineString([(x0 + f * (x1 - x0), y0), (x0 + f * (x1 - x0), y1)]) if long_x else LineString([(x0, y0 + f * (y1 - y0)), (x1, y0 + f * (y1 - y0))])
                d.add("A-STAR", seg, "detail", prov=MODEL_VERIFIED, ref="escalator tread (schematic)")

    # ------------------------------------------------------------------ free area, aprons
    def free_area(self):
        g = self.g
        solid = [box(*b) for b in g.cores.values()] + [w["footprint"] for w in self.wc_info.values()]
        self.solid = unary_union(solid)
        self.free = g.slab.difference(self.solid).buffer(0)
        aprons = []
        for cid, ci in self.core_info.items():
            if ci["served"]:
                n = APRON_DIR[CORE_VES_SIDE[cid]]
                aprons.append(oriented_rect(ci["hall_door_c"], n, 2.8, 2.4))
        for wi in self.wc_info.values():
            aprons.append(wi["swings"].buffer(1.2))
        for ti in self.tube_info.values():
            if ti.get("entry_zone") is not None:
                aprons.append(ti["entry_zone"].buffer(1.0))
        self.aprons = unary_union(aprons).intersection(g.slab) if aprons else Polygon()
        self.zones = [(PROG.get(z["name_ko"], "retail"), z["poly"].buffer(0)) for z in g.zones]
        self.prog_poly = {}
        for p, z in self.zones:
            self.prog_poly[p] = z if p not in self.prog_poly else self.prog_poly[p].union(z)

    def prog_of(self, poly):
        best, ba = None, 0.0
        for p, z in self.zones:
            a = poly.intersection(z).area
            if a > ba:
                best, ba = p, a
        if best is None and self.zones:
            best = min(self.zones, key=lambda pz: poly.distance(pz[1]))[0]
        return best or "retail"

    # ------------------------------------------------------------------ units
    def make_cells(self):
        """Candidate unit cells on the column grid (merge/split by program), before fitting to the verified slab."""
        bx0, by0, bx1, by1 = AN.building_envelope()
        xs, ys = AN.typical_grid()
        xi0, xi1, yi0, yi1 = xs[1], xs[-2], ys[1], ys[-2]
        xe = [bx0] + xs[1:-1] + [bx1]
        ye = [yi0] + ys[2:-2] + [yi1]
        sides = {
            "N": [box(xe[i], yi1, xe[i + 1], by1) for i in range(len(xe) - 1)],
            "S": [box(xe[i], by0, xe[i + 1], yi0) for i in range(len(xe) - 1)],
            "W": [box(bx0, ye[i], xi0, ye[i + 1]) for i in range(len(ye) - 1)],
            "E": [box(xi1, ye[i], bx1, ye[i + 1]) for i in range(len(ye) - 1)],
        }
        avail = self.free.difference(self.aprons)
        self.cells = []
        for side, rects in sides.items():
            seq = []
            for r in rects:
                raw = r.intersection(avail)
                seq.append({"rect": r, "prog": self.prog_of(raw) if raw.area > 1 else None, "full": raw.area >= 0.7 * r.area})
            i = 0
            while i < len(seq):
                c = seq[i]
                if c["prog"] is None or c["prog"] == "garden":
                    i += 1
                    continue
                nxt = seq[i + 1] if i + 1 < len(seq) else None
                if c["prog"] in ("fnb", "culture") and nxt and nxt["prog"] == c["prog"] and c["full"] and nxt["full"] \
                        and (c["prog"] == "culture" or self.rng.random() < 0.5):
                    self.cells.append({"rect": c["rect"].union(nxt["rect"]).envelope, "prog": c["prog"], "side": side})
                    i += 2
                    continue
                if c["prog"] == "retail" and c["full"] and self.rng.random() < 0.5:
                    x0, y0, x1, y1 = c["rect"].bounds
                    if side in ("N", "S"):
                        xm = (x0 + x1) / 2
                        parts = [box(x0, y0, xm, y1), box(xm, y0, x1, y1)]
                    else:
                        ym = (y0 + y1) / 2
                        parts = [box(x0, y0, x1, ym), box(x0, ym, x1, y1)]
                    self.cells += [{"rect": q, "prog": "retail", "side": side} for q in parts]
                else:
                    self.cells.append({"rect": c["rect"], "prog": c["prog"], "side": side})
                i += 1

    def fit_rect(self, cell, usable, step=0.3):
        """Largest rectangle inside `usable` obtained by pulling the cell's non-facade sides in (units stay square)."""
        x0, y0, x1, y1 = cell["rect"].bounds
        fixed = {"N": 3, "S": 1, "W": 0, "E": 2}[cell["side"]]

        def viol(b):
            return box(*b).difference(usable).area
        b = [x0, y0, x1, y1]
        for _ in range(120):
            if viol(b) < 0.05:
                break
            cands = []
            for k in range(4):
                if k == fixed:
                    continue
                nb = list(b)
                nb[k] += step if k < 2 else -step
                if nb[2] - nb[0] < MIN_UNIT_W or nb[3] - nb[1] < MIN_UNIT_W:
                    continue
                cands.append(nb)
            if not cands:
                return None
            b = min(cands, key=lambda nb: (round(viol(nb), 3), -(nb[2] - nb[0]) * (nb[3] - nb[1])))
        else:
            return None
        if viol(b) >= 0.05 or box(*b).area < MIN_UNIT_AREA:
            return None
        return b

    def fit_units(self, block):
        avail = self.free.difference(self.aprons).difference(block)
        fitted = []
        for cell in self.cells:
            b = self.fit_rect(cell, avail)
            if b:
                fitted.append({"b": b, "prog": cell["prog"], "side": cell["side"]})
        fixed = {"N": 3, "S": 1, "W": 0, "E": 2}
        for u in fitted:                                       # close <=1 m gaps between neighbouring units
            for k in range(4):
                if k == fixed[u["side"]]:
                    continue
                x0, y0, x1, y1 = u["b"]
                strip = [box(x0 - 1.0, y0, x0, y1), box(x0, y0 - 1.0, x1, y0), box(x1, y0, x1 + 1.0, y1), box(x0, y1, x1, y1 + 1.0)][k]
                others = [box(*o["b"]) for o in fitted if o is not u and box(*o["b"]).intersects(strip)]
                if not others:
                    continue
                hb = unary_union(others).intersection(strip).bounds
                if len(hb) < 4 or not hb:
                    continue
                dist = [x0 - hb[2], y0 - hb[3], hb[0] - x1, hb[1] - y1][k]
                if 0.02 < dist <= 1.0:
                    nb = list(u["b"])
                    nb[k] += -dist if k < 2 else dist
                    if box(*nb).difference(avail).area < 0.05:
                        u["b"] = nb
        self.units = []
        for u in fitted:
            poly = box(*u["b"]).intersection(avail).buffer(0)
            if poly.geom_type == "Polygon" and poly.area >= MIN_UNIT_AREA:
                self.units.append({"poly": poly, "prog": u["prog"], "side": u["side"]})

    def required_nodes(self):
        nodes = {}
        for cid, ci in self.core_info.items():
            if ci["served"]:
                n = APRON_DIR[CORE_VES_SIDE[cid]]
                c = ci["hall_door_c"]
                nodes["core " + cid] = Point(c[0] + n[0] * 1.6, c[1] + n[1] * 1.6)
        for n, ti in self.tube_info.items():
            if ti.get("kind") == "elevator":
                cx, cy = ti["center"]
                nodes["tube " + n] = Point(cx, cy - ti["r"] - 0.9)
        for wid, wi in self.wc_info.items():
            nodes["wc " + wid] = wi["swings"].centroid
        return nodes

    def ortho_route(self, src, goal_poly, space, cost_poly, step=0.6, turn=1.2):
        """Orthogonal least-cost path (turn-penalised Dijkstra) from point `src` to any cell inside `goal_poly`,
        moving only through `space`; cells inside `cost_poly` (units) cost 3x. Returns a list of corner points or None."""
        minx, miny, maxx, maxy = space.bounds
        xs = np.arange(minx, maxx + step, step)
        ys = np.arange(miny, maxy + step, step)
        X, Y = np.meshgrid(xs, ys)
        allowed = shapely.contains_xy(space, X, Y)
        goals = shapely.contains_xy(goal_poly, X, Y) & allowed
        costly = shapely.contains_xy(cost_poly, X, Y) if cost_poly is not None and not cost_poly.is_empty else np.zeros_like(allowed)
        H, W = allowed.shape
        if not allowed.any() or not goals.any():
            return None
        j0, i0 = int(round((src.y - miny) / step)), int(round((src.x - minx) / step))
        if not (0 <= j0 < H and 0 <= i0 < W and allowed[j0, i0]):
            ay, ax = np.nonzero(allowed)
            m = int(np.argmin((ax - i0) ** 2 + (ay - j0) ** 2))
            j0, i0 = int(ay[m]), int(ax[m])
        dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        dist = {(j0, i0, -1): 0.0}
        prev = {}
        pq = [(0.0, j0, i0, -1)]
        end = None
        while pq:
            dd, j, i, d = heapq.heappop(pq)
            if dd > dist.get((j, i, d), 1e18):
                continue
            if goals[j, i]:
                end = (j, i, d)
                break
            for nd, (dj, di) in enumerate(dirs):
                nj, ni = j + dj, i + di
                if 0 <= nj < H and 0 <= ni < W and allowed[nj, ni]:
                    c = dd + step * (3.0 if costly[nj, ni] else 1.0) + (turn if d != -1 and nd != d else 0.0)
                    if c < dist.get((nj, ni, nd), 1e18):
                        dist[(nj, ni, nd)] = c
                        prev[(nj, ni, nd)] = (j, i, d)
                        heapq.heappush(pq, (c, nj, ni, nd))
        if end is None:
            return None
        cells = [end]
        while cells[-1] in prev:
            cells.append(prev[cells[-1]])
        pts = [(minx + i * step, miny + j * step) for j, i, _ in reversed(cells)]
        out = [pts[0]]
        for k in range(1, len(pts) - 1):
            a, b, c = pts[k - 1], pts[k], pts[k + 1]
            if (abs(b[0] - a[0]) < 1e-6 and abs(c[0] - b[0]) < 1e-6) or (abs(b[1] - a[1]) < 1e-6 and abs(c[1] - b[1]) < 1e-6):
                continue
            out.append(b)
        out.append(pts[-1])
        return out

    def connect_pockets(self):
        """Every core door / restroom / elevator entry must reach the main hall: carve a 2.6 m orthogonal corridor if not."""
        self.make_cells()
        block = Polygon()
        self.fit_units(block)
        nodes = {k: p for k, p in self.required_nodes().items() if k.startswith(("core", "wc"))}
        tried = set()
        for _ in range(10):
            uu = unary_union([u["poly"] for u in self.units]) if self.units else Polygon()
            hall = self.free.difference(uu).buffer(0.02).buffer(-0.02)
            walk = hall.buffer(-0.7).difference(self.col_u.buffer(0.2))       # where a 1.4 m wide passage actually fits
            comps = polys(walk, 1.0)
            if not comps:
                break
            main = max(comps, key=lambda q: q.area)
            bad = [(k, p) for k, p in nodes.items() if k not in tried and main.distance(p) > 1.4]
            if not bad:
                break
            k, p = bad[0]
            tried.add(k)
            goal = main.buffer(-1.0)
            path = None
            for clr in (1.2, 0.85, 0.55):                      # prefer wide channels, accept a 1.1 m clear channel last
                space = self.free.buffer(-clr).union(Point(p.x, p.y).buffer(0.8))
                path = self.ortho_route(p, goal if not goal.is_empty else main, space, uu)
                if path:
                    break
            if not path or len(path) < 2:
                self.d.notes.append("POCKET_NOT_CONNECTED %s" % k)
                continue
            cor = LineString([(p.x, p.y)] + path).buffer(1.8, cap_style=2, join_style=2).intersection(self.free)
            block = block.union(cor)
            self.fit_units(block)
        self.carved = block

    def place_doors(self):
        """One door per unit on the longest edge facing the hall; units without a hall edge are dropped (merged into hall)."""
        for _round in range(2):
            uu = unary_union([u["poly"] for u in self.units]) if self.units else Polygon()
            hall = self.free.difference(uu).buffer(0)
            hall_b = hall.buffer(0.08)
            keep = []
            for u in self.units:
                edge = u["poly"].boundary.intersection(hall_b)
                if edge.is_empty:
                    segs = []
                elif edge.geom_type == "MultiLineString":
                    try:
                        segs = lines(linemerge(edge))
                    except ValueError:
                        segs = lines(edge)
                else:
                    segs = lines(edge)
                segs = sorted(segs, key=lambda s: -s.length)
                door = None
                for s in segs:
                    if s.length < 2.7:
                        continue
                    wdt = 1.8 if u["poly"].area >= 50 and s.length >= 3.4 else 1.2
                    for frac in (0.5, 0.35, 0.65, 0.25, 0.75):
                        p = s.interpolate(frac, normalized=True)
                        if p.distance(self.col_u) < wdt / 2 + 0.55:
                            continue
                        dist = s.project(p)
                        a, b = s.interpolate(max(dist - 0.4, 0)), s.interpolate(min(dist + 0.4, s.length))
                        tv = (b.x - a.x, b.y - a.y)
                        L = math.hypot(*tv) or 1.0
                        t = (tv[0] / L, tv[1] / L)
                        nvec = (-t[1], t[0])
                        if not hall.contains(Point(p.x + nvec[0] * 0.5, p.y + nvec[1] * 0.5)):
                            nvec = (-nvec[0], -nvec[1])
                        if not hall.contains(Point(p.x + nvec[0] * 0.5, p.y + nvec[1] * 0.5)):
                            continue
                        door = {"center": (p.x, p.y), "t": t, "n": nvec, "w": wdt}
                        break
                    if door:
                        break
                if door:
                    leaves, arcs, sw = door_symbol(door["center"], door["t"], door["n"], door["w"])
                    door.update({"leaves": leaves, "arcs": arcs, "swing": sw})
                    u["door"] = door
                    keep.append(u)
            if len(keep) == len(self.units):
                break
            self.units = keep
        self.hall_all = self.free.difference(unary_union([u["poly"] for u in self.units]) if self.units else Polygon()).buffer(0)
        self.swing_u = unary_union([u["door"]["swing"] for u in self.units]) if self.units else Polygon()

    def walls_and_door_items(self):
        g, d = self.g, self.d
        if not self.units:
            return
        edges = unary_union([u["poly"].boundary for u in self.units])
        excl = unary_union([g.outline.exterior.buffer(0.07)] + [h.exterior.buffer(0.07) for h in g.holes] +
                           [box(*b).buffer(0.07) for b in g.cores.values()] +
                           [w["footprint"].buffer(0.1) for w in self.wc_info.values()])
        wall_lines = edges.difference(excl)
        walls = wall_lines.buffer(0.075, cap_style=3, join_style=2)
        gaps = []
        for u in self.units:
            dr = u["door"]
            ang = math.degrees(math.atan2(dr["t"][1], dr["t"][0]))
            gap = affinity.rotate(box(-dr["w"] / 2, -0.3, dr["w"] / 2, 0.3), ang, origin=(0, 0))
            gaps.append(affinity.translate(gap, dr["center"][0], dr["center"][1]))
        walls = walls.difference(unary_union(gaps))
        d.add("A-WALL-PART", walls, "cut_medium", fill="#666666", prov=PROPOSED, ref="unit partition walls (150 mm)")
        for i, u in enumerate(self.units):
            dr = u["door"]
            d.add("A-DOOR", MultiLineString([[tuple(c) for c in l.coords] for l in dr["leaves"]]), "projection_light", prov=PROPOSED, ref="unit door leaf")
            d.add("A-DOOR", MultiLineString([[tuple(c) for c in a.coords] for a in dr["arcs"]]), "detail", prov=PROPOSED, ref="unit door swing")
            self.doors.append({"center": dr["center"], "width": dr["w"], "kind": "double" if dr["w"] >= 1.6 else "single"})

    # ------------------------------------------------------------------ rooms
    def build_rooms(self):
        rooms = []
        cu = 0
        for u in self.units:
            if u["prog"] == "culture":
                use = CULTURE_USES[cu % len(CULTURE_USES)]
                cu += 1
                name = use
            else:
                use = ""
                name = UNIT_NAME.get(u["prog"], "점포")
            rooms.append({"name": name, "program": u["prog"], "poly": u["poly"], "kind": "unit", "use": use,
                          "prov": PROPOSED, "door": u["door"]})
        hall = self.hall_all.buffer(0.02).buffer(-0.02)
        hp = {p: hall.intersection(z) for p, z in self.prog_poly.items()}
        left = hall.difference(unary_union(list(hp.values()))) if hp else hall
        for piece in polys(left, 0.01):
            p = min(self.prog_poly.items(), key=lambda kv: piece.distance(kv[1]))[0] if self.prog_poly else "retail"
            hp[p] = hp[p].union(piece) if p in hp else piece
        for p, hg in hp.items():
            for comp in polys(hg.buffer(0.03).buffer(-0.03), 12.0):          # smaller leftovers are circulation slivers, not rooms
                rooms.append({"name": HALL_NAME.get(p, "홀"), "program": p, "poly": comp,
                              "kind": "garden" if p == "garden" else "hall", "use": "", "prov": PROPOSED})
        for wid, wi in self.wc_info.items():
            for un in wi["units"]:
                rooms.append({"name": "화장실 " + un["label"], "program": "restroom", "poly": un["poly"], "kind": "restroom",
                              "use": un["name"], "prov": SYMBOL_REUSE})
        rooms.sort(key=lambda r: (-round(r["poly"].centroid.y / 7.0), r["poly"].centroid.x))
        for i, r in enumerate(rooms):
            r["id"] = "%02d" % (i + 1)
            r["area_m2"] = round(r["poly"].area, 1)
        self.rooms = rooms

    # ------------------------------------------------------------------ circulation
    def circulation(self):
        g = self.g
        halls = unary_union([r["poly"] for r in self.rooms if r["kind"] in ("hall", "garden")])
        walk = halls.buffer(-0.4).difference(self.col_u.buffer(0.35)).difference(self.swing_u.buffer(0.05))
        self.walk = walk
        self.routes = []
        if walk.is_empty:
            return
        nodes = self.required_nodes()
        for e in self.g.escalators:
            hole = next((h for h in g.holes if h.intersects(e["poly"])), None)
            nodes["esc " + e["name"]] = (hole or e["poly"]).centroid
        minx, miny, maxx, maxy = walk.bounds
        step = 0.6
        X, Y = np.meshgrid(np.arange(minx, maxx + step, step), np.arange(miny, maxy + step, step))
        mask = shapely.contains_xy(walk, X, Y)
        H, W = mask.shape
        idx_of = {}
        for k, pt in nodes.items():
            if mask.sum() == 0:
                break
            if walk.distance(pt) > 2.5:
                self.d.notes.append("CIRC_NODE_SKIPPED %s (not in hall space)" % k)
                continue
            q = nearest_points(walk, pt)[0]
            i, j = int(round((q.x - minx) / step)), int(round((q.y - miny) / step))
            if 0 <= j < H and 0 <= i < W and mask[j, i]:
                idx_of[k] = (j, i)
            else:                                              # nearest masked cell
                ys_, xs_ = np.nonzero(mask)
                m = np.argmin((xs_ - i) ** 2 + (ys_ - j) ** 2)
                idx_of[k] = (int(ys_[m]), int(xs_[m]))
        names = list(idx_of)
        if len(names) < 2:
            return
        nb = [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0), (-1, -1, 1.414), (-1, 1, 1.414), (1, -1, 1.414), (1, 1, 1.414)]

        def dijkstra(src):
            dist = {src: 0.0}
            prev = {}
            pq = [(0.0, src)]
            while pq:
                dd, u = heapq.heappop(pq)
                if dd > dist.get(u, 1e18):
                    continue
                for dj, di, w in nb:
                    v = (u[0] + dj, u[1] + di)
                    if 0 <= v[0] < H and 0 <= v[1] < W and mask[v]:
                        nd = dd + w * step
                        if nd < dist.get(v, 1e18):
                            dist[v], prev[v] = nd, u
                            heapq.heappush(pq, (nd, v))
            return dist, prev
        tabs = {k: dijkstra(idx_of[k]) for k in names}
        done, rest = {names[0]}, set(names[1:])
        while rest:
            best = None
            for a in done:
                for b in rest:
                    dd = tabs[a][0].get(idx_of[b], 1e18)
                    if best is None or dd < best[0]:
                        best = (dd, a, b)
            if best is None or best[0] >= 1e17:
                self.d.notes.append("CIRC_UNREACHABLE: " + ",".join(sorted(rest)))
                break
            _, a, b = best
            path, cur = [idx_of[b]], idx_of[b]
            prev = tabs[a][1]
            while cur != idx_of[a]:
                cur = prev[cur]
                path.append(cur)
            pts = [(minx + i * step, miny + j * step) for j, i in reversed(path)]
            if len(pts) >= 2:
                self.routes.append((a, b, LineString(pts).simplify(0.45)))
            done.add(b)
            rest.discard(b)
        self.nodes = nodes

    # ------------------------------------------------------------------ labels
    def place_labels(self):
        d = self.d
        circ_buf = unary_union([r[2].buffer(0.7) for r in self.routes]) if self.routes else Polygon()
        blockers_common = unary_union([self.swing_u.buffer(0.15), self.col_u.buffer(0.6), circ_buf, self.aprons.buffer(0.0)])
        self.label_zones = []
        for r in self.rooms:
            poly = r["poly"]
            if r["kind"] == "restroom":
                modes = [("tag", None)]
            else:
                nm, ar = r["name"], "%s㎡" % format(r["area_m2"], ",.1f")
                wn, hn = text_extent_m(nm, 8.0, "bold")
                wa, ha = text_extent_m(ar, 6.25)
                bw, bh = 0.95 + 0.2 + max(wn, wa), max(0.95, hn + ha + 0.15)
                modes = [("full", (bw, bh, nm, ar, wn, wa, hn, ha)), ("tag", None)]
            blockers = blockers_common.union(self.walk.boundary.buffer(0.0)) if False else blockers_common
            r["label"] = None
            for mode, dat in modes:
                w, h = (dat[0], dat[1]) if dat else (0.95, 0.95)
                free = poly.buffer(-0.3, join_style=2).difference(blockers).difference(unary_union(self.label_zones) if self.label_zones else Polygon())
                spot = None
                for comp in sorted(polys(free), key=lambda p: -p.area)[:4]:
                    if comp.area < w * h * 1.05:
                        continue
                    pole = polylabel(comp, 0.15)
                    offs = [(0.0, 0.0)] + [(dx, dy) for rad in np.arange(0.5, 14.0, 0.5)
                                           for dx, dy in [(rad, 0), (-rad, 0), (0, rad), (0, -rad), (rad, rad), (-rad, -rad), (rad, -rad), (-rad, rad)]]
                    for dx, dy in offs:
                        cand = box(pole.x + dx - w / 2, pole.y + dy - h / 2, pole.x + dx + w / 2, pole.y + dy + h / 2)
                        if comp.contains(cand):
                            spot = (pole.x + dx, pole.y + dy, cand)
                            break
                    if spot:
                        break
                if spot:
                    r["label"] = {"mode": mode, "cx": spot[0], "cy": spot[1], "dat": dat}
                    self.label_zones.append(spot[2].buffer(0.25))
                    break
            if r["label"] is None:                              # AGENTS 3.1 fallback: white-masked tag at the pole of inaccessibility
                pole = polylabel(max(polys(poly), key=lambda q: q.area), 0.15) if polys(poly) else poly.representative_point()
                r["label"] = {"mode": "tag", "cx": pole.x, "cy": pole.y, "dat": None, "forced": True}
                d.notes.append("LABEL_FORCED_TAG room %s (%s, %.1f m2): too narrow for a clear label, white-masked tag used" % (r["id"], r["name"], r["area_m2"]))

    def draw_labels(self):
        d = self.d
        for r in self.rooms:
            lb = r["label"]
            if not lb:
                continue
            cx, cy = lb["cx"], lb["cy"]
            if lb["mode"] == "full":
                bw, bh, nm, ar, wn, wa, hn, ha = lb["dat"]
                tx = cx - bw / 2 + 0.475
                d.add("A-ANNO-TAGS", Point(tx, cy).buffer(0.45, quad_segs=10), "projection_light", fill="#ffffff", prov=PROPOSED, ref="tag " + r["id"])
                d.text(tx, cy - 0.2, r["id"], "micro", layer="A-ANNO-TAGS", prov=PROPOSED)
                x0 = cx - bw / 2 + 0.95 + 0.2
                d.text(x0, cy + 0.15 * 0 + bh / 2 - hn * 0.85, r["name"], "room", anchor="start", prov=PROPOSED)
                d.text(x0, cy - bh / 2 + 0.25, "%s㎡" % format(r["area_m2"], ",.1f"), "sub", anchor="start", prov=PROPOSED)
            else:
                d.add("A-ANNO-TAGS", Point(cx, cy).buffer(0.45, quad_segs=10), "projection_light", fill="#ffffff", prov=PROPOSED, ref="tag " + r["id"])
                d.text(cx, cy - 0.2, r["id"], "micro", layer="A-ANNO-TAGS", prov=PROPOSED)

    # ------------------------------------------------------------------ furniture
    def furnish(self):
        d = self.d
        circ_buf = unary_union([r[2].buffer(1.1) for r in self.routes]) if self.routes else Polygon()
        label_u = unary_union(self.label_zones) if self.label_zones else Polygon()
        tubes_ctx = [{"c": Point(*ti["center"]), "r": ti["r"]} for n, ti in self.tube_info.items() if n in ("T1", "T2")]
        for r in self.rooms:
            items = []
            if r["kind"] == "unit" and r["program"] in ("retail", "fnb", "culture"):
                dr = r["door"]
                door = {"center": dr["center"], "inward": (-dr["n"][0], -dr["n"][1]), "swing": dr["swing"], "width": dr["w"]}
                items = FO.fit(r["poly"], r["program"], r["use"], door, self.col_u, label_u, self.rng)
            elif r["kind"] in ("hall", "garden"):
                reg = r["poly"].buffer(-1.3, join_style=2)
                obst = unary_union([circ_buf, self.swing_u.buffer(0.3), label_u, self.aprons.buffer(0.3)])
                hard = self.col_u.buffer(SRC.COL_R + 1.2 - 0.45 + 0.45 * 0 + 0.0)
                for comp in polys(reg, 12.0):
                    try:
                        ctx = {"tubes": [t for t in tubes_ctx if comp.distance(t["c"]) < 14], "plaza": None}
                        items += UL.layout(UL_NAME.get(r["program"], "판매"), comp, obst, hard, self.rng, self.g.floor, ctx)
                    except Exception as e:                       # keep the build going, record the reason
                        d.notes.append("FURNITURE_FALLBACK room %s: %s" % (r["id"], repr(e)[:90]))
            bodies = [g for g, k in items if k == "body"]
            lns = [g for g, k in items if k == "line"]
            fol = [g for g, k in items if k == "foliage"]
            if bodies:
                d.add("A-FURN", shapely.geometry.MultiPolygon([b for b in bodies if b.geom_type == "Polygon"]), "projection_light", fill="#ffffff", prov=PROPOSED, ref="furniture room " + r["id"])
            if lns:
                d.add("A-FURN", MultiLineString([[tuple(c) for c in l.coords] for l in lns if l.geom_type == "LineString"]), "detail", prov=PROPOSED, ref="furniture detail room " + r["id"])
            if fol:
                for f in fol:
                    d.add("A-FURN", f if f.geom_type in ("Polygon", "MultiPolygon") else f, "detail", fill="#eeeeee" if f.geom_type == "Polygon" else None, prov=PROPOSED, ref="planting room " + r["id"])
            r["n_furniture"] = len(items)

    def tints_and_routes(self):
        d = self.d
        for r in self.rooms:
            if r["kind"] in ("hall", "garden", "unit"):
                tint = TINT.get(r["program"], "#f6f6f6") if r["kind"] != "unit" else "#ffffff"
                d.add("A-ZONE", r["poly"], None, fill=tint, prov=PROPOSED, ref="zone tint %s" % r["id"])
        for a, b, ls in self.routes:
            d.add("A-CIRC", ls, "circ", dash="circ", prov=PROPOSED, ref="circulation %s -> %s" % (a, b))
        for k, p in getattr(self, "nodes", {}).items():
            d.add("A-CIRC", p.buffer(0.28, quad_segs=6), "circ", fill="#2f5d8a", prov=PROPOSED, ref="node " + k)

    def run(self):
        self.structure_and_symbols()
        self.free_area()
        self.connect_pockets()
        self.place_doors()
        self.walls_and_door_items()
        self.build_rooms()
        self.circulation()
        self.place_labels()
        self.furnish()
        self.tints_and_routes()
        self.draw_labels()
        AN.add_grid_and_dims(self.d, self.g.z, self.g.floor)
        self.d.rooms = self.rooms
        self.d.meta.update({"vertical": self.vertical, "doors": self.doors})
        return self.d


def plan_floor(floor: str, seed=7) -> Drawing:
    return Planner(SRC.load_floor(floor), seed).run()

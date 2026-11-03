"""STEP 2 — 위상 복원 + 파라메트릭 CAD/SVG 엔진.

    python src/02_topology_to_cad.py --raw output/drawing_pipeline/raw_slices --out output/drawing_pipeline [--floors 1F,2F] [--scale 200]

입력: floor_<층>_slice.json + camera_bounds.json (STEP 1)
출력: out/cad/floor_<층>.dxf, out/vector/floor_<층>_vector.svg, out/vector/floor_<층>_layout.json (글자 상자: 충돌 검사용)

모든 숫자(면적·치수)는 도형에서 계산한 값이다. 이 파일에 좌표를 직접 쓰지 않는다 (AGENTS.md §6.1·§6.3).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import ezdxf
from ezdxf import const
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import polylabel, unary_union

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline_common as pc  # noqa: E402

PT = 0.3528                                        # 1 pt = 0.3528 mm
FONT_FAMILY = "Malgun Gothic, 'Segoe UI', Arial, sans-serif"

# AIA 레이어: (이름, 선 두께 mm(종이), 색 #hex, DXF ACI 색)
LAYERS = {                                          # 6단계 선 위계(A3 종이 mm, architectural_plan_renderer와 동일): 절단벽 0.45 > 문짝 0.18 > 계단 0.12 > 유리 0.09 > 스윙·가구 0.08 > 헤어라인 0.05
    "A-WALL-CUT": (0.45, "#000000", 7),
    "A-COLS-CUT": (0.45, "#000000", 7),
    "A-GLAZ-CUT": (0.09, "#4A4A4A", 8),
    "A-FLOR-PRJ": (0.05, "#CCCCCC", 9),
    "A-VERT-SYMB": (0.12, "#444444", 8),
    "A-DOOR-SYMB": (0.18, "#222222", 7),
    "A-FURN-2D": (0.08, "#666666", 8),
    "A-AREA-ZONE": (0.05, "#CCCCCC", 9),
    "A-ANNO-DIMS": (0.05, "#CCCCCC", 9),
    "A-ANNO-TEXT": (0.10, "#222222", 7),
}
POCHE = "#1A1A1A"
# 텍스트 위계 (AGENTS.md §3.1): (pt, 굵기, 색)
TEXT = {
    "room": (8.0, "bold", "#222222"),
    "sub": (6.5, "normal", "#555555"),
    "micro": (5.5, "bold", "#333333"),
    "dim": (6.0, "normal", "#555555"),
}


class Ctx:
    def __init__(self, bounds, scale):
        self.b = bounds
        self.scale = scale
        self.k = scale / 1000.0                    # 종이 1 mm = 도면 k m
        self.side = bounds["xmax"] - bounds["xmin"]

    def lw(self, layer):                           # 선 두께(도면 단위 m)
        return LAYERS[layer][0] * self.k

    def fs(self, role):                            # 글자 높이(도면 단위 m)
        return TEXT[role][0] * PT * self.k

    def sx(self, x):
        return x - self.b["xmin"]

    def sy(self, y):
        return self.b["ymax"] - y


def text_size(s: str, h: float) -> tuple[float, float]:
    """글자 상자 (폭, 높이). 한글은 전각, 그 밖은 0.55 폭으로 어림한다."""
    w = sum(1.0 if ord(c) > 0x2E80 else 0.55 for c in s) * h
    return w, h * 1.15


def hatch_lines(geom, spacing, angle_deg=45.0):
    """도형 안을 채우는 평행선 (SVG·DXF 공통, 패턴 정의에 의존하지 않는다)."""
    if geom.is_empty:
        return []
    minx, miny, maxx, maxy = geom.bounds
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    r = math.hypot(maxx - minx, maxy - miny) / 2 + spacing
    a = math.radians(angle_deg)
    dx, dy = math.cos(a), math.sin(a)
    nx, ny = -dy, dx
    segs = []
    n = int(r / spacing) + 1
    for i in range(-n, n + 1):
        ox, oy = cx + nx * i * spacing, cy + ny * i * spacing
        line = LineString([(ox - dx * r, oy - dy * r), (ox + dx * r, oy + dy * r)])
        inter = line.intersection(geom)
        for g in ([inter] if inter.geom_type == "LineString" else list(getattr(inter, "geoms", []))):
            if g.geom_type == "LineString" and g.length > 1e-6:
                segs.append(list(g.coords))
    return segs


# ── 분류: 어떤 kind가 어느 레이어·표현인가 ────────────────────────────────────────────────────────
def classify_cut(item, geom=None):
    k, mat, src = item["kind"], (item.get("material") or ""), item.get("source")
    if k == "column":
        return "A-COLS-CUT", "poche"
    if k == "core_wall":
        # 이름 규칙에서 온 코어는 속 찬 상자라 내부 상세가 없다 → 해치. 태그 모델의 코어벽은 실제 벽이다 → 포셰
        return ("A-WALL-CUT", "core") if src == "name" else ("A-WALL-CUT", "poche")
    if k in ("partition_wall", "exterior_wall"):
        return "A-WALL-CUT", "poche"
    if k == "tube_wall":
        thin = geom is not None and geom.length > 0 and geom.area / (geom.length / 2) < 0.35      # 얇은 링 = 유리 튜브
        return ("A-GLAZ-CUT", "glass") if ("glass" in mat or thin) else ("A-WALL-CUT", "poche")
    if k == "shaft":
        return ("A-WALL-CUT", "poche") if src == "name" else ("A-WALL-CUT", "outline")
    if k == "facade":
        return "A-GLAZ-CUT", "glass"
    if k in ("stair", "ramp"):
        return "A-VERT-SYMB", "outline"
    return "A-FURN-2D", "outline"


def rings(geom):
    for p in pc.iter_polygons(geom):
        yield list(p.exterior.coords)
        for h in p.interiors:
            yield list(h.coords)


# ── 라벨 배치 (글자는 빈 공간에, 서로 겹치지 않게) ──────────────────────────────────────────────────
class Placer:
    def __init__(self, obstacles):
        self.obstacles = obstacles
        self.boxes = []                              # 이미 놓인 글자 상자

    def fits(self, cx, cy, w, h, region):
        bx = box(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
        if not region.contains(bx):
            return None
        if any(bx.intersects(o) for o in self.boxes):
            return None
        return bx

    def place(self, region, w, h, prefer=None):
        """region 안에서 상자 (w×h)가 들어가는 가장 여유 있는 위치. 없으면 None."""
        if region.is_empty:
            return None
        cands = []
        if prefer is not None:
            cands.append((prefer.x, prefer.y))
        polys = sorted(pc.iter_polygons(region), key=lambda p: -p.area)
        for p in polys[:3]:
            try:
                c = polylabel(p, tolerance=0.05)
                cands.append((c.x, c.y))
            except Exception:
                pass
        minx, miny, maxx, maxy = region.bounds
        step = max(0.5, min(maxx - minx, maxy - miny) / 40)
        pts = []
        x = minx
        while x <= maxx:
            y = miny
            while y <= maxy:
                pt = Point(x, y)
                if region.contains(pt):
                    pts.append((region.boundary.distance(pt), x, y))
                y += step
            x += step
        pts.sort(reverse=True)
        cands += [(x, y) for _, x, y in pts[:400]]
        for cx, cy in cands:
            bx = self.fits(cx, cy, w, h, region)
            if bx is not None:
                self.boxes.append(bx.buffer(0.05))
                return cx, cy, bx
        return None


# ── 치수 체인 ────────────────────────────────────────────────────────────────────────────────────
def merge_breaks(vals, lo, hi, tol=0.02):
    pts = sorted(set([round(lo, 4), round(hi, 4)] + [round(v, 4) for v in vals if lo + tol < v < hi - tol]))
    out = []
    for v in pts:
        if not out or v - out[-1] > tol:
            out.append(v)
    return out


def build_dims(building, cuts, cols, dim_h):
    """4변 × 3단 치수. 단1(1.2 m): 바깥 변에 닿는 구조 요소 구간, 단2(2.0 m): 기둥 그리드, 단3(2.8 m): 전체."""
    x0, y0, x1, y1 = building
    perim = [g for kind, items in cuts.items() if kind != "column" for _, g in items]
    colx = [g.centroid.x for g in cols]
    coly = [g.centroid.y for g in cols]
    dims = []   # (tier, side, p1, p2, offset)

    def edge_breaks(side):
        vals = []
        for g in perim:
            gx0, gy0, gx1, gy1 = g.bounds
            if side == "bottom" and gy0 <= y0 + 0.6:
                vals += [gx0, gx1]
            if side == "top" and gy1 >= y1 - 0.6:
                vals += [gx0, gx1]
            if side == "left" and gx0 <= x0 + 0.6:
                vals += [gy0, gy1]
            if side == "right" and gx1 >= x1 - 0.6:
                vals += [gy0, gy1]
        return vals

    for side in ("bottom", "top", "left", "right"):
        horiz = side in ("bottom", "top")
        lo, hi = (x0, x1) if horiz else (y0, y1)
        e = {"bottom": y0, "top": y1, "left": x0, "right": x1}[side]
        sign = -1 if side in ("bottom", "left") else 1
        tiers = {
            1: merge_breaks(edge_breaks(side), lo, hi),
            2: merge_breaks(colx if horiz else coly, lo, hi, tol=0.05),
            3: [lo, hi],
        }
        for tier, off in ((1, 1.2), (2, 2.0), (3, 2.8)):
            br = tiers[tier]
            if len(br) < 2 or (tier == 1 and len(br) == 2):
                continue                                         # 구간이 하나뿐이면 단3과 같으므로 생략
            for a, b in zip(br, br[1:]):
                if text_size(fmt_mm(b - a), dim_h)[0] + 0.15 > (b - a):      # 글자가 구간에 들어가지 않으면 생략 (치수 글자 겹침 방지)
                    continue
                p1 = (a, e) if horiz else (e, a)
                p2 = (b, e) if horiz else (e, b)
                dims.append((tier, side, p1, p2, sign * off))
    return dims


# ── 한 층 처리 ───────────────────────────────────────────────────────────────────────────────────
def process_floor(raw, floor, out_dir, ctx: Ctx):
    sl = pc.load_slice(raw, floor)
    cuts = pc.cut_geometries(sl)
    slab_geoms = [pc.polygons_from_segments(p["segments"]) for p in sl["projection"]]
    slab = unary_union([g for g in slab_geoms if not g.is_empty]) if slab_geoms else Polygon()
    all_cut = unary_union([g for items in cuts.values() for _, g in items]) if cuts else Polygon()
    ref = slab if not slab.is_empty else all_cut
    building = ref.bounds
    cols = [g for _, g in cuts.get("column", [])]

    # 영역(방) 폴리곤
    zones = []
    for z in sl["zones"]:
        g = pc.polygons_from_segments(z["segments"])
        if not g.is_empty:
            zones.append((z, g))

    # 글자 배치: 장애물 = 모든 절단 요소(약간 팽창)
    obstacles = all_cut.buffer(0.35) if not all_cut.is_empty else Polygon()
    placer = Placer(obstacles)
    labels = []   # dict(text, role, x, y, w, h, bold)

    def add_label(lines, region, anchor=None, inside=False):
        """lines: [(text, role)] 줄 묶음을 한 상자로 놓는다. inside=True면 region 자체가 요소 안쪽이라 장애물을 빼지 않는다.
        빈 공간에 못 들어가면 선 위에 순백색 배경 상자를 깔고 놓는다 (AGENTS.md §3.1 부득이한 경우)."""
        free = region if (inside or obstacles.is_empty) else region.difference(obstacles)
        rw = (region.bounds[2] - region.bounds[0]) if not region.is_empty else 0

        def wrap(t, h, maxw):                       # 공백에서 줄바꿈 (긴 이름이 작은 방에 들어가도록)
            if text_size(t, h)[0] <= maxw or " " not in t:
                return [t]
            out, cur = [], ""
            for w_ in t.split(" "):
                nxt = (cur + " " + w_).strip()
                if cur and text_size(nxt, h)[0] > maxw:
                    out.append(cur)
                    cur = w_
                else:
                    cur = nxt
            return out + [cur]

        def build(scale):
            rows = []
            for t, r in lines:
                h = ctx.fs(r) * scale
                for part in wrap(t, h, max(rw * 0.9, h)):
                    rows.append((part, r, h))
            return rows, max(text_size(t, h)[0] for t, _, h in rows), sum(h * 1.15 for _, _, h in rows)

        res, rows, knockout = None, None, False
        for scale in (1.0, 0.85, 0.7, 0.6):         # 글자를 단계적으로 줄여 빈 공간에 먼저 시도
            rows, W, H = build(scale)
            res = placer.place(free, W, H, prefer=anchor)
            if res is not None:
                break
        if res is None and not inside:              # 그래도 안 되면 흰 배경 상자로 선 위에 놓는다 (이때도 글자를 단계적으로 줄인다)
            for scale in (0.7, 0.6, 0.5):
                rows, W, H = build(scale)
                res = placer.place(region.buffer(-0.1), W + 0.3, H + 0.2, prefer=anchor)
                if res is not None:
                    knockout = True
                    break
        if res is None:
            return False
        cx, cy, bx = res
        y = cy + H / 2
        for t, r, h in rows:
            y -= h * 1.15
            labels.append({"text": t, "role": r, "x": cx, "y": y + h * 0.2, "w": text_size(t, h)[0], "h": h, "knockout": knockout})
        return True

    unplaced, covered = [], []
    visible = []
    for z, g in zones:
        free_area = g.difference(obstacles).area if not obstacles.is_empty else g.area
        if free_area < 1.0:                       # 영역이 코어·튜브 등 절단 요소 안에 통째로 들어가 있다 (모델의 볼륨 겹침) → 글자를 놓을 곳이 없다
            covered.append({"name": z["name_ko"], "area_m2": round(g.area, 2)})
        else:
            visible.append((z, g))
    zones = visible
    for z, g in zones:
        area = sum(p.area for p in pc.iter_polygons(g))
        name = z["name_ko"]
        ok = add_label([(name, "room"), ("%s㎡" % format(round(area), ","), "sub")], g)
        if not ok:
            unplaced.append(name)
    for kind in ("core_wall",):
        for it, g in cuts.get(kind, []):
            if it.get("source") == "name":                       # 속 찬 코어 상자에만 (태그 모델의 코어는 방 영역이 이름을 가진다)
                add_label([(it["name_ko"], "room")], g.buffer(-0.3), inside=True)
    for kind in ("tube_wall",):
        for it, g in cuts.get(kind, []):
            if len(it["name_ko"]) <= 6 and "튜브" in it["name_ko"] and it["name_ko"].split()[-1].startswith("T"):
                # 큰 튜브(T1~T4)는 속이 비어 있으므로 링의 외곽 안쪽 공간에 코드만 적는다
                shell = Polygon(max(pc.iter_polygons(g), key=lambda p: p.area).exterior)
                add_label([(it["name_ko"].split()[-1], "micro")], shell.buffer(-0.2))

    symbols = []                                              # 문 스윙 부채꼴·위생도기 등 변환 메타데이터 + 윤곽
    for s in sl.get("symbols", []):
        g = pc.polygons_from_segments(s.get("segments", []))
        if not g.is_empty:
            symbols.append((s, g))
    dims = build_dims(building, cuts, cols, ctx.fs("dim"))
    return {"sl": sl, "cuts": cuts, "slab": slab, "building": building, "zones": zones, "labels": labels,
            "dims": dims, "unplaced": unplaced, "cols": cols, "covered": covered, "symbols": symbols}


def fmt_mm(v):
    return format(int(round(v * 1000)), ",")


def escalator_arrow(item, floor):
    ax, rg = item.get("axis"), item.get("escalator_range")
    if not ax or not rg:
        return None
    lo, hi = ax["low_xy"], ax["high_xy"]
    if floor == rg[0]:
        return lo, hi, "UP"
    if floor == rg[1]:
        return hi, lo, "DN"
    return None


# ── SVG ──────────────────────────────────────────────────────────────────────────────────────────
def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")


def write_svg(path, ctx: Ctx, data, floor):
    import svgwrite
    S = ctx.side
    mm = S * 1000.0 / ctx.scale
    dwg = svgwrite.Drawing(path, size=("%.3fmm" % mm, "%.3fmm" % mm), viewBox="0 0 %.6f %.6f" % (S, S), profile="full")
    dwg.set_desc(desc="camera_bounds " + json.dumps({k: ctx.b[k] for k in ("xmin", "ymin", "xmax", "ymax")}))   # 도면 좌표 경계(미터)
    P = lambda pts: [(ctx.sx(x), ctx.sy(y)) for x, y in pts]
    layer_g = {n: dwg.g(id=n, fill="none", stroke=LAYERS[n][1], stroke_width=ctx.lw(n), stroke_linejoin="miter") for n in LAYERS}

    def path_d(geom):
        d = []
        for r in rings(geom):
            pts = P(r)
            d.append("M" + " L".join("%.5f,%.5f" % p for p in pts) + " Z")
        return " ".join(d)

    g = layer_g["A-FLOR-PRJ"]
    if not data["slab"].is_empty:
        g.add(dwg.path(d=path_d(data["slab"]), fill="none", fill_rule="evenodd"))

    for kind, items in data["cuts"].items():
        for it, geom in items:
            layer, mode = classify_cut(it, geom)
            tgt = layer_g[layer]
            d = path_d(geom)
            if mode == "poche":
                tgt.add(dwg.path(d=d, fill=POCHE, fill_rule="evenodd"))
            elif mode == "glass":
                tgt.add(dwg.path(d=d, fill="#dfe9ee", fill_rule="evenodd", fill_opacity=0.6))
            elif mode == "core":
                tgt.add(dwg.path(d=d, fill="#f2f2f2", fill_rule="evenodd", stroke_width=ctx.lw("A-WALL-CUT")))
                for seg in hatch_lines(geom, 1.2 * ctx.k, 45):
                    tgt.add(dwg.polyline(P(seg), stroke="#777777", stroke_width=ctx.lw("A-ANNO-DIMS") * 0.8, fill="none"))
            else:
                tgt.add(dwg.path(d=d, fill="none", fill_rule="evenodd"))
                arrow = escalator_arrow(it, data["sl"]["floor"])
                if arrow:
                    (x1, y1), (x2, y2), tag = arrow
                    A = P([(x1, y1), (x2, y2)])
                    layer_g["A-VERT-SYMB"].add(dwg.line(A[0], A[1], stroke="#333333", stroke_width=ctx.lw("A-VERT-SYMB")))
                    ang = math.atan2(A[1][1] - A[0][1], A[1][0] - A[0][0])
                    hl = 1.2 * ctx.k * 2.0
                    for da in (2.6, -2.6):
                        layer_g["A-VERT-SYMB"].add(dwg.line(A[1], (A[1][0] - hl * math.cos(ang + da / 3), A[1][1] - hl * math.sin(ang + da / 3)),
                                                            stroke="#333333", stroke_width=ctx.lw("A-VERT-SYMB")))
                    layer_g["A-VERT-SYMB"].add(dwg.text(tag, insert=((A[0][0] + A[1][0]) / 2, (A[0][1] + A[1][1]) / 2),
                                                        font_size=ctx.fs("micro"), font_family=FONT_FAMILY, font_weight="bold",
                                                        fill=TEXT["micro"][2], stroke="none", text_anchor="middle"))
    for z, g_ in data["zones"]:
        layer_g["A-AREA-ZONE"].add(dwg.path(d=path_d(g_), fill="none", stroke_dasharray="%.3f,%.3f" % (3 * ctx.k, 2 * ctx.k)))
    for s, g_ in data["symbols"]:                      # 문: 스윙 부채꼴(호 + 문짝), 그 밖: 위생도기·가구 윤곽
        lay = "A-DOOR-SYMB" if s["category"] == "door" else "A-FURN-2D"
        layer_g[lay].add(dwg.path(d=path_d(g_), fill="#ffffff" if lay == "A-DOOR-SYMB" else "none", fill_opacity=0.0 if lay == "A-DOOR-SYMB" else 1,
                                  fill_rule="evenodd"))

    # 치수
    gd = layer_g["A-ANNO-DIMS"]
    tick = 1.0 * ctx.k
    ext = 0.6
    for tier, side, p1, p2, off in data["dims"]:
        horiz = side in ("bottom", "top")
        q1 = (p1[0], p1[1] + off) if horiz else (p1[0] + off, p1[1])
        q2 = (p2[0], p2[1] + off) if horiz else (p2[0] + off, p2[1])
        for p, q in ((p1, q1), (p2, q2)):                                    # 치수 보조선
            e = (q[0] - (0 if not horiz else 0), q[1])
            sgn = 1 if off > 0 else -1
            qe = (q[0], q[1] + sgn * ext * 0.5) if horiz else (q[0] + sgn * ext * 0.5, q[1])
            a, b = P([(p[0] + (0 if horiz else sgn * 0.25), p[1] + (sgn * 0.25 if horiz else 0)), qe])
            gd.add(dwg.line(a, b, stroke="#aaaaaa", stroke_width=ctx.lw("A-ANNO-DIMS") * 0.8))
        a, b = P([q1, q2])
        gd.add(dwg.line(a, b, stroke="#555555", stroke_width=ctx.lw("A-ANNO-DIMS")))
        for q in (a, b):                                                       # 45° 눈금
            gd.add(dwg.line((q[0] - tick / 2, q[1] + tick / 2), (q[0] + tick / 2, q[1] - tick / 2), stroke="#333333", stroke_width=ctx.lw("A-ANNO-DIMS") * 1.6))
        label = fmt_mm(math.hypot(p2[0] - p1[0], p2[1] - p1[1]))
        h = ctx.fs("dim")
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        sgn = 1 if off > 0 else -1
        if horiz:
            ty = my + (h * 0.5 + 0.25 * ctx.k if sgn > 0 else -0.25 * ctx.k)
            gd.add(dwg.text(label, insert=(mx, ty if sgn > 0 else my - 0.3 * ctx.k), font_size=h, font_family=FONT_FAMILY,
                            fill=TEXT["dim"][2], stroke="none", text_anchor="middle"))
        else:
            tx = mx + (-0.3 * ctx.k if sgn < 0 else h * 0.9)
            t = dwg.text(label, insert=(tx, my), font_size=h, font_family=FONT_FAMILY, fill=TEXT["dim"][2], stroke="none", text_anchor="middle")
            t.rotate(-90, center=(tx, my))
            gd.add(t)

    gt = layer_g["A-ANNO-TEXT"]
    for lb in data["labels"]:
        role = lb["role"]
        if lb.get("knockout"):                                                 # 순백색 배경 상자로 아래 선을 차폐 (AGENTS.md §3.1)
            pad = 0.2 * ctx.k
            gt.add(dwg.rect(insert=(ctx.sx(lb["x"] - lb["w"] / 2) - pad, ctx.sy(lb["y"] + lb["h"]) - pad),
                            size=(lb["w"] + 2 * pad, lb["h"] * 1.15 + 2 * pad), fill="#ffffff", stroke="none"))
        gt.add(dwg.text(lb["text"], insert=(ctx.sx(lb["x"]), ctx.sy(lb["y"])), font_size=lb["h"], font_family=FONT_FAMILY,
                        font_weight=TEXT[role][1], fill=TEXT[role][2], stroke="none", text_anchor="middle"))

    # 진북 화살표는 합성기(STEP 4)가 도곽에 그린다. 여기서는 도면만.
    dwg.add(dwg.rect(insert=(0, 0), size=(S, S), fill="none", stroke="none"))        # viewBox 전체를 점유 (경계 고정)
    for n in LAYERS:
        dwg.add(layer_g[n])
    dwg.save()


# ── DXF ──────────────────────────────────────────────────────────────────────────────────────────
def write_dxf(path, ctx: Ctx, data, floor):
    doc = ezdxf.new("R2018", setup=True)
    doc.units = ezdxf.units.M
    doc.header["$INSUNITS"] = 6
    for name, (lw, _, aci) in LAYERS.items():
        want = lw * 100                                            # 1/100 mm. DXF는 표준 값만 허용하므로 가장 가까운 값으로 맞춘다
        std = min(const.VALID_DXF_LINEWEIGHTS, key=lambda v: abs(v - want))
        doc.layers.add(name, color=aci, lineweight=std)
    doc.styles.add("KR", font="malgun.ttf")
    ds = doc.dimstyles.new("ARCH")
    ds.dxf.dimtxsty = "KR"
    ds.dxf.dimtxt = ctx.fs("dim")
    ds.dxf.dimtsz = 1.0 * ctx.k            # 45° 눈금
    ds.dxf.dimasz = 0
    ds.dxf.dimexe = 0.3 * ctx.k
    ds.dxf.dimexo = 0.25
    ds.dxf.dimdec = 0
    ds.dxf.dimlfac = 1000.0                # 미터 → 밀리미터 표기
    ds.dxf.dimclrd = 8
    ds.dxf.dimclre = 8
    ds.dxf.dimclrt = 8
    ds.dxf.dimgap = 0.4 * ctx.k
    ds.dxf.dimtad = 1
    msp = doc.modelspace()

    def poly(layer, geom, close=True):
        for r in rings(geom):
            msp.add_lwpolyline(r[:-1] if r[0] == r[-1] else r, close=close, dxfattribs={"layer": layer})

    def hatch(layer, geom, rgb=None, pattern=None, scale=1.0):
        h = msp.add_hatch(color=7, dxfattribs={"layer": layer})
        h.dxf.hatch_style = const.HATCH_STYLE_NORMAL
        if pattern:
            h.set_pattern_fill(pattern, scale=scale, angle=45)
        else:
            h.set_solid_fill(color=250 if rgb is None else rgb)
        for r in rings(geom):
            h.paths.add_polyline_path(r, is_closed=True)

    if not data["slab"].is_empty:
        poly("A-FLOR-PRJ", data["slab"])
    for kind, items in data["cuts"].items():
        for it, geom in items:
            layer, mode = classify_cut(it, geom)
            poly(layer, geom)
            if mode == "poche":
                hatch(layer, geom, rgb=250)
            elif mode == "core":
                hatch(layer, geom, pattern="ANSI31", scale=ctx.k * 6)
            elif mode == "outline":
                arrow = escalator_arrow(it, data["sl"]["floor"])
                if arrow:
                    (x1, y1), (x2, y2), tag = arrow
                    msp.add_line((x1, y1), (x2, y2), dxfattribs={"layer": "A-VERT-SYMB"})
                    msp.add_text(tag, height=ctx.fs("micro"), dxfattribs={"layer": "A-ANNO-TEXT", "style": "KR"}).set_placement(
                        ((x1 + x2) / 2, (y1 + y2) / 2), align=const.MTEXT_MIDDLE_CENTER if False else ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
    for z, g in data["zones"]:
        poly("A-AREA-ZONE", g)
    for s, g in data["symbols"]:
        poly("A-DOOR-SYMB" if s["category"] == "door" else "A-FURN-2D", g)
    for tier, side, p1, p2, off in data["dims"]:
        dim = msp.add_aligned_dim(p1=p1, p2=p2, distance=off, dimstyle="ARCH", dxfattribs={"layer": "A-ANNO-DIMS"})
        dim.render()
    for lb in data["labels"]:
        msp.add_text(lb["text"], height=lb["h"], dxfattribs={"layer": "A-ANNO-TEXT", "style": "KR"}).set_placement(
            (lb["x"], lb["y"]), align=ezdxf.enums.TextEntityAlignment.BOTTOM_CENTER)
    doc.saveas(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--floors", default="")
    ap.add_argument("--scale", type=int, default=200)
    a = ap.parse_args()
    raw, out = os.path.abspath(a.raw), os.path.abspath(a.out)
    os.makedirs(os.path.join(out, "cad"), exist_ok=True)
    os.makedirs(os.path.join(out, "vector"), exist_ok=True)
    bounds = pc.load_bounds(raw)
    ctx = Ctx(bounds, a.scale)
    floors = [f for f in a.floors.split(",") if f] or pc.list_floors(raw)
    for f in floors:
        data = process_floor(raw, f, out, ctx)
        svg = os.path.join(out, "vector", "floor_%s_vector.svg" % f)
        dxf = os.path.join(out, "cad", "floor_%s.dxf" % f)
        write_svg(svg, ctx, data, f)
        write_dxf(dxf, ctx, data, f)
        layout = {"floor": f, "scale": a.scale, "labels": data["labels"], "unplaced": data["unplaced"],
                  "dims": [{"tier": t, "side": s, "p1": p1, "p2": p2, "offset": o} for t, s, p1, p2, o in data["dims"]],
                  "counts": {k: len(v) for k, v in data["cuts"].items()}, "building": list(data["building"]),
                  "slab_area_m2": round(data["slab"].area, 2), "covered_zones": data["covered"],
                  "zones": [{"name": z["name_ko"], "area_m2": round(sum(p.area for p in pc.iter_polygons(g)), 2)} for z, g in data["zones"]],
                  "floor_z": data["sl"]["floor_z"], "cut_z": data["sl"]["cut_z"]}
        with open(os.path.join(out, "vector", "floor_%s_layout.json" % f), "w", encoding="utf-8") as fh:
            json.dump(layout, fh, ensure_ascii=False, indent=1)
        print("CAD", f, "labels=%d dims=%d unplaced=%s" % (len(data["labels"]), len(data["dims"]), data["unplaced"]), os.path.abspath(svg))
    print("DONE_CAD", out)


if __name__ == "__main__":
    main()

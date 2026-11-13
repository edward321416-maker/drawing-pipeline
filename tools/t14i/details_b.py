"""C-T14I details D-406 ... D-410 (agent D2): envelope + slab edge, escalator, sunken stair, cargo elevator, roof.

    python -X utf8 tools/t14i/details_b.py [--run <RUN>] [--only D-406,D-407] [--verify]

build(run, out_dir) -> list[registry row]      draws the five sheets into RUN\\v4\\details\\<SID>_detail.svg/.pdf/.png
verify(run)         -> dict                    re-measures every MODEL VERIFIED fact from the raw model cache (model_world.npz,
                                               model_objects.json, floor_1F_slice.json) with code that does NOT share the drawing path
                                               and compares it with the value/printed text recorded in details_b_facts.json

Truth classes (COMMON_BRIEF): MODEL VERIFIED (measured from the cache), DERIVED (arithmetic on model values), CONCEPT PROPOSED
(our proposal, labelled schematic, never a construction fact), UNRESOLVED (no source, no decision: stated, not drawn).
Nothing here edits model geometry; the cache is read only.
"""
import t14i  # noqa: F401  (edition env, sys.path, text policy) -- must be first
import argparse
import json
import math
import os
import re
import sys

import numpy as np
from PIL import Image, ImageFont
from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

import book_views as bv
import pipeline_common as pc
import t14d_sheet as _ts
import t14e_dims as dm
from t14d_sheet import Sheet, geom_lines, geom_rings
from t14e_make_views import r5
from t14f import fonts as _fonts
from t14g import registry as sheetreg, truth
from t14i import axon, common, config as cfg

PT = 0.3528
CLS_MV, CLS_DR, CLS_CP, CLS_UN = "MODEL VERIFIED", "DERIVED", "CONCEPT PROPOSED", "UNRESOLVED"
CLS_COL = dict(cfg.CLASS_COLOR)
CLS_COL[CLS_DR] = "#3b4fa0"
OFF_MASTER = (9.0, 18.0)        # master (building-local) = drawing frame + OFF_MASTER (checked on Core A/D and Shaft_FR)

# ------------------------------------------------------------------------------------------------------------------------------
# text metrics / wrapping
# ------------------------------------------------------------------------------------------------------------------------------
_FONTS = {}


def _pil_font(bold):
    key = "bold" if bold else "regular"
    if key not in _FONTS:
        _FONTS[key] = ImageFont.truetype(_fonts.resolve(key)[0], 200)
    return _FONTS[key]


def tw(s, pt, bold=False):
    """Rendered width (mm) of a string at pt points."""
    return _pil_font(bold).getlength(s) / 200.0 * pt * PT


def wrap(s, width_mm, pt, bold=False):
    """Greedy word wrap with character-level break for words wider than the line (Korean text has few spaces)."""
    out = []
    for para in str(s).split("\n"):
        words = para.split(" ")
        cur = ""
        for w in words:
            cand = w if not cur else cur + " " + w
            if tw(cand, pt, bold) <= width_mm:
                cur = cand
                continue
            if cur:
                out.append(cur)
            cur = ""
            while tw(w, pt, bold) > width_mm and len(w) > 1:       # break a long word
                k = len(w)
                while k > 1 and tw(w[:k], pt, bold) > width_mm:
                    k -= 1
                out.append(w[:k])
                w = w[k:]
            cur = w
        out.append(cur)
    return out


def text_block(sh, x, y, w, s, pt=7.0, weight="normal", color="#333", lead=1.42, anchor="start"):
    """Draw wrapped text with its top at y. Returns y of the next free line (bottom of the block)."""
    size = max(pt, _ts.MIN_PT) * PT
    lines = wrap(s, w, max(pt, _ts.MIN_PT), weight == "bold")
    yy = y
    for ln in lines:
        yy += size * lead if yy > y else size * 1.0
        sh.text(x if anchor == "start" else x + w, yy, ln, pt, weight, color, anchor)
    return yy + size * 0.35


def block_height(w, s, pt=7.0, lead=1.42, bold=False):
    size = max(pt, _ts.MIN_PT) * PT
    n = len(wrap(s, w, max(pt, _ts.MIN_PT), bold))
    return size * 1.0 + (n - 1) * size * lead + size * 0.35


# ------------------------------------------------------------------------------------------------------------------------------
# facts
# ------------------------------------------------------------------------------------------------------------------------------
class Facts:
    def __init__(self):
        self.rows = []
        self._ids = set()

    def add(self, sid, key, label, value, unit, cls, source, printed=None):
        fid = "%s.%s" % (sid, key)
        assert fid not in self._ids, "duplicate fact id " + fid
        self._ids.add(fid)
        if isinstance(value, (np.floating, np.integer)):
            value = float(value)
        self.rows.append({"id": fid, "label": label, "value": value, "unit": unit, "class": cls, "source": source, "printed": printed})
        return printed

    def printed(self, fid, text):
        for r in self.rows:
            if r["id"] == fid:
                r["printed"] = text
                return text
        raise KeyError(fid)


def mm(v_m):
    """metres -> integer millimetres rounded to 10 mm (the sheet convention of t14e_dims.fmt_mm)."""
    return int(round(v_m * 100.0) * 10)


def lvl(z, F):
    """Level text relative to GL = 1F FFL (= +-0.000)."""
    v = r5(z - F["1F"])
    return "±0.000" if abs(v) < 0.0005 else "%+.3f" % v


# ------------------------------------------------------------------------------------------------------------------------------
# model access (drawing path)
# ------------------------------------------------------------------------------------------------------------------------------
class Geo:
    def __init__(self, run):
        self.run = run
        self.model = common.load_model(run)
        self.F = self.model.floors
        self.byname = {o["name"]: o for o in self.model.objects}
        self.master = pc.load_json(os.path.join(run, "reference_1F", "floor_1F_slice.json"))
        self._plan = {}

    def objs(self, prefix=None, kinds=None, pred=None):
        out = []
        for o in self.model.objects:
            if prefix and not o["name"].startswith(prefix):
                continue
            if kinds and o["kind"] not in kinds:
                continue
            if pred and not pred(o):
                continue
            out.append(o)
        return out

    def tris_window(self, o, x0=None, y0=None, x1=None, y1=None, z0=None, z1=None):
        """Triangles of o whose bounding box meets the window (cheap prefilter for the heavy facade objects)."""
        T = self.model.tris(o)
        if len(T) == 0:
            return T
        keep = np.ones(len(T), bool)
        for ax, lo, hi in ((0, x0, x1), (1, y0, y1), (2, z0, z1)):
            if lo is not None:
                keep &= T[:, :, ax].max(axis=1) >= lo
            if hi is not None:
                keep &= T[:, :, ax].min(axis=1) <= hi
        return T[keep]

    def bbox(self, o):
        T = self.model.tris(o).reshape(-1, 3)
        return T.min(0), T.max(0)

    def cut_z(self, z, kinds, window=None):
        key = (round(z, 4), tuple(sorted(kinds)), None if window is None else tuple(np.round(window, 3)))
        if key not in self._plan:
            self._plan[key] = bv.plan_cut(self.model, z, set(kinds), window)
        return self._plan[key]

    def cut_obj_z(self, o, z, window=None):
        """Horizontal cut polygon of ONE object (any kind) at height z, triangles prefiltered by the window."""
        if window is not None:
            T = self.tris_window(o, window[0], window[1], window[2], window[3])
        else:
            T = self.model.tris(o)
        return plan_cut_tris(T, z)

    def cut_obj_vert(self, o, axis, value, look, window=None):
        """Vertical cut polygon (u,z) of ONE object at axis=value looking +/-axis (u = bv.section 'right' coordinate)."""
        ax = 0 if axis == "x" else 1
        lk = np.zeros(2)
        lk[ax] = look
        right = np.array([lk[1], -lk[0]])
        n = np.zeros(3)
        n[ax] = look
        c = look * value
        kw = {"x0": None, "x1": None, "y0": None, "y1": None, "z0": None, "z1": None}
        if window:
            kw.update(window)
        kw["xyz"[ax] + "0"] = value - 1e-6
        kw["xyz"[ax] + "1"] = value + 1e-6
        T = self.tris_window(o, **kw)
        if len(T) == 0:
            return Polygon()
        crossing = ((T[:, :, ax].min(axis=1) < value) & (T[:, :, ax].max(axis=1) > value)).any()
        if not crossing:
            return Polygon()
        return bv._cut_polygon(T, n, c, right)


def plan_cut_tris(T, z):
    """Same algorithm as bv.plan_cut for one triangle array."""
    from shapely.ops import polygonize
    if len(T) == 0:
        return Polygon()
    d = T[:, :, 2] - z
    segs = []
    for i in range(len(T)):
        di = d[i]
        if not ((di > 1e-9).any() and (di < -1e-9).any()):
            continue
        pts = []
        for j in range(3):
            a, b = T[i][j], T[i][(j + 1) % 3]
            da, db = di[j], di[(j + 1) % 3]
            if (da > 1e-9 and db < -1e-9) or (da < -1e-9 and db > 1e-9):
                pts.append(a + (da / (da - db)) * (b - a))
        if len(pts) >= 2 and np.linalg.norm(pts[0] - pts[1]) > 1e-7:
            segs.append(LineString([(round(pts[0][0], 4), round(pts[0][1], 4)), (round(pts[1][0], 4), round(pts[1][1], 4))]))
    if not segs:
        return Polygon()
    return bv._evenodd(list(polygonize(unary_union(segs))))


def footprint(T):
    """Union of the xy footprints of triangles (projection seen from above)."""
    tris = []
    for t in T:
        p = Polygon([(t[0][0], t[0][1]), (t[1][0], t[1][1]), (t[2][0], t[2][1])])
        if p.area > 1e-9:
            tris.append(p)
    if not tris:
        return Polygon()
    u = unary_union(tris)
    return u.buffer(0.001, join_style=2).buffer(-0.001, join_style=2)


def parts(g):
    return [p for p in (g.geoms if hasattr(g, "geoms") else [g]) if p.geom_type == "Polygon" and not p.is_empty]


def snap(g, step=0.005):
    """Round coordinates to 5 mm (kills 1-2 mm mesh noise so straight edges stay straight on paper)."""
    if g.is_empty:
        return g
    try:
        import shapely
        return shapely.set_precision(g, step)
    except Exception:
        return g


def from_master(g):
    """Master (building-local) geometry -> drawing frame."""
    return affinity.translate(g, -OFF_MASTER[0], -OFF_MASTER[1])


# ------------------------------------------------------------------------------------------------------------------------------
# sheet drawing helpers
# ------------------------------------------------------------------------------------------------------------------------------
INK = "#111"


class View:
    """Model-metre -> sheet-mm mapping of one drawing view. kind 'plan' (x right, y up) or 'sec' (u right, z up)."""

    def __init__(self, ox, oy, cx, cy, scale):
        self.k = 1000.0 / scale
        self.scale = scale
        self.ox, self.oy, self.cx, self.cy = ox, oy, cx, cy      # (ox,oy) = sheet point of model point (cx,cy)

    def X(self, a):
        return self.ox + (a - self.cx) * self.k

    def Y(self, b):
        return self.oy - (b - self.cy) * self.k

    def pt(self, a, b):
        return (self.X(a), self.Y(b))

    def rings(self, g):
        return [[(self.X(x), self.Y(y)) for x, y in r] for r in geom_rings(g)]

    def poly_mm(self, g):
        out = []
        for p in parts(g):
            out.append(Polygon([(self.X(x), self.Y(y)) for x, y in p.exterior.coords], [[(self.X(x), self.Y(y)) for x, y in r.coords] for r in p.interiors]))
        return out

    def rect(self, a0, b0, a1, b1):
        return (self.X(a0), self.Y(b1), self.X(a1), self.Y(b0))   # x0,y0,x1,y1 in sheet mm (y0 = top)


def hatch(sh, polys_mm, spacing=1.7, angle=45.0, w=0.05, color="#777"):
    for g in polys_mm:
        if g.is_empty:
            continue
        x0, y0, x1, y1 = g.bounds
        r = math.hypot(x1 - x0, y1 - y0)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        n = int(r / spacing) + 2
        ln = []
        for i in range(-n, n + 1):
            base = LineString([(cx - r, cy + i * spacing), (cx + r, cy + i * spacing)])
            seg = affinity.rotate(base, angle, origin=(cx, cy))
            ln += geom_lines(seg.intersection(g))
        if ln:
            sh.path(ln, stroke=color, w=w, closed=False)


def draw_cut(sh, view, g, fill="#fff", stroke="#000", w=0.45, hatch_it=True, spacing=1.7):
    """Cut polygon (model coords) -> filled outline (+ generic hatch = 'material not decided')."""
    g = g if g is not None else Polygon()
    if g.is_empty:
        return
    sh.path(view.rings(g), fill=fill, stroke=stroke, w=w)
    if hatch_it:
        hatch(sh, view.poly_mm(g), spacing=spacing)


def draw_outline(sh, view, g, stroke="#555", w=0.2, fill="none", dash=None):
    g = g if g is not None else Polygon()
    if g.is_empty:
        return
    sh.path(view.rings(g), fill=fill, stroke=stroke, w=w, dash=dash)


def dline(sh, pts_mm, color="#444", w=0.2, dash=None):
    sh.path([list(pts_mm)], stroke=color, w=w, closed=False, dash=dash)


def panel(sh, name, x0, y0, x1, y1, title=None, tag=None, border="#bbb", pt=7.5):
    """Claimed rectangle with a thin frame and a header line (title left, class badge right)."""
    sh.claim(name, x0, y0, x1, y1)
    sh.path([[(x0, y0), (x1, y0), (x1, y1), (x0, y1)]], stroke=border, w=0.15)
    if title:
        sh.text(x0 + 2.0, y0 + 4.2, title, pt, "bold", "#111")
    if tag:
        tag_badge(sh, x1 - 2.0 - tag_w(tag), y0 + 0.9, tag)


def tag_w(kind, pt=6.0):
    return tw(kind, pt, True) + 3.4


def tag_badge(sh, x, y, kind, pt=6.0, h=4.2):
    col = CLS_COL[kind]
    w = tag_w(kind, pt)
    sh.path([[(x, y), (x + w, y), (x + w, y + h), (x, y + h)]], fill="#fff", stroke=col, w=0.3)
    sh.text(x + w / 2, y + h * 0.73, kind, pt, "bold", col, "middle")
    return x + w


def bullets(sh, x, y, w, items, pt=7.0, tag_col=27.0, gap=1.6):
    """items: [(class, text)] -> badge column + wrapped text. Returns the y below the last bullet."""
    yy = y
    for cls, txt in items:
        tag_badge(sh, x, yy, cls)
        yy2 = text_block(sh, x + tag_col, yy, w - tag_col, txt, pt)
        yy = max(yy2, yy + 4.6) + gap
    return yy


def bullets_height(w, items, pt=7.0, tag_col=27.0, gap=1.6):
    h = 0.0
    for cls, txt in items:
        h += max(block_height(w - tag_col, txt, pt), 4.6) + gap
    return h


def level_mark(sh, x, y, label, side="right", pt=6.5, color="#222"):
    """Filled level triangle on a level line + text."""
    sh.path([[(x, y), (x + 1.7, y - 2.5), (x - 1.7, y - 2.5)]], fill="#000", stroke="#000", w=0.1)
    sh.text(x + 3.0, y - 0.7, label, pt, "bold", color)


def leader(sh, p_from, p_text, text, pt=6.5, color="#06a", anchor="start", dot=True, bold=False, dy=0.0):
    """Leader line from a feature point to a text anchor (text sits next to the end, never on linework)."""
    dline(sh, [p_from, p_text], color, 0.15)
    if dot:
        sh.path([[(p_from[0] + 0.55 * math.cos(t / 8 * 2 * math.pi), p_from[1] + 0.55 * math.sin(t / 8 * 2 * math.pi)) for t in range(9)]], fill=color, stroke=color, w=0.05)
    gap = 1.0 if anchor == "start" else -1.0
    sh.text(p_text[0] + gap, p_text[1] + 0.8 + dy, text, pt, "bold" if bold else "normal", color, anchor)


def num_bubble(sh, x, y, n, color="#a00", r=2.4):
    dm.bubble(sh, x, y, str(n), r=r, pt=6.5, color=color)


def break_line(sh, x0, y0, x1, y1, color="#222"):
    """Zig-zag break (cut-off) line between two sheet points."""
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    n = max(int(L / 3.0), 2)
    pts = [(x0, y0)]
    for i in range(1, n):
        t = i / n
        off = 1.1 if i % 2 else -1.1
        pts.append((x0 + dx * t + nx * off, y0 + dy * t + ny * off))
    pts.append((x1, y1))
    dline(sh, pts, color, 0.25)


def local_scale_bar(sh, x, y, scale, meters, label=None, color="#333"):
    """Small graphic scale for an inset drawn at another scale (a line with ticks, NOT a filled bar)."""
    k = 1000.0 / scale
    L = meters[-1] * k
    sh.path([[(x, y), (x + L, y)]], stroke=color, w=0.3, closed=False)
    for m_ in meters:
        sh.path([[(x + m_ * k, y - 1.2), (x + m_ * k, y + 1.2)]], stroke=color, w=0.3, closed=False)
        sh.text(x + m_ * k, y - 2.0, "%g%s" % (m_, " m" if m_ == meters[-1] else ""), 6.0, "normal", color, "middle")
    sh.text(x, y + 4.6, label or "1:%d" % scale, 6.0, "normal", "#555")


def keyplan(sh, run, x, y, size, center_xy, ring_mm=3.0, label="확대 위치 KEY PLAN"):
    """3F plan as a tiny keyplan with the enlarged location ringed (mapping identical to t14e_make_views.mini_keyplan)."""
    sl = pc.load_slice(os.path.join(run, "raw_slices"), "3F")
    cuts = pc.cut_geometries(sl)
    slab = bv._union([pc.polygons_from_segments(p["segments"]) for p in sl["projection"]])
    x0, y0, x1, y1 = slab.bounds
    k = size / max(x1 - x0, y1 - y0)
    P = lambda a, b: (x + (a - x0) * k, y + (y1 - b) * k)
    sh.text(x, y - 2.0, label, 6.5, "bold", "#222")
    sh.path([[P(a, b) for a, b in r] for r in geom_rings(slab)], fill="#f4f4f4", stroke="#555", w=0.2)
    for kind, fill in (("core_wall", "#333"), ("tube_wall", "#fff")):
        for it, g in cuts.get(kind, []):
            sh.path([[P(a, b) for a, b in r] for r in geom_rings(g)], fill=fill, stroke="#222", w=0.12)
    cx, cy = P(*center_xy)
    sh.path([[(cx + ring_mm * math.cos(t / 24 * 2 * math.pi), cy + ring_mm * math.sin(t / 24 * 2 * math.pi)) for t in range(25)]], stroke="#a60", w=0.45, closed=True)
    return (x, y - 5.0, x + size, y + size * (y1 - y0) / max(x1 - x0, y1 - y0))


def embed_image(sh, img, x, y, w, h, quality=88, fmt="JPEG"):
    """Embed a PIL image as base64 into the sheet SVG (placed in the box, aspect preserved, centred). Returns the drawn box."""
    import base64
    import io
    iw, ih = img.size
    s = min(w / iw, h / ih)
    dw, dh = iw * s, ih * s
    ox, oy = x + (w - dw) / 2, y + (h - dh) / 2
    buf = io.BytesIO()
    if fmt == "JPEG":
        img.convert("RGB").save(buf, "JPEG", quality=quality, optimize=True)
        mime = "image/jpeg"
    else:
        img.save(buf, "PNG", optimize=True)
        mime = "image/png"
    sh.parts.append('<image x="%.3f" y="%.3f" width="%.3f" height="%.3f" preserveAspectRatio="none" href="data:%s;base64,%s"/>' % (ox, oy, dw, dh, mime, base64.b64encode(buf.getvalue()).decode("ascii")))
    return ox, oy, dw, dh, s


def box_clip(x0, y0, x1, y1):
    """axon clip: keep the part of every triangle inside the xy window (drawing-frame metres)."""
    def f(T):
        if len(T) == 0:
            return T
        for n, c in ((np.array([1.0, 0, 0]), x0), (np.array([-1.0, 0, 0]), -x1), (np.array([0, 1.0, 0]), y0), (np.array([0, -1.0, 0]), -y1)):
            T = bv._clip_half(T, n, c)
            if len(T) == 0:
                break
        return T
    return f


def prefilter_obj(geo, o, x0=None, y0=None, x1=None, y1=None):
    """A lightweight object stand-in (dict) is not possible for axon.render (it reads model.tris(o)); heavy objects are
    pre-clipped through `clip` instead. This helper just answers 'does the object meet the window'."""
    lo, hi = geo.bbox(o)
    ok = True
    if x0 is not None:
        ok &= hi[0] >= x0
    if x1 is not None:
        ok &= lo[0] <= x1
    if y0 is not None:
        ok &= hi[1] >= y0
    if y1 is not None:
        ok &= lo[1] <= y1
    return ok


def axon_panel(sh, geo, run, key, groups, box_mm, az, el, width_px=1500, extent_m=None, labels=(), caption=None, title="3D VIEW", name=None,
               img_h_mm=None, outline="#2b2b2b"):
    """Model-derived axonometric inside a panel: header, image, 'MODEL VERIFIED (3D render of cache mesh)' caption and optional
    labels = [(model_xyz, text, (dx_mm, dy_mm))] drawn with leader lines. Cache: RUN\\v4\\axon_cache\\<key>.png."""
    x0, y0, x1, y1 = box_mm
    name = name or ("axon_" + key)
    panel(sh, name, x0, y0, x1, y1, title, CLS_MV)
    cap = caption or "MODEL VERIFIED (3D render of cache mesh)"
    ch = 6.0
    ix, iy, iw, ih = x0 + 1.5, y0 + 6.5, (x1 - x0) - 3.0, (y1 - y0) - 6.5 - ch - 1.0
    cache = os.path.join(common.v4_dir(run, "axon_cache"), key + ".png")
    kw = dict(az=az, el=el, width_px=width_px, outline=outline)
    if extent_m is not None:
        kw["extent_m"] = extent_m
    img, pr = axon.render_cached(cache, geo.model, groups, **kw)
    ox, oy, dw, dh, s = embed_image(sh, img, ix, iy, iw, ih)
    for (xyz, text, (dx, dy)) in labels:
        px, py = pr.to_px(*xyz)
        sx, sy = ox + px * s, oy + py * s
        leader(sh, (sx, sy), (sx + dx, sy + dy), text, 6.0, "#222", "start" if dx >= 0 else "end")
    sh.text(x0 + 2.0, y1 - 1.8, cap, 6.0, "normal", "#0a6b3d")
    return img, pr, (ox, oy, dw, dh, s)


# ------------------------------------------------------------------------------------------------------------------------------
# common sheet furniture
# ------------------------------------------------------------------------------------------------------------------------------
def intent_box(sh, name, x0, y0, x1, y1, text, pt=7.0):
    panel(sh, name, x0, y0, x1, y1, "DESIGN INTENT 설계 의도", CLS_CP)
    yy = text_block(sh, x0 + 2.5, y0 + 5.2, (x1 - x0) - 5.0, text, pt)
    sh.text(x0 + 2.5, y1 - 1.6, "해석이며 모델·승인된 사실이 아님 (CONCEPT PROPOSED)", 6.0, "normal", CLS_COL[CLS_CP])
    return yy


def tech_panel(sh, name, x0, y0, x1, y1, items, pt=7.0):
    panel(sh, name, x0, y0, x1, y1, "TECHNICAL RELATIONSHIP 기술 관계")
    bullets(sh, x0 + 2.5, y0 + 6.2, (x1 - x0) - 5.0, items, pt)


def need_height(w, items, pt=7.0):
    return 6.2 + bullets_height(w - 5.0, items, pt) + 1.0


def north(sh, model, x, y, r=5.0):
    sh.north_arrow(x, y, model.north_deg, r=r)


def finish(sh, fname_base):
    sh.title_block()
    return sh.save(fname_base)


def mk_row(sh, base, sid, title, grade, classes, extra=None):
    scale = sheetreg.detail_scale(sid)
    ex = {"classes": classes, "part": "II", "kind": "detail"}
    if extra:
        ex.update(extra)
    return common.sheet_row(sh, base, title, grade, "details", scale, sh.paper, " + ".join(classes), ex)


# ==============================================================================================================================
# D-406  envelope + slab edge
# ==============================================================================================================================
def build_406(geo, facts, out_dir, run):
    sid = "D-406"
    scale = sheetreg.detail_scale(sid)
    assert scale == 50
    m, F = geo.model, geo.F
    ffl6, ffl7 = F["6F"], F["7F"]
    Y0, Y1 = 17.4, 27.6                                   # plan window (bay between column axes y=18.0 and y=27.0, west facade)
    X0, X1 = -10.3, -4.5
    ysec = 22.5                                           # section A-A through the mullion at y = 22.5
    sh = Sheet(sid, "전형층 외피·층판 가장자리와 입면 부재 (6F 서측)", scale, "MODEL VERIFIED 평면·단면 · CONCEPT PROPOSED 접합 개념 · UNRESOLVED 사양",
               subtitle="외피 부재 A-FACD_* 와 층판 단부 A-FLOR_s7_6F·기둥의 관계 — 6F 서측 외벽 · 참조 E-204 · P-101 · A-900 U-04",
               extra_lines=["모델 형상은 읽기 전용: 접합·재료·단열·방수는 모델에 없어 CONCEPT PROPOSED 개략도로만 분리 표기", "해칭은 재료 미확정 절단 표시, GL = 1F = ±0.000"])
    # ---- geometry --------------------------------------------------------------------------------------------------------
    win = (X0 - 0.5, Y0 - 0.5, X1 + 0.5, Y1 + 0.5)
    fac_names = ["A-FACD_glass", "A-FACD_mullion", "A-FACD_band", "A-FACD_spandrel", "A-FACD_louver", "A-FACD_rail"]
    zc = ffl6 + 1.5
    slab6 = geo.byname["A-FLOR_s7_6F"]
    slab_g = box(X0, Y0, X1, Y1).intersection(plan_cut_tris(geo.tris_window(slab6, X0 - 1, Y0 - 1, X1 + 1, Y1 + 1), ffl6 - 0.05))
    cutp = {}
    for nm in fac_names[:2]:
        cutp[nm] = box(X0, Y0, X1, Y1).intersection(geo.cut_obj_z(geo.byname[nm], zc, win))
    cols = [(o, box(X0, Y0, X1, Y1).intersection(geo.cut_obj_z(o, zc, win))) for o in geo.objs("A-STRC_column")]
    cols = [(o, g) for o, g in cols if not g.is_empty]
    # band footprint below the cut (outer strip) and mullion pieces
    band = geo.byname["A-FACD_band"]
    Tb = geo.tris_window(band, X0 - 1, Y0 - 1, X1 + 1, Y1 + 1, None, None, 24.5, 27.0)
    band_fp = box(X0, Y0, X1, Y1).intersection(footprint(Tb[(Tb[:, :, 2].max(axis=1) <= ffl6 + 0.4)])) if len(Tb) else Polygon()
    mul_pieces = sorted(parts(cutp["A-FACD_mullion"]), key=lambda p: p.centroid.y)
    # ---- measured values -------------------------------------------------------------------------------------------------
    glass_p = max(parts(cutp["A-FACD_glass"]), key=lambda p: p.area)
    g_b = glass_p.bounds                                   # x -9.041 .. -8.998
    slab_edge_x = slab_g.bounds[0]
    mul_b = [p.bounds for p in mul_pieces]
    mul_x_out = min(b[0] for b in mul_b)
    mul_y = [p.centroid.y for p in mul_pieces]
    pitch = float(np.mean(np.diff(mul_y)))
    col_c = sorted([g.centroid.y for o, g in cols if g.centroid.x < X1], key=lambda v: v)
    col_b = [g.bounds for o, g in cols if g.centroid.x < X1]
    col_face_x = min(b[0] for b in col_b)
    col_axis_pitch = col_c[-1] - col_c[0]
    Tband = geo.cut_obj_vert(band, "y", ysec, +1, dict(x0=-10, x1=-8, z0=24.5, z1=32.5))
    band_pieces = sorted(parts(Tband), key=lambda p: p.bounds[1])
    band_depth = band_pieces[0].bounds[2] - band_pieces[0].bounds[0]
    band_h = band_pieces[0].bounds[3] - band_pieces[0].bounds[1]
    band6 = band_pieces[0].bounds
    mull_sec = geo.cut_obj_vert(geo.byname["A-FACD_mullion"], "y", ysec, +1, dict(x0=-10, x1=-8, z0=24.5, z1=32.5))
    mull_sec_p = max(parts(mull_sec), key=lambda p: p.area)
    mb = mull_sec_p.bounds                                  # u -9.30 .. -9.04, z 26.0 .. 31.0
    mul_proj = (g_b[0] - mb[0])                              # projection beyond glass outer face
    slab_thk = geo.bbox(slab6)[1][2] - geo.bbox(slab6)[0][2]
    h_ff = ffl7 - ffl6
    # overlap mullion vs band at the 6F and 7F bands (measured on the section polygons)
    ov = []
    for bp in band_pieces:
        ovp = mull_sec_p.intersection(bp)
        ov.append((ovp.bounds[2] - ovp.bounds[0], ovp.bounds[3] - ovp.bounds[1]) if not ovp.is_empty else (0.0, 0.0))
    fac_objs = geo.objs("A-FACD")
    fam = {}
    for o in fac_objs:
        k = re.sub(r"\.\d+$", "", o["name"])
        k = re.sub(r"_(6F|7F)$", "_6F/7F", k)
        fam.setdefault(k, []).append(o)
    # ---- facts -----------------------------------------------------------------------------------------------------------
    fid = lambda k: "%s.%s" % (sid, k)
    facts.add(sid, "slab_t", "6F 슬래브(A-FLOR_s7_6F) 두께", mm(slab_thk), "mm", CLS_MV, "A-FLOR_s7_6F z 범위")
    facts.add(sid, "glass_t", "유리 A-FACD_glass 두께(서측)", mm(g_b[2] - g_b[0]), "mm", CLS_MV, "A-FACD_glass 절단 x 범위, y=22.5")
    facts.add(sid, "glass_gap", "슬래브 단부 외면과 유리 내면 간격", mm(g_b[2] - slab_edge_x), "mm", CLS_MV, "유리 내면 x − 슬래브 단부 x")
    facts.add(sid, "mull_proj", "멀리언 돌출(유리 외면 기준)", mm(mul_proj), "mm", CLS_MV, "A-FACD_mullion 절단 x 최외곽 − 유리 외면")
    facts.add(sid, "mull_pitch", "멀리언 간격", mm(pitch), "mm", CLS_MV, "A-FACD_mullion 평면 절단 중심 y 간격(서측, 18.9~26.1)")
    facts.add(sid, "col_pitch", "기둥 축 간격(03-04)", mm(col_axis_pitch), "mm", CLS_MV, "A-STRC_column_03/04 평면 절단 중심")
    facts.add(sid, "col_inset", "기둥 외면 후퇴(슬래브 단부 기준)", mm(col_face_x - slab_edge_x), "mm", CLS_MV, "기둥 외면 x − 슬래브 단부 x")
    facts.add(sid, "band_h", "밴드 높이", mm(band_h), "mm", CLS_MV, "A-FACD_band 절단 z 범위")
    facts.add(sid, "band_d", "밴드 깊이", mm(band_depth), "mm", CLS_MV, "A-FACD_band 절단 x 범위")
    facts.add(sid, "band_below", "밴드 하단이 슬래브 하면보다 내려간 길이", mm((ffl6 - slab_thk) - band6[1]), "mm", CLS_MV, "슬래브 하면 z − 밴드 하단 z")
    facts.add(sid, "band_above", "밴드 상단이 슬래브 상면보다 올라간 길이", mm(band6[3] - ffl6), "mm", CLS_MV, "밴드 상단 z − 6F FFL")
    facts.add(sid, "ff", "층고 6F→7F", mm(h_ff), "mm", CLS_MV, "A-FLOR_s7 6F/7F 상면 차")
    facts.add(sid, "ov_d", "멀리언-밴드 겹침 깊이", mm(ov[0][0]), "mm", CLS_MV, "멀리언·밴드 단면 교집합 폭, y=22.5")
    facts.add(sid, "ov_h6", "겹침 높이(6F 밴드)", mm(ov[0][1]), "mm", CLS_MV, "교집합 높이")
    facts.add(sid, "ov_h7", "겹침 높이(7F 밴드)", mm(ov[1][1]), "mm", CLS_MV, "교집합 높이")
    facts.add(sid, "n_facd", "A-FACD_* 객체 수", len(fac_objs), "개", CLS_MV, "model_objects.json 이름 접두 A-FACD")
    facts.add(sid, "bays", "기둥 축 간격 ÷ 멀리언 간격", round(col_axis_pitch / pitch, 2), "-", CLS_DR, "9000 / 1800")
    mull_off = abs(np.mean([v for v in mul_y if abs(v - col_c[0]) < 1.0] and [abs(v - col_c[0]) for v in mul_y if abs(v - col_c[0]) < 1.0]))
    facts.add(sid, "mull_off", "멀리언 중심과 기둥 축의 최단 거리", mm(mull_off), "mm", CLS_MV, "멀리언 y − 기둥 축 y (18.0)")
    # ---- layout ----------------------------------------------------------------------------------------------------------
    # column 1: plan
    P = View(0, 0, 0, 0, scale)                       # placeholder to get k
    k = P.k
    px0, py0 = 10.0, 8.0
    pw, ph = (X1 - X0) * k + 14.0, (Y1 - Y0) * k + 8.0
    plan = View(px0 + 5.0 + (0 - X0) * k * 0 + 0, 0, 0, 0, scale)
    plan = View(px0 + 3.0 + 0.0, py0 + 6.5 + (Y1 - Y0) * k, X0, Y0, scale)   # model (X0,Y0) -> sheet (px0+3, bottom of window)
    plan.ox = px0 + 3.0
    plan.oy = py0 + 7.0 + (Y1 - Y0) * k
    panel(sh, "plan_panel", px0, py0, px0 + pw + 8.0, py0 + ph + 4.0 + 5.0, "평면 PLAN 6F +1.5 m · 서측 외벽 1 bay", CLS_MV)
    wx0, wy0, wx1, wy1 = plan.rect(X0, Y0, X1, Y1)
    # floor plate (below cut) and facade cut
    draw_outline(sh, plan, snap(slab_g), "#666", 0.25, "#f1f1f1")
    # band strip below the cut (projection) light
    draw_outline(sh, plan, snap(band_fp), "#999", 0.2, "#dcdcdc")
    for p in parts(cutp["A-FACD_glass"]):
        sh.path(plan.rings(snap(p)), fill="#000", stroke="#000", w=0.15)
    for p in mul_pieces:
        sh.path(plan.rings(snap(p)), fill="#333", stroke="#000", w=0.12)
    for o, g in cols:
        draw_cut(sh, plan, snap(g), "#fff", "#000", 0.45)
    # grid axes of the columns (y = col centres) as 1-dot chain lines + labels
    for yc, lab in ((col_c[0], "03"), (col_c[-1], "04")):
        sh.path([[(plan.X(X0), plan.Y(yc)), (plan.X(X1) - 14.0, plan.Y(yc))]], stroke="#bbb", w=0.15, closed=False, dash="6,1.4,1,1.4")
        dm.bubble(sh, plan.X(X1) - 9.5, plan.Y(yc), lab, r=3.0, pt=6.5)
    # section line A-A
    ys = plan.Y(ysec)
    sh.path([[(plan.X(X0) - 1.0, ys), (plan.X(X1) - 14.0, ys)]], stroke="#c00", w=0.5, closed=False, dash="5,1.2,1,1.2")
    dm.section_tag(sh, plan.X(X0) + 4.0, ys, "A", "D-406", arrow=(0, -1), r=3.0)
    # dimensions: mullion pitch chain (right side of the glass, in clear plan space), column pitch overall
    ysx = [plan.Y(v) for v in mul_y]
    xd = plan.X(-6.6)
    dm.chain_v(sh, ysx, xd, [str(mm(b - a)) for a, b in zip(mul_y, mul_y[1:])], from_x=plan.X(-8.3), pt=6.0, color="#06a", left=False)
    dm.dim_v(sh, plan.Y(col_c[0]), plan.Y(col_c[-1]), plan.X(-5.2), "기둥 축 %d" % mm(col_axis_pitch), from_x=plan.X(-6.6), pt=6.0, color="#06a", left=False)
    # leaders for the three thin things (glass / mullion / band), in the white space left of the facade
    lx = plan.X(X0) + 1.0
    # numbers
    yy_g = plan.Y(Y0 + 1.4)
    sh.text(plan.X(-9.6), plan.Y(Y1 - 0.45), "외부 EXTERIOR", 6.0, "bold", "#555", "middle")
    # callouts 1..5
    cy_ = plan.Y(mul_y[0] + 0.5 * (mul_y[1] - mul_y[0]))
    pts = {1: (plan.X(-9.020), cy_), 2: (plan.X(-9.17), plan.Y(mul_y[1])), 3: (plan.X(-9.145), cy_ - 4.5), 4: (plan.X(-8.4), plan.Y(col_c[0])), 5: (plan.X(-9.0), plan.Y(col_c[0] + 0.45) - 1.0)}
    # (numbers are drawn once the layout of the right panels is known)
    # ---- scale bar + keyplan under the plan -----------------------------------------------------------------------------
    plan_bottom = py0 + ph + 9.0
    sh.scale_bar(px0 + 5.0, plan_bottom + 12.0)
    kp = keyplan(sh, run, px0 + 4.0, plan_bottom + 30.0, 24.0, ((geo.byname["A-FLOR_s7_6F"] and -9.0) or 0, 22.5), ring_mm=2.6)
    sh.claim("keyplan", kp[0], kp[1], kp[2] + 40.0, kp[3] + 1.0)
    sh.text(px0 + 36.0, plan_bottom + 33.5, "참조 CROSS-REF", 6.5, "bold", "#a60")
    for i, t in enumerate(["E-204 서측 입면 (외피 전경)", "P-101 3F 평면 (층판 윤곽)", "S-302 단면 A-A (층 구성)", "A-900 U-04 외피 접합 미결"]):
        sh.text(px0 + 36.0, plan_bottom + 38.0 + 3.8 * i, t, 6.5, "normal", "#a60")
    north(sh, m, px0 + pw + 1.0, py0 + 14.0, 4.2)
    return sh, locals()


def _unused():
    pass

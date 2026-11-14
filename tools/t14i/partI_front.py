"""PART I front pages (Graduation Design Book): G-001 cover, G-002 contents, G-101..G-106 analysis / concept pages.

    python -X utf8 tools/t14i/partI_front.py --run <RUN> [--only G-001,G-101] [--views-only] [--procs 6]
    build(run, out_dir=None) -> [registry rows]      writes <out_dir>/<SID>_<name>.{svg,pdf,png}, partI_front_registry.json, partI_front_facts.json
    build_contents(run, out_base, entries) -> row    G-002 (called again by the assembler once page numbers are known)

Truth classes (tools/t14i/config.py): geometry = MODEL VERIFIED (model cache / slices / A-003), arithmetic = DERIVED ("계산값"),
narrative, route, furniture, colours of the story = CONCEPT PROPOSED.  Nothing on these pages is a construction fact that the model does not hold.
Every image is rendered from the model-cache triangles (tools/t14i/axon.py) and cached under <RUN>/v4/axon_cache/.
"""
import os
import sys

_T = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _T not in sys.path:
    sys.path.insert(0, _T)

import base64  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import re  # noqa: E402
import time  # noqa: E402
import unicodedata  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

import t14i  # noqa: E402,F401
from t14i import common as cm  # noqa: E402
from t14i import config as cfg  # noqa: E402
import t14d_sheet as TS  # noqa: E402

MV, CP, UR = cfg.MODEL_VERIFIED, cfg.CONCEPT_PROPOSED, cfg.UNRESOLVED
DV = "DERIVED"
PART = "partI"
STATUS_MIX = "MODEL VERIFIED + CONCEPT PROPOSED · CANDIDATE - NOT FROZEN"
STATUS_MV = "MODEL VERIFIED · CANDIDATE - NOT FROZEN"
STATUS_DOC = "DOCUMENT · CANDIDATE - NOT FROZEN"
INK, GREY, LIGHT = "#111", "#555", "#999"
NTS_TEXT = "축척 없음 NOT TO SCALE"

# ═════════════════════════════════════════════════════════════════════════════════════════════
# text measurement / layout helpers (so that overflow is a build error, not a visual surprise)
# ═════════════════════════════════════════════════════════════════════════════════════════════
_NARROW = set("ilI.,:;|!'`()[]{}/ -·")


def tw(s, pt, bold=False):
    """Estimated width (mm) of s at pt (Malgun Gothic like: Hangul = 1 em, Latin ~0.55 em)."""
    em = pt * 0.3528
    w = 0.0
    for ch in s:
        ea = unicodedata.east_asian_width(ch)
        if ea in "WF":
            w += 1.0
        elif ch in _NARROW:
            w += 0.34
        elif ch.isupper() or ch.isdigit() or ch in "&%@#":
            w += 0.66
        else:
            w += 0.56
    return w * em * (1.06 if bold else 1.0)


def wrap(s, width, pt, bold=False):
    """Greedy wrap of s into lines no wider than width mm (spaces first, characters if a word is too long)."""
    out = []
    for para in str(s).split("\n"):
        words = para.split(" ")
        cur = ""
        for w in words:
            trial = (cur + " " + w) if cur else w
            if tw(trial, pt, bold) <= width:
                cur = trial
                continue
            if cur:
                out.append(cur)
                cur = ""
            while tw(w, pt, bold) > width:        # a single over-long word: break by characters
                k = len(w)
                while k > 1 and tw(w[:k], pt, bold) > width:
                    k -= 1
                out.append(w[:k])
                w = w[k:]
            cur = w
        out.append(cur)
    return out


class Fit(Exception):
    pass


def para(sh, x, y, s, width, pt=7.0, color="#333", weight="normal", lead=1.42, ymax=None, anchor="start", max_lines=None):
    """Draw wrapped text; returns the y of the next free baseline. Raises Fit when it would pass ymax."""
    lines = wrap(s, width, pt, weight == "bold")
    if max_lines and len(lines) > max_lines:
        raise Fit("paragraph has %d lines, limit %d: %r" % (len(lines), max_lines, s[:40]))
    h = pt * 0.3528 * lead
    for ln in lines:
        if ymax is not None and y > ymax + 1e-6:
            raise Fit("text %r passes y=%.1f > %.1f" % (s[:40], y, ymax))
        sh.text(x if anchor == "start" else (x + width / 2 if anchor == "middle" else x + width), y, ln, pt, weight, color, anchor)
        y += h
    return y


def lh(pt, lead=1.42):
    return pt * 0.3528 * lead


# ═════════════════════════════════════════════════════════════════════════════════════════════
# sheet class: title block with an explicit scale text (NOT TO SCALE for presentation diagrams)
# ═════════════════════════════════════════════════════════════════════════════════════════════
class PSheet(TS.Sheet):
    def __init__(self, sid, title, scale, status, subtitle="", extra_lines=(), paper=(420.0, 297.0), scale_text=None):
        super().__init__(sid, title, scale, status, subtitle, extra_lines, paper)
        self.scale_text = scale_text
        self.sub_claims = []

    def title_block(self):
        W, H = self.paper
        x0, y0, x1, y1 = 10.0, H - 35.0, W - 10.0, H - 10.0
        c1, c2 = W - 120.0, W - 62.0
        self.claim("title_block", x0, y0, x1, y1)
        self.path([[(x0, y0), (x1, y0), (x1, y1), (x0, y1)]], fill="#fff", stroke="#222", w=0.35)
        self.line(c1, y0, c1, y1, 0.2, "#222")
        self.line(c2, y0, c2, y1, 0.2, "#222")
        self.text(x0 + 4, y0 + 7.5, self.sid, 12, "bold", "#111")
        self.text(x0 + 30, y0 + 7.5, self.title, 12, "bold", "#111")
        if self.subtitle:
            self.text(x0 + 30, y0 + 13.5, self.subtitle, 7, "normal", "#444")
        yy = y0 + 19
        for ln in self.extra[:2]:
            self.text(x0 + 30, yy, ln, 6, "normal", "#555")
            yy += 4.2
        pn = "A3" if tuple(self.paper) == TS.A3 else ("A1" if tuple(self.paper) == (841.0, 594.0) else "%gx%g" % tuple(self.paper))
        if self.scale_text:
            st = self.scale_text
        else:
            st = ("축척 1:%d (%s)" % (self.scale, pn)) if self.scale else "축척 — (표·문서, %s)" % pn
        self.text(c1 + 5, y0 + 7, st, 8, "bold", "#222")
        parts = [t.strip() for t in self.status.split(" · ")]
        lines = [parts[0], " · ".join(parts[1:])] if len(parts) > 1 else [parts[0]]
        yy2 = y0 + 12.5
        for i, ln_ in enumerate(lines[:2]):
            self.text(c1 + 5, yy2, ln_, 6.0, "bold" if i == 0 else "normal", "#a33")
            yy2 += 4.0
        self.text(c1 + 5, y0 + 21.5, "도면집 후보 %s · FREEZE 아님" % TS.EDITION, 6.0, "normal", "#555")
        self.text(c2 + 5, y0 + 7, TS.PROJECT_CODE, 8, "bold", "#222")
        self.text(c2 + 5, y0 + 13, ("개정 %s (%s)" % (TS.REVISION, TS.EDITION)) if TS.REVISION else TS.ISSUE_DATE, 6, "normal", "#555")
        if TS.REVISION:
            self.text(c2 + 5, y0 + 18.5, "출력 %s" % TS.ISSUE_DATE, 6, "normal", "#555")

    def sub(self, name, x0, y0, x1, y1, parent):
        """Claim a rectangle that lives inside the claimed panel `parent` (overlap with the parent is allowed)."""
        self.claim(name, x0, y0, x1, y1)
        self.sub_claims.append((parent, name))

    def save2(self, base):
        return self.save(base, allow=tuple(self.sub_claims))


def frame(sh, name, x0, y0, x1, y1, title=None, kind=None, pt=8.0, stroke="#aaa", sub_of=None):
    """Panel frame (claimed), optional bold heading (left) and truth-class badge (right). Returns (cx0, cy0, cx1, cy1) of the content area."""
    if sub_of:
        sh.sub(name, x0, y0, x1, y1, sub_of)
    else:
        sh.claim(name, x0, y0, x1, y1)
    sh.path([[(x0, y0), (x1, y0), (x1, y1), (x0, y1)]], fill="none", stroke=stroke, w=0.2)
    top = y0
    if title:
        sh.text(x0 + 2.5, y0 + 4.8, title, pt, "bold", INK)
        top = y0 + 7.4
    if kind:
        w = tw(kind, 6.0, True) + 3.6
        cm.badge(sh, x1 - w - 2.0, y0 + 1.2, kind, w=w)
    return x0 + 2.5, top, x1 - 2.5, y1 - 1.5


def put_image(sh, name, img, x0, y0, x1, y1, fmt="JPEG", align="c", quality=88, claim=True, parent=None, max_px=None):
    """Embed a PIL image, contain-fit in the rectangle. Returns (px_to_mm_scale, ox_mm, oy_mm, (placed rectangle))."""
    iw, ih = img.size
    s = min((x1 - x0) / iw, (y1 - y0) / ih)
    w, h = iw * s, ih * s
    ox = x0 + ((x1 - x0) - w) / 2 if align in ("c", "t") else (x0 if align == "l" else x1 - w)
    oy = y0 + ((y1 - y0) - h) / 2 if align == "c" else y0
    if max_px and iw > max_px:
        k = max_px / iw
        img = img.resize((max_px, int(round(ih * k))), Image.LANCZOS)
    buf = io.BytesIO()
    if fmt == "JPEG":
        img.convert("RGB").save(buf, "JPEG", quality=quality, optimize=True, subsampling=0)
        mime = "image/jpeg"
    else:
        img.save(buf, "PNG", optimize=True)
        mime = "image/png"
    sh.parts.append('<image x="%.3f" y="%.3f" width="%.3f" height="%.3f" preserveAspectRatio="none" href="data:%s;base64,%s"/>' % (ox, oy, w, h, mime, base64.b64encode(buf.getvalue()).decode()))
    if claim:
        if parent:
            sh.sub(name, ox, oy, ox + w, oy + h, parent)
        else:
            sh.claim(name, ox, oy, ox + w, oy + h)
    return s, ox, oy, (ox, oy, ox + w, oy + h)


def circle_pts(cx, cy, r, n=24):
    return [(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n)) for i in range(n + 1)]


def marker(sh, x, y, label, r=2.3, col="#111", fill="#fff", pt=6.0):
    sh.path([circle_pts(x, y, r)], fill=fill, stroke=col, w=0.3)
    sh.text(x, y + pt * 0.3528 * 0.36, str(label), pt, "bold", col, "middle")


def leader(sh, p, q, col="#444", w=0.18, dash=None):
    sh.line(p[0], p[1], q[0], q[1], w, col, dash)


def swatch(sh, x, y, col, w=5.0, h=3.2, stroke="#555", alpha=None):
    sh.path([[(x, y), (x + w, y), (x + w, y + h), (x, y + h)]], fill=col, stroke=stroke, w=0.15, opacity=alpha)


def arrow_head(sh, x, y, dx, dy, size=1.6, col="#111"):
    n = math.hypot(dx, dy) or 1.0
    ux, uy = dx / n, dy / n
    sh.path([[(x, y), (x - ux * size * 1.8 + uy * size * 0.7, y - uy * size * 1.8 - ux * size * 0.7), (x - ux * size * 1.8 - uy * size * 0.7, y - uy * size * 1.8 + ux * size * 0.7)]], fill=col, stroke=col, w=0.1)


# ═════════════════════════════════════════════════════════════════════════════════════════════
# context object (run folder, model, facts, rows)
# ═════════════════════════════════════════════════════════════════════════════════════════════
class Ctx:
    def __init__(self, run, out_dir=None):
        self.run = os.path.abspath(run)
        self.out = out_dir or cm.v4_dir(self.run, PART)
        os.makedirs(self.out, exist_ok=True)
        self.cache = cm.v4_dir(self.run, "axon_cache")
        self.facts = []
        self.rows = []
        self._model = None
        self.times = {}

    @property
    def model(self):
        if self._model is None:
            self._model = cm.load_model(self.run)
        return self._model

    def fact(self, id_, label, value, unit, cls, source, printed=None):
        self.facts.append({"id": id_, "label": label, "value": value, "unit": unit, "class": cls, "source": source, "printed": printed})

    def path(self, sid, name):
        return os.path.join(self.out, "%s_%s" % (sid, name))

    def finish(self, sh, base, title, scale=None, status_class=None, extra=None):
        sh.save2(base)
        row = cm.sheet_row(sh, base, title, "PRESENTATION", PART, scale, sh.paper, status_class or "MODEL VERIFIED + CONCEPT PROPOSED", extra)
        self.rows.append(row)
        return row


def floors_rel(model):
    """{floor: FFL relative to 1F} (1F = ±0.000)."""
    z1 = model.floors["1F"]
    return {n: z - z1 for n, z in model.floors.items()}


def obj_by_name(model, name):
    for o in model.objects:
        if o["name"] == name:
            return o
    raise KeyError(name)


def objs(model, kind=None, name_re=None, exclude_re=None):
    out = []
    for o in model.objects:
        if kind and o["kind"] not in (kind if isinstance(kind, (list, tuple, set)) else [kind]):
            continue
        if name_re and not re.search(name_re, o["name"]):
            continue
        if exclude_re and re.search(exclude_re, o["name"]):
            continue
        out.append(o)
    return out


def esc_name(n):
    return n.replace("A-VERT-", "").replace("A-CORE-TUBE_", "TUBE ").replace("A-FLOR_", "")


# ═════════════════════════════════════════════════════════════════════════════════════════════
# axonometric render jobs (JSON-able specs -> cached PNG; run in a process pool)
# ═════════════════════════════════════════════════════════════════════════════════════════════
class WModel:
    """Model wrapper: an object may carry '_tris' = synthetic geometry (drawing-frame metres, (n,3,3))."""

    def __init__(self, m):
        self.m = m

    def __getattr__(self, k):
        return getattr(self.m, k)

    def tris(self, o):
        t = o.get("_tris")
        return t if t is not None else self.m.tris(o)


def box_tris(x0, y0, x1, y1, z0, z1):
    p = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    T = []
    for i in range(4):
        a, b = p[i], p[(i + 1) % 4]
        A, B = (a[0], a[1], z0), (b[0], b[1], z0)
        C, D = (b[0], b[1], z1), (a[0], a[1], z1)
        T += [(A, B, C), (A, C, D)]
    T += [((x0, y0, z1), (x1, y0, z1), (x1, y1, z1)), ((x0, y0, z1), (x1, y1, z1), (x0, y1, z1))]
    T += [((x0, y0, z0), (x1, y1, z0), (x1, y0, z0)), ((x0, y0, z0), (x0, y1, z0), (x1, y1, z0))]
    return np.array(T, float)


def prism_tris(poly, z0, z1):
    """Extrude a shapely Polygon (drawing frame) into triangles (top, bottom and side walls)."""
    from shapely import constrained_delaunay_triangles
    from shapely.geometry import Polygon
    out = []
    if poly.is_empty or poly.geom_type != "Polygon" or poly.area < 1e-6:
        return np.zeros((0, 3, 3))
    for t in constrained_delaunay_triangles(poly).geoms:
        c = list(t.exterior.coords)[:3]
        out.append([(x, y, z1) for x, y in c])
        out.append([(c[0][0], c[0][1], z0), (c[2][0], c[2][1], z0), (c[1][0], c[1][1], z0)])
    r = list(poly.exterior.coords)
    for a, b in zip(r, r[1:]):
        if abs(a[0] - b[0]) + abs(a[1] - b[1]) < 1e-9:
            continue
        out.append([(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1)])
        out.append([(a[0], a[1], z0), (b[0], b[1], z1), (a[0], a[1], z1)])
    return np.array(out, float)


FURN_H = {"wall_display": 1.8, "brand_cell": 1.2, "cashier": 1.0, "waiting_bench": 0.45, "popup_kiosk": 2.2, "demo_table": 0.8, "experience_counter": 1.1,
          "banquette": 0.9, "table_": 0.75, "chair": 0.45, "service_counter": 1.1, "bar_counter": 1.1, "communal_table": 0.75,
          "assembly_step": 0.45, "plinth": 0.45, "lounge_sofa": 0.8, "lounge_table": 0.45, "lounge_round_table": 0.45, "lounge_armchair": 0.8, "lounge_bench": 0.45,
          "info_desk": 1.1, "garden_bench": 0.45, "planting_bed": 0.5, "shrub": 0.7, "tree": 3.2, "tree_canopy": 0.4}


def furn_height(typ):
    for k, v in FURN_H.items():
        if typ.startswith(k):
            return v
    return 0.75


def furniture_objs(run, floor, zbase):
    """Synthetic objects from the V3 layout (plans/_raw/raw_plan_<F>_check.json 'furniture_v3'): extruded prisms. CONCEPT PROPOSED (PROPOSED_ONLY)."""
    from shapely import wkt
    c = json.load(open(os.path.join(run, "plans", "_raw", "raw_plan_%s_check.json" % floor), encoding="utf-8"))
    tris, n = [], 0
    for it in c["furniture_v3"]:
        if it["kind"] not in ("body", "counter", "foliage"):
            continue
        g = wkt.loads(it["wkt"])
        h = furn_height(it["type"])
        for p in (list(g.geoms) if hasattr(g, "geoms") else [g]):
            T = prism_tris(p, zbase, zbase + h)
            if len(T):
                tris.append(T)
                n += 1
    return [{"name": "furn_%s" % floor, "kind": "furn", "name_ko": "가구(제안)", "_tris": np.concatenate(tris) if tris else np.zeros((0, 3, 3))}], n


def sel_objs(model, s):
    out = []
    for o in model.objects:
        if "kind" in s and o["kind"] not in s["kind"]:
            continue
        if "name_re" in s and not re.search(s["name_re"], o["name"]):
            continue
        if "not_re" in s and re.search(s["not_re"], o["name"]):
            continue
        if "zfloors" in s:
            m = re.match(r"A-PROG_([^_]+)_", o["name"])
            if not m or m.group(1) not in s["zfloors"]:
                continue
        if "programs" in s and o.get("name_ko") not in s["programs"]:
            continue
        out.append(o)
    return out


def build_groups(model, spec, run):
    from t14i import axon as ax
    ex = spec.get("explode")
    bands = ax.floor_bands(model, ex["gap"], ex.get("lo", "B2"), ex.get("hi", "15F"), ex.get("top_extra", 7.0)) if ex else None
    groups = []
    for L in spec["layers"]:
        syn = L.get("synthetic")
        if syn == "box":
            os_ = [{"name": "box", "kind": "box", "_tris": box_tris(*L["box"])}]
        elif syn == "furniture":
            os_, _n = furniture_objs(run, L["floor"], L["zbase"])
        else:
            os_ = sel_objs(model, L["sel"])
        parts = [(os_, L.get("color"))]
        if L.get("program_colors"):
            parts = []
            for prog, col in ax.PROGRAM_COLORS.items():
                sub = [o for o in os_ if o.get("name_ko") == prog]
                if sub:
                    parts.append((sub, col))
        for sub, col in parts:
            if not sub:
                continue
            g = dict(objs=sub, color=col, alpha=L.get("alpha", 1.0), edge=L.get("edge", True))
            if L.get("explode") and bands:
                g["bands"] = bands
            for k in ("z0", "z1", "dz"):
                if k in L:
                    g[k] = L[k]
            c = L.get("clip") or spec.get("clip")
            if c:
                g["clip"] = ax.cut_quadrant(c[1], c[2]) if c[0] == "quad" else ax.cut_halfspace(c[1], c[2], c[3])
            groups.append(g)
    return groups


def box_extent(model, az, el, z0, z1, pad=0.6):
    from t14i import axon as ax
    b = model.building
    pts = [(x, y, z) for x in (b["xmin"] - pad, b["xmax"] + pad) for y in (b["ymin"] - pad, b["ymax"] + pad) for z in (z0, z1)]
    u, v, _ = ax.Proj(az, el, 1.0, 0, 0).uvd(np.array(pts))
    return (float(u.min()), float(u.max()), float(v.min()), float(v.max()))


def spec_key(key, spec):
    import hashlib
    return "%s_%s" % (key, hashlib.sha1(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:8])


def view_path(cache, key, spec):
    return os.path.join(cache, spec_key(key, spec) + ".png")


def run_view(args):
    run, key, spec = args
    from t14i import axon as ax
    t0 = time.time()
    cache = cm.v4_dir(run, "axon_cache")
    p = view_path(cache, key, spec)
    if os.path.exists(p) and os.path.exists(p + ".json"):
        return key, p, 0.0
    m = WModel(cm.load_model(run))
    groups = build_groups(m, spec, run)
    kw = dict(az=spec["az"], el=spec["el"], width_px=spec["width_px"], pad_px=spec.get("pad_px", 30))
    if spec.get("extent_z"):
        kw["extent_m"] = box_extent(m, spec["az"], spec["el"], *spec["extent_z"])
    ax.render_cached(p, m, groups, **kw)
    return key, p, time.time() - t0


# colour palette of the book (one place)
C_SLAB, C_ROOF, C_COL, C_CORE = "#d8d1c4", "#c9c9c9", "#6e6e6e", "#5f5f5f"
C_TUBE, C_TUBE2, C_SHAFT, C_CAR = "#6fb0d2", "#a9c9d8", "#9c8fd0", "#5b4fa8"
C_ESC, C_SPR, C_FAC = "#e08a2e", "#d1562a", "#aecfdc"
L_SLAB = {"sel": {"kind": ["slab"]}, "color": C_SLAB}
L_ROOF = {"sel": {"kind": ["roof"]}, "color": C_ROOF}
L_COLS = {"sel": {"kind": ["column"]}, "color": C_COL}
L_CORES = {"sel": {"kind": ["core_wall"]}, "color": C_CORE}
L_TUBES = {"sel": {"kind": ["tube_wall"], "name_re": r"TUBE_(T[1-4]|cap[WE])$"}, "color": C_TUBE, "alpha": 0.35}
L_TUBE_MIN = {"sel": {"kind": ["tube_wall"], "name_re": r"TUBE_(FR|M1|M2|PL)$"}, "color": C_TUBE2, "alpha": 0.35}
L_SHAFTS = {"sel": {"kind": ["shaft"], "name_re": r"TUBE_EV"}, "color": C_SHAFT, "alpha": 0.4}
L_CARS = {"sel": {"kind": ["shaft"], "name_re": r"ELEV_car"}, "color": C_CAR}
L_ESC = {"sel": {"kind": ["stair"]}, "color": C_ESC}
L_SPR = {"sel": {"kind": ["ramp"]}, "color": C_SPR}
L_FAC = {"sel": {"kind": ["facade"]}, "color": C_FAC, "alpha": 0.22, "edge": False}
L_ZONES = {"sel": {"kind": ["zone"]}, "program_colors": True, "alpha": 0.55, "edge": False}
FLOORS_FLOOR_VIEWS = ("3F", "10F", "13F", "15F")
AZ_OUT, AZ_IN, EL = 40.0, 220.0, 28.0          # AZ_OUT: seen from the (-x,-y) corner; AZ_IN: from the (+x,+y) corner (axon.cut_quadrant opens that corner)


def ex(layer, **kw):
    d = dict(layer)
    d["explode"] = True
    d.update(kw)
    return d


def view_specs(run, model):
    fr = floors_rel(model)
    b = model.building
    cx, cy = (b["xmin"] + b["xmax"]) / 2, (b["ymin"] + b["ymax"]) / 2
    ZB0, ZB1 = -11.5, 77.0
    S = {}
    # cover hero: exploded, no program colour
    S["hero"] = dict(az=AZ_OUT, el=26.0, width_px=1700, explode={"gap": 8.0}, layers=[ex(L_SLAB), ex(L_ROOF), ex(L_COLS), ex(L_CORES), ex(L_TUBES), ex(L_SHAFTS), ex(L_ESC), ex(L_SPR)])
    # G-102 mass formation steps (non exploded, same framing)
    base = dict(az=AZ_OUT, el=EL, width_px=1000, extent_z=(ZB0, ZB1), pad_px=24)
    box = {"synthetic": "box", "box": [b["xmin"], b["ymin"], b["xmax"], b["ymax"], model.floors["B2"] - 0.5, 76.5], "color": "#cfd6dc", "alpha": 0.85, "edge": True}
    slabs = [L_SLAB, L_ROOF]
    S["step1"] = dict(base, layers=[box])
    S["step2"] = dict(base, layers=slabs)
    S["step3"] = dict(base, layers=slabs + [L_COLS])
    S["step4"] = dict(base, layers=slabs + [L_COLS, L_TUBES, L_TUBE_MIN])
    S["step5"] = dict(base, layers=slabs + [L_COLS, L_TUBES, L_TUBE_MIN, L_CORES])
    S["step6"] = dict(base, layers=slabs + [L_COLS, L_TUBES, L_TUBE_MIN, L_CORES, L_SHAFTS, L_CARS, L_ESC, L_SPR])
    S["step7"] = dict(base, layers=slabs + [L_COLS, L_TUBES, L_TUBE_MIN, L_CORES, L_SHAFTS, L_CARS, L_ESC, L_SPR, L_FAC])
    S["step8"] = dict(base, layers=slabs + [L_CORES, L_TUBES, L_ESC, L_SPR, L_ZONES])
    # G-103 program colours, exploded
    S["prog"] = dict(az=AZ_OUT, el=26.0, width_px=1500, explode={"gap": 8.0}, layers=[ex(L_SLAB), ex(L_ROOF), ex(L_ZONES), ex(L_CORES), ex(L_TUBES), ex(L_ESC), ex(L_SPR)])
    # G-104 vertical system
    cut = ["quad", cx, cy]
    S["vcut"] = dict(az=AZ_IN, el=EL, width_px=1500, extent_z=(ZB0, ZB1), clip=cut,
                     layers=[dict(L_SLAB, color="#e7e2d8"), L_CORES, L_TUBES, L_TUBE_MIN, L_SHAFTS, L_CARS, L_ESC, L_SPR])
    S["vglass"] = dict(az=AZ_OUT, el=22.0, width_px=1500, extent_z=(ZB0, ZB1),
                       layers=[dict(L_SLAB, color="#b9b3a6", alpha=0.10, edge=True), dict(L_CORES, alpha=0.5), L_TUBES, L_TUBE_MIN, L_SHAFTS, L_CARS, L_ESC, L_SPR])
    # G-105 floor experiences
    for F in FLOORS_FLOOR_VIEWS:
        fz = model.floors[F]
        nxt = sorted(model.floors.values())
        top = min([z for z in nxt if z > fz + 1.0] or [fz + 4.5]) - 0.55
        z0, z1 = fz - 0.55, min(top, fz + 4.9)
        band = {"z0": z0, "z1": z1}
        S["floor_" + F] = dict(az=AZ_OUT, el=34.0, width_px=1300, extent_z=(z0 - 0.3, z1 + 0.5), pad_px=24, layers=[
            dict(L_SLAB, **band), dict(L_COLS, **band), dict(L_CORES, **band), dict(L_TUBES, **band), dict(L_SHAFTS, **band), dict(L_ESC, **band), dict(L_SPR, **band),
            {"sel": {"kind": ["zone"], "zfloors": [F]}, "program_colors": True, "alpha": 0.5, "edge": False, "z0": fz, "z1": fz + 0.3},
            {"synthetic": "furniture", "floor": F, "zbase": fz, "color": "#8d7f6e", "edge": True}])
    # G-106 walking sequence: exploded, near corner cut away
    S["route"] = dict(az=AZ_IN, el=26.0, width_px=1700, explode={"gap": 6.0}, clip=cut,
                      layers=[ex(dict(L_SLAB, color="#e3ddd0")), ex(L_ROOF), ex(L_CORES), ex(L_TUBES), ex(L_ESC), ex(L_SPR), ex(L_SHAFTS)])
    return S


def ensure_views(run, keys=None, procs=6, model=None):
    """Render (and cache) the axon views in a process pool. Returns ({key: (path, spec)}, {key: seconds})."""
    m = model or cm.load_model(run)
    specs = view_specs(run, m)
    keys = keys or list(specs)
    jobs = [(run, k, specs[k]) for k in keys]
    cache = cm.v4_dir(run, "axon_cache")
    todo = [j for j in jobs if not os.path.exists(view_path(cache, j[1], j[2]) + ".json")]
    secs = {}
    if todo:
        import multiprocessing as mp
        ctx = mp.get_context("spawn")
        with ctx.Pool(min(procs, len(todo))) as pool:
            for k, p, s in pool.imap_unordered(run_view, todo):
                secs[k] = s
                print("  rendered %-12s %.1fs %s" % (k, s, p), flush=True)
    out = {k: (view_path(cache, k, specs[k]), specs[k]) for k in keys}
    return out, secs


def load_view(path):
    from t14i import axon as ax
    d = json.load(open(path + ".json"))
    return Image.open(path).convert("RGB"), ax.Proj(d["az_deg"], d["el_deg"], d["s"], d["ox"], d["oy"])


def north_on_axon(proj, model):
    """On-screen angle (deg clockwise from sheet-up) of true north for an axon projection (north = +y world; drawing frame rotated by theta)."""
    nd = math.radians(model.north_deg)
    u, v, _ = proj.uvd(np.array([[math.sin(nd), math.cos(nd), 0.0]]))
    return math.degrees(math.atan2(u[0], v[0]))


# ═════════════════════════════════════════════════════════════════════════════════════════════
# Part I sheet builders
# ═════════════════════════════════════════════════════════════════════════════════════════════
def _view(ctx, key):
    specs = view_specs(ctx.run, ctx.model)
    p = view_path(ctx.cache, key, specs[key])
    if not os.path.exists(p):
        ensure_views(ctx.run, [key], procs=1, model=ctx.model)
    return Image.open(p).convert("RGB")


def _img(path):
    return Image.open(path).convert("RGB")


def _pdf_image(path, dpi=120):
    import pymupdf
    d = pymupdf.open(path)
    pm = d[0].get_pixmap(dpi=dpi, alpha=False)
    return Image.frombytes("RGB", (pm.width, pm.height), pm.samples)


def _pdf_crop_image(path, crop_mm, dpi=300):
    """Rasterize an editorial crop from a source PDF without changing the source.

    ``crop_mm`` is expressed in the source sheet's physical millimetres.  All
    Part-I re-edits use this helper so technical title blocks and long legends
    are not repeatedly miniaturised into presentation pages.
    """
    import pymupdf
    d = pymupdf.open(path)
    k = 72.0 / 25.4
    clip = pymupdf.Rect(*(float(v) * k for v in crop_mm))
    if not d[0].rect.contains(clip):
        raise ValueError("crop outside page: %s %s" % (path, crop_mm))
    pm = d[0].get_pixmap(dpi=dpi, alpha=False, clip=clip)
    return Image.frombytes("RGB", (pm.width, pm.height), pm.samples)


def _sheet(sid, title, status=STATUS_MIX, subtitle=""):
    return PSheet(sid, title, None, status, subtitle=subtitle, scale_text=NTS_TEXT)


def _image_frame(sh, name, img, box, title, kind=MV, parent=None, quality=88, max_px=1800):
    x0, y0, x1, y1 = box
    frame(sh, name, x0, y0, x1, y1, title, kind, sub_of=parent)
    return put_image(sh, name + "_image", img, x0 + 2, y0 + 8, x1 - 2, y1 - 2,
                     quality=quality, parent=name, max_px=max_px)


def _finish(ctx, sh, name, title, classes=(MV, CP)):
    sh.title_block()
    return ctx.finish(sh, ctx.path(sh.sid, name), title, status_class=" + ".join(classes),
                      extra={"classes": list(classes), "part": "I", "kind": "presentation"})


def build_cover(ctx):
    sh = _sheet("G-001", "졸업 설계 도면집 표지", STATUS_MIX,
                "다층 상업시설의 수직 보행·튜브·프로그램 적층 — 후보 %s" % cfg.EDITION)
    hero = _view(ctx, "hero")
    put_image(sh, "hero", hero, 18, 22, 402, 226, quality=91, max_px=1900)
    sh.path([[(18, 18), (244, 18), (244, 72), (18, 72)]], fill="#ffffff", stroke="none", w=0, opacity=0.92)
    sh.text(25, 34, "VERTICAL MARKET", 25, "bold", INK)
    sh.text(25, 48, "도시 안에서 층을 걷는 다층 상업시설", 13, "bold", "#333")
    sh.text(25, 59, "GRADUATION DESIGN BOOK · CANDIDATE %s" % cfg.EDITION, 8, "normal", GREY)
    cm.badge(sh, 25, 65, MV, w=42, h=5.5, pt=6)
    sh.text(72, 69.4, "3D = model_world.npz 캐시 실제 메시", 6.5, "normal", "#333")
    sh.text(20, 240, "원본 GLB 없음 · 캐시 기반 검증 가능 범위만 표현 · 제안 서술은 CONCEPT PROPOSED", 7, "normal", "#444")
    return _finish(ctx, sh, "cover", "졸업 설계 도면집 표지")


def build_overview(ctx):
    sh = _sheet("G-101", "프로젝트 개요와 문제의식", STATUS_MIX, "수직 이동을 공간 경험으로 전환하는 설계 질문")
    _image_frame(sh, "hero_overview", _view(ctx, "hero"), (12, 10, 254, 252), "실제 모델 축투상", MV)
    x = 266
    sh.text(x, 20, "DESIGN THESIS", 12, "bold", INK)
    facts = [("문제", "엘리베이터 중심의 단절된 층 이동은 상업 프로그램 사이의 보행 경험을 짧게 만든다.", CP),
             ("전략", "램프·튜브·에스컬레이터를 층판의 개구와 함께 드러내어 이동 자체를 공간의 중심으로 조직한다.", CP),
             ("검증 범위", "층판·기둥·튜브·코어·수직 장치는 model_world.npz 캐시 형상에서 확인한다.", MV),
             ("보류", "운영·피난·재료·외피 접합은 기술 부록의 UNRESOLVED 항목으로 남긴다.", UR)]
    y = 35
    for label, value, cls in facts:
        cm.badge(sh, x, y, cls, w=37, h=5, pt=6)
        sh.text(x, y + 10, label, 8, "bold", INK)
        y = para(sh, x, y + 17, value, 138, 7, "#333", ymax=238) + 7
    sh.text(x, 218, "DESIGN QUESTION", 9, "bold", INK)
    para(sh, x, 230, "도시의 수평 보행을 건물 안에서 ‘걷고 머무르는 수직 경험’으로 어떻게 연속시킬 것인가?", 138, 8, "#333", "bold", ymax=250)
    return _finish(ctx, sh, "overview", "프로젝트 개요와 문제의식")


def build_context(ctx):
    sh = _sheet("G-102", "대지·도시 맥락과 접근", STATUS_MIX, "A-003에서 확인되는 도시 보행의 건물 진입 방식")
    site_path = os.path.join(ctx.run, "plans", "A-003_site_plan_1F_1to400.pdf")
    site = _pdf_crop_image(site_path, (0, 0, 324, 282), 260)
    _image_frame(sh, "site", site, (12, 10, 286, 252), "A-003 도시 맥락·대지 영역 발췌 · NTS", MV, max_px=3000)
    x = 298
    sh.text(x, 18, "URBAN READING", 11, "bold", INK)
    items = [(MV, "A-003에서 도로·보도·대지 경계·조경·1층 건물 형상을 확인한다."),
             (CP, "도로에서 외부공간과 1층 홀을 지나 수직 동선으로 전환되는 접근 시퀀스를 설계 해석으로 읽는다."),
             (UR, "검증된 실제 지명·좌표·법정 경계·도로 단면 자료가 없어 임의 표기하지 않는다."),
             (MV, "정확한 원본 참조: A-003 · 지하층 P-106/107 · 단면 키플랜 S-301." )]
    y = 34
    for cls, text in items:
        cm.badge(sh, x, y, cls, w=39, h=5, pt=6)
        y = para(sh, x, y + 10, text, 108, 7, "#333", ymax=246) + 7
    return _finish(ctx, sh, "context", "대지·도시 맥락과 접근")


def build_mass(ctx):
    sh = _sheet("G-103", "설계 개념과 매스 형성", STATUS_MIX, "같은 모델 프레임에서 구성 요소를 순차적으로 드러낸 분석")
    labels = ["01 도시 블록", "02 층판 적층", "03 구조 프레임", "04 튜브 삽입", "05 코어 조직", "06 수직 이동", "07 외피", "08 프로그램"]
    for i in range(8):
        c, r = i % 4, i // 4
        x0, y0 = 12 + c * 101, 10 + r * 116
        _image_frame(sh, "step%d" % (i + 1), _view(ctx, "step%d" % (i + 1)), (x0, y0, x0 + 94, y0 + 104), labels[i], MV)
    sh.text(14, 244, "형성 순서는 설계 해석(CONCEPT PROPOSED), 각 단계의 형상은 model_world.npz 실제 메시(MODEL VERIFIED).", 7, "normal", "#444")
    return _finish(ctx, sh, "mass", "설계 개념과 매스 형성")


def build_vertical(ctx):
    sh = _sheet("G-104", "수직 보행·튜브·램프 구조", STATUS_MIX, "층판을 관통하는 이동 장치를 전체 높이에서 읽기")
    _image_frame(sh, "vcut", _view(ctx, "vcut"), (12, 10, 214, 214), "절개 축투상 — 층판·코어·튜브·수직 이동", MV)
    _image_frame(sh, "vglass", _view(ctx, "vglass"), (220, 10, 408, 214), "투명 외곽 검토 — 시스템 중첩", MV)
    cols = [("T1", "나선 램프", "보행 연속성", "D-401"), ("T2", "빛 튜브", "채광 원리", "D-402"),
            ("T3/T4", "파노라마 승강기", "수직 조망", "D-403"), ("ESCL", "에스컬레이터", "층간 가시성", "D-407")]
    for i, row in enumerate(cols):
        x = 14 + i * 99
        sh.text(x, 226, row[0], 9, "bold", INK)
        sh.text(x, 234, row[1], 7.5, "bold", "#333")
        sh.text(x, 241, row[2] + " · " + row[3], 6.5, "normal", GREY)
    return _finish(ctx, sh, "vertical", "수직 보행·튜브·램프 구조")


def build_program(ctx):
    from t14i.axon import PROGRAM_COLORS
    sh = _sheet("G-105", "층별 프로그램 다이어그램", STATUS_MIX, "프로그램 볼륨 투영과 층판을 구분한 전체 적층")
    _image_frame(sh, "program", _view(ctx, "prog"), (12, 10, 300, 252), "프로그램 적층 축투상", MV)
    x, y = 312, 24
    sh.text(x, 18, "PROGRAM LEGEND", 10, "bold", INK)
    for name, col in PROGRAM_COLORS.items():
        swatch(sh, x, y - 3, col, 7, 4)
        sh.text(x + 12, y, name, 7, "normal", "#333")
        y += 11
    cm.badge(sh, x, 180, MV, w=40, h=5, pt=6)
    para(sh, x, 192, "형상·층 위치는 캐시 객체 A-PROG_*에서 직접 렌더링.", 94, 7, "#333")
    cm.badge(sh, x, 214, UR, w=40, h=5, pt=6)
    para(sh, x, 226, "프로그램 투영 면적은 순사용면적·층판면적과 동일하지 않음. A-903 참조.", 94, 7, "#333")
    return _finish(ctx, sh, "program", "층별 프로그램 다이어그램")


def build_plans(ctx):
    sh = _sheet("G-106", "대표층 평면도", STATUS_MIX, "주요 도면 3F + 보조 도면 13F · 기술 제목란과 장문 범례 제외")
    crop = (20, 128, 329, 432)
    p3 = _pdf_crop_image(os.path.join(ctx.run, "v4", "plans", "P-201_plan_3F_A1_1to200.pdf"), crop, 320)
    p13 = _pdf_crop_image(os.path.join(ctx.run, "v4", "plans", "P-202_plan_13F_A1_1to200.pdf"), crop, 320)
    _image_frame(sh, "plan3", p3, (12, 10, 278, 238), "3F 시장층 · P-201 도면 영역 발췌 · NTS", MV, quality=94, max_px=3300)
    _image_frame(sh, "plan13", p13, (284, 10, 408, 132), "13F 문화·엔터층 · P-202 · NTS", MV, quality=94, max_px=2200)
    frame(sh, "plan_note", 284, 138, 408, 238, "평면 독해", CP)
    para(sh, 290, 156, "3F는 시장 프로그램과 원형 수직 장치의 관계를 주도면으로 확대했다. 13F는 같은 구조 프레임 안에서 문화·엔터 프로그램으로 전환되는 비교층이다.", 112, 7, "#333", ymax=208)
    sh.text(290, 220, "정확한 축척·치수: P-201 / P-202 / A-905", 6.5, "bold", "#555")
    sh.text(14, 248, "재편집 도면 NTS · 원본 A1 1:200의 기하·축선·치수는 변경하지 않음", 7, "normal", "#444")
    return _finish(ctx, sh, "representative_plans", "대표층 평면도")


def build_scenario(ctx):
    sh = _sheet("G-107", "공간 사용 시나리오", STATUS_MIX, "도시 진입에서 상층 체류까지의 한 가지 읽기 — 채택 전 제안")
    img = _view(ctx, "route")
    _image_frame(sh, "route", img, (12, 10, 296, 252), "절개·분해 축투상", MV)
    steps = [("01", "도시에서 1F 홀로 진입"), ("02", "T1 램프와 에스컬레이터로 프로그램을 연속 경험"),
             ("03", "T3/T4 승강기에서 도시 방향과 층간 관계를 인지"), ("04", "상층 문화·F&B·정원에서 체류 후 다른 수직 경로로 복귀")]
    y = 24
    for n, text in steps:
        marker(sh, 314, y, n, r=4, col="#b5600a", pt=6)
        y = para(sh, 324, y + 2, text, 80, 7.2, "#333", "bold", ymax=232) + 16
    cm.badge(sh, 310, 224, CP, w=42, h=5, pt=6)
    sh.text(310, 238, "동선은 설계 의도 표현이며\n운영·피난 확정안이 아니다.", 6.5, "normal", "#555")
    sh.text(310, 252, "운영·하역 동선 검토 D-409", 6.5, "bold", "#a32020")
    return _finish(ctx, sh, "scenario", "공간 사용 시나리오")


def build_elevations(ctx):
    sh = _sheet("G-108", "주요 입면도", STATUS_MV, "북측 입면을 중심으로 외피·튜브·층판의 수직 질서를 읽기")
    ecrop = (40, 8, 285, 257)
    e201 = _pdf_crop_image(os.path.join(ctx.run, "elevations", "E-201_north_elevation.pdf"), ecrop, 320)
    e202 = _pdf_crop_image(os.path.join(ctx.run, "elevations", "E-202_east_elevation.pdf"), ecrop, 280)
    _image_frame(sh, "elev_E201", e201, (12, 10, 286, 238), "주요 도면 · E-201 북측 입면 발췌 · NTS", MV, quality=94, max_px=3200)
    _image_frame(sh, "elev_E202", e202, (292, 10, 408, 126), "보조 · E-202 동측 · NTS", MV, quality=93, max_px=2000)
    frame(sh, "elevation_note", 292, 132, 408, 238, "입면 설계 의도", MV)
    para(sh, 298, 150, "북측 입면은 반복 층판과 수직 튜브가 외피 뒤에서 드러나는 관계를 가장 명확히 보여준다. 동측 입면은 같은 높이 체계의 측면 깊이를 보조한다.", 104, 7, "#333", ymax=210)
    sh.text(298, 224, "전체 4면·레벨: E-201~E-204", 6.5, "bold", "#555")
    sh.text(14, 248, "재편집 도면 NTS · 원본 1:400 도면의 레벨·치수·축척은 기술 부록 참조", 7, "normal", "#444")
    return _finish(ctx, sh, "elevations", "주요 입면도", (MV,))


def build_sections(ctx):
    sh = _sheet("G-109", "주요 단면도", STATUS_MV, "B-B 단면을 중심으로 층판 개구와 수직 이동의 공간 관계를 읽기")
    scrop = (35, 8, 260, 257)
    s303 = _pdf_crop_image(os.path.join(ctx.run, "sections", "S-303_section_B-B.pdf"), scrop, 320)
    s302 = _pdf_crop_image(os.path.join(ctx.run, "sections", "S-302_section_A-A.pdf"), scrop, 280)
    _image_frame(sh, "section_S303", s303, (12, 10, 286, 238), "주요 도면 · S-303 B-B 실제 메시 절단 · NTS", MV, quality=94, max_px=3200)
    _image_frame(sh, "section_S302", s302, (292, 10, 408, 126), "보조 · S-302 A-A · NTS", MV, quality=93, max_px=2000)
    frame(sh, "section_note", 292, 132, 408, 238, "수직 관계", MV)
    para(sh, 298, 150, "B-B는 중앙의 큰 개구와 상·하부 층판 적층이 만나는 단면이다. 검은 절단면은 모델 메시의 실제 절단이며, 보행·피난 확정 경로를 뜻하지 않는다.", 104, 7, "#333", ymax=212)
    sh.text(298, 224, "절단 위치 S-301 · 전체 S-302~305", 6.5, "bold", "#555")
    sh.text(14, 248, "재편집 도면 NTS · 원본 1:400의 레벨·치수는 기술 부록 참조", 7, "normal", "#444")
    return _finish(ctx, sh, "sections", "주요 단면도", (MV,))


def build_axon(ctx):
    sh = _sheet("G-110", "실제 모델 기반 3D 축투상", STATUS_MV, "모델 캐시의 메시 그룹을 편집적 색상으로 구분")
    _image_frame(sh, "axon_main", _view(ctx, "hero"), (12, 10, 408, 238), "전체 분해 축투상", MV)
    sh.text(14, 247, "형상 = model_world.npz MODEL VERIFIED · 색상/분해 간격 = 편집 표현 · 원본 GLB = BLOCKED_MISSING_SOURCE", 7, "bold", "#333")
    return _finish(ctx, sh, "axon", "실제 모델 기반 3D 축투상", (MV, UR))


def build_details(ctx):
    sh = _sheet("G-111", "대표 상세와 설계 의도", STATUS_MIX, "D-401 나선 램프의 평면·수직 관계를 중심으로 확대")
    d401 = os.path.join(ctx.run, "v4", "details", "D-401_detail_v4.pdf")
    plan = _pdf_crop_image(d401, (10, 10, 202, 230), 320)
    section = _pdf_crop_image(d401, (205, 10, 408, 230), 320)
    d404 = _pdf_crop_image(os.path.join(ctx.run, "v4", "details", "D-404_detail_v4.pdf"), (10, 10, 202, 230), 260)
    _image_frame(sh, "detail_D401_plan", plan, (12, 10, 166, 238), "D-401 / T1 램프 평면 · NTS", MV, quality=94, max_px=2500)
    _image_frame(sh, "detail_D401_section", section, (172, 10, 326, 238), "D-401 / 레벨·경사 관계 · NTS", MV, quality=94, max_px=2500)
    _image_frame(sh, "detail_D404", d404, (332, 10, 408, 104), "보조 D-404 코어 · NTS", MV, quality=92, max_px=1400)
    frame(sh, "detail_note", 332, 110, 408, 238, "설계 의도와 근거", CP)
    para(sh, 338, 128, "T1은 원형 평면과 층간 레벨을 연결하는 연속 보행 장치다. 램프 외곽·레벨은 모델 근거, 동선 해석은 설계 제안으로 구분한다.", 64, 6.5, "#333", ymax=190)
    cm.badge(sh, 338, 200, MV, w=40, h=5, pt=6)
    cm.badge(sh, 338, 210, CP, w=44, h=5, pt=6)
    sh.text(338, 228, "전체 상세 D-401~410", 6.2, "bold", "#555")
    sh.text(14, 248, "재편집 도면 NTS · 상세 축척·계산·미확정 항목은 기술 부록 원본 참조", 7, "normal", "#444")
    return _finish(ctx, sh, "details", "대표 상세와 설계 의도")


def build_floor_experience(ctx):
    sh = _sheet("G-112", "층별 프로그램과 공간 경험", STATUS_MIX, "대표층 4개를 동일 시점에서 비교")
    captions = {"3F": "시장 — 교환과 통과", "10F": "F&B — 체류와 조망", "13F": "문화·엔터 — 집합", "15F": "상층 정원·F&B — 완결"}
    for i, fl in enumerate(FLOORS_FLOOR_VIEWS):
        c, r = i % 2, i // 2
        x0, y0 = 12 + c * 198, 10 + r * 116
        _image_frame(sh, "floor_" + fl, _view(ctx, "floor_" + fl), (x0, y0, x0 + 192, y0 + 106), fl + "  " + captions[fl], MV)
    cm.badge(sh, 14, 242, MV, w=40, h=5, pt=6)
    sh.text(58, 246, "층판·기둥·튜브·프로그램 볼륨", 6.5, "normal", "#444")
    cm.badge(sh, 192, 242, CP, w=44, h=5, pt=6)
    sh.text(240, 246, "가구·색상·사용 장면", 6.5, "normal", "#444")
    return _finish(ctx, sh, "floor_experience", "층별 프로그램과 공간 경험")


def build_summary(ctx):
    sh = _sheet("G-113", "설계 요약·기술 부록 참조", STATUS_MIX, "후보 %s의 성취와 미확정 사항을 함께 제시" % cfg.EDITION)
    sh.text(14, 20, "DESIGN SUMMARY", 13, "bold", INK)
    summaries = [("01", "수직 이동을 독립 설비가 아니라 프로그램을 잇는 공간 장치로 드러낸다."),
                 ("02", "층판·튜브·코어·외피를 실제 모델 형상으로 통합해 도면 간 참조를 만든다."),
                 ("03", "모델에 없는 벽·문·재료·피난·배수는 완성 사실처럼 그리지 않는다."),
                 ("04", "A1/A3 출력 축척과 면적 정의를 기술 부록에서 별도로 검증한다.")]
    y = 34
    for n, t in summaries:
        marker(sh, 20, y, n, r=3.4, col="#0a6b3d")
        y = para(sh, 30, y + 2, t, 170, 8, "#333", "bold", ymax=132) + 10
    sh.text(218, 20, "TECHNICAL APPENDIX MAP", 11, "bold", INK)
    refs = [("평면", "P-101~112 · P-201/202 · P-211~214"), ("입면", "E-201~204"), ("단면", "S-301~305"),
            ("상세", "D-401~410"), ("검증", "A-903 면적 · A-905 축척 · A-906 QA · A-907 출처"), ("미확정", "A-900")]
    yy = 36
    for a, b in refs:
        sh.text(220, yy, a, 8, "bold", "#222")
        sh.text(267, yy, b, 7, "normal", "#333")
        sh.line(220, yy + 3, 405, yy + 3, 0.08, "#ccc")
        yy += 16
    frame(sh, "decision", 14, 154, 406, 250, "OPEN DESIGN DECISIONS", UR)
    decisions = ["상층 구획벽·문·피난 경로", "코어 내부 계단·부속실", "선큰 계단 승인 치수", "외피 접합·재료·단열",
                 "화물 승강기 장비·운영", "지붕 개방/폐쇄·방수·배수", "프로그램 면적을 순사용면적으로 해석할지", "원본 GLB 재검증"]
    for i, t in enumerate(decisions):
        c, r = i % 2, i // 2
        x, y0 = 22 + c * 190, 174 + r * 17
        sh.text(x, y0, "U-%02d" % (i + 1), 7, "bold", COL_UR if False else "#a32020")
        sh.text(x + 24, y0, t, 7, "normal", "#333")
    return _finish(ctx, sh, "summary", "설계 요약·기술 부록 참조")


def build_contents(run, out_base, entries):
    sh = _sheet("G-002", "PROJECT INFORMATION / 건축개요 및 배치계획", STATUS_DOC,
                "전체 도면 목록은 기술 부록 A-001 참조")
    panels = {
        "context": (12.0, 12.0, 206.0, 126.0),
        "site": (214.0, 12.0, 408.0, 126.0),
        "overview": (12.0, 134.0, 206.0, 248.0),
        "area": (214.0, 134.0, 408.0, 248.0),
    }
    site_pdf = os.path.join(run, "plans", "A-003_site_plan_1F_1to400.pdf")
    context_img = _pdf_crop_image(site_pdf, (0, 0, 324, 175), 320)
    site_img = _pdf_crop_image(site_pdf, (8, 42, 316, 287), 320)
    frame(sh, "panel_context", *panels["context"], "01  LOCATION / 위치도", MV)
    put_image(sh, "context_crop", context_img, 16, 22, 202, 110, quality=94, parent="panel_context", max_px=3000)
    sh.text(16, 119, "A-003 확인 주변 맥락 · 실제 지명·좌표 미확정 · NTS", 6.2, "normal", "#555")
    frame(sh, "panel_site", *panels["site"], "02  SITE PLAN / 배치도", MV)
    put_image(sh, "site_crop", site_img, 218, 22, 404, 110, quality=94, parent="panel_site", max_px=3000)
    sh.text(218, 119, "대지경계·도로·조경·외부동선·건물 발췌 · A-003 · NTS", 6.2, "normal", "#555")

    model = cm.load_model(run)
    fr = floors_rel(model)
    b = model.building
    frame(sh, "panel_overview", *panels["overview"], "03  PROJECT DATA / 건축개요", MV)
    rows = [
        ("용도", "다층 상업시설"),
        ("모델 레벨", "B2–15F · %d개 레벨" % len(fr)),
        ("레벨 범위", "%+.1f m – %+.1f m (1F=±0.000)" % (min(fr.values()), max(fr.values()))),
        ("모델 평면 범위", "%.1f × %.1f m" % (b["xmax"] - b["xmin"], b["ymax"] - b["ymin"])),
        ("수직 장치", "나선 램프 · 빛 튜브 · 승강기 튜브 · 에스컬레이터"),
        ("형상 근거", "model_world.npz 캐시 · 원본 GLB 미존재"),
    ]
    y = 153
    for label, value in rows:
        sh.text(18, y, label, 6.5, "bold", "#333")
        sh.text(63, y, value, 6.5, "normal", "#333")
        sh.line(18, y + 3.0, 200, y + 3.0, 0.08, "#d0d0d0")
        y += 13.0
    sh.text(18, 238, "법정 용적률·건폐율·연면적은 검증 자료가 없어 기재하지 않음.", 6.2, "normal", "#a32020")

    frame(sh, "panel_area", *panels["area"], "04  FLOOR PROGRAM / 층별 프로그램·면적", MV)
    sh.text(220, 151, "층", 6.2, "bold", "#555")
    sh.text(241, 151, "프로그램", 6.2, "bold", "#555")
    sh.text(316, 151, "볼륨 투영 합계", 6.2, "bold", "#555")
    sh.text(367, 151, "층판 순면적", 6.2, "bold", "#555")
    area = cm.jl(os.path.join(run, "v4", "area", "typical_floor_coverage_v2.json"))
    by_floor = {r["floor"]: r for r in area["floors"]}
    y = 164
    for fl in ("1F", "3F", "8F", "12F", "13F", "15F"):
        r = by_floor[fl]
        names = " + ".join(r["program_volume_footprint_by_program_m2"].keys())
        sh.text(220, y, fl, 6.5, "bold", "#222")
        sh.text(241, y, names, 6.2, "normal", "#333")
        sh.text(350, y, "{:,.1f}㎡".format(r["program_volume_footprint_union_m2"]), 6.2, "normal", "#333", "end")
        sh.text(402, y, "{:,.1f}㎡".format(r["slab_net_m2"]), 6.2, "normal", "#333", "end")
        sh.line(220, y + 3.0, 402, y + 3.0, 0.08, "#d0d0d0")
        y += 11.2
    sh.text(220, 238, "프로그램 볼륨 수평 투영 · 전용면적/법정 연면적 아님 · A-903", 6.2, "bold", "#a35a00")
    sh.title_block()
    sh.save2(out_base)
    layout = {"sheet": "G-002", "paper_mm": [420.0, 297.0], "panels_mm": panels,
              "panel_size_mm": [194.0, 114.0], "gap_mm": [8.0, 8.0],
              "source_a003": site_pdf, "source_a003_sha256": cm.sha_file(site_pdf),
              "area_source": os.path.join(run, "v4", "area", "typical_floor_coverage_v2.json"),
              "entries_part_i": len([e for e in entries if e.get("part") == "I"]),
              "entries_part_ii": len([e for e in entries if e.get("part") == "II"])}
    cm.jd(layout, out_base + "_layout.json")
    return cm.sheet_row(sh, out_base, "PROJECT INFORMATION / 건축개요 및 배치계획", "DOCUMENT · MODEL VERIFIED", PART, None, sh.paper, "DOCUMENT",
                        {"panel_boxes_mm": panels, "panel_size_mm": [194.0, 114.0], "part": "I", "kind": "presentation"})


def build(run, out_dir=None):
    ctx = Ctx(run, out_dir)
    builders = [build_cover, build_overview, build_context, build_mass, build_vertical, build_program,
                build_plans, build_scenario, build_elevations, build_sections, build_axon,
                build_details, build_floor_experience, build_summary]
    for fn in builders:
        t0 = time.time()
        row = fn(ctx)
        ctx.times[row["sheet"]] = round(time.time() - t0, 3)
        print(row["sheet"], os.path.abspath(row["files"]["pdf"]["path"]))
    cm.jd(ctx.rows, os.path.join(ctx.out, "partI_front_registry.json"))
    cm.jd({"facts": ctx.facts, "render_seconds": ctx.times,
           "source": "model_world.npz + raw_slices + verified technical sheets",
           "truth_policy": [MV, CP, UR]}, os.path.join(ctx.out, "partI_front_facts.json"))
    return ctx.rows


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=cm.RUN_DEFAULT)
    args = ap.parse_args()
    build(os.path.abspath(args.run))


if __name__ == "__main__":
    main()

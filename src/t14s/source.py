"""Verified-source loader. Reads the hash-pinned slice copy; never modifies it."""
from __future__ import annotations

import functools
import hashlib
import json
import math
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from . import ROOT
import pipeline_common as pc

SRC_DIR = ROOT / "data" / "t14s" / "source_slices"
MANIFEST = SRC_DIR / "manifest.json"
DEFAULT_RAW = Path(r"D:/Users/admin/Desktop/중간마감/drawing-pipeline-T14J/output/C_T14J_run/raw_slices")
FLOORS = ["B2", "B1"] + ["%dF" % i for i in range(1, 16)]
TARGET_FLOORS = [f for f in FLOORS if f != "1F"]          # 1F is the preserved reference
COL_R = 0.45                                              # m_1f_source.json col_r
M1F = ROOT / "engine" / "model" / "m_1f_source.json"


def north_angle_deg() -> float:
    """True north, clockwise from drawing-up. Same derivation as engine/master/build_master.py (slice meta is null)."""
    nu, nv = json.loads(M1F.read_text(encoding="utf-8"))["north_vec"]
    return round(math.degrees(math.atan2(nu, nv)), 3)


def sha256(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for part in iter(lambda: f.read(1 << 20), b""):
            h.update(part)
    return h.hexdigest()


def sync_sources(raw_dir: Path = DEFAULT_RAW) -> dict:
    """Copy the 17 slices + bounds into the repo once; refuse to overwrite a copy whose hash differs."""
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    names = ["floor_%s_slice.json" % f for f in FLOORS] + ["camera_bounds.json", "floors.json"]
    man = {"source_dir": str(raw_dir), "files": {}}
    for n in names:
        src, dst = Path(raw_dir) / n, SRC_DIR / n
        if dst.exists() and sha256(dst) != sha256(src):
            raise RuntimeError("source copy differs from original, refusing to overwrite: %s" % n)
        if not dst.exists():
            shutil.copyfile(src, dst)
        man["files"][n] = sha256(dst)
    MANIFEST.write_text(json.dumps(man, indent=1, ensure_ascii=False), encoding="utf-8")
    return man


def verify_sources(raw_dir: Path = DEFAULT_RAW) -> dict:
    """Source geometry unchanged: copy matches its manifest, and the original when it is reachable."""
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    bad, orig_checked = [], 0
    for n, h in man["files"].items():
        if sha256(SRC_DIR / n) != h:
            bad.append("copy!=manifest:" + n)
        o = Path(raw_dir) / n
        if o.exists():
            orig_checked += 1
            if sha256(o) != h:
                bad.append("copy!=original:" + n)
    return {"ok": not bad, "problems": bad, "files": len(man["files"]), "original_checked": orig_checked}


@dataclass
class Tube:
    name: str            # T1..T4, capE, capW, FR, M1, M2, PL
    outer: Polygon       # glass-wall outer boundary (= slab opening)
    center: tuple
    r: float             # equivalent radius
    circular: bool


@dataclass
class FloorGeometry:
    floor: str
    z: float
    slab: object                    # Polygon / MultiPolygon with openings as interiors
    outline: Polygon
    holes: list
    columns: list                   # [(x, y)]
    cores: dict                     # id -> (x0, y0, x1, y1)
    tubes: dict                     # name -> Tube
    shafts: dict                    # EV1/EV2 -> Polygon
    escalators: list                # [{"name", "poly"}]
    ramps: list
    facade: dict                    # glass/louver/mullion -> geometry
    zones: list                     # [{"name_ko", "program_floor", "poly"}]
    north_deg: float
    slice_sha256: str = ""
    elements_count: int = 0
    esc_ends: list = field(default_factory=list)   # verified escalator axes seen from this floor (board / arrive / through)
    cars: dict = field(default_factory=dict)       # elevator-car section objects (source id -> polygon); not drawn as labels


@functools.lru_cache(maxsize=4)
def all_escalators(src_dir: str = str(SRC_DIR)) -> dict:
    """Every escalator axis in the pinned slices (name -> record). The slice of a floor only holds the flights that cross the
    1.5 m cut plane, so arrivals are found in the slice of the lower floor."""
    out = {}
    for f in FLOORS:
        d = json.loads((Path(src_dir) / ("floor_%s_slice.json" % f)).read_text(encoding="utf-8"))
        for e in d["elements"]:
            if "axis" in e and e["name"] not in out:
                a = e["axis"]
                fa, fb = e["escalator_range"]
                lo, hi = tuple(a["low_xy"]), tuple(a["high_xy"])
                L = math.hypot(hi[0] - lo[0], hi[1] - lo[1])
                out[e["name"]] = {"source_id": e["name"], "from": fa, "to": fb, "low": lo, "high": hi, "z_low": a["z_low"],
                                  "z_high": a["z_high"], "u": ((hi[0] - lo[0]) / L, (hi[1] - lo[1]) / L), "length": L,
                                  "express": FLOORS.index(fb) - FLOORS.index(fa) > 1 and fa != "B1"}
    return out


def _esc_width(poly, u) -> float:
    nx, ny = -u[1], u[0]
    ps = [x * nx + y * ny for x, y in poly.exterior.coords]
    return round(max(ps) - min(ps), 2)


def _tube_from(name, g) -> Tube:
    polys = list(getattr(g, "geoms", [g]))
    outer = unary_union([Polygon(p.exterior) for p in polys])
    c = outer.centroid
    r = math.sqrt(outer.area / math.pi)
    circular = outer.convex_hull.area > 0 and abs(outer.area - math.pi * r * r) / outer.area < 0.03
    return Tube(name, outer, (c.x, c.y), r, circular)


def load_floor(floor: str, src_dir: Path = SRC_DIR) -> FloorGeometry:
    sl = pc.load_slice(str(src_dir), floor)
    cuts = pc.cut_geometries(sl)
    proj = unary_union([pc.polygons_from_segments(p["segments"]) for p in sl["projection"]])
    polys = list(getattr(proj, "geoms", [proj]))
    outline = unary_union([Polygon(p.exterior) for p in polys])
    holes = [Polygon(r) for p in polys for r in p.interiors]
    cols = sorted((round(g.centroid.x, 3), round(g.centroid.y, 3)) for _, g in cuts.get("column", []))
    cores = {it["name"][-1]: tuple(round(v, 3) for v in g.bounds) for it, g in cuts.get("core_wall", [])}
    tubes = {it["name"].replace("A-CORE-TUBE_", ""): _tube_from(it["name"].replace("A-CORE-TUBE_", ""), g)
             for it, g in cuts.get("tube_wall", [])}
    shafts = {it["name"].replace("A-CORE-TUBE_", ""): g for it, g in cuts.get("shaft", [])}
    esc = [{"name": it["name"].replace("A-VERT-ESCL_", ""), "poly": g} for it, g in cuts.get("stair", [])]
    ramps = [{"name": it["name"], "poly": g} for it, g in cuts.get("ramp", [])]
    facade = {it["name"].replace("A-FACD_", ""): g for it, g in cuts.get("facade", [])}
    cars = {k: shafts.pop(k) for k in [k for k in shafts if k.startswith("A-VERT-ELEV_car")]}
    esc_ends = []
    fi = FLOORS.index(floor)
    for rec in all_escalators(str(src_dir)).values():
        a, b = FLOORS.index(rec["from"]), FLOORS.index(rec["to"])
        role = "board" if a == fi else "arrive" if b == fi else "through" if a < fi < b else None
        if role is None:
            continue
        cut = next((e["poly"] for e in esc if e["name"].startswith(rec["from"] + "-" + rec["to"]) or rec["source_id"].endswith(e["name"])), None)
        width = _esc_width(cut, rec["u"]) if cut is not None else 3.6
        esc_ends.append({**rec, "role": role, "width": width, "side": "N" if abs(rec["u"][0]) > abs(rec["u"][1]) else ("W" if (rec["low"][0] + rec["high"][0]) / 2 < 18 else "E"),
                         "label": "%s→%s" % (rec["from"], rec["to"])})
    zones = []
    for z in sl["zones"]:
        g = pc.polygons_from_segments(z["segments"])
        if not g.is_empty and z["kind"] in ("room", "zone", "void"):
            zones.append({"name_ko": z["name_ko"], "program_floor": z.get("program_floor"), "poly": g})
    return FloorGeometry(floor, float(sl["floor_z"]), proj, outline, holes, cols, cores, tubes, shafts, esc, ramps,
                         facade, zones, north_angle_deg(),
                         sha256(Path(src_dir) / ("floor_%s_slice.json" % floor)), len(sl["elements"]), esc_ends, cars)

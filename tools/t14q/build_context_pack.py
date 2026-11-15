"""Build the Blender-ready Site Context dataset (cache frame) from the studio OSM extract.

Run (system Python, needs shapely/numpy):
  python tools/t14q/build_context_pack.py --out <dir>/context_pack.json

Every attribute that is not tagged in OSM carries an explicit provenance flag
(``*_source`` = "OSM:..." | "ASSUMED:...").  Nothing here is surveyed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.t14q import frames as fr  # noqa: E402

OSM_DEFAULT = Path(r"D:\Users\admin\Desktop\5-2\설계스튜디오\중간발표\02_site_analysis\data\osm_ddp.json")
SITE_DEFAULT = OSM_DEFAULT.parent / "site_estimate.json"

LANE_W = 3.25
CARRIAGEWAY = {"primary", "primary_link", "secondary", "tertiary", "tertiary_link",
               "residential", "unclassified", "service", "living_street", "busway", "road"}
FOOT = {"pedestrian", "footway", "path", "cycleway", "steps"}
DEFAULT_LANES = {"primary": 4, "primary_link": 1, "secondary": 3, "tertiary": 2, "tertiary_link": 1,
                 "residential": 2, "unclassified": 2, "service": 1, "living_street": 1, "busway": 1, "road": 2}
SIDEWALK_W = {"primary": 3.15, "primary_link": 0.0, "secondary": 3.0, "tertiary": 2.5, "tertiary_link": 0.0,
              "residential": 2.0, "unclassified": 1.8, "service": 0.0, "living_street": 0.0, "busway": 0.0, "road": 1.5}
LEVEL_H = {"commercial": 4.0, "retail": 4.2, "office": 3.8, "hotel": 3.4, "apartments": 3.0,
           "hospital": 3.8, "school": 3.8}


def _h01(key: str) -> float:
    """Deterministic pseudo-random in [0,1) from a string (reproducible assumptions)."""
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def estimate_height(tags: dict, area: float, fid: str) -> tuple[float, str, int | None]:
    levels = None
    if "building:levels" in tags:
        try:
            levels = int(float(str(tags["building:levels"]).split(";")[0]))
        except ValueError:
            levels = None
    if "height" in tags:
        try:
            return float(str(tags["height"]).replace("m", "").strip()), "OSM:height", levels
        except ValueError:
            pass
    btype = tags.get("building", "yes")
    if levels:
        return round(levels * LEVEL_H.get(btype, 3.4) + 1.0, 1), f"OSM:levels*{LEVEL_H.get(btype, 3.4)}+1", levels
    r = _h01(fid)
    if btype == "roof":
        return 4.0, "ASSUMED:open canopy 4.0 m", None
    if btype in ("garage", "garages", "shed", "kiosk", "service", "hut", "carport"):
        return 3.5 + 1.5 * r, "ASSUMED:ancillary type", None
    # footprint-area heuristic for untagged buildings (dense mixed-use fabric)
    if area < 60:
        lo, hi = 6.0, 10.0
    elif area < 200:
        lo, hi = 9.0, 17.0
    elif area < 600:
        lo, hi = 14.0, 28.0
    elif area < 1500:
        lo, hi = 22.0, 42.0
    else:
        lo, hi = 30.0, 55.0
    if btype in ("commercial", "retail", "office", "hotel"):
        lo, hi = lo * 1.25, hi * 1.25
    return round(lo + (hi - lo) * r, 1), "ASSUMED:footprint-area heuristic", None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--osm", type=Path, default=OSM_DEFAULT)
    ap.add_argument("--site", type=Path, default=SITE_DEFAULT)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-dist", type=float, default=1450.0, help="forward range along view axis (m)")
    args = ap.parse_args()

    osm = json.loads(args.osm.read_text(encoding="utf-8"))
    site_ring = [fr.osm_to_cache(x, y) for x, y in json.loads(args.site.read_text(encoding="utf-8"))["calibrated_site_xy"]]
    site = Polygon(site_ring)
    cam = fr.g002_camera()
    cx, cy, _ = cam["camera_cache_world_m"]
    vb = math.radians(cam["view_bearing_deg"])
    fwd = np.array([math.sin(vb), math.cos(vb)])
    rgt = np.array([math.cos(vb), -math.sin(vb)])
    half = math.radians(cam["hfov_deg"] / 2.0) * 1.35

    def keep(pts: np.ndarray) -> bool:
        c = pts.mean(0)
        if math.hypot(c[0] - site.centroid.x, c[1] - site.centroid.y) < 340:
            return True
        d = c - np.array([cx, cy])
        f, r = float(d @ fwd), float(d @ rgt)
        return -30 < f < args.max_dist and abs(r) <= max(f, 1.0) * math.tan(half) + 70

    buildings, carriage, foot, crossings, greens, other = [], [], [], [], [], []
    excluded = []
    for f in osm["features"]:
        t = f["tags"]
        pts = np.array([fr.osm_to_cache(x, y) for x, y in f["xy"]])
        if len(pts) < 2 or not keep(pts):
            continue
        fid = f["id"]
        if "building" in t and f.get("closed") and len(pts) >= 4:
            poly = Polygon(pts)
            if not poly.is_valid:
                poly = poly.buffer(0)
            if poly.is_empty or poly.area < 6.0:
                continue
            if poly.centroid.within(site) or poly.intersection(site).area > 0.3 * poly.area:
                excluded.append({"id": fid, "name": t.get("name"), "reason": "inside design lot (existing block replaced by the design)"})
                continue
            if isinstance(poly, MultiPolygon):
                poly = max(poly.geoms, key=lambda g: g.area)
            h, hsrc, lev = estimate_height(t, poly.area, fid)
            buildings.append({"id": fid, "name": t.get("name"), "type": t.get("building"),
                              "ring": [[round(x, 3), round(y, 3)] for x, y in poly.exterior.coords],
                              "area_m2": round(poly.area, 1), "height_m": h, "height_source": hsrc, "levels": lev,
                              "canopy": t.get("building") == "roof"})
            continue
        hw = t.get("highway")
        if hw and (t.get("tunnel") in ("yes", "building_passage") or t.get("covered") == "yes" or str(t.get("layer", "0")) in ("-1", "-2")):
            continue
        if hw in CARRIAGEWAY and len(pts) >= 2:
            lanes_tag = t.get("lanes")
            try:
                lanes = int(float(lanes_tag)) if lanes_tag else None
            except ValueError:
                lanes = None
            oneway = t.get("oneway") == "yes"
            n = lanes if lanes else DEFAULT_LANES.get(hw, 2)
            width = round(max(n, 1) * LANE_W + (0.5 if hw in ("residential", "unclassified") else 0.0), 2)
            carriage.append({"id": fid, "name": t.get("name"), "class": hw, "lanes": n,
                             "lanes_source": "OSM:lanes" if lanes else "ASSUMED:class default",
                             "width_m": width, "width_source": "ASSUMED:lanes*3.25 m (not surveyed)",
                             "oneway": oneway, "bridge": t.get("bridge") == "yes",
                             "line": [[round(x, 3), round(y, 3)] for x, y in pts]})
        elif hw in FOOT or hw == "crossing":
            is_cross = t.get("footway") == "crossing" or t.get("crossing") is not None or hw == "crossing"
            rec = {"id": fid, "name": t.get("name"), "class": hw, "line": [[round(x, 3), round(y, 3)] for x, y in pts]}
            (crossings if is_cross else foot).append(rec)
        elif t.get("leisure") in ("garden", "park", "pitch") or t.get("landuse") in ("grass", "forest", "meadow") or t.get("natural") in ("wetland", "water", "sand", "grassland"):
            if f.get("closed") and len(pts) >= 4:
                kind = t.get("leisure") or t.get("landuse") or t.get("natural")
                greens.append({"id": fid, "kind": kind, "ring": [[round(x, 3), round(y, 3)] for x, y in pts]})
        elif t.get("amenity") in ("parking", "marketplace") and f.get("closed") and len(pts) >= 4:
            other.append({"id": fid, "kind": t["amenity"], "ring": [[round(x, 3), round(y, 3)] for x, y in pts]})

    # --- derived sidewalks (band around carriageways, minus carriageway & buildings) ---
    cw_polys, walk_polys = [], []
    for r in carriage:
        if r["bridge"]:
            continue
        ls = LineString(r["line"])
        cw_polys.append(ls.buffer(r["width_m"] / 2.0, cap_style=2, join_style=1))
        sw = SIDEWALK_W.get(r["class"], 0.0)
        if sw > 0:
            walk_polys.append(ls.buffer(r["width_m"] / 2.0 + sw, cap_style=2, join_style=1))
    cw_union = unary_union(cw_polys) if cw_polys else Polygon()
    bld_union = unary_union([Polygon(b["ring"]).buffer(0.2) for b in buildings]) if buildings else Polygon()
    walk_union = unary_union(walk_polys).difference(cw_union).difference(bld_union) if walk_polys else Polygon()

    def rings_of(g):
        out = []
        geoms = g.geoms if hasattr(g, "geoms") else [g]
        for p in geoms:
            if p.is_empty or p.geom_type != "Polygon" or p.area < 1.0:
                continue
            out.append({"shell": [[round(x, 3), round(y, 3)] for x, y in p.exterior.coords],
                        "holes": [[[round(x, 3), round(y, 3)] for x, y in h.coords] for h in p.interiors]})
        return out

    # --- assumed street trees along primary/secondary/tertiary sidewalks ---
    trees = []
    for r in carriage:
        if r["class"] not in ("primary", "secondary", "tertiary"):
            continue
        ls = LineString(r["line"])
        sw = SIDEWALK_W[r["class"]]
        off = r["width_m"] / 2.0 + sw * 0.55
        step = 9.0
        for side in (1, -1):
            d = step * (0.3 + _h01(r["id"] + str(side)))
            while d < ls.length:
                p = ls.interpolate(d)
                q = ls.interpolate(min(d + 1.0, ls.length))
                dx, dy = q.x - p.x, q.y - p.y
                L = math.hypot(dx, dy) or 1.0
                tx, ty = p.x - side * dy / L * off, p.y + side * dx / L * off
                pt = Point(tx, ty)
                if walk_union.buffer(0.1).contains(pt):
                    near_cross = any(LineString(c["line"]).distance(pt) < 6.0 for c in crossings)
                    if not near_cross:
                        trees.append({"xy": [round(tx, 2), round(ty, 2)], "scale": round(0.8 + 0.5 * _h01(f"{r['id']}{d}"), 2),
                                      "source": "ASSUMED:street tree (OSM has no tree data)"})
                d += step * (0.85 + 0.3 * _h01(f"{r['id']}{d}s"))
    pack = {
        "provenance": {
            "osm_file": str(args.osm), "osm_sha256": hashlib.sha256(args.osm.read_bytes()).hexdigest(),
            "osm_downloaded": "2026-10-26 (studio 02_site_analysis/sources.md)", "osm_licence": "ODbL, (c) OpenStreetMap contributors",
            "frame": "cache-world (E/N, origin = lot centroid): cache_xy = osm_xy + %s" % (fr.CACHE_FROM_OSM_OFFSET,),
            "camera": {k: (list(v) if isinstance(v, tuple) else v) for k, v in cam.items()},
            "limits": ["building heights mostly ASSUMED", "road widths = lanes*3.25 m", "sidewalk widths assumed per class",
                       "no tree / street-lamp data in OSM -> trees are ASSUMED", "bridges/tunnels flattened or skipped",
                       "facade materials are generic look-development, not surveyed"],
        },
        "site_polygon": [[round(x, 3), round(y, 3)] for x, y in site_ring],
        "excluded_existing": excluded,
        "buildings": buildings, "carriageways": carriage, "footways": foot, "crossings": crossings,
        "sidewalk_polygons": rings_of(walk_union), "carriageway_polygons": rings_of(cw_union),
        "greens": greens, "paved_areas": other, "street_trees": trees,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(pack, ensure_ascii=False), encoding="utf-8")
    hs = {}
    for b in buildings:
        k = b["height_source"].split(":")[0]
        hs[k] = hs.get(k, 0) + 1
    print("context pack ->", args.out.resolve())
    print("buildings", len(buildings), "height sources", hs, "excluded", len(excluded))
    print("carriageways", len(carriage), "footways", len(foot), "crossings", len(crossings), "greens", len(greens),
          "walk polys", len(pack["sidewalk_polygons"]), "street trees", len(trees))


if __name__ == "__main__":
    main()

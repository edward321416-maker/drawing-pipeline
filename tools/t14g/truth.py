"""Geometric truth checks computed from the model mesh / master (independent of any drawing code).

  circularity(g)            4*pi*A/P^2 of the outer ring (1.0 = circle)
  is_circle(g)              True only if a diameter symbol (Ø) is legitimate for the outline
  sloped_incline(model, o)  true incline of an escalator/ramp from the *sloped faces* of the 3D mesh
  congruent(model, a, b)    translation-invariant symmetric Hausdorff distance between two objects
  stair_derived(...)        values that are arithmetic on model/master properties (flagged as derived)

Why sloped faces: the section polygon of an escalator contains the flat landings and the plate thickness, so a
minimum rotated rectangle (V2) or a regression over all vertices gives 24-25 deg for a flight that is built at 30 deg.
The triangle normals of the inclined faces give the physical incline directly.
"""
import math

import numpy as np
from scipy.spatial import cKDTree
from shapely.geometry import Polygon

CIRCLE_MIN = 0.98


def _largest(g):
    ps = [p for p in (g.geoms if hasattr(g, "geoms") else [g]) if p.geom_type == "Polygon" and not p.is_empty]
    return max(ps, key=lambda q: q.area) if ps else None


def circularity(g):
    p = _largest(g)
    if p is None:
        return 0.0
    ext = Polygon(p.exterior)
    return 4.0 * math.pi * ext.area / (ext.length ** 2)


def is_circle(g, min_circ=CIRCLE_MIN):
    return circularity(g) >= min_circ


def diameter_label(g, value_text, circle_prefix="Ø", other_prefix="폭 "):
    """'Ø5600' only when the outline is circular, otherwise '폭 5600' (never the wrong symbol)."""
    return (circle_prefix if is_circle(g) else other_prefix) + value_text


def sloped_incline(model, objs, nz_band=(0.5, 0.97), bin_deg=0.5, window_deg=1.5):
    """Incline (deg) of the inclined faces of one or more mesh objects, area weighted, plus the plan run of those faces."""
    objs = objs if isinstance(objs, (list, tuple)) else [objs]
    angs, wts, pts = [], [], []
    for o in objs:
        T = model.tris(o)
        n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
        ln = np.linalg.norm(n, axis=1)
        A = ln / 2.0
        nz = np.abs(n[:, 2]) / np.maximum(ln, 1e-12)
        sl = (nz > nz_band[0]) & (nz < nz_band[1])
        angs.append(np.degrees(np.arccos(nz[sl])))
        wts.append(A[sl])
        pts.append(T[sl])
    ang, w = np.concatenate(angs), np.concatenate(wts)
    P = np.concatenate(pts)
    if len(ang) == 0:
        return None
    hist, edges = np.histogram(ang, bins=np.arange(10.0, 61.0, bin_deg), weights=w)
    dom = edges[hist.argmax()] + bin_deg / 2.0
    sel = np.abs(ang - dom) < window_deg
    angle = float(np.average(ang[sel], weights=w[sel]))
    V = P[sel].reshape(-1, 3)
    xy = V[:, :2] - V[:, :2].mean(0)
    _, vec = np.linalg.eigh(np.cov(xy.T))
    axis = vec[:, 1]
    s = xy @ axis
    run = float(s.max() - s.min())
    return {"angle_deg": angle, "dominant_bin_deg": float(dom), "plan_run_m": run, "rise_from_angle_m": run * math.tan(math.radians(angle)),
            "travel_axis_xy": [float(axis[0]), float(axis[1])], "faces": int(sel.sum()), "method": "area-weighted triangle normals of inclined faces"}


def _canon(model, o):
    T = model.tris(o).reshape(-1, 3)
    c = (T.max(0) + T.min(0)) / 2.0
    return np.unique(np.round(T - c, 3), axis=0), T


def congruent(model, name_a, name_b, tol_m=0.02):
    byname = {o["name"]: o for o in model.objects}
    ca, ta = _canon(model, byname[name_a])
    cb, tb = _canon(model, byname[name_b])
    d = max(cKDTree(cb).query(ca)[0].max(), cKDTree(ca).query(cb)[0].max())
    size_a, size_b = ta.max(0) - ta.min(0), tb.max(0) - tb.min(0)
    return {"a": name_a, "b": name_b, "hausdorff_centered_m": float(d), "size_a_m": [round(float(v), 3) for v in size_a],
            "size_b_m": [round(float(v), 3) for v in size_b], "z_range_a": [round(float(ta[:, 2].min()), 3), round(float(ta[:, 2].max()), 3)],
            "z_range_b": [round(float(tb[:, 2].min()), 3), round(float(tb[:, 2].max()), 3)],
            "unique_vertices": [int(len(ca)), int(len(cb))], "congruent": bool(d <= tol_m and abs(size_a - size_b).max() <= tol_m)}


def stair_derived(drop_m, treads, run_m):
    """Arithmetic on master/model values only: nothing here is in the model as an attribute."""
    return {"riser_mm": 1000.0 * drop_m / treads, "tread_mm": 1000.0 * run_m / treads, "drop_m": drop_m, "treads": treads, "run_m": run_m,
            "status": "DERIVED (no riser/tread attribute in the master)"}

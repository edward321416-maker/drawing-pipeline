"""R10-B: true mesh-plane section of the original GLB (read-only).

The source GLB is never modified.  Geometry is loaded, welded in memory, moved into the drawing
frame and cut with an exact plane.  Nothing here uses object bounding boxes as a stand-in for
cut geometry.

Frame (data/t14s/source_slices/camera_bounds.json, key "frame"):
    drawing = R(-theta) . world          (world +Y is true north, theta = 63.2017 deg, no translation)
glTF is Y-up, the pipeline's "world" is Blender Z-up:   world = (x_gltf, -z_gltf, y_gltf).
Section sheet axes:  h = -y_drawing  (viewer looks along +X_drawing, right-hand side is south),  v = z.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
from dataclasses import dataclass, field

import numpy as np
import trimesh
from shapely.geometry import LineString, MultiPolygon, Polygon
from shapely.ops import polygonize, unary_union

logging.disable(logging.CRITICAL)  # trimesh prints one Draco warning per mesh otherwise

GLB_PATH = r"D:\Users\admin\Desktop\5-2\설계스튜디오\중간발표\07_representation\render\out\GMC-ZZ-ZZ-M3-0701.glb"
GLB_SHA256 = "b1927ffd8335853fcdf55f6ec49cee3233465cfc1362295ffa717f214b45ab88"
FRAME_JSON = os.path.join(os.path.dirname(__file__), "..", "..", "data", "t14s", "source_slices", "camera_bounds.json")


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def frame_theta() -> float:
    with open(FRAME_JSON, encoding="utf-8") as fh:
        return math.radians(json.load(fh)["frame"]["theta_deg"])


def kind_of(node: str) -> str:
    """Layer prefix -> coarse element class.  Prefixes are the GLB's own layer names."""
    table = (
        ("A-FLOR", "slab"), ("A-ROOF", "roof"), ("A-CORE-TUBE", "tube"), ("A-VERT-STRS", "stair_core"),
        ("A-VERT-ESCL", "escalator"), ("A-VERT-ELEV", "elevator_car"), ("A-VERT-SPRL", "spiral_ramp"),
        ("A-FACD", "facade"), ("A-STRC", "structure"), ("A-PROG", "program"), ("A-SITE", "site"),
        ("C-SITE", "site"), ("L-PLNT", "planting"), ("X-CTXT", "context"), ("Icosphere", "planting"),
        ("Cylinder", "other"),
    )
    for prefix, kind in table:
        if node.startswith(prefix):
            return kind
    return "other"


@dataclass
class CutItem:
    node: str
    kind: str
    polygons: list          # shapely Polygons in (h, v) sheet metres
    lines: list             # shapely LineStrings (open cut lines that did not close)
    watertight: bool
    bounds_hv: tuple        # (h0, v0, h1, v1) of the actual cut geometry


@dataclass
class SectionCut:
    axis_value: float
    glb_sha256: str
    items: list = field(default_factory=list)
    skipped: list = field(default_factory=list)  # nodes the plane does not touch


def load_scene(verify_hash: bool = True):
    if verify_hash:
        got = sha256_file(GLB_PATH)
        if got != GLB_SHA256:
            raise RuntimeError(f"GLB hash changed: {got}")
    return trimesh.load(GLB_PATH, force="scene")


def world_vertices(scene, node: str) -> tuple[np.ndarray, np.ndarray]:
    T, gname = scene.graph[node]
    g = scene.geometry[gname]
    v = trimesh.transform_points(np.asarray(g.vertices, float), T)
    return np.stack([v[:, 0], -v[:, 2], v[:, 1]], axis=1), np.asarray(g.faces)


def to_drawing(world_xyz: np.ndarray, theta: float) -> np.ndarray:
    c, s = math.cos(theta), math.sin(theta)
    x, y, z = world_xyz[:, 0], world_xyz[:, 1], world_xyz[:, 2]
    return np.stack([x * c + y * s, -x * s + y * c, z], axis=1)


def _plane_segments(vd: np.ndarray, faces: np.ndarray, x0: float, ax: int = 0):
    """Exact triangle/plane intersection segments for the plane  component[ax] = x0  (drawing frame)."""
    tri = vd[faces]                                   # (n,3,3)
    d = tri[:, :, ax] - x0                             # signed distance of each corner
    segs = []
    for i in range(len(faces)):
        di = d[i]
        if (di > 0).all() or (di < 0).all():
            continue
        pts = []
        for a, b in ((0, 1), (1, 2), (2, 0)):
            da, db = di[a], di[b]
            if da == 0 and db == 0:
                pts.extend([tri[i, a], tri[i, b]])
            elif (da < 0 < db) or (db < 0 < da) or da == 0 or db == 0:
                if da == db:
                    continue
                t = da / (da - db)
                if 0.0 <= t <= 1.0:
                    pts.append(tri[i, a] + t * (tri[i, b] - tri[i, a]))
        # de-duplicate within 1e-9 m
        uniq = []
        for p in pts:
            if not any(np.linalg.norm(p - q) < 1e-9 for q in uniq):
                uniq.append(p)
        if len(uniq) >= 2:
            segs.append((uniq[0], uniq[1]))
    return segs


def cut_at_x(scene, x0: float, nodes=None, theta: float | None = None, snap: float = 1e-4) -> SectionCut:
    """A-A style cut: plane x_drawing = x0, viewer looks along +X, sheet h = -y_drawing."""
    return cut_plane(scene, "x", x0, nodes, theta, snap)


def cut_plane(scene, axis: str, value: float, nodes=None, theta: float | None = None, snap: float = 1e-4) -> SectionCut:
    """Exact cut by the plane  axis_drawing = value.
    axis 'x': viewer looks along +X, sheet h = -y_drawing.   axis 'y': viewer looks along +Y, sheet h = +x_drawing.
    Sheet v = z in both cases (right-hand rule: looking along d, the right-hand side is d rotated -90 degrees)."""
    ax = {"x": 0, "y": 1}[axis]
    hs = {"x": (1, -1.0), "y": (0, 1.0)}[axis]          # (drawing component used for h, sign)
    theta = frame_theta() if theta is None else theta
    out = SectionCut(axis_value=value, glb_sha256=GLB_SHA256)
    x0 = value
    for node in sorted(nodes if nodes is not None else scene.graph.nodes_geometry):
        vw, faces = world_vertices(scene, node)
        vd = to_drawing(vw, theta)
        if vd[:, ax].min() > x0 or vd[:, ax].max() < x0:
            out.skipped.append(node)
            continue
        segs = _plane_segments(vd, faces, x0, ax)
        if not segs:
            out.skipped.append(node)
            continue
        lines = []
        for p, q in segs:
            a = (round(hs[1] * p[hs[0]] / snap) * snap, round(p[2] / snap) * snap)
            b = (round(hs[1] * q[hs[0]] / snap) * snap, round(q[2] / snap) * snap)
            if a != b:
                lines.append(LineString([a, b]))
        if not lines:
            out.skipped.append(node)
            continue
        merged = unary_union(lines)
        polys = list(polygonize(merged))
        # polygonize on a shared-edge mesh gives every cell; merge them into outer shells (cut solid)
        solid = unary_union(polys) if polys else None
        poly_list = []
        if solid is not None and not solid.is_empty:
            poly_list = list(solid.geoms) if isinstance(solid, MultiPolygon) else [solid]
        used = unary_union(poly_list).boundary if poly_list else None
        open_lines = []
        if used is not None:
            rest = merged.difference(used.buffer(snap * 2))
            if not rest.is_empty:
                open_lines = list(rest.geoms) if hasattr(rest, "geoms") else [rest]
        else:
            open_lines = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
        allgeom = unary_union(poly_list + open_lines) if (poly_list or open_lines) else merged
        out.items.append(CutItem(node, kind_of(node), poly_list, open_lines,
                                 bool(poly_list) and not open_lines, tuple(round(v, 4) for v in allgeom.bounds)))
    return out

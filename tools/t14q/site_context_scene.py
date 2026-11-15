"""C-T14Q Blender scene: verified G-002 building mesh + location-registered site context.

  blender -b --factory-startup -P tools/t14q/site_context_scene.py -- \
      --cache-dir <model_cache> --pack <context_pack.json> --out-dir <new empty dir> \
      --variant daylight|bluehour --width 1600 --height 900 --samples 32

What stays untouched : every ARCHITECTURE_KINDS triangle of the cache (slab, column, core_wall,
                       tube_wall, shaft, stair, ramp, facade, roof) and the cache `site` objects
                       (plaza, grove, sunken court, steps, roof/mid-level garden surfaces).
What is replaced     : the cache's single merged `context_building` (unsurveyed grey blocks) and its
                       83 sphere-proxy trees (same positions / canopy volumes, realistic canopy).
What is added        : OSM-registered roads, sidewalks, crossings, lane marks, green areas, ~800
                       buildings, assumed street trees, real sun position, sky, haze.
All context attributes are look-development with explicit provenance (see context_pack.json).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector, noise as mnoise
from mathutils.geometry import tessellate_polygon

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import os  # noqa: E402

if os.environ.get("T14Q_PYDEPS"):  # project-local wheels (shapely) for Blender's bundled Python
    sys.path.insert(0, os.environ["T14Q_PYDEPS"])
from tools.t14o import blender_pbr_scene as t14o  # noqa: E402
from tools.t14o.cache_validation import validate_cache  # noqa: E402
from tools.t14q import frames as fr  # noqa: E402

KST = timezone(timedelta(hours=9))
SUN_TIME = {"daylight": datetime(2026, 10, 17, 15, 30, tzinfo=KST), "bluehour": datetime(2026, 10, 17, 18, 12, tzinfo=KST)}
G = fr.GROUND_Z_LOCAL
BASE_Z, ROAD_Z, MARK_Z, WALK_Z, GREEN_Z = G - 0.25, G - 0.15, G - 0.12, G - 0.01, G - 0.02
WINDOW_EMISSION = 0.7  # blue-hour lit-window emission (look-dev; set from CLI before materials are built)
SKY_STRENGTH_DEFAULT = {"daylight": 1.0, "bluehour": 70.0}  # Nishita twilight is ~2 orders dimmer than day
EXPOSURE_DEFAULT = {"daylight": -0.9, "bluehour": 0.0}


def h01(key: str) -> float:
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


# ------------------------------------------------------------------ node helpers
def nd(nt, kind, loc=(0, 0), **kw):
    n = nt.nodes.new(kind)
    n.location = loc
    for k, v in kw.items():
        setattr(n, k, v)
    return n


def link(nt, a, b):
    nt.links.new(a, b)


def math_node(nt, op, a=None, b=None, c=None, clamp=False):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.use_clamp = clamp
    for i, v in enumerate((a, b, c)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = float(v)
        else:
            link(nt, v, n.inputs[i])
    return n.outputs[0]


def principled(nt):
    return next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")


def new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, m.node_tree, principled(m.node_tree)


def noise_color(nt, scale, c0, c1, detail=4.0, rough=0.55, coord="OBJECT", var=1.0):
    tc = nd(nt, "ShaderNodeTexCoord")
    nz = nd(nt, "ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = detail
    nz.inputs["Roughness"].default_value = rough
    link(nt, tc.outputs[coord.title() if coord != "OBJECT" else "Object"], nz.inputs["Vector"])
    ramp = nd(nt, "ShaderNodeMixRGB")
    ramp.inputs["Color1"].default_value = c0
    ramp.inputs["Color2"].default_value = c1
    link(nt, nz.outputs["Fac"], ramp.inputs["Fac"])
    return ramp.outputs["Color"], nz.outputs["Fac"]


# ------------------------------------------------------------------ context materials
def mat_asphalt(variant):
    m, nt, b = new_mat("CTX_asphalt")
    col, fac = noise_color(nt, 0.35, (0.030, 0.031, 0.033, 1), (0.060, 0.060, 0.062, 1))
    link(nt, col, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.48 if variant == "bluehour" else 0.78
    bump = nd(nt, "ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    bump.inputs["Distance"].default_value = 0.02
    n2 = nd(nt, "ShaderNodeTexNoise")
    n2.inputs["Scale"].default_value = 90.0
    n2.inputs["Detail"].default_value = 6.0
    link(nt, nt.nodes.new("ShaderNodeTexCoord").outputs["Object"], n2.inputs["Vector"])
    link(nt, n2.outputs["Fac"], bump.inputs["Height"])
    link(nt, bump.outputs["Normal"], b.inputs["Normal"])
    return m


def mat_paving(variant):
    m, nt, b = new_mat("CTX_sidewalk_paving")
    tc = nd(nt, "ShaderNodeTexCoord")
    br = nd(nt, "ShaderNodeTexBrick")
    br.inputs["Scale"].default_value = 1.0
    br.inputs["Color1"].default_value = (0.30, 0.285, 0.265, 1)
    br.inputs["Color2"].default_value = (0.235, 0.225, 0.215, 1)
    br.inputs["Mortar"].default_value = (0.09, 0.09, 0.09, 1)
    br.inputs["Mortar Size"].default_value = 0.012
    br.inputs["Brick Width"].default_value = 0.6
    br.inputs["Row Height"].default_value = 0.3
    br.inputs["Bias"].default_value = 0.0
    link(nt, tc.outputs["Object"], br.inputs["Vector"])
    link(nt, br.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.55 if variant == "bluehour" else 0.72
    bump = nd(nt, "ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25
    bump.inputs["Distance"].default_value = 0.01
    link(nt, br.outputs["Fac"], bump.inputs["Height"])
    link(nt, bump.outputs["Normal"], b.inputs["Normal"])
    return m


def mat_flat(name, rgba, rough=0.6, emission=None, strength=0.0):
    m, nt, b = new_mat(name)
    b.inputs["Base Color"].default_value = rgba
    b.inputs["Roughness"].default_value = rough
    if emission is not None:
        b.inputs["Emission Color"].default_value = emission
        b.inputs["Emission Strength"].default_value = strength
    return m


def mat_grass():
    m, nt, b = new_mat("CTX_grass")
    col, fac = noise_color(nt, 1.2, (0.050, 0.095, 0.030, 1), (0.110, 0.150, 0.050, 1))
    link(nt, col, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.9
    return m


STYLES = [  # wall rgba, window w (m), floor h (m), win u-range, win v-range, glass rgba, glazing share kind
    dict(name="stone", wall=(0.30, 0.295, 0.28, 1), ww=2.5, fh=3.6, u=(0.16, 0.84), v=(0.26, 0.80), curtain=False),
    dict(name="stucco", wall=(0.37, 0.32, 0.25, 1), ww=2.8, fh=3.3, u=(0.22, 0.78), v=(0.30, 0.80), curtain=False),
    dict(name="curtain", wall=(0.085, 0.11, 0.13, 1), ww=1.8, fh=3.9, u=(0.04, 0.96), v=(0.06, 0.90), curtain=True),
    dict(name="brick", wall=(0.22, 0.095, 0.07, 1), ww=2.4, fh=3.3, u=(0.24, 0.76), v=(0.28, 0.76), curtain=False),
    dict(name="charcoal", wall=(0.08, 0.085, 0.095, 1), ww=3.2, fh=3.6, u=(0.05, 0.95), v=(0.32, 0.72), curtain=False),
    dict(name="white", wall=(0.44, 0.44, 0.42, 1), ww=2.6, fh=3.4, u=(0.20, 0.80), v=(0.28, 0.80), curtain=False),
]


def mat_facade(style: dict, variant: str):
    m, nt, b = new_mat(f"CTX_facade_{style['name']}")
    uvn = nd(nt, "ShaderNodeUVMap")
    uvn.uv_map = "UVMap"
    sep = nd(nt, "ShaderNodeSeparateXYZ")
    link(nt, uvn.outputs["UV"], sep.inputs["Vector"])
    u, v = sep.outputs["X"], sep.outputs["Y"]
    fu = math_node(nt, "FRACT", math_node(nt, "DIVIDE", u, style["ww"]))
    fv = math_node(nt, "FRACT", math_node(nt, "DIVIDE", v, style["fh"]))
    mu = math_node(nt, "MULTIPLY", math_node(nt, "GREATER_THAN", fu, style["u"][0]), math_node(nt, "LESS_THAN", fu, style["u"][1]))
    mv = math_node(nt, "MULTIPLY", math_node(nt, "GREATER_THAN", fv, style["v"][0]), math_node(nt, "LESS_THAN", fv, style["v"][1]))
    win = math_node(nt, "MULTIPLY", mu, mv)
    # ground-floor storefront glazing (first 4.2 m): wide continuous windows
    gf = math_node(nt, "LESS_THAN", v, 4.2)
    sf_v = math_node(nt, "MULTIPLY", math_node(nt, "GREATER_THAN", v, 0.5), math_node(nt, "LESS_THAN", v, 3.6))
    sf_u = math_node(nt, "MULTIPLY", math_node(nt, "GREATER_THAN", fu, 0.04), math_node(nt, "LESS_THAN", fu, 0.96))
    store = math_node(nt, "MULTIPLY", sf_v, sf_u)
    mask = math_node(nt, "MAXIMUM", math_node(nt, "MULTIPLY", win, math_node(nt, "SUBTRACT", 1.0, gf)), math_node(nt, "MULTIPLY", store, gf))
    # per-building variation
    brand = nd(nt, "ShaderNodeAttribute")
    brand.attribute_name = "brand"
    bf = brand.outputs["Fac"]
    tint = math_node(nt, "MULTIPLY_ADD", bf, 0.35, 0.82)  # 0.82..1.17
    wall = nd(nt, "ShaderNodeMixRGB")
    wall.blend_type = "MULTIPLY"
    wall.inputs["Fac"].default_value = 1.0
    wall.inputs["Color1"].default_value = style["wall"]
    comb = nd(nt, "ShaderNodeCombineXYZ")
    for i in range(3):
        link(nt, tint, comb.inputs[i])
    link(nt, comb.outputs["Vector"], wall.inputs["Color2"])
    # weathering noise on opaque wall
    wcol, _ = noise_color(nt, 0.6, (0.80, 0.80, 0.80, 1), (1.05, 1.05, 1.05, 1), coord="OBJECT")
    wall2 = nd(nt, "ShaderNodeMixRGB")
    wall2.blend_type = "MULTIPLY"
    wall2.inputs["Fac"].default_value = 1.0
    link(nt, wall.outputs["Color"], wall2.inputs["Color1"])
    link(nt, wcol, wall2.inputs["Color2"])
    glass_rgb = (0.018, 0.030, 0.042, 1) if not style["curtain"] else (0.020, 0.045, 0.060, 1)
    mix = nd(nt, "ShaderNodeMixRGB")
    link(nt, mask, mix.inputs["Fac"])
    link(nt, wall2.outputs["Color"], mix.inputs["Color1"])
    mix.inputs["Color2"].default_value = glass_rgb
    link(nt, mix.outputs["Color"], b.inputs["Base Color"])
    rough = math_node(nt, "MULTIPLY_ADD", mask, -0.72, 0.82)  # wall 0.82 -> glass 0.10
    link(nt, rough, b.inputs["Roughness"])
    if variant == "bluehour":
        wn = nd(nt, "ShaderNodeTexWhiteNoise")
        wn.noise_dimensions = "3D"
        cu = math_node(nt, "FLOOR", math_node(nt, "DIVIDE", u, style["ww"]))
        cv = math_node(nt, "FLOOR", math_node(nt, "DIVIDE", v, style["fh"]))
        vec = nd(nt, "ShaderNodeCombineXYZ")
        link(nt, cu, vec.inputs[0])
        link(nt, cv, vec.inputs[1])
        link(nt, math_node(nt, "MULTIPLY", bf, 97.0), vec.inputs[2])
        link(nt, vec.outputs["Vector"], wn.inputs["Vector"])
        lit_thr = math_node(nt, "GREATER_THAN", wn.outputs["Value"], 0.64)
        lit = math_node(nt, "MULTIPLY", math_node(nt, "MULTIPLY", lit_thr, mask), math_node(nt, "GREATER_THAN", bf, 0.12))
        warm = nd(nt, "ShaderNodeMixRGB")
        warm.inputs["Fac"].default_value = 0.5
        warm.inputs["Color1"].default_value = (1.0, 0.52, 0.20, 1)
        warm.inputs["Color2"].default_value = (1.0, 0.74, 0.42, 1)
        link(nt, wn.outputs["Value"], warm.inputs["Fac"])
        link(nt, warm.outputs["Color"], b.inputs["Emission Color"])
        link(nt, math_node(nt, "MULTIPLY", lit, WINDOW_EMISSION), b.inputs["Emission Strength"])
    return m


def mat_roof():
    m, nt, b = new_mat("CTX_roof")
    col, _ = noise_color(nt, 0.4, (0.055, 0.056, 0.058, 1), (0.14, 0.135, 0.13, 1))
    link(nt, col, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.92
    bump = nd(nt, "ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.3
    bump.inputs["Distance"].default_value = 0.03
    n2 = nd(nt, "ShaderNodeTexNoise")
    n2.inputs["Scale"].default_value = 60.0
    n2.inputs["Detail"].default_value = 5.0
    link(nt, nt.nodes.new("ShaderNodeTexCoord").outputs["Object"], n2.inputs["Vector"])
    link(nt, n2.outputs["Fac"], bump.inputs["Height"])
    link(nt, bump.outputs["Normal"], b.inputs["Normal"])
    return m


def mat_foliage(variant, seed):
    m, nt, b = new_mat(f"CTX_foliage_{seed}")
    oi = nd(nt, "ShaderNodeObjectInfo")
    col, fac = noise_color(nt, 2.2, (0.020, 0.040, 0.012, 1), (0.075, 0.105, 0.030, 1), detail=6.0)
    yellow = nd(nt, "ShaderNodeMixRGB")
    yellow.inputs["Color1"].default_value = (0, 0, 0, 1)
    link(nt, col, yellow.inputs["Color1"])
    yellow.inputs["Color2"].default_value = (0.150, 0.115, 0.022, 1)
    thr = math_node(nt, "MULTIPLY", math_node(nt, "GREATER_THAN", oi.outputs["Random"], 0.80), 0.45)
    nz = nd(nt, "ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 3.0
    link(nt, nt.nodes.new("ShaderNodeTexCoord").outputs["Object"], nz.inputs["Vector"])
    link(nt, math_node(nt, "MULTIPLY", thr, nz.outputs["Fac"]), yellow.inputs["Fac"])
    link(nt, yellow.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.78
    bump = nd(nt, "ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.5
    bump.inputs["Distance"].default_value = 0.12
    vor = nd(nt, "ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 9.0
    link(nt, nt.nodes.new("ShaderNodeTexCoord").outputs["Object"], vor.inputs["Vector"])
    link(nt, vor.outputs["Distance"], bump.inputs["Height"])
    link(nt, bump.outputs["Normal"], b.inputs["Normal"])
    return m


# ------------------------------------------------------------------ mesh helpers
def mesh_object(name, verts, faces, mats, uv=None, brand=None, smooth=False, coll=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in verts], [], [tuple(map(int, f)) for f in faces])
    me.update(calc_edges=True)
    for m in mats:
        me.materials.append(m)
    if uv is not None:
        layer = me.uv_layers.new(name="UVMap")
        flat = np.asarray(uv, dtype=np.float32).reshape(-1)
        layer.data.foreach_set("uv", flat)
    if brand is not None:
        att = me.attributes.new(name="brand", type="FLOAT", domain="POINT")
        att.data.foreach_set("value", np.asarray(brand, dtype=np.float32))
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    (coll or bpy.context.collection).objects.link(ob)
    return ob


def tess(poly_shell, holes=()):
    """Triangulate a 2D polygon with holes -> (verts2d, tris)."""
    loops = [[Vector((x, y, 0.0)) for x, y in poly_shell]] + [[Vector((x, y, 0.0)) for x, y in h] for h in holes]
    if loops[0][0] == loops[0][-1]:
        loops[0] = loops[0][:-1]
    loops = [l[:-1] if (len(l) > 1 and l[0] == l[-1]) else l for l in loops]
    tris = tessellate_polygon(loops)
    pts = [(p.x, p.y) for l in loops for p in l]
    return pts, tris


def L(x, y):
    return x - fr.LOCAL_ORIGIN[0], y - fr.LOCAL_ORIGIN[1]


def flat_surface(name, rings, z, mat, coll=None):
    """rings: list of {'shell','holes'} in cache XY.  Returns object or None."""
    verts, faces = [], []
    for r in rings:
        shell = [L(*p) for p in r["shell"]]
        holes = [[L(*p) for p in h] for h in r.get("holes", [])]
        try:
            pts, tris = tess(shell, holes)
        except Exception:  # degenerate polygon
            continue
        base = len(verts)
        verts.extend((x, y, z) for x, y in pts)
        for t in tris:
            a, b, c = (base + t[0], base + t[1], base + t[2])
            # force upward normal
            ax, ay = verts[a][0], verts[a][1]
            bx, by = verts[b][0], verts[b][1]
            cx, cy = verts[c][0], verts[c][1]
            if (bx - ax) * (cy - ay) - (by - ay) * (cx - ax) < 0:
                b, c = c, b
            faces.append((a, b, c))
    if not faces:
        return None
    return mesh_object(name, verts, faces, [mat], coll=coll)


# ------------------------------------------------------------------ trees
def canopy_mesh(name, seed, subdiv=4):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=1.0)
    rng_off = Vector((h01(f"{seed}a") * 40, h01(f"{seed}b") * 40, h01(f"{seed}c") * 40))
    for v in bm.verts:
        p = v.co.copy()
        d = p.normalized()
        n1 = mnoise.noise(d * 1.6 + rng_off)
        n2 = mnoise.noise(d * 5.0 + rng_off * 1.7)
        n3 = mnoise.noise(d * 13.0 + rng_off * 2.3)
        r = 1.0 + 0.22 * n1 + 0.10 * n2 + 0.045 * n3
        v.co = d * r
        v.co.z *= 0.84
        if v.co.z < -0.45:  # flatten the underside
            v.co.z = -0.45 + (v.co.z + 0.45) * 0.35
    bm.normal_update()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def trunk_mesh(name):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=9, radius1=0.5, radius2=0.26, depth=1.0)
    for v in bm.verts:
        v.co.z += 0.5  # base at z=0, top at z=1
    bm.normal_update()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


class TreeLib:
    def __init__(self, variant):
        self.canopies = [canopy_mesh(f"CTX_canopy_{i}", f"canopy{i}") for i in range(4)]
        self.fol = [mat_foliage(variant, i) for i in range(2)]
        self.trunk = trunk_mesh("CTX_trunk")
        self.bark = mat_flat("CTX_bark", (0.075, 0.052, 0.036, 1), 0.9)
        for me in self.canopies:
            me.materials.append(self.fol[0])
        self.trunk.materials.append(self.bark)
        self.coll = bpy.data.collections.new("CTX_TREES")
        bpy.context.scene.collection.children.link(self.coll)
        self.count = 0

    def place(self, x, y, z0, trunk_h, crown_rx, crown_ry, crown_h, key):
        i = int(h01(key) * 4) % 4
        rot = h01(key + "r") * math.tau
        tr = bpy.data.objects.new(f"CTX_trunk_{self.count}", self.trunk)
        tr.location = (x, y, z0)
        tr.scale = (max(0.18, crown_rx * 0.11), max(0.18, crown_rx * 0.11), trunk_h + crown_h * 0.25)
        tr["id_class"] = "context_tree"
        self.coll.objects.link(tr)
        cr = bpy.data.objects.new(f"CTX_canopy_{self.count}", self.canopies[i])
        # unit canopy spans z in about [-0.45, +0.84] (x0.77*crown_h): bottom sits on the trunk top
        cr.location = (x, y, z0 + trunk_h + crown_h * 0.35)
        cr.rotation_euler = (0, 0, rot)
        cr.scale = (crown_rx, crown_ry, crown_h * 0.77)
        cr["id_class"] = "context_tree"
        self.coll.objects.link(cr)
        self.count += 1


# ------------------------------------------------------------------ scene
def footprint(rec, V, F):
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    tri = F[rec["f0"]:rec["f0"] + rec["nf"]]
    polys = []
    for t in tri:
        p = V[t][:, :2]
        pg = Polygon(p)
        if pg.is_valid and pg.area > 1e-6:
            polys.append(pg)
    return unary_union(polys)


def build_scene(V, F, records, pack, variant, width, height, samples, device, exposure_override=None, haze=0.0,
                sky_strength=1.0):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    dev = t14o.configure_cycles_device(scene, device)
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.035 if samples <= 32 else 0.012
    scene.cycles.max_bounces = 10
    scene.cycles.diffuse_bounces = 4
    scene.cycles.glossy_bounces = 5
    scene.cycles.transmission_bounces = 8
    scene.cycles.transparent_max_bounces = 8
    scene.cycles.caustics_reflective = False
    scene.cycles.caustics_refractive = False
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = width, height, 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "16"
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"
    for look in ("AgX - Medium High Contrast", "Medium High Contrast", "AgX - Base Contrast", "None"):
        try:
            scene.view_settings.look = look
            break
        except (TypeError, ValueError):
            continue
    scene.view_settings.exposure = exposure_override if exposure_override is not None else EXPOSURE_DEFAULT[variant]

    ARCH = t14o.ARCHITECTURE_KINDS
    design = [o for o in records if o.get("kind") in ARCH]
    vmin = np.min([V[o["v0"]:o["v0"] + o["nv"]].min(axis=0) for o in design], axis=0)
    vmax = np.max([V[o["v0"]:o["v0"] + o["nv"]].max(axis=0) for o in design], axis=0)
    origin = np.array([(vmin[0] + vmax[0]) / 2, (vmin[1] + vmax[1]) / 2, vmin[2]], dtype=float)
    assert np.allclose(origin, fr.LOCAL_ORIGIN, atol=1e-6), f"origin drift {origin} vs {fr.LOCAL_ORIGIN}"
    mats = t14o.materials(variant)
    arch_objs, site_objs, tree_pairs = [], [], {}
    counts = {}
    # ---- verified architecture + cache site objects (unchanged triangles) ----
    for rec in records:
        kind = str(rec.get("kind", ""))
        if kind in ARCH or kind == "site":
            v0, nv, f0, nf = (int(rec[k]) for k in ("v0", "nv", "f0", "nf"))
            verts = np.asarray(V[v0:v0 + nv], dtype=np.float64) - origin
            faces = np.asarray(F[f0:f0 + nf], dtype=np.int64) - v0
            me = bpy.data.meshes.new(f"CACHED_MESH_{len(arch_objs) + len(site_objs):06d}")
            me.from_pydata(verts.tolist(), [], faces.tolist())
            me.update(calc_edges=True)
            ob = bpy.data.objects.new(str(rec["name"]), me)
            bpy.context.collection.objects.link(ob)
            ob["source_kind"] = kind
            ob["design_authority"] = "CACHED_MESH_GEOMETRY_ONLY"
            ob["id_class"] = "design_architecture" if kind in ARCH else "design_site"
            key = t14o.material_class(rec)
            me.materials.append(mats[key])
            if kind == "tube_wall":
                for p in me.polygons:
                    p.use_smooth = True
            (arch_objs if kind in ARCH else site_objs).append((ob, rec))
            counts[kind] = counts.get(kind, 0) + 1
        elif kind == "tree":
            tree_pairs.setdefault(rec["name"], rec)
    # ---- camera (identical formula to T14O) ----
    size = vmax - vmin
    size_xy, tower_h = float(max(size[0], size[1])), float(size[2])
    target = Vector((0.0, 0.0, tower_h * fr.CAMERA_TARGET_HEIGHT_RATIO))
    az = math.radians(fr.CAMERA_AZIMUTH_DEG)
    dist = max(size_xy * 2.8, tower_h * fr.CAMERA_DISTANCE_SCALE)
    cam_xyz = Vector((math.cos(az) * dist, -math.sin(az) * dist, tower_h * fr.CAMERA_HEIGHT_RATIO))
    cd = bpy.data.cameras.new("PROPOSED_ARCHITECTURAL_CAMERA")
    cam = bpy.data.objects.new("PROPOSED_ARCHITECTURAL_CAMERA", cd)
    bpy.context.collection.objects.link(cam)
    cam.location = cam_xyz
    cd.type, cd.lens, cd.clip_end = "PERSP", fr.CAMERA_LENS_MM, 100000
    t14o._aim(cam, target)
    scene.camera = cam

    # ---- ground, roads, sidewalks, markings, greens ----
    asphalt, paving, grass = mat_asphalt(variant), mat_paving(variant), mat_grass()
    white = mat_flat("CTX_marking_white", (0.62, 0.62, 0.60, 1), 0.55)
    yellow = mat_flat("CTX_marking_yellow", (0.62, 0.45, 0.04, 1), 0.55)
    ctx_coll = bpy.data.collections.new("CTX_SITE_CONTEXT")
    scene.collection.children.link(ctx_coll)
    from shapely.geometry import LineString, Polygon, box
    from shapely.ops import unary_union

    site_poly = Polygon(pack["site_polygon"])
    sunk = unary_union([footprint(r, V, F) for r, _ in [(rec, None) for _, rec in site_objs if "sunken" in rec["name"].lower()]])
    big = box(fr.LOCAL_ORIGIN[0] - 2200, fr.LOCAL_ORIGIN[1] - 2200, fr.LOCAL_ORIGIN[0] + 2200, fr.LOCAL_ORIGIN[1] + 2200)
    ground = big.difference(sunk) if not sunk.is_empty else big

    def rings_of_geom(g):
        out = []
        for p in (g.geoms if hasattr(g, "geoms") else [g]):
            if p.geom_type == "Polygon" and p.area > 0.5:
                out.append({"shell": list(p.exterior.coords), "holes": [list(h.coords) for h in p.interiors]})
        return out

    # base ground is already in cache XY (big polygon is built in cache frame via LOCAL_ORIGIN offset)
    def tag(o, cls):
        if o is not None:
            o["id_class"] = cls
        return o

    tag(flat_surface("CTX_ground_base", rings_of_geom(ground), BASE_Z, paving, ctx_coll), "context_ground")
    carr = [r for r in pack["carriageway_polygons"]]
    cw = unary_union([Polygon(r["shell"], r["holes"]) for r in carr]).difference(site_poly) if carr else None
    if cw is not None and not cw.is_empty:
        tag(flat_surface("CTX_roads", rings_of_geom(cw), ROAD_Z, asphalt, ctx_coll), "context_road")
    walks = [Polygon(r["shell"], r["holes"]) for r in pack["sidewalk_polygons"]]
    if walks:
        wk = unary_union(walks).difference(site_poly)
        tag(flat_surface("CTX_sidewalks", rings_of_geom(wk), WALK_Z, paving, ctx_coll), "context_sidewalk")
    gr = [Polygon(g["ring"]).buffer(0) for g in pack["greens"] if g["kind"] in ("garden", "park", "grass", "meadow", "forest", "grassland", "wetland")]
    if gr:
        gu = unary_union(gr).difference(site_poly)
        if cw is not None:
            gu = gu.difference(cw)
        tag(flat_surface("CTX_greens", rings_of_geom(gu), GREEN_Z, grass, ctx_coll), "context_green")

    # lane markings: dashed centre / lane lines on two-way primary & tertiary carriageways, zebra at crossings
    def dashes(line_xy, offset, dash=3.0, gap=5.0, wmark=0.15, solid=False):
        ls = LineString(line_xy)
        if offset:
            ls = ls.parallel_offset(offset, "left", join_style=2)
            if ls.geom_type != "LineString":
                return []
        out, d = [], 0.0
        step = ls.length if solid else dash
        while d < ls.length:
            a, b = ls.interpolate(d), ls.interpolate(min(d + step, ls.length))
            dx, dy = b.x - a.x, b.y - a.y
            Ln = math.hypot(dx, dy)
            if Ln > 0.2:
                nx, ny = -dy / Ln * wmark / 2, dx / Ln * wmark / 2
                out.append([(a.x + nx, a.y + ny), (b.x + nx, b.y + ny), (b.x - nx, b.y - ny), (a.x - nx, a.y - ny)])
            d += step + (0 if solid else gap)
        return out

    yv, wv = [], []
    for r in pack["carriageways"]:
        if r["class"] not in ("primary", "secondary", "tertiary") or r["bridge"]:
            continue
        if r["oneway"]:
            n = r["lanes"]
            for k in range(1, n):
                wv += dashes(r["line"], (k - n / 2.0) * 3.25)
        else:
            yv += dashes(r["line"], 0.12, solid=True) + dashes(r["line"], -0.12, solid=True)
            n = max(1, r["lanes"] // 2)
            for k in range(1, n):
                wv += dashes(r["line"], k * 3.25) + dashes(r["line"], -k * 3.25)
    for c in pack["crossings"]:
        ls = LineString(c["line"])
        if ls.length < 3 or ls.length > 40:
            continue
        s = 0.0
        while s < ls.length:
            p, q = ls.interpolate(s), ls.interpolate(min(s + 0.5, ls.length))
            dx, dy = q.x - p.x, q.y - p.y
            Ln = math.hypot(dx, dy)
            if Ln > 0.1:
                ux, uy = dx / Ln, dy / Ln
                nx, ny = -uy * 1.6, ux * 1.6
                wv.append([(p.x + nx, p.y + ny), (q.x + nx, q.y + ny), (q.x - nx, q.y - ny), (p.x - nx, p.y - ny)])
            s += 1.0

    def mark_obj(name, polys, mat):
        rings = [{"shell": r, "holes": []} for r in polys if len(r) >= 4]
        if rings:
            o = flat_surface(name, rings, MARK_Z, mat, ctx_coll)
            if o:
                o["id_class"] = "context_road"

    mark_obj("CTX_marking_white", wv, white)
    mark_obj("CTX_marking_yellow", yv, yellow)

    # ---- context buildings ----
    style_mats = [mat_facade(s, variant) for s in STYLES]
    roof_mat = mat_roof()
    groups = {i: dict(v=[], f=[], uv=[], br=[]) for i in range(len(STYLES))}
    roofs = dict(v=[], f=[])
    n_bld = 0
    for b in pack["buildings"]:
        ring = [(x, y) for x, y in b["ring"]]
        if len(ring) < 4:
            continue
        h = float(b["height_m"])
        area = Polygon(ring).area
        if Polygon(ring).exterior.is_ccw is False:
            ring = ring[::-1]
        hh = h01(b["id"])
        if b.get("canopy"):
            si = 5
        elif h > 45 and hh < 0.5:
            si = 2
        else:
            r = h01(b["id"] + "s")
            si = [0, 0, 1, 1, 3, 5, 4, 2][int(r * 8) % 8] if h > 20 else [1, 1, 3, 5, 0, 5, 1, 3][int(r * 8) % 8]
        g = groups[si]
        z0 = G if not b.get("canopy") else G + 3.6
        z1 = z0 + (h if not b.get("canopy") else 0.35)
        cum = 0.0
        for i in range(len(ring) - 1):
            (x0, y0), (x1, y1) = L(*ring[i]), L(*ring[i + 1])
            ln = math.hypot(x1 - x0, y1 - y0)
            if ln < 0.15:
                continue
            k = len(g["v"])
            g["v"] += [(x0, y0, z0), (x1, y1, z0), (x1, y1, z1), (x0, y0, z1)]
            g["f"].append((k, k + 1, k + 2, k + 3))
            g["uv"] += [(cum, 0.0), (cum + ln, 0.0), (cum + ln, z1 - z0), (cum, z1 - z0)]
            g["br"] += [hh] * 4
            cum += ln
        try:
            pts, tris = tess([L(*p) for p in ring[:-1]])
        except Exception:
            pts, tris = [], []
        base = len(roofs["v"])
        roofs["v"] += [(x, y, z1) for x, y in pts]
        for t in tris:
            a, bb, c = base + t[0], base + t[1], base + t[2]
            ax, ay = roofs["v"][a][:2]; bx, by = roofs["v"][bb][:2]; cx, cy = roofs["v"][c][:2]
            if (bx - ax) * (cy - ay) - (by - ay) * (cx - ax) < 0:
                bb, c = c, bb
            roofs["f"].append((a, bb, c))
        # parapet lip (0.9 m) along the roof edge
        if not b.get("canopy") and h > 8:
            kk = len(roofs["v"])
            for i in range(len(ring) - 1):
                (x0, y0), (x1, y1) = L(*ring[i]), L(*ring[i + 1])
                if math.hypot(x1 - x0, y1 - y0) < 0.15:
                    continue
                k0 = len(roofs["v"])
                roofs["v"] += [(x0, y0, z1), (x1, y1, z1), (x1, y1, z1 + 0.9), (x0, y0, z1 + 0.9)]
                roofs["f"].append((k0, k0 + 1, k0 + 2, k0 + 3))
        # rooftop plant boxes (look-dev clutter), density grows with roof area
        if area > 150 and h > 12 and not b.get("canopy"):
            nb = min(14, 1 + int(h01(b["id"] + "n") * 3) + int(area / 300))
            cxy = Polygon([L(*p) for p in ring]).representative_point()
            for j in range(nb):
                bw, bd, bh = 2.0 + 3 * h01(f"{b['id']}w{j}"), 2.0 + 3 * h01(f"{b['id']}d{j}"), 1.4 + 1.6 * h01(f"{b['id']}h{j}")
                ox = (h01(f"{b['id']}x{j}") - 0.5) * math.sqrt(area) * 0.8
                oy = (h01(f"{b['id']}y{j}") - 0.5) * math.sqrt(area) * 0.8
                cx_, cy_ = cxy.x + ox, cxy.y + oy
                if not Polygon([L(*p) for p in ring]).contains(Polygon([(cx_ - bw / 2, cy_ - bd / 2), (cx_ + bw / 2, cy_ - bd / 2), (cx_ + bw / 2, cy_ + bd / 2), (cx_ - bw / 2, cy_ + bd / 2)])):
                    continue
                k = len(roofs["v"])
                for zz in (z1, z1 + bh):
                    roofs["v"] += [(cx_ - bw / 2, cy_ - bd / 2, zz), (cx_ + bw / 2, cy_ - bd / 2, zz), (cx_ + bw / 2, cy_ + bd / 2, zz), (cx_ - bw / 2, cy_ + bd / 2, zz)]
                roofs["f"] += [(k + 4, k + 5, k + 6, k + 7), (k, k + 1, k + 5, k + 4), (k + 1, k + 2, k + 6, k + 5), (k + 2, k + 3, k + 7, k + 6), (k + 3, k, k + 4, k + 7)]
        n_bld += 1
    for si, g in groups.items():
        if g["f"]:
            o = mesh_object(f"CTX_buildings_{STYLES[si]['name']}", g["v"], g["f"], [style_mats[si]], uv=g["uv"], brand=g["br"], coll=ctx_coll)
            o["id_class"] = "context_building"
    if roofs["f"]:
        o = mesh_object("CTX_roofs", roofs["v"], roofs["f"], [roof_mat], coll=ctx_coll)
        o["id_class"] = "context_building"

    # ---- trees: cache design plantings (same positions / volumes) + assumed street trees ----
    lib = TreeLib(variant)
    n_design_trees = 0
    names = sorted(tree_pairs)
    for name in names:
        if not name.startswith("Cylinder"):
            continue
        suffix = name[len("Cylinder"):]
        trunk, can = tree_pairs[name], tree_pairs.get("Icosphere" + suffix)
        if can is None:
            continue
        cb = can["bbox"]
        cx_, cy_ = (cb[0] + cb[2]) / 2, (cb[1] + cb[3]) / 2
        rx, ry = (cb[2] - cb[0]) / 2, (cb[3] - cb[1]) / 2
        z_c0, z_c1 = float(can["zmin"]), float(can["zmax"])
        lx, ly, lz = fr.cache_to_local(cx_, cy_, float(trunk["zmin"]))
        lib.place(lx, ly, lz, max(z_c0 - float(trunk["zmin"]), 0.5), rx * 1.06, ry * 1.06, (z_c1 - z_c0) * 1.12, f"design{name}")
        n_design_trees += 1
    n_street = 0
    for t in pack["street_trees"]:
        lx, ly = L(*t["xy"])
        s = t["scale"]
        lib.place(lx, ly, G, 3.0 * s, 2.5 * s, 2.5 * s, 4.4 * s, f"st{t['xy']}")
        n_street += 1

    # ---- sky, sun, haze ----
    lat, lon = fr.OSM_ORIGIN_LAT, fr.OSM_ORIGIN_LON
    sun_az, sun_el = fr.sun_position(lat, lon, SUN_TIME[variant])
    world = bpy.data.worlds.new("C_T14Q_SKY_REAL_SUN")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = "NISHITA"
    sky.sun_elevation = math.radians(max(sun_el, -12.0))
    sky.sun_rotation = 0.0
    sky.sun_disc = True
    sky.sun_size = math.radians(0.545)
    sky.sun_intensity = 1.0
    sky.altitude = 40.0
    sky.air_density = 1.0
    sky.dust_density = 2.2 if variant == "daylight" else 1.6
    sky.ozone_density = 1.0
    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = sky_strength
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    # Cycles Nishita: sun direction = (cos(el) sin(rot), cos(el) cos(rot), sin(el)), i.e. rotation is the compass
    # azimuth when world +Y is North (our cache world is East/North).  Verified in preview by shadow direction.
    sky.sun_rotation = math.radians(sun_az)
    check_az = sun_az
    # Optional unbounded world-volume haze.  OFF by default: an infinite homogeneous volume blacked out the
    # whole frame in the first test (rays to the sky never leave the medium).  Aerial perspective is applied
    # in post from the DEPTH pass instead (see tools/t14q/postprocess).
    if haze > 0:
        vol = nt.nodes.new("ShaderNodeVolumeScatter")
        vol.inputs["Density"].default_value = haze
        vol.inputs["Anisotropy"].default_value = 0.35
        vol.inputs["Color"].default_value = (0.82, 0.88, 1.0, 1)
        nt.links.new(vol.outputs["Volume"], out.inputs["Volume"])

    n_lamps = 0
    if variant == "bluehour":
        # ASSUMED street lamps (OSM has none; field photos show cobra-head lamps): every ~30 m along the
        # kerb side of primary/secondary/tertiary carriageways.  Visualization assumption, not a survey.
        bulb_me = bpy.data.meshes.new("CTX_lamp_bulb")
        bmb = bmesh.new()
        bmesh.ops.create_icosphere(bmb, subdivisions=2, radius=0.35)
        bmb.to_mesh(bulb_me)
        bmb.free()
        bulb_me.materials.append(mat_flat("CTX_lamp_glow", (1, 0.7, 0.4, 1), 0.4, emission=(1.0, 0.68, 0.38, 1), strength=30.0))
        lamp_coll = bpy.data.collections.new("CTX_LAMPS_ASSUMED")
        scene.collection.children.link(lamp_coll)
        for r in pack["carriageways"]:
            if r["class"] not in ("primary", "secondary", "tertiary") or r["bridge"]:
                continue
            ls = LineString(r["line"])
            sw = 0.0
            off = r["width_m"] / 2.0 + 0.9
            d = 8.0 + 22.0 * h01(r["id"] + "l")
            side = 1
            while d < ls.length:
                p, q = ls.interpolate(d), ls.interpolate(min(d + 1.0, ls.length))
                dx, dy = q.x - p.x, q.y - p.y
                Ln = math.hypot(dx, dy) or 1.0
                lx, ly = L(p.x - side * dy / Ln * off, p.y + side * dx / Ln * off)
                bo = bpy.data.objects.new(f"CTX_lamp_{n_lamps}", bulb_me)
                bo.location = (lx, ly, G + 9.0)
                bo["id_class"] = "context_tree"
                lamp_coll.objects.link(bo)
                ld = bpy.data.lights.new(f"CTX_lamplight_{n_lamps}", "POINT")
                ld.energy, ld.color, ld.shadow_soft_size = 900.0, (1.0, 0.70, 0.42), 0.35
                lo = bpy.data.objects.new(f"CTX_lamplight_{n_lamps}", ld)
                lo.location = (lx, ly, G + 8.8)
                lamp_coll.objects.link(lo)
                n_lamps += 1
                side = -side
                d += 28.0 + 6.0 * h01(f"{r['id']}{d}d")
        for index, z_ratio in enumerate((0.17, 0.35, 0.53, 0.72)):
            ld = bpy.data.lights.new(f"LOOKDEV_INTERIOR_{index:02d}", "AREA")
            lo = bpy.data.objects.new(f"LOOKDEV_INTERIOR_{index:02d}", ld)
            bpy.context.collection.objects.link(lo)
            lo.location = (0.0, 0.0, tower_h * z_ratio)
            ld.shape, ld.size, ld.energy, ld.color = "DISK", max(8.0, size_xy * 0.24), 1650, (1.0, 0.54, 0.28)

    return {
        "cycles_device": dev,
        "source_coordinate_origin_m": origin.tolist(),
        "architecture_kind_counts": {k: v for k, v in counts.items() if k in ARCH},
        "cache_site_objects_kept": counts.get("site", 0),
        "design_trees_replaced_with_realistic_canopies": n_design_trees,
        "street_lamps_assumed": n_lamps,
        "context": {"buildings": n_bld, "street_trees_assumed": n_street, "carriageway_segments": len(pack["carriageways"]),
                    "crossings": len(pack["crossings"]), "sidewalk_polygons": len(pack["sidewalk_polygons"])},
        "sun": {"time_local": SUN_TIME[variant].isoformat(), "azimuth_deg": sun_az, "elevation_deg": sun_el,
                "blender_sun_azimuth_check_deg": check_az, "status": "ASSUMED DATE/TIME; real solar geometry for the lot position"},
        "camera": {"location_local_m": list(cam.location), "rotation_euler": list(cam.rotation_euler), "lens_mm": cd.lens,
                   "geo": fr.g002_camera()["camera_lonlat"], "view_bearing_deg": fr.g002_camera()["view_bearing_deg"]},
        "_arch_objs": arch_objs,
        "origin": origin,
    }


def verify_building_untouched(arch_objs, V, F, origin):
    """Read the Blender meshes back and compare with the cache arrays (float32 tolerance)."""
    max_dv, nv_tot, nf_tot, ok = 0.0, 0, 0, True
    for ob, rec in arch_objs:
        me = ob.data
        v0, nv, f0, nf = (int(rec[k]) for k in ("v0", "nv", "f0", "nf"))
        got = np.empty(len(me.vertices) * 3, dtype=np.float32)
        me.vertices.foreach_get("co", got)
        want = (np.asarray(V[v0:v0 + nv]) - origin).astype(np.float32).reshape(-1)
        ok &= len(me.vertices) == nv and len(me.polygons) == nf
        max_dv = max(max_dv, float(np.abs(got - want).max()))
        nv_tot += len(me.vertices)
        nf_tot += len(me.polygons)
    return {"objects": len(arch_objs), "vertices": nv_tot, "triangles": nf_tot, "counts_match_cache": bool(ok),
            "max_vertex_deviation_m": max_dv, "status": "UNCHANGED" if ok and max_dv < 1e-3 else "CHANGED_REJECT"}


def scene_fingerprint():
    rows = []
    for ob in bpy.data.objects:
        if ob.type != "MESH" or ob.name.startswith("CTX_lamp_"):  # Blue-Hour-only assumed lamps are lighting, not geometry
            continue
        bb = [tuple(round(c, 4) for c in v) for v in ob.bound_box]
        rows.append((ob.name, len(ob.data.vertices), len(ob.data.polygons), tuple(map(lambda x: round(x, 4), ob.location)), bb[0], bb[6]))
    rows.sort()
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest(), len(rows)


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", type=Path, required=True)
    ap.add_argument("--pack", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--variant", choices=("daylight", "bluehour"), default="daylight")
    ap.add_argument("--width", type=int, default=1600)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--device", choices=("auto", "cpu", "cuda", "optix"), default="auto")
    ap.add_argument("--exposure", type=float, default=None)
    ap.add_argument("--haze", type=float, default=0.0, help="world-volume scatter density (1/m); 0 = off")
    ap.add_argument("--sky-strength", type=float, default=None)
    ap.add_argument("--window-emission", type=float, default=None, help="blue-hour lit-window emission strength")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--aov", action="store_true", help="also render flat object-class ID and depth maps")
    return ap.parse_args(argv)


def render_aovs(out: Path, variant: str, width: int, height: int):
    scene = bpy.context.scene
    colors = {"design_architecture": (1, 0, 0), "design_site": (1, 0.5, 0), "context_building": (0, 0, 1), "context_road": (0.5, 0.5, 0.5),
              "context_sidewalk": (0.8, 0.8, 0.8), "context_ground": (0.3, 0.3, 0.3), "context_green": (0, 0.6, 0), "context_tree": (0, 1, 0)}
    emis = {}
    for k, c in colors.items():
        m = bpy.data.materials.new(f"ID_{k}")
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        e = nt.nodes.new("ShaderNodeEmission")
        e.inputs["Color"].default_value = (*c, 1)
        o = nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(e.outputs["Emission"], o.inputs["Surface"])
        emis[k] = m
    saved = {}
    for ob in bpy.data.objects:
        if ob.type == "MESH":
            saved[ob.name] = [s.material for s in ob.material_slots]
            cls = ob.get("id_class", "design_architecture")
            for s in ob.material_slots:
                s.material = emis.get(cls, emis["design_architecture"])
    scene.view_settings.view_transform, scene.view_settings.exposure = "Standard", 0.0
    for look in ("None", "AgX - Base Contrast"):
        try:
            scene.view_settings.look = look
            break
        except (TypeError, ValueError):
            continue
    scene.cycles.samples, scene.cycles.use_denoising, scene.cycles.use_adaptive_sampling = 8, False, False
    scene.render.image_settings.color_depth = "8"
    world = scene.world
    for n in world.node_tree.nodes:
        if n.type == "BACKGROUND":
            n.inputs["Color"].default_value = (0, 0, 0, 1)
            n.inputs["Strength"].default_value = 0.0
    for l in list(world.node_tree.links):
        if l.to_node.type == "OUTPUT_WORLD" and l.to_socket.name == "Volume":
            world.node_tree.links.remove(l)
    for n in world.node_tree.nodes:
        if n.type == "TEX_SKY":
            pass
    scene.render.filepath = str(out / f"G002_{variant}_ID.png")
    bpy.ops.render.render(write_still=True)
    # depth: emission = (viewZ - near)/(far - near)
    dm = bpy.data.materials.new("DEPTH")
    dm.use_nodes = True
    nt = dm.node_tree
    nt.nodes.clear()
    cdn = nt.nodes.new("ShaderNodeCameraData")
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value, mr.inputs["From Max"].default_value = 150.0, 1800.0
    nt.links.new(cdn.outputs["View Z Depth"], mr.inputs["Value"])
    e = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(mr.outputs["Result"], e.inputs["Color"])
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(e.outputs["Emission"], o.inputs["Surface"])
    for ob in bpy.data.objects:
        if ob.type == "MESH":
            for s in ob.material_slots:
                s.material = dm
    scene.render.image_settings.color_depth = "16"
    scene.render.filepath = str(out / f"G002_{variant}_DEPTH.png")
    bpy.ops.render.render(write_still=True)


def main():
    args = parse()
    out = args.out_dir.resolve()
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"Refusing to overwrite nonempty folder: {out}")
    report = validate_cache(args.cache_dir.resolve(), t14o.EXPECTED_CACHE_SHA, t14o.EXPECTED_OBJECTS_SHA)
    if report["status"] != "CACHE_INDEX_VALID":
        raise RuntimeError("SOURCE_VERIFICATION_FAILED: " + json.dumps(report, ensure_ascii=False))
    with np.load(args.cache_dir / "model_world.npz", allow_pickle=False) as d:
        V, F = d["V"], d["F"]
    meta = json.loads((args.cache_dir / "model_objects.json").read_text(encoding="utf-8"))
    pack = json.loads(args.pack.read_text(encoding="utf-8"))
    global WINDOW_EMISSION
    if args.window_emission is not None:
        WINDOW_EMISSION = args.window_emission
    audit = build_scene(V, F, meta["objects"], pack, args.variant, args.width, args.height, args.samples, args.device,
                        args.exposure, args.haze,
                        args.sky_strength if args.sky_strength is not None else SKY_STRENGTH_DEFAULT[args.variant])
    arch_objs, origin = audit.pop("_arch_objs"), audit.pop("origin")
    audit["building_mesh_verification"] = verify_building_untouched(arch_objs, V, F, origin)
    if audit["building_mesh_verification"]["status"] != "UNCHANGED":
        raise RuntimeError("BUILDING_MESH_CHANGED: " + json.dumps(audit["building_mesh_verification"]))
    fp, n = scene_fingerprint()
    audit["scene_fingerprint_sha256"], audit["mesh_object_count"] = fp, n
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / f"G002_{args.variant}_SITE_CONTEXT.blend"))
    if not args.no_render:
        bpy.context.scene.render.filepath = str(out / f"G002_{args.variant}_SITE_CONTEXT_BASE.png")
        t0 = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        audit["render_seconds"] = round(time.perf_counter() - t0, 2)
        if args.aov:
            render_aovs(out, args.variant, args.width, args.height)
    audit.update({
        "variant": args.variant,
        "render_settings": {"width_px": args.width, "height_px": args.height, "samples": args.samples,
                            "blender_version": bpy.app.version_string, "exposure": bpy.context.scene.view_settings.exposure},
        "source_geometry_verification": report,
        "status": "BLENDER_BASE_RENDER__LOOKDEV_CONTEXT__HUMAN_QA_PENDING",
        "context_pack": str(args.pack),
    })
    (out / f"G002_{args.variant}_site_context_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print("AUDIT_OK", out)


if __name__ == "__main__":
    main()

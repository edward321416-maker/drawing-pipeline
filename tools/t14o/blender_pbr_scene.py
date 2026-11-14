"""Build *real* Cycles geometry/PBR lighting from authoritative model cache.

Invoke with Blender, not system Python:
  blender -b --factory-startup -P tools/t14o/blender_pbr_scene.py -- \
    --cache-dir <real output/C_T14I_run/model_cache> \
    --out-dir <new, isolated T14O output> --variant daylight --samples 64

This reconstructs the exact cached triangle mesh, not a 'similar' AI tower.
Shaders, atmosphere, stage and camera are provisional VISUALIZATION proposals;
no unverified material or view is presented as authoritative design intent.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys

import bpy
import numpy as np
from mathutils import Vector

EXPECTED_CACHE_SHA = "992e2ec51ec17dc494ed2f99ddb11298671449dd6661d92df3b3536a0049537b"
EXPECTED_OBJECTS_SHA = "722dd7359e2f13534ff4ae91088ba8649e8a8f96b27c60f000ddb09c01106488"
ARCHITECTURE_KINDS = {
    "slab", "column", "core_wall", "tube_wall", "shaft", "stair", "ramp",
    "facade", "roof", "exterior_wall", "partition_wall", "door",
}
SITE_KINDS = {"site", "road", "sidewalk", "context_building", "exterior_space"}
SUGGESTED_CLASS = {
    "slab": "concrete_light", "core_wall": "concrete_light",
    "column": "concrete_light", "stair": "concrete_light", "ramp": "concrete_light",
    "roof": "concrete_light", "exterior_wall": "concrete_light",
    "partition_wall": "concrete_light", "tube_wall": "glass_neutral",
    "facade": "facade_neutral", "shaft": "metal_soft", "door": "metal_soft",
    "context_building": "context_gray", "site": "ground", "road": "pavement",
    "sidewalk": "pavement", "exterior_space": "ground",
}


def digest(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def build_material(name: str, rgba: tuple[float, float, float, float], roughness: float,
                   metallic: float = 0, transmission: float = 0) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = rgba
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    transmission_socket = "Transmission Weight" if "Transmission Weight" in bsdf.inputs else "Transmission"
    if transmission_socket in bsdf.inputs:
        bsdf.inputs[transmission_socket].default_value = transmission
    if transmission:
        bsdf.inputs["IOR"].default_value = 1.45
    return mat


def materials() -> dict[str, bpy.types.Material]:
    # These are presentation assumptions pending approval, NOT evidence of real specifications.
    return {
        "concrete_light": build_material("LOOKDEV_PROPOSED_concrete_rough", (0.59, 0.60, 0.58, 1), .64),
        "glass_neutral": build_material("LOOKDEV_PROPOSED_glazing", (.21, .32, .36, 1), .12, .03, .72),
        # A generic 'facade' label does not prove that the full surface is glass.
        "facade_neutral": build_material("LOOKDEV_PROPOSED_opaque_facade_pending_material_approval", (.48, .52, .50, 1), .44, .05),
        "metal_soft": build_material("LOOKDEV_PROPOSED_brushed_metal", (.43, .46, .47, 1), .26, .73),
        "context_gray": build_material("CONCEPT_CONTEXT_unsurveyed", (.48, .50, .49, 1), .76),
        "ground": build_material("CONCEPT_STAGE_ground", (.38, .39, .37, 1), .86),
        "pavement": build_material("CONCEPT_STAGE_pavement", (.24, .25, .25, 1), .90),
    }


def _aim(obj: bpy.types.Object, point: Vector) -> None:
    obj.rotation_euler = (point - obj.location).to_track_quat("-Z", "Y").to_euler()


def make_scene(v: np.ndarray, f: np.ndarray, records: list[dict], variant: str,
               samples: int, width: int, height: int) -> dict:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.render.image_settings.color_depth = "16"
    scene.view_settings.view_transform = "AgX"
    # Blender 4.x variants differ slightly in Look identifiers.
    look_names = [item.identifier for item in scene.view_settings.bl_rna.properties["look"].enum_items]
    if "Medium High Contrast" in look_names:
        scene.view_settings.look = "Medium High Contrast"
    elif look_names:
        scene.view_settings.look = look_names[0]
    scene.view_settings.exposure = -.10 if variant == "daylight" else .16
    scene.view_settings.gamma = 1.0
    scene.render.filepath = ""

    design = [o for o in records if o.get("kind") in ARCHITECTURE_KINDS]
    if not design:
        raise ValueError("BLOCKED: no authoritative architecture mesh found")
    vmin = np.min([v[o["v0"]:o["v0"]+o["nv"]].min(axis=0) for o in design], axis=0)
    vmax = np.max([v[o["v0"]:o["v0"]+o["nv"]].max(axis=0) for o in design], axis=0)
    origin = np.array([(vmin[0]+vmax[0])/2, (vmin[1]+vmax[1])/2, vmin[2]], dtype=float)
    mats = materials()
    categories: dict[str, int] = {}
    imported = 0
    # Preserve every source vertex and original triangle index, modulo global translation
    # to prevent numerical instabilities when coordinates are large.
    for rec in records:
        kind = str(rec.get("kind", "unknown"))
        if kind not in ARCHITECTURE_KINDS | SITE_KINDS:
            continue
        v0, nv, f0, nf = (int(rec[k]) for k in ("v0", "nv", "f0", "nf"))
        verts = np.asarray(v[v0:v0 + nv], dtype=np.float64) - origin
        faces = np.asarray(f[f0:f0 + nf], dtype=np.int64) - v0
        if len(verts) < 3 or not len(faces) or np.any(faces < 0) or np.any(faces >= nv):
            raise ValueError(f"BAD_FACES: {rec.get('name')}")
        mesh = bpy.data.meshes.new(f"CACHED_MESH_{imported:06d}")
        mesh.from_pydata(verts.tolist(), [], faces.tolist())
        mesh.update(calc_edges=True)
        obj = bpy.data.objects.new(str(rec.get("name") or f"source_{imported}"), mesh)
        bpy.context.collection.objects.link(obj)
        obj["source_kind"] = kind
        obj["source_floor"] = str(rec.get("floor", ""))
        obj["source_v0"] = v0
        obj["source_nv"] = nv
        obj["source_f0"] = f0
        obj["source_nf"] = nf
        obj["design_authority"] = "CACHED_MESH_GEOMETRY_ONLY"
        mesh.materials.append(mats[SUGGESTED_CLASS.get(kind, "context_gray")])
        categories[kind] = categories.get(kind, 0) + 1
        imported += 1

    size = vmax - vmin
    size_xy = float(max(size[0], size[1]))
    tower_height = float(size[2])
    # Camera is a 2-point *perspective* photograph; do not claim original G-002 match.
    target = Vector((0.0, 0.0, tower_height * .47))
    azimuth = math.radians(38)
    dist = max(size_xy * 2.8, tower_height * 2.85)
    cam_xyz = Vector((math.cos(azimuth) * dist, -math.sin(azimuth) * dist, target.z))
    camera_data = bpy.data.cameras.new("PROPOSED_ARCHITECTURAL_CAMERA")
    camera = bpy.data.objects.new("PROPOSED_ARCHITECTURAL_CAMERA", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = cam_xyz
    camera_data.type = "PERSP"  # photographic perspective with straight verticals
    camera_data.lens = 50
    camera_data.clip_end = 100000
    _aim(camera, target)
    scene.camera = camera

    # Ground elevation is anchored to the cached *1F slab*; absent datum means
    # no ground construction rather than an invented ground elevation.
    level_slabs = [r for r in design if r.get("kind") == "slab" and str(r.get("floor", "")).upper() == "1F"]
    ground_level = None
    if level_slabs and not any(r.get("kind") == "site" for r in records):
        ground_level = float(min(v[r["v0"]:r["v0"]+r["nv"], 2].min() for r in level_slabs) - origin[2])
        bpy.ops.mesh.primitive_plane_add(size=2, location=(0, 0, ground_level - .08))
        stage = bpy.context.object
        stage.name = "CONCEPT_STAGE_FIRST_FLOOR_DATUM__NOT_SURVEYED_TERRAIN"
        stage.scale = (max(250., size_xy * 3), max(250., size_xy * 3), 1)
        stage.data.materials.append(mats["ground"])

    world = bpy.data.worlds.new("LOOKDEV_SKY_NOT_SITE_VERIFIED")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    if variant == "daylight":
        sky = nt.nodes.new("ShaderNodeTexSky")
        sky.sky_type = "NISHITA"
        sky.sun_elevation = math.radians(32)
        sky.sun_rotation = math.radians(125)
        nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = .55
    else:
        bg.inputs["Color"].default_value = (.035, .067, .14, 1)
        bg.inputs["Strength"].default_value = .36
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

    sun_data = bpy.data.lights.new("LOOKDEV_SUN", "SUN")
    sun_obj = bpy.data.objects.new("LOOKDEV_SUN", sun_data)
    bpy.context.collection.objects.link(sun_obj)
    sun_obj.rotation_euler = (math.radians(36), math.radians(-15), math.radians(25))
    sun_data.energy = 2.3 if variant == "daylight" else .10
    sun_data.angle = math.radians(5.0 if variant == "daylight" else 11.0)

    area_data = bpy.data.lights.new("LOOKDEV_BOUNCE", "AREA")
    area_obj = bpy.data.objects.new("LOOKDEV_BOUNCE", area_data)
    bpy.context.collection.objects.link(area_obj)
    area_obj.location = (size_xy*.66, -size_xy*.64, tower_height*.91)
    _aim(area_obj, target)
    area_data.shape = "DISK"
    area_data.size = max(20., size_xy*.85)
    area_data.energy = 6500 if variant == "daylight" else 1400

    return {
        "cached_geometry_objects_imported": imported,
        "source_coordinate_origin_m": origin.tolist(),
        "source_architecture_bbox_m": {"min": vmin.tolist(), "max": vmax.tolist()},
        "source_height_m": tower_height,
        "source_kind_counts": dict(sorted(categories.items())),
        "camera": {
            "type": camera_data.type, "location_local_m": list(camera.location),
            "rotation_euler": list(camera.rotation_euler),
            "lens_mm": camera_data.lens,
            "relationship_to_G002_original": "NEW_VISUALIZATION_CAMERA__ORIGINAL_CAMERA_UNAVAILABLE",
        },
        "material_status": "LOOKDEV_ONLY__NOT_VERIFIED_CONSTRUCTION_SPEC",
        "ground_status": "DERIVED_FROM_1F_SLAB__NOT_SURVEYED_TERRAIN" if ground_level is not None else "GROUND_DATUM_NOT_FOUND",
        "ground_z_local_m": ground_level,
    }


def parse_arguments():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--variant", choices=("daylight", "bluehour"), default="daylight")
    ap.add_argument("--samples", type=int, default=48)
    ap.add_argument("--width", type=int, default=4800)
    ap.add_argument("--height", type=int, default=2700)
    ap.add_argument("--expected-sha", default=EXPECTED_CACHE_SHA)
    ap.add_argument("--expected-objects-sha", default=EXPECTED_OBJECTS_SHA)
    return ap.parse_args(argv)


def main():
    args = parse_arguments()
    if args.width < 640 or args.height < 360 or args.samples < 1:
        raise ValueError("Output dimensions/samples below valid minimum")
    out = args.out_dir.resolve()
    # No overwritten output files: fail closed unless the separate candidate folder is empty.
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(f"Refusing to overwrite nonempty candidate folder: {out}")
    cache = args.cache_dir.resolve()
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    from tools.t14o.cache_validation import validate_cache
    report = validate_cache(cache, args.expected_sha, args.expected_objects_sha)
    if report["status"] != "CACHE_INDEX_VALID":
        raise RuntimeError("SOURCE_VERIFICATION_FAILED: " + json.dumps(report, ensure_ascii=False))
    # Do not authorize a full building if key class/floor completeness is unverified.
    if report["z_span_m"] < 40 or report["floor_tag_count"] < 10:
        raise RuntimeError("FULL_TOWER_INSUFFICIENT: cached floors/height require investigation")
    missing = set(("slab", "core_wall", "column", "tube_wall")) - set(report["kinds"])
    if missing:
        raise RuntimeError("SOURCE_CLASSES_MISSING: " + ",".join(sorted(missing)))
    with np.load(cache / "model_world.npz", allow_pickle=False) as d:
        V, F = d["V"], d["F"]
    meta = json.loads((cache / "model_objects.json").read_text(encoding="utf-8"))
    scene_audit = make_scene(V, F, meta["objects"], args.variant, args.samples, args.width, args.height)
    out.mkdir(parents=True, exist_ok=True)
    bpy.context.scene.render.filepath = str(out / f"G002_{args.variant}_CYCLES_PBR_SOURCE_MESH.png")
    bpy.ops.wm.save_as_mainfile(filepath=str(out / f"G002_{args.variant}_SOURCE_MESH_LOOKDEV.blend"))
    bpy.ops.render.render(write_still=True)
    result = {
        "variant": args.variant, "status": "PBR_PREVIEW_ONLY__HUMAN_GEOMETRY_AND_VISUAL_QA_PENDING",
        "source_geometry_verification": report,
        "scene": scene_audit,
        "source_blender_file": str(out / f"G002_{args.variant}_SOURCE_MESH_LOOKDEV.blend"),
        "render_png": str(out / f"G002_{args.variant}_CYCLES_PBR_SOURCE_MESH.png"),
        "render_png_sha256": digest(out / f"G002_{args.variant}_CYCLES_PBR_SOURCE_MESH.png"),
    }
    (out / "pbr_render_audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"render": result["render_png"], "sha": result["render_png_sha256"], "status": result["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
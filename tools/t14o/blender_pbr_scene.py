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
import time

import bpy
import numpy as np
from mathutils import Vector

EXPECTED_CACHE_SHA = "992e2ec51ec17dc494ed2f99ddb11298671449dd6661d92df3b3536a0049537b"
EXPECTED_OBJECTS_SHA = "722dd7359e2f13534ff4ae91088ba8649e8a8f96b27c60f000ddb09c01106488"
ARCHITECTURE_KINDS = {
    "slab", "column", "core_wall", "tube_wall", "shaft", "stair", "ramp",
    "facade", "roof", "exterior_wall", "partition_wall", "door",
}
CONTEXT_KINDS = {
    "site", "road", "sidewalk", "context_building", "exterior_space", "tree",
}


def digest(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def build_material(name: str, rgba: tuple[float, float, float, float], roughness: float,
                   metallic: float = 0, transmission: float = 0,
                   bump_strength: float = 0.0, bump_scale: float = 3.0,
                   color_variation: float = 0.0, bevel_radius: float = 0.0,
                   emission: tuple[float, float, float, float] | None = None,
                   emission_strength: float = 0.0) -> bpy.types.Material:
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
    if emission and "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = emission
        bsdf.inputs["Emission Strength"].default_value = emission_strength
    if bump_strength or color_variation:
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        geometry = nodes.new("ShaderNodeNewGeometry")
        noise = nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = bump_scale
        noise.inputs["Detail"].default_value = 3.0
        noise.inputs["Roughness"].default_value = 0.62
        links.new(geometry.outputs["Position"], noise.inputs["Vector"])
        if color_variation:
            ramp = nodes.new("ShaderNodeValToRGB")
            ramp.color_ramp.elements[0].position = .22
            ramp.color_ramp.elements[1].position = .78
            low = tuple(max(0.0, c * (1.0 - color_variation)) for c in rgba[:3]) + (1.0,)
            high = tuple(min(1.0, c * (1.0 + color_variation)) for c in rgba[:3]) + (1.0,)
            ramp.color_ramp.elements[0].color = low
            ramp.color_ramp.elements[1].color = high
            links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
            links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
        if bump_strength:
            bump = nodes.new("ShaderNodeBump")
            bump.inputs["Strength"].default_value = bump_strength
            bump.inputs["Distance"].default_value = 0.035
            links.new(noise.outputs["Fac"], bump.inputs["Height"])
            if bevel_radius:
                bevel = nodes.new("ShaderNodeBevel")
                bevel.inputs["Radius"].default_value = bevel_radius
                bevel.samples = 3
                links.new(bevel.outputs["Normal"], bump.inputs["Normal"])
            links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    elif bevel_radius:
        bevel = mat.node_tree.nodes.new("ShaderNodeBevel")
        bevel.inputs["Radius"].default_value = bevel_radius
        bevel.samples = 3
        mat.node_tree.links.new(bevel.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def materials(variant: str) -> dict[str, bpy.types.Material]:
    """Look-development materials, never construction-spec evidence.

    The source registry and legacy G-002 asset identify semantic groups such as
    glass, mullion, louver, band and spandrel.  We use those labels to avoid the
    previous all-opaque facade, while retaining an explicit provisional status.
    """
    facade_emission = (1.0, 0.56, 0.27, 1.0) if variant == "bluehour" else None
    facade_emission_strength = 0.040 if variant == "bluehour" else 0.0
    return {
        "concrete": build_material(
            "LOOKDEV_PROPOSED_fine_boardformed_concrete", (.235, .245, .235, 1), .72,
            bump_strength=.14, bump_scale=2.4, color_variation=.075, bevel_radius=.035,
        ),
        "concrete_dark": build_material(
            "LOOKDEV_PROPOSED_core_concrete", (.13, .145, .145, 1), .78,
            bump_strength=.12, bump_scale=2.0, color_variation=.06, bevel_radius=.03,
        ),
        "glass_facade": build_material(
            "LOOKDEV_PROPOSED_facade_glazing", (.035, .085, .12, 1), .16, .02, .82,
            emission=facade_emission, emission_strength=facade_emission_strength,
        ),
        "glass_tube": build_material(
            "LOOKDEV_PROPOSED_tube_glazing", (.055, .14, .16, 1), .13, .02, .76,
        ),
        "metal_dark": build_material(
            "LOOKDEV_PROPOSED_dark_anodized_metal", (.055, .065, .068, 1), .25, .82,
        ),
        "metal_soft": build_material(
            "LOOKDEV_PROPOSED_brushed_metal", (.28, .30, .30, 1), .31, .76,
        ),
        "accent_band": build_material(
            "LOOKDEV_PROPOSED_terracotta_band", (.17, .025, .012, 1), .54, .03,
            bump_strength=.035, bump_scale=5.0, color_variation=.04, bevel_radius=.012,
        ),
        "spandrel": build_material(
            "LOOKDEV_PROPOSED_warm_spandrel", (.18, .08, .02, 1), .43, .08,
            bevel_radius=.008,
        ),
        "facade_neutral": build_material(
            "LOOKDEV_PROPOSED_opaque_facade_pending_material_approval", (.37, .39, .38, 1), .53, .05,
        ),
        "context_gray": build_material("CONCEPT_CONTEXT_unsurveyed", (.155, .16, .16, 1), .82),
        "ground": build_material("CONCEPT_STAGE_ground", (.13, .14, .125, 1), .92),
        "pavement": build_material("CONCEPT_STAGE_pavement", (.09, .095, .095, 1), .88),
        "landscape": build_material("CACHE_DERIVED_landscape_surface", (.095, .18, .09, 1), .90),
        "foliage": build_material("CACHE_DERIVED_tree_canopy", (.075, .20, .075, 1), .86),
        "bark": build_material("CACHE_DERIVED_tree_trunk", (.16, .075, .035, 1), .88),
    }


def material_class(rec: dict) -> str:
    kind = str(rec.get("kind", "unknown"))
    name = str(rec.get("name", "")).lower()
    if kind == "facade":
        if "glass" in name:
            return "glass_facade"
        if any(token in name for token in ("mullion", "louver", "rail")):
            return "metal_dark"
        if "band" in name:
            return "accent_band"
        if "spandrel" in name:
            return "spandrel"
        return "facade_neutral"
    if kind == "tube_wall":
        return "glass_tube"
    if kind == "slab" and "glassfloor" in name:
        return "glass_facade"
    if kind == "core_wall":
        return "concrete_dark"
    if kind in {"slab", "column", "stair", "ramp", "roof", "exterior_wall", "partition_wall"}:
        return "concrete"
    if kind in {"shaft", "door"}:
        return "metal_soft"
    if kind == "context_building":
        return "context_gray"
    if kind == "tree":
        return "bark" if name.startswith("cylinder") else "foliage"
    if kind == "site":
        if any(token in name for token in ("garden", "lawn", "grove")):
            return "landscape"
        if any(token in name for token in ("plaza", "passage", "runway", "steps", "sunken")):
            return "pavement"
        return "ground"
    if kind in {"road", "sidewalk"}:
        return "pavement"
    return "ground"


def _aim(obj: bpy.types.Object, point: Vector) -> None:
    obj.rotation_euler = (point - obj.location).to_track_quat("-Z", "Y").to_euler()


def configure_cycles_device(scene: bpy.types.Scene, requested: str) -> dict:
    """Select a real Cycles device, with an audited CPU fallback."""
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.refresh_devices()
    available = [{"name": d.name, "type": d.type} for d in prefs.devices]
    selected = "CPU"
    if requested != "cpu":
        preferred = [requested.upper()] if requested in {"cuda", "optix"} else ["OPTIX", "CUDA"]
        for device_type in preferred:
            if any(d.type == device_type for d in prefs.devices):
                try:
                    prefs.compute_device_type = device_type
                except TypeError:
                    continue
                prefs.refresh_devices()
                for device in prefs.devices:
                    device.use = device.type == device_type
                scene.cycles.device = "GPU"
                selected = device_type
                break
    if selected == "CPU":
        for device in prefs.devices:
            device.use = device.type == "CPU"
        scene.cycles.device = "CPU"
    return {"requested": requested, "selected": selected, "available": available}


def make_scene(v: np.ndarray, f: np.ndarray, records: list[dict], variant: str,
               samples: int, width: int, height: int, device: str = "auto",
               azimuth_deg: float = 62.0, target_height_ratio: float = .42,
               camera_height_ratio: float = 1.55, distance_scale: float = 3.4,
               lens_mm: float = 55.0) -> dict:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    device_audit = configure_cycles_device(scene, device)
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = .035 if samples <= 32 else .012
    scene.cycles.max_bounces = 10
    scene.cycles.diffuse_bounces = 4
    scene.cycles.glossy_bounces = 5
    scene.cycles.transmission_bounces = 8
    scene.cycles.transparent_max_bounces = 8
    scene.cycles.caustics_reflective = False
    scene.cycles.caustics_refractive = False
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.render.image_settings.color_depth = "16"
    scene.view_settings.view_transform = "AgX"
    # Blender 4.x/5.x expose different identifiers and display names for the
    # same AgX looks.  Assign only a value the running build actually accepts;
    # some 4.2 builds report identifier ``NONE`` but accept display value
    # ``None``, which otherwise aborts the render before any pixels are made.
    accepted_looks = [
        "AgX - Medium High Contrast", "Medium High Contrast",
        "AgX - Base Contrast", "None",
    ]
    for look in accepted_looks:
        try:
            scene.view_settings.look = look
            break
        except (TypeError, ValueError):
            continue
    scene.view_settings.exposure = -.68 if variant == "daylight" else .58
    scene.view_settings.gamma = 1.0
    scene.render.filepath = ""

    design = [o for o in records if o.get("kind") in ARCHITECTURE_KINDS]
    if not design:
        raise ValueError("BLOCKED: no authoritative architecture mesh found")
    vmin = np.min([v[o["v0"]:o["v0"]+o["nv"]].min(axis=0) for o in design], axis=0)
    vmax = np.max([v[o["v0"]:o["v0"]+o["nv"]].max(axis=0) for o in design], axis=0)
    origin = np.array([(vmin[0]+vmax[0])/2, (vmin[1]+vmax[1])/2, vmin[2]], dtype=float)
    mats = materials(variant)
    categories: dict[str, int] = {}
    imported = 0
    # Preserve every source vertex and original triangle index, modulo global translation
    # to prevent numerical instabilities when coordinates are large.
    for rec in records:
        kind = str(rec.get("kind", "unknown"))
        if kind not in ARCHITECTURE_KINDS | CONTEXT_KINDS:
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
        material_key = material_class(rec)
        mesh.materials.append(mats[material_key])
        obj["lookdev_material_class"] = material_key
        if kind in {"tube_wall", "tree"}:
            for polygon in mesh.polygons:
                polygon.use_smooth = True
        categories[kind] = categories.get(kind, 0) + 1
        imported += 1

    size = vmax - vmin
    size_xy = float(max(size[0], size[1]))
    tower_height = float(size[2])
    # Camera is a 2-point *perspective* photograph; do not claim original G-002 match.
    target = Vector((0.0, 0.0, tower_height * target_height_ratio))
    azimuth = math.radians(azimuth_deg)
    dist = max(size_xy * 2.8, tower_height * distance_scale)
    cam_xyz = Vector((
        math.cos(azimuth) * dist,
        -math.sin(azimuth) * dist,
        tower_height * camera_height_ratio,
    ))
    camera_data = bpy.data.cameras.new("PROPOSED_ARCHITECTURAL_CAMERA")
    camera = bpy.data.objects.new("PROPOSED_ARCHITECTURAL_CAMERA", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = cam_xyz
    camera_data.type = "PERSP"  # photographic perspective with straight verticals
    camera_data.lens = lens_mm
    camera_data.clip_end = 100000
    _aim(camera, target)
    scene.camera = camera

    # Ground underlay closes only the unmodelled void between authoritative site
    # patches.  Its elevation comes from near-grade cached site surfaces when
    # available, otherwise from the cached 1F slab; it is never surveyed terrain.
    level_slabs = [r for r in design if r.get("kind") == "slab" and str(r.get("floor", "")).upper() == "1F"]
    ground_level = None
    ground_source = "GROUND_DATUM_NOT_FOUND"
    site_grade = []
    for rec in records:
        if rec.get("kind") != "site":
            continue
        vv = v[rec["v0"]:rec["v0"] + rec["nv"], 2]
        if len(vv) and float(vv.min()) >= -.5 and float(vv.max()) <= 1.0:
            site_grade.append(float(vv.max()))
    if site_grade:
        ground_level = float(np.median(site_grade) - origin[2])
        ground_source = "DERIVED_FROM_NEAR_GRADE_CACHED_SITE_PATCHES__NOT_SURVEYED_TERRAIN"
    elif level_slabs:
        ground_level = float(min(v[r["v0"]:r["v0"]+r["nv"], 2].min() for r in level_slabs) - origin[2])
        ground_source = "DERIVED_FROM_1F_SLAB__NOT_SURVEYED_TERRAIN"
    if ground_level is not None:
        bpy.ops.mesh.primitive_plane_add(size=2, location=(0, 0, ground_level - .08))
        stage = bpy.context.object
        stage.name = "CONCEPT_STAGE_GRADE_UNDERLAY__NOT_SURVEYED_TERRAIN"
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
        bg.inputs["Strength"].default_value = .32
    else:
        bg.inputs["Color"].default_value = (.04, .085, .18, 1)
        bg.inputs["Strength"].default_value = .56
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])

    sun_data = bpy.data.lights.new("LOOKDEV_SUN", "SUN")
    sun_obj = bpy.data.objects.new("LOOKDEV_SUN", sun_data)
    bpy.context.collection.objects.link(sun_obj)
    sun_obj.rotation_euler = (math.radians(36), math.radians(-15), math.radians(25))
    sun_data.energy = 1.25 if variant == "daylight" else .32
    sun_data.angle = math.radians(3.2 if variant == "daylight" else 8.0)

    area_data = bpy.data.lights.new("LOOKDEV_BOUNCE", "AREA")
    area_obj = bpy.data.objects.new("LOOKDEV_BOUNCE", area_data)
    bpy.context.collection.objects.link(area_obj)
    area_obj.location = (size_xy*.66, -size_xy*.64, tower_height*.91)
    _aim(area_obj, target)
    area_data.shape = "DISK"
    area_data.size = max(20., size_xy*.85)
    area_data.energy = 1800 if variant == "daylight" else 1550

    if variant == "bluehour":
        # Warm look-development luminaires sit inside the verified envelope.
        # They are visualization-only light sources and add no geometry.
        for index, z_ratio in enumerate((.17, .35, .53, .72)):
            light_data = bpy.data.lights.new(f"LOOKDEV_INTERIOR_{index:02d}", "AREA")
            light_obj = bpy.data.objects.new(f"LOOKDEV_INTERIOR_{index:02d}", light_data)
            bpy.context.collection.objects.link(light_obj)
            light_obj.location = (0.0, 0.0, tower_height * z_ratio)
            light_obj.rotation_euler = (0.0, 0.0, 0.0)
            light_data.shape = "DISK"
            light_data.size = max(8.0, size_xy * .24)
            light_data.energy = 1650
            light_data.color = (1.0, .54, .28)

    return {
        "cached_geometry_objects_imported": imported,
        "source_coordinate_origin_m": origin.tolist(),
        "source_architecture_bbox_m": {"min": vmin.tolist(), "max": vmax.tolist()},
        "source_height_m": tower_height,
        "source_kind_counts": dict(sorted(categories.items())),
        "cycles_device": device_audit,
        "camera": {
            "type": camera_data.type, "location_local_m": list(camera.location),
            "rotation_euler": list(camera.rotation_euler),
            "lens_mm": camera_data.lens,
            "azimuth_deg": azimuth_deg,
            "target_height_ratio": target_height_ratio,
            "camera_height_ratio": camera_height_ratio,
            "distance_scale": distance_scale,
            "relationship_to_G002_original": "NEW_VISUALIZATION_CAMERA__ORIGINAL_CAMERA_UNAVAILABLE",
        },
        "material_status": "SEMANTIC_NAME_DERIVED_LOOKDEV_ONLY__NOT_VERIFIED_CONSTRUCTION_SPEC",
        "ground_status": ground_source,
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
    ap.add_argument("--device", choices=("auto", "cpu", "cuda", "optix"), default="auto")
    ap.add_argument("--azimuth-deg", type=float, default=62.0)
    ap.add_argument("--target-height-ratio", type=float, default=.42)
    ap.add_argument("--camera-height-ratio", type=float, default=1.55)
    ap.add_argument("--distance-scale", type=float, default=3.4)
    ap.add_argument("--lens-mm", type=float, default=55.0)
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
    scene_audit = make_scene(
        V, F, meta["objects"], args.variant, args.samples, args.width, args.height,
        device=args.device, azimuth_deg=args.azimuth_deg,
        target_height_ratio=args.target_height_ratio,
        camera_height_ratio=args.camera_height_ratio,
        distance_scale=args.distance_scale, lens_mm=args.lens_mm,
    )
    out.mkdir(parents=True, exist_ok=True)
    bpy.context.scene.render.filepath = str(out / f"G002_{args.variant}_CYCLES_PBR_SOURCE_MESH.png")
    bpy.ops.wm.save_as_mainfile(filepath=str(out / f"G002_{args.variant}_SOURCE_MESH_LOOKDEV.blend"))
    render_started = time.perf_counter()
    bpy.ops.render.render(write_still=True)
    render_seconds = round(time.perf_counter() - render_started, 3)
    is_target_resolution = args.width >= 4800 and args.height >= 2700
    result = {
        "variant": args.variant,
        "status": (
            "PBR_TARGET_RENDER_COMPLETE__HUMAN_ARCHITECTURAL_APPROVAL_PENDING"
            if is_target_resolution else
            "PBR_PREVIEW_ONLY__HUMAN_GEOMETRY_AND_VISUAL_QA_PENDING"
        ),
        "render_settings": {
            "width_px": args.width, "height_px": args.height,
            "samples": args.samples, "render_seconds": render_seconds,
            "blender_version": bpy.app.version_string,
            "blender_build_hash": bpy.app.build_hash.decode("ascii", errors="replace"),
        },
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

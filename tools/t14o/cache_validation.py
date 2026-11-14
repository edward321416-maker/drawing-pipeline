"""Validate the model cache's object-level geometry *before* any PBR render.

Uses only numpy and the Python standard library. Does not modify inputs or
manufacture missing geometry. On failure, exits nonzero and records reasons.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

REQUIRED_KINDS = {"slab", "core_wall", "column", "tube_wall"}
KNOWN_KINDS = {
    "column", "slab", "stair", "tube_wall", "shaft", "core_wall",
    "ramp", "facade", "roof", "exterior_wall", "partition_wall", "door",
    "site", "road", "sidewalk", "context_building", "exterior_space",
    "tree", "void", "zone", "room", "fixture", "sanitary", "entrance",
    "subway_exit", "setback", "road_marking", "sunken_stair",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_cache(cache_dir: Path, expected_hash: str | None = None,
                   expected_objects_hash: str | None = None) -> dict[str, Any]:
    cache_dir = Path(cache_dir)
    mesh_file = cache_dir / "model_world.npz"
    objects_file = cache_dir / "model_objects.json"
    errors: list[str] = []
    warnings: list[str] = []
    result: dict[str, Any] = {
        "status": "BLOCKED", "cache_dir": str(cache_dir.resolve()),
        "errors": errors, "warnings": warnings,
    }
    for path in (mesh_file, objects_file):
        if not path.is_file():
            errors.append(f"SOURCE_NOT_FOUND: {path}")
    if errors:
        return result
    result["model_npz_sha256"] = sha256(mesh_file)
    result["model_objects_sha256"] = sha256(objects_file)
    if expected_hash and result["model_npz_sha256"].lower() != expected_hash.lower():
        errors.append("SOURCE_HASH_MISMATCH: authoritative cache hash differs")
        return result
    if expected_objects_hash and result["model_objects_sha256"].lower() != expected_objects_hash.lower():
        errors.append("OBJECT_METADATA_HASH_MISMATCH: authoritative object registry differs")
        return result

    try:
        with np.load(mesh_file, allow_pickle=False) as src:
            V = np.asarray(src["V"])
            F = np.asarray(src["F"])
        meta = json.loads(objects_file.read_text(encoding="utf-8"))
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as ex:
        errors.append(f"UNREADABLE_CACHE: {type(ex).__name__}: {ex}")
        return result

    if V.ndim != 2 or V.shape[1] != 3 or not np.issubdtype(V.dtype, np.number):
        errors.append("BAD_VERTICES: V must be numeric (N,3)")
    if F.ndim != 2 or F.shape[1] != 3 or not np.issubdtype(F.dtype, np.integer):
        errors.append("BAD_TRIANGLES: F must be integer (M,3)")
    if errors:
        return result
    if not len(V) or not len(F):
        errors.append("EMPTY_MESH")
        return result
    if not np.isfinite(V).all():
        errors.append("NONFINITE_VERTICES")
    if int(F.min()) < 0 or int(F.max()) >= len(V):
        errors.append("GLOBAL_FACE_INDEX_OUT_OF_RANGE")

    objects = meta.get("objects", [])
    if not isinstance(objects, list) or not objects:
        errors.append("NO_OBJECTS_IN_METADATA")
        return result
    kinds = Counter()
    floors = Counter()
    occupied_v: list[tuple[int, int]] = []
    occupied_f: list[tuple[int, int]] = []
    failed_objects = []
    for index, obj in enumerate(objects):
        try:
            v0, nv, f0, nf = (int(obj[x]) for x in ("v0", "nv", "f0", "nf"))
        except (TypeError, ValueError, KeyError):
            failed_objects.append(f"{index}: missing/invalid offsets")
            continue
        name = str(obj.get("name", index))
        if nv < 3 or nf < 1 or v0 < 0 or f0 < 0 or v0 + nv > len(V) or f0 + nf > len(F):
            failed_objects.append(f"{name}: invalid object index window")
            continue
        local_faces = F[f0:f0 + nf]
        if (local_faces < v0).any() or (local_faces >= v0 + nv).any():
            failed_objects.append(f"{name}: faces reference vertices outside the object's window")
            continue
        kinds[str(obj.get("kind", "UNKNOWN"))] += 1
        if obj.get("floor") is not None:
            floors[str(obj["floor"])] += 1
        occupied_v.append((v0, v0 + nv))
        occupied_f.append((f0, f0 + nf))
    if failed_objects:
        errors.extend(["OBJECT_GEOMETRY_INVALID: " + x for x in failed_objects[:12]])
        if len(failed_objects) > 12:
            errors.append(f"OBJECT_GEOMETRY_INVALID: plus {len(failed_objects)-12} others")
    if len(occupied_v) != len(objects):
        errors.append("OBJECT_COVERAGE_INCOMPLETE")
    for windows, name in ((occupied_v, "VERTEX"), (occupied_f, "FACE")):
        windows.sort()
        if any(windows[i][1] > windows[i+1][0] for i in range(len(windows)-1)):
            errors.append(f"{name}_OBJECT_WINDOWS_OVERLAP")
    bbox_min = V.min(axis=0).astype(float).tolist()
    bbox_max = V.max(axis=0).astype(float).tolist()
    z_span = bbox_max[2] - bbox_min[2]
    if z_span < 40:
        warnings.append(f"SHORT_CACHE_Z_RANGE: {z_span:.2f}m; full-tower completeness unverified")
    missing = REQUIRED_KINDS.difference(kinds)
    if missing:
        warnings.append("MISSING_TOWER_CLASSES: " + ", ".join(sorted(missing)))
    unknown = set(kinds).difference(KNOWN_KINDS)
    if unknown:
        warnings.append("UNKNOWN_CLASSES: " + ", ".join(sorted(unknown)))
    recorded_floors = meta.get("floors")
    if recorded_floors is None:
        warnings.append("FLOOR_REGISTRY_MISSING")
    result.update({
        "vertex_count": int(len(V)), "triangle_count": int(len(F)),
        "object_count": len(objects), "bbox_min": bbox_min, "bbox_max": bbox_max,
        "z_span_m": round(z_span, 3), "kinds": dict(sorted(kinds.items())),
        "floor_tag_count": len(floors), "floor_tags": sorted(floors),
        "floor_registry_type": type(recorded_floors).__name__,
        "verified_cache_geometry": not bool(errors),
        "model_completeness_and_materials_verified": False,
        "status": "CACHE_INDEX_VALID" if not errors else "BLOCKED",
    })
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cache-dir", required=True, type=Path)
    ap.add_argument("--expected-npz-sha256", default="")
    ap.add_argument("--expected-objects-sha256", default="")
    ap.add_argument("--report", type=Path)
    args = ap.parse_args()
    result = validate_cache(args.cache_dir, args.expected_npz_sha256 or None,
                            args.expected_objects_sha256 or None)
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output, encoding="utf-8")
    print(output)
    raise SystemExit(0 if result["status"] == "CACHE_INDEX_VALID" else 2)


if __name__ == "__main__":
    main()
"""What model source a run really has. The full-building GLB is not in the repository and not on this machine;
the derived mesh cache (model_cache/model_world.npz + model_objects.json) is. Sheets are generated from the cache,
so the identity that is *verified* is the cache hash; the GLB hash is only what V2 recorded and is reported as such.
"""
import hashlib
import json
import os


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def identity(run, glb=None):
    run = os.path.abspath(run)
    cache = os.path.join(run, "model_cache")
    rec = None
    for rel in ("sections/section_line_registry.json", "elevations/elevation_registry.json"):
        p = os.path.join(run, *rel.split("/"))
        if os.path.exists(p):
            rec = json.load(open(p, encoding="utf-8")).get("model", {}).get("sha256")
            if rec:
                break
    out = {
        "glb_name": "GMC-ZZ-ZZ-M3-0701.glb",
        "glb_present": bool(glb and os.path.exists(glb)),
        "glb_sha256_verified": sha256_file(glb) if glb and os.path.exists(glb) else None,
        "glb_sha256_recorded_by_v2": rec,
        "cache_sha256": {n: sha256_file(os.path.join(cache, n)) for n in ("model_world.npz", "model_objects.json") if os.path.exists(os.path.join(cache, n))},
    }
    out["status"] = "GLB_VERIFIED" if out["glb_present"] else "GLB_ORIGINAL_MISSING__CACHE_ONLY"
    return out


def model_sha(run, glb=None):
    """The hash written into sheet registries: the verified GLB hash if the file is given, else the V2 recorded value."""
    i = identity(run, glb)
    return i["glb_sha256_verified"] or i["glb_sha256_recorded_by_v2"]

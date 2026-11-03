# FILE: extract/blender_export.py
"""Blender 안에서 실행: blender -b <file.blend> --python blender_export.py -- <out.json>

모든 MESH 객체를 월드 좌표(미터)로 내보낸다. 커스텀 속성(kind, name_ko 등)을 그대로 보존한다.
"""
import json
import sys

import bpy


def _simple_props(obj):
    out = {}
    for key in obj.keys():
        if key.startswith("_"):
            continue
        value = obj[key]
        if isinstance(value, (str, int, float, bool)):
            out[key] = value
    return out


def export(out_path):
    scale = bpy.context.scene.unit_settings.scale_length
    deps = bpy.context.evaluated_depsgraph_get()
    objects = []
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        evaluated = obj.evaluated_get(deps)
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            world = obj.matrix_world
            verts = [[c * scale for c in (world @ v.co)] for v in mesh.vertices]
            tris = [list(t.vertices) for t in mesh.loop_triangles]
        finally:
            evaluated.to_mesh_clear()
        objects.append({"name": obj.name, "props": _simple_props(obj), "verts": verts, "tris": tris})
    scene = bpy.context.scene
    meta = {
        k: scene[k] for k in scene.keys()
        if not k.startswith("_") and isinstance(scene[k], (str, int, float, bool))
    }
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({"schema": 1, "units": "m", "meta": meta, "objects": objects}, fh, ensure_ascii=False)


if __name__ == "__main__":
    export(sys.argv[sys.argv.index("--") + 1])

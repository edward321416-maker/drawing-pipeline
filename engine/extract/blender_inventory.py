# FILE: extract/blender_inventory.py
"""Blender 안에서 실행: blender -b <file.blend> --python blender_inventory.py -- <out.json>"""
import json
import sys

import bpy


def main(out_path):
    items = []
    for obj in bpy.data.objects:
        props = {
            k: obj[k] for k in obj.keys()
            if not k.startswith("_") and isinstance(obj[k], (str, int, float, bool))
        }
        item = {"name": obj.name, "type": obj.type, "props": props}
        if obj.type == "MESH" and len(obj.data.vertices):
            pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
            item["bbox_min"] = [min(p[i] for p in pts) for i in range(3)]
            item["bbox_max"] = [max(p[i] for p in pts) for i in range(3)]
        items.append(item)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({"objects": items}, fh, ensure_ascii=False)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1])

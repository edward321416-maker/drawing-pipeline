"""Blender 안에서 실행: blender -b --python make_blend.py -- <model.json> <out.blend>

엔진 모델 JSON(태그 포함, 월드 좌표 m)에서 .blend를 만든다. kind별 컬렉션으로 정리하고
태그(kind, name_ko 등)를 객체 사용자 정의 속성으로 저장한다. 정점·삼각형은 JSON 그대로다.
"""
import json
import sys

import bpy

model_json, out_blend = sys.argv[sys.argv.index("--") + 1:][:2]
with open(model_json, encoding="utf-8") as fh:
    data = json.load(fh)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.scale_length = 1.0
for key, value in data.get("meta", {}).items():  # 모델 전체 정보(진북 각도 등)는 씬 사용자 정의 속성으로 보존
    scene[key] = value

collections = {}
for item in data["objects"]:
    kind = item["props"].get("kind", "untagged")
    coll = collections.get(kind)
    if coll is None:
        coll = bpy.data.collections.new(kind)
        scene.collection.children.link(coll)
        collections[kind] = coll
    mesh = bpy.data.meshes.new(item["name"])
    mesh.from_pydata(item["verts"], [], item["tris"])
    mesh.update()
    obj = bpy.data.objects.new(item["name"], mesh)
    for key, value in item["props"].items():
        obj[key] = value
    coll.objects.link(obj)

bpy.ops.wm.save_as_mainfile(filepath=out_blend)
print("saved", out_blend, len(data["objects"]))

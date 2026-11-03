"""Blender 안에서 실행: blender -b <master.blend> --python render_review.py -- <out_dir>

3D 검토용 렌더 두 장(등각, 평면 조망)을 Workbench로 만든다. 평면도가 아니다 — 평면도는 엔진이 모델을 절단해서 만든다.
"""
import math
import os
import sys

import bpy
from mathutils import Vector

out_dir = sys.argv[sys.argv.index("--") + 1]
scene = bpy.context.scene

scene.render.engine = "BLENDER_WORKBENCH"
scene.render.resolution_x, scene.render.resolution_y = 2400, 1700
scene.render.threads_mode = "FIXED"
scene.render.threads = 4            # 자원 제한: 8코어 이하
scene.render.image_settings.file_format = "PNG"
scene.render.use_file_extension = False

shading = scene.display.shading
shading.light = "STUDIO"
shading.color_type = "OBJECT"
shading.show_object_outline = True
shading.object_outline_color = (0.0, 0.0, 0.0)

world = bpy.data.worlds.new("W")
world.color = (1.0, 1.0, 1.0)
scene.world = world

KIND_COLOR = {
    "slab": (0.86, 0.85, 0.82, 1), "column": (0.08, 0.08, 0.08, 1), "core_wall": (0.25, 0.25, 0.25, 1),
    "partition_wall": (0.45, 0.45, 0.45, 1), "tube_wall": (0.55, 0.75, 0.90, 1),
    "shaft": (0.60, 0.60, 0.62, 1), "void": (0.90, 0.30, 0.25, 1),
}
ZONE_COLOR = {
    "market_hall": (0.96, 0.90, 0.78, 1), "service": (0.80, 0.80, 0.84, 1), "piloti_plaza": (0.82, 0.90, 0.80, 1),
}
for ob in bpy.data.objects:
    kind = ob.get("kind")
    if kind == "zone":
        ob.color = ZONE_COLOR.get(ob.get("use"), (0.9, 0.9, 0.9, 1))
    else:
        ob.color = KIND_COLOR.get(kind, (0.7, 0.7, 0.7, 1))
    if kind in ("void", "room", "door", "site", "setback", "road", "sidewalk", "context_building"):
        # 개구부는 비어 있는 공간(층판의 구멍으로 보인다), room은 라벨 전용, door는 스윙 영역이라 3D에서는 그리지 않는다.
        # 대지·도로·이웃 건물은 카메라가 건물 기준으로 고정된 이 검토 렌더에서는 숨긴다(평면 도면에서 쓴다)
        ob.hide_render = True

cam_data = bpy.data.cameras.new("Cam")
cam_data.type = "ORTHO"
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
target = Vector((27.0, 27.0, 2.0))


def shoot(filename, location, ortho_scale):
    cam.location = location
    cam.rotation_euler = (target - Vector(location)).to_track_quat("-Z", "Y").to_euler()
    cam_data.ortho_scale = ortho_scale
    scene.render.filepath = os.path.join(out_dir, filename)
    bpy.ops.render.render(write_still=True)
    print("rendered", scene.render.filepath)


shoot("1F_마스터모델_3D검토_등각.png", (27 - 70, 27 - 70, 62), 95)
# ortho_scale은 긴 변(가로 2400 px) 기준이다. 54 m 건물이 세로 1700 px에 여유 있게 들어가려면 약 88 m가 필요하다
shoot("1F_마스터모델_3D검토_평면조망.png", (27, 27, 120), 88)

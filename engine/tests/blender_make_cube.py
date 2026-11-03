# FILE: tests/blender_make_cube.py
"""Blender 안에서 실행: blender -b --python blender_make_cube.py -- <out.blend>"""
import sys

import bpy

out_path = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(5.0, 5.0, 0.5))
obj = bpy.context.active_object
obj.name = "Col_test"
obj.scale = (0.9, 0.9, 1.0)
obj["kind"] = "column"
obj["name_ko"] = "기둥 시험"
bpy.ops.wm.save_as_mainfile(filepath=out_path)

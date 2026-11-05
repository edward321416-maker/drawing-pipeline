"""도면집용 3D 추출 (Blender 안에서 실행). 입면·단면·상세가 모두 이 한 번의 추출에서 나온다.

    blender -b --factory-startup -P src/05_extract_model.py -- --input <model.glb> --out <폴더>

산출: model_world.npz (모든 객체의 월드 좌표 삼각형), model_objects.json (객체 이름·종류·층·이름 태그 출처·z 범위).
분류 규칙은 01_headless_slicer.py의 것을 그대로 쓴다(그 파일의 main() 호출만 뺀 앞부분을 실행). 좌표는 월드 그대로이고
도면 좌표틀 회전은 뷰 단계에서 camera_bounds.json의 theta로 적용한다.
"""
import json
import os
import sys

import bmesh
import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    d = {}
    for i in range(0, len(argv) - 1, 2):
        d[argv[i].lstrip("-")] = argv[i + 1]
    return d


def main():
    a = args()
    src = open(os.path.join(HERE, "01_headless_slicer.py"), encoding="utf-8").read()
    body = src.rsplit("\nmain()", 1)[0]                                   # main() 호출만 제외
    ns = {"__name__": "slicer_lib", "__file__": os.path.join(HERE, "01_headless_slicer.py")}
    exec(compile(body, "01_headless_slicer.py", "exec"), ns)
    ns["load_scene"](a["input"])
    deps = bpy.context.evaluated_depsgraph_get()
    recs = ns["collect"](deps)
    floors = ns["floors_from"](recs)
    V, F, meta = [], [], []
    voff = 0
    for r in recs:
        bm = r["bm"]
        bm.verts.index_update()
        tris = bm.calc_loop_triangles()
        verts = np.array([(v.co.x, v.co.y, v.co.z) for v in bm.verts], dtype=np.float64)
        faces = np.array([[l.vert.index for l in t] for t in tris], dtype=np.int64).reshape(-1, 3)
        meta.append({"name": r["name"], "kind": r["kind"], "name_ko": r["name_ko"], "floor": r["floor"], "source": r["source"],
                     "zmin": r["zmin"], "zmax": r["zmax"], "bbox": r["bbox"], "v0": voff, "nv": len(verts), "f0": sum(len(f) for f in F), "nf": len(faces)})
        V.append(verts)
        F.append(faces + voff)
        voff += len(verts)
    np.savez_compressed(os.path.join(a["out"], "model_world.npz"), V=np.vstack(V), F=np.vstack(F))
    json.dump({"floors": floors, "objects": meta}, open(os.path.join(a["out"], "model_objects.json"), "w", encoding="utf-8"), ensure_ascii=False)
    kinds = {}
    for m in meta:
        kinds[m["kind"]] = kinds.get(m["kind"], 0) + 1
    print("EXTRACT objects=%d verts=%d tris=%d kinds=%s" % (len(meta), voff, sum(len(f) for f in F), kinds))
    print("DONE_EXTRACT", os.path.abspath(a["out"]))


main()

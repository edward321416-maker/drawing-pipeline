# FILE: tests/model_fixtures.py
"""Blender 없이 쓰는 합성 1F 축소 모델 (18 m x 18 m, 9 m 격자 3x3)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from extract.schema import Model, ModelObject


def box_mesh(x0, y0, x1, y1, z0, z1):
    v = np.array(
        [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
         [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]],
        dtype=float,
    )
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    tris = [t for a, b, c, d in quads for t in ((a, b, c), (a, c, d))]
    return v, np.array(tris, dtype=int)


def cylinder_mesh(cx, cy, r, z0, z1, n=48):
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    bottom = np.c_[cx + r * np.cos(ang), cy + r * np.sin(ang), np.full(n, z0)]
    top = bottom.copy()
    top[:, 2] = z1
    verts = np.vstack([bottom, top, [[cx, cy, z0]], [[cx, cy, z1]]])
    cb, ct = 2 * n, 2 * n + 1
    tris = []
    for i in range(n):
        j = (i + 1) % n
        tris += [(i, j, n + j), (i, n + j, n + i), (cb, j, i), (ct, n + i, n + j)]
    return verts, np.array(tris, dtype=int)


def ring_mesh(cx, cy, r_out, r_in, z0, z1, n=48):
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)

    def ring(r, z):
        return np.c_[cx + r * np.cos(ang), cy + r * np.sin(ang), np.full(n, z)]

    verts = np.vstack([ring(r_out, z0), ring(r_out, z1), ring(r_in, z0), ring(r_in, z1)])
    ob, ot, ib, it = 0, n, 2 * n, 3 * n
    tris = []
    for i in range(n):
        j = (i + 1) % n
        tris += [(ob + i, ob + j, ot + j), (ob + i, ot + j, ot + i)]   # 외측면
        tris += [(ib + i, it + j, ib + j), (ib + i, it + i, it + j)]   # 내측면
        tris += [(ot + i, ot + j, it + j), (ot + i, it + j, it + i)]   # 상부 링
        tris += [(ob + i, ib + j, ob + j), (ob + i, ib + i, ib + j)]   # 하부 링
    return verts, np.array(tris, dtype=int)


def mk(name, kind, name_ko, mesh, **extra) -> ModelObject:
    verts, tris = mesh
    return ModelObject(name, {"kind": kind, "name_ko": name_ko, **extra}, verts, tris)


def sample_model() -> Model:
    t = 0.175
    objs = [mk("Slab_1F", "slab", "1층 바닥", box_mesh(0, 0, 18, 18, -0.3, 0.0))]
    objs += [
        mk("Wall_S", "exterior_wall", "남측 외벽", box_mesh(-t, -t, 18 + t, t, 0, 4.5)),
        mk("Wall_N", "exterior_wall", "북측 외벽", box_mesh(-t, 18 - t, 18 + t, 18 + t, 0, 4.5)),
        mk("Wall_W", "exterior_wall", "서측 외벽", box_mesh(-t, -t, t, 18 + t, 0, 4.5)),
        mk("Wall_E", "exterior_wall", "동측 외벽", box_mesh(18 - t, -t, 18 + t, 18 + t, 0, 4.5)),
    ]
    for gx in (0, 9, 18):
        for gy in (0, 9, 18):
            if (gx, gy) == (9, 9):  # 튜브가 차지하는 격자점은 기둥 생략
                continue
            objs.append(mk(f"Col_{gx}_{gy}", "column", f"기둥 {gx}-{gy}", cylinder_mesh(gx, gy, 0.45, 0, 4.5)))
    objs += [
        mk("Tube_T1", "tube_wall", "T1 튜브", ring_mesh(9, 9, 3.0, 2.85, 0, 4.5)),
        mk("Void_Esc", "void", "에스컬 보이드", box_mesh(13, 6, 16, 12, 0, 4.5)),
        mk("Bench_1", "fixture", "벤치", box_mesh(2, 13, 4.2, 13.5, 0, 0.45)),
        mk("Showcase_1", "fixture", "쇼케이스", box_mesh(14, 1.5, 15.4, 2.9, 0, 1.0)),
        mk("Zone_West", "zone", "공공보행통로", box_mesh(0, 0, 9, 18, 0, 0.05)),
        mk("Zone_East", "zone", "시장 홀", box_mesh(9, 0, 18, 18, 0, 0.05)),
    ]
    return Model(objs)


def write_model_json(model: Model, path) -> Path:
    data = {
        "schema": 1,
        "units": "m",
        "objects": [
            {"name": o.name, "props": o.props, "verts": o.verts.tolist(), "tris": o.tris.tolist()}
            for o in model.objects
        ],
    }
    path = Path(path)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path

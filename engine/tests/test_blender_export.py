# FILE: tests/test_blender_export.py
from pathlib import Path

import numpy as np
import pytest

from extract.loader import load_model
from extract.run_blender import export_model, find_blender, run_blender_script

pytestmark = pytest.mark.skipif(find_blender() is None, reason="Blender 실행 파일을 찾을 수 없음")

MAKE_CUBE = Path(__file__).with_name("blender_make_cube.py")


def test_export_applies_world_matrix_and_keeps_tags(tmp_path):
    blend = tmp_path / "cube.blend"
    run_blender_script(None, MAKE_CUBE, blend)
    assert blend.exists()

    out = export_model(blend, tmp_path / "model.json")
    model = load_model(out)
    assert len(model.objects) == 1
    cube = model.objects[0]
    assert cube.name == "Col_test"
    assert cube.kind == "column"
    assert cube.name_ko == "기둥 시험"
    lo, hi = cube.verts.min(axis=0), cube.verts.max(axis=0)
    # location(5,5,0.5) + scale(0.9,0.9,1) 가 월드 좌표에 반영돼야 한다
    assert np.allclose(lo, [4.55, 4.55, 0.0], atol=1e-4)
    assert np.allclose(hi, [5.45, 5.45, 1.0], atol=1e-4)
    assert len(cube.tris) == 12


def test_run_blender_script_raises_on_python_error(tmp_path):
    bad = tmp_path / "bad.py"
    bad.write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    with pytest.raises(RuntimeError):
        run_blender_script(None, bad)

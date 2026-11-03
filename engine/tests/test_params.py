# FILE: tests/test_params.py
from pathlib import Path

import pytest

from engine_params import DEFAULT_PATH, load_params


def test_default_params_load():
    p = load_params()
    assert p.plan_cut_height_m == 1.5
    assert p.plan_cut_height_m in p.check_heights_m
    assert 5.7 in p.check_heights_m  # 층고 6.0 m의 천장 아래 0.3 m
    assert p.grid_spacing_m == 9.0
    assert p.scale_denominator == 200        # 나머지 도면 1:200 (사용자 지시 2026-11-01)
    assert p.site_scale_denominator == 400   # 전체 1층 도면(대지 포함) 1:400


def test_cut_height_must_be_among_check_heights(tmp_path: Path):
    text = DEFAULT_PATH.read_text(encoding="utf-8")
    bad = tmp_path / "params.yaml"
    bad.write_text(text.replace("[0.3, 1.5, 3.0, 5.7]", "[0.3, 3.0, 5.7]"), encoding="utf-8")
    with pytest.raises(ValueError):
        load_params(bad)

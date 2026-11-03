import math

import pytest

from checks.registry import run_render_checks
from engine_params import load_params
from extract.slicer import slice_model
from model_fixtures import sample_model
from render.annotations import Annotation, grid_positions
from render.plan_renderer import render_plan

P = load_params()
ANN = Annotation("1F 단선 공간 기획도", "시험 | 18,000 × 18,000 mm", north_angle_deg=63.2)


def _render(tmp_path, annotation=ANN):
    return render_plan(slice_model(sample_model(), P.check_heights_m), P, tmp_path / "a.png", annotation=annotation)


def test_grid_positions_cover_the_building_edges():
    assert grid_positions(-0.175, 18.175, 9.0) == [0.0, 9.0, 18.0]
    assert grid_positions(0.0, 54.0, 9.0) == [k * 9.0 for k in range(7)]


def test_annotated_render_has_outline_bubbles_dimensions_title_north_and_scale(tmp_path):
    res = _render(tmp_path)
    texts = {t.text for t in res.texts}
    assert {"1", "2", "3", "A", "B", "C"} <= texts                  # 격자 기호 (가로 숫자, 세로 문자)
    assert {"9,000", "18,000"} <= texts                             # 칸별·전체 치수(격자 간격에서 계산)
    assert {"1F 단선 공간 기획도", "시험 | 18,000 × 18,000 mm", "N"} <= texts
    assert {"0", "2.5", "5", "10 m"} <= texts                       # 축척 막대(1:200에서는 10 m)
    assert any(l.owner == "Slab_1F:outline" and l.klass == "cut_heavy" for l in res.lines)


def test_annotated_render_passes_every_text_check(tmp_path):
    assert run_render_checks(_render(tmp_path), P) == []


def test_north_arrow_points_along_the_given_angle(tmp_path):
    res = _render(tmp_path)
    shaft = next(l for l in res.lines if l.owner == "annot:north_shaft")
    head = next(l for l in res.lines if l.owner == "annot:north_head")
    (bx, by) = shaft.geom.coords[0]
    dx, dy = head.geom.centroid.x - bx, head.geom.centroid.y - by
    assert math.degrees(math.atan2(dx, dy)) == pytest.approx(63.2, abs=1.0)  # 위쪽에서 시계 방향


def test_plain_render_has_no_annotation_layer(tmp_path):
    res = _render(tmp_path, annotation=None)
    assert not any(l.owner.startswith("annot:") or l.owner == "Slab_1F:outline" for l in res.lines)
    assert "N" not in {t.text for t in res.texts}

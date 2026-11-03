# FILE: tests/test_slicer.py
import math

import pytest
from shapely.geometry import Point

from extract.slicer import filled_shell, section, slice_model
from model_fixtures import box_mesh, cylinder_mesh, mk, ring_mesh, sample_model


def _obj(mesh):
    return mk("T", "column", "시험", mesh)


def test_box_section_area_and_bounds():
    g = section(_obj(box_mesh(1, 2, 4, 6, 0, 3)), 1.5)
    assert g.area == pytest.approx(12.0)
    assert g.bounds == pytest.approx((1, 2, 4, 6))


def test_section_outside_height_range_is_empty():
    assert section(_obj(box_mesh(0, 0, 1, 1, 0, 1)), 5.0).is_empty


def test_section_on_top_face_does_not_crash_and_keeps_area():
    g = section(_obj(box_mesh(0, 0, 2, 2, 0, 2)), 2.0)
    assert g.area == pytest.approx(4.0, rel=1e-3)


def test_cylinder_section_matches_polygon_area():
    n, r = 48, 0.45
    expected = 0.5 * n * r * r * math.sin(2 * math.pi / n)
    g = section(_obj(cylinder_mesh(5, 5, r, 0, 4, n)), 1.5)
    assert g.area == pytest.approx(expected, rel=1e-3)


def test_ring_section_keeps_hole_and_filled_shell_fills_it():
    n, ro, ri = 48, 3.0, 2.85
    k = 0.5 * n * math.sin(2 * math.pi / n)
    g = section(_obj(ring_mesh(9, 9, ro, ri, 0, 4.5, n)), 1.5)
    assert g.area == pytest.approx(k * (ro**2 - ri**2), rel=1e-3)
    assert not g.contains(Point(9, 9))
    assert filled_shell(g).contains(Point(9, 9))
    assert filled_shell(g).area == pytest.approx(k * ro**2, rel=1e-3)


def test_slice_model_exposes_heights_footprints_and_kinds():
    model = sample_model()
    sections = slice_model(model, (0.3, 1.5, 3.0))
    assert "Col_0_0" in sections.at(1.5)
    assert "Bench_1" in sections.at(0.3) and "Bench_1" not in sections.at(1.5)
    assert sections.footprint("Zone_West").area == pytest.approx(162.0)
    assert sections.footprint("Slab_1F").area == pytest.approx(324.0)
    assert sections.kind("Tube_T1") == "tube_wall"
    assert sections.obj("Tube_T1").name == "Tube_T1"

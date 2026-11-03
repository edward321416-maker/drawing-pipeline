# FILE: tests/test_text_checks.py
from pathlib import Path

from shapely.geometry import box

from checks.text import check_t1_text_overlap, check_t2_text_on_line, check_t3_canvas, check_t4_style
from engine_params import load_params
from extract.slicer import slice_model
from model_fixtures import sample_model
from render.plan_renderer import LineRecord, RenderResult, TextRecord, render_plan

P = load_params()


def _text(owner, text, bbox, role="room", size=8.0):
    return TextRecord(owner, text, role, size, bbox)


def _render(texts=(), lines=(), canvas=(0, 0, 20, 20)):
    return RenderResult(Path("x.png"), list(texts), list(lines), canvas)


def test_real_render_of_clean_model_passes_all_text_checks(tmp_path):
    """솔버가 만든 배치를 독립 검사기가 다시 검증한다 (구성 시 검증 + 사후 검증)."""
    res = render_plan(slice_model(sample_model(), P.check_heights_m), P, tmp_path / "plan.png")
    assert check_t1_text_overlap(res, P) == []
    assert check_t2_text_on_line(res, P) == []
    assert check_t3_canvas(res, P) == []
    assert check_t4_style(res, P) == []


def test_t1_detects_overlapping_texts():
    r = _render(texts=[_text("a", "남성", (2, 2, 6, 4)), _text("b", "장애인", (5, 3, 9, 5))])
    v = check_t1_text_overlap(r, P)
    assert len(v) == 1 and v[0].check == "T1"


def test_t1_allows_touching_but_not_overlapping_texts():
    r = _render(texts=[_text("a", "가", (2, 2, 6, 4)), _text("b", "나", (6, 2, 9, 4))])
    assert check_t1_text_overlap(r, P) == []


def test_t2_detects_text_on_wall_but_not_on_grid_or_own_leader():
    wall = LineRecord("Wall", "cut_heavy", 1.7, box(0, 0, 10, 0.35), filled=True)
    grid = LineRecord("grid", "grid", 0.4, box(0, 0, 0, 0).union(box(4, 0, 4.01, 10)), filled=True)
    own_leader = LineRecord("lab", "detail", 0.38, box(2, 1, 2.1, 8), filled=True, leader=True)
    text = _text("lab", "라벨", (2, 0.1, 5, 1.0))
    v = check_t2_text_on_line(_render(texts=[text], lines=[wall]), P)
    assert len(v) == 1 and v[0].check == "T2"
    assert check_t2_text_on_line(_render(texts=[text], lines=[grid, own_leader]), P) == []


def test_t2_unfilled_polygon_is_checked_by_its_outline_only():
    outline = LineRecord("Zone", "detail", 0.38, box(0, 0, 10, 10), filled=False)
    inside = _text("lab", "안쪽", (3, 3, 6, 5))
    on_edge = _text("lab", "경계", (-1, 4, 2, 6))
    assert check_t2_text_on_line(_render(texts=[inside], lines=[outline]), P) == []
    assert len(check_t2_text_on_line(_render(texts=[on_edge], lines=[outline]), P)) == 1


def test_t3_detects_text_outside_canvas():
    r = _render(texts=[_text("legend", "범례", (18, 5, 22, 6))])
    v = check_t3_canvas(r, P)
    assert len(v) == 1 and v[0].check == "T3"


def test_t4_detects_off_table_sizes_and_widths():
    bad_text = _text("a", "큰글씨", (1, 1, 2, 2), role="room", size=10.0)
    bad_line = LineRecord("Wall", "cut_heavy", 2.5, box(0, 0, 1, 1), filled=True)
    v = check_t4_style(_render(texts=[bad_text], lines=[bad_line]), P)
    assert {x.check for x in v} == {"T4"} and len(v) == 2
    ok_text = _text("a", "정상", (1, 1, 2, 2), role="room", size=8.0)
    ok_line = LineRecord("Wall", "cut_heavy", 1.7, box(0, 0, 1, 1), filled=True)
    assert check_t4_style(_render(texts=[ok_text], lines=[ok_line]), P) == []

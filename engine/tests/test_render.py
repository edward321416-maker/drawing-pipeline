# FILE: tests/test_render.py
from engine_params import load_params
from extract.slicer import slice_model
from model_fixtures import sample_model
from render.plan_renderer import render_plan

P = load_params()


def _render(tmp_path):
    sections = slice_model(sample_model(), P.check_heights_m)
    return render_plan(sections, P, tmp_path / "plan.png")


def test_render_writes_png_and_records(tmp_path):
    res = _render(tmp_path)
    assert res.png_path.exists() and res.png_path.stat().st_size > 5000
    assert res.canvas[2] > res.canvas[0] and res.canvas[3] > res.canvas[1]
    assert any(l.klass == "cut_heavy" for l in res.lines)
    assert any(l.klass == "grid" for l in res.lines)


def test_zone_labels_carry_computed_areas(tmp_path):
    res = _render(tmp_path)
    texts = [t.text for t in res.texts]
    assert "공공보행통로" in texts and "시장 홀" in texts
    assert texts.count("162㎡") >= 2  # 두 구획존 모두 폴리곤 면적(9 x 18)에서 계산된 값


def test_void_label_too_big_for_void_uses_leader(tmp_path):
    res = _render(tmp_path)
    assert any(l.leader and l.owner == "Void_Esc" for l in res.lines)
    assert any(t.text == "에스컬 보이드" for t in res.texts)


def test_no_label_straddles_the_zone_boundary_line(tmp_path):
    """튜브가 구획존 경계(x=9)에 걸쳐 있어도 어떤 라벨도 그 선을 가로지르지 않는다 (솔버가 존 윤곽을 장애물로 취급)."""
    res = _render(tmp_path)
    for t in res.texts:
        x0, _y0, x1, _y1 = t.bbox
        assert not (x0 < 9.0 < x1), f"'{t.text}' 가 x=9 경계선을 가로지름"


def test_recorded_styles_come_from_the_drawn_artists(tmp_path):
    res = _render(tmp_path)
    by_role = {t.role: t.size for t in res.texts}
    assert by_role["room"] == 8.0 and by_role["sub"] == 6.25
    heavy = [l.lw for l in res.lines if l.klass == "cut_heavy"]
    assert heavy and all(abs(w - 1.7) < 1e-6 for w in heavy)

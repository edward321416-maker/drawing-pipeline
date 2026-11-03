from shapely.geometry import LineString
from shapely.ops import unary_union

from checks.registry import run_model_checks, run_render_checks
from engine_params import load_params
from extract.slicer import slice_model
from model_fixtures import box_mesh, mk, sample_model
from render.annotations import Annotation
from render.plan_renderer import render_plan

P = load_params()
ANN = Annotation("시험", "부제", north_angle_deg=0.0)


def _render(model, tmp_path, annotation=ANN):
    return render_plan(slice_model(model, P.check_heights_m), P, tmp_path / "r.png", annotation=annotation)


def test_room_gets_name_and_polygon_area_but_is_not_drawn(tmp_path):
    m = sample_model()
    m.objects.append(mk("Room_X", "room", "코어 X", box_mesh(1.0, 1.0, 7.0, 7.0, 0.05, 0.10), label_text="코어 X"))
    res = _render(m, tmp_path)
    assert {"코어 X", "36㎡"} <= {t.text for t in res.texts}
    assert not any(l.owner == "Room_X" and not l.leader for l in res.lines)  # 윤곽은 그리지 않는다(지시선만 가능)
    assert run_render_checks(res, P) == []


def test_room_is_not_a_zone_so_it_cannot_break_zone_tiling():
    m = sample_model()
    m.objects.append(mk("Room_X", "room", "코어 X", box_mesh(1.0, 1.0, 7.0, 7.0, 0.05, 0.10)))
    assert run_model_checks(slice_model(m, P.check_heights_m), P) == []


def test_outline_next_to_piloti_is_drawn_light_and_the_rest_heavy(tmp_path):
    m = sample_model()
    m.get("Zone_West").props["use"] = "piloti_plaza"
    res = _render(m, tmp_path)
    heavy = [l for l in res.lines if l.owner == "Slab_1F:outline"]
    light = [l for l in res.lines if l.owner == "Slab_1F:outline_open"]
    assert heavy and all(l.klass == "cut_heavy" for l in heavy)
    assert light and all(l.klass == "projection_light" for l in light)
    # 서쪽 구획존(x 0~9)이 필로티이므로 서쪽 변(x=0)은 얇은 선, 동쪽 변(x=18)은 굵은 선
    light_all = unary_union([l.geom for l in light]).buffer(0.01)
    heavy_all = unary_union([l.geom for l in heavy]).buffer(0.01)
    assert light_all.contains(LineString([(0, 1), (0, 17)]))
    assert not light_all.intersects(LineString([(18, 1), (18, 17)]))
    assert heavy_all.contains(LineString([(18, 1), (18, 17)]))
    assert not heavy_all.intersects(LineString([(0, 1), (0, 17)]))


def test_outline_without_piloti_is_entirely_heavy(tmp_path):
    res = _render(sample_model(), tmp_path)
    assert not [l for l in res.lines if l.owner == "Slab_1F:outline_open"]
    assert run_render_checks(res, P) == []

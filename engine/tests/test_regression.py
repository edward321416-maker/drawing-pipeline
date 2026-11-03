# FILE: tests/test_regression.py
"""사용자가 지적한 결함(결함 장부)의 회귀 검사. 각 함수 이름은 ledger.yaml의 regression_test와 일치해야 한다."""
from pathlib import Path

from shapely.geometry import box

from checks.geometry import check_g1_columns, check_g2_fixtures
from checks.text import check_t1_text_overlap, check_t2_text_on_line, check_t3_canvas
from engine_params import load_params
from extract.slicer import slice_model
from model_fixtures import box_mesh, cylinder_mesh, mk, sample_model
from render.plan_renderer import LineRecord, RenderResult, TextRecord

P = load_params()


def _ids(violations):
    return {v.check for v in violations}


def _sections(model):
    return slice_model(model, P.check_heights_m)


def _render(texts=(), lines=(), canvas=(0, 0, 20, 20)):
    return RenderResult(Path("x.png"), list(texts), list(lines), canvas)


def _text(owner, text, bbox):
    return TextRecord(owner, text, "room", 8.0, bbox)


def test_d001_tree_bench_encroaches_on_elevator_tube():
    m = sample_model()
    m.objects.append(mk("Tree_T4", "fixture", "수목 벤치", box_mesh(8.0, 7.0, 10.0, 8.5, 0, 0.5)))
    assert "G2" in _ids(check_g2_fixtures(_sections(m), P))


def test_d002_column_passes_through_void_escalator():
    m = sample_model()
    m.objects.append(mk("Col_bad", "column", "기둥 오류", cylinder_mesh(14.5, 9.0, 0.45, 0, 4.5)))
    assert "G1" in _ids(check_g1_columns(_sections(m), P))


def test_d003_furniture_overlaps_column():
    m = sample_model()
    m.objects.append(mk("Stand_bad", "fixture", "가판대", box_mesh(-0.2, -0.2, 0.9, 0.9, 0, 0.9)))
    assert "G2" in _ids(check_g2_fixtures(_sections(m), P))


def test_d004_title_box_covers_furniture():
    fixture = LineRecord("Showcase", "projection_light", 0.55, box(5, 3, 7, 6), filled=False)
    title = _text("title", "시장 홀 (마켓 플라자)", (4, 4, 8, 5))
    assert "T2" in _ids(check_t2_text_on_line(_render(texts=[title], lines=[fixture]), P))


def test_d005_restroom_labels_overlap_each_other():
    r = _render(texts=[_text("m", "남성 화장실", (2, 2, 7, 3.5)), _text("u", "장애인 다목적", (4, 3, 9, 4.5))])
    assert "T1" in _ids(check_t1_text_overlap(r, P))


def test_d006_legend_text_is_clipped_by_canvas():
    r = _render(texts=[_text("legend", "구조 기둥 Ø0.9m (RC Column)", (14, 18, 24, 19))])
    assert "T3" in _ids(check_t3_canvas(r, P))


def test_d007_overall_dimension_hidden_by_caption():
    r = _render(texts=[_text("dim", "54,000", (8, 2, 12, 3)), _text("caption", "남측 썬큰 광장", (7, 2.5, 13, 3.8))])
    assert "T1" in _ids(check_t1_text_overlap(r, P))


def test_d009_text_collides_with_line_in_approved_single_line_plan():
    wall = LineRecord("Wall", "cut_heavy", 1.7, box(0, 0, 10, 0.35), filled=True)
    r = _render(texts=[_text("atrium", "필로티 보이드 아트리움", (2, 0.1, 8, 1.0))], lines=[wall])
    assert "T2" in _ids(check_t2_text_on_line(r, P))


def test_d010_void_overlaps_core_wall():
    from checks.overlaps import check_g6_overlaps
    from test_overlap_checks import core_walls

    m = sample_model()
    m.objects += core_walls("D", 0, 0, 6, 6)
    m.objects.append(mk("Void_SunkenLink", "void", "선큰 연결 개구부", box_mesh(5.1, 0.8, 15.4, 5.2, -0.5, 4.5)))
    assert "G6" in _ids(check_g6_overlaps(_sections(m), P))


def test_d011_stair_core_rules_and_door_swing():
    from dataclasses import replace

    from checks.symbol_rules import check_g3_door_swings, check_r1_stair_core
    from symbols.stair_core import build_stair_core

    bounds = (0, 47, 6, 54)
    short_tread = build_stair_core("A", bounds, "S", replace(P.stair, tread_m=0.25))
    assert "R1" in _ids(check_r1_stair_core(short_tread, P))
    wide_door = build_stair_core("A", bounds, "S", replace(P.stair, door_w_m=2.0))
    assert "G3" in _ids(check_g3_door_swings(wide_door, P))


def test_d012_restroom_entry_cubicle_and_door_swing():
    from dataclasses import replace

    from shapely.geometry import Point

    from checks.restroom_rules import check_g3_restroom_doors, check_r2_restroom
    from symbols.restroom import Fixture, build_restroom

    rr = build_restroom("B", (49.5, 41.4, 54.0, 46.7), "unisex", P.restroom)
    rr.fixtures.append(Fixture("막는 물건", "basin", rr.units[0].clear_zone.buffer(-0.1)))   # 출입구 앞 통로를 가로막음
    assert "R2" in _ids(check_r2_restroom(rr, P))
    small = build_restroom("B", (49.5, 41.4, 54.0, 46.7), "unisex", replace(P.restroom, accessible_depth_m=1.9))
    assert "R2" in _ids(check_r2_restroom(small, P))                                          # 장애인 큐비클 치수 미달
    hall_column = Point(50.5, 40.8).buffer(0.45, quad_segs=12)
    swing = build_restroom("B", (49.5, 41.4, 54.0, 46.7), "unisex", P.restroom, [hall_column])
    assert "G3" in _ids(check_g3_restroom_doors(swing, P))                                     # 문 스윙이 기둥과 겹침


def test_d013_core_label_avoids_neighbouring_restroom_door(tmp_path):
    """코어 C 라벨이 바로 위 화장실 C의 남자문 문짝·호 위에 놓여 T2가 났다. 심볼 상세는 모든 라벨의 장애물이다."""
    from checks.registry import run_render_checks
    from master.build_master import build_master
    from render.annotations import Annotation
    from render.plan_renderer import render_plan

    res = render_plan(_sections(build_master()), P, tmp_path / "d013.png",
                      annotation=Annotation("시험", "부제", north_angle_deg=63.2), detail=True)
    assert [v for v in run_render_checks(res, P) if v.check == "T2"] == []
    door_lines = [l for l in res.lines if l.owner.startswith("C:") and "문" in l.owner]
    label = next(t for t in res.texts if t.text == "코어 C")
    assert door_lines and not any(box(*label.bbox).intersects(l.geom) for l in door_lines)


def test_d014_thin_plate_footprint_survives_json_rounding():
    """얇은 판(5 cm)의 바닥 윤곽이 소수 6자리 JSON 반올림 뒤에도 면적을 가지고, 윤곽이 사라지면 G7이 잡는다."""
    from checks.geometry import check_g7_footprints
    from extract.schema import Model, ModelObject
    from master.build_master import build_master

    arrow = build_master().get("Entrance_Main")
    rounded = ModelObject(arrow.name, arrow.props, arrow.verts.round(6), arrow.tris)   # write_model_json과 같은 반올림
    s = _sections(Model([rounded]))
    assert s.footprint("Entrance_Main").area > 1.0 and check_g7_footprints(s, P) == []
    broken = ModelObject("깨진 판", {"kind": "zone", "name_ko": "깨진 판"}, rounded.verts, rounded.tris[:-4])   # 벽 삼각형 누락
    assert any(v.check == "G7" for v in check_g7_footprints(_sections(Model([broken])), P))

def test_d015_tube_column_shaft_and_lobby_rules():
    from dataclasses import replace

    from shapely.geometry import Point

    from checks.registry import run_tube_checks
    from symbols.tube import build_elevator, build_ramp

    col = Point(3.2, 0.0).buffer(0.45, quad_segs=12)
    assert "R3" in _ids(run_tube_checks(build_ramp("T1", "T1", (0, 0), 4.5, P.tube, [col]), P))               # 램프를 기둥이 관통
    lobby_col = Point(0.0, -2.0).buffer(0.45, quad_segs=12)
    assert "R3" in _ids(run_tube_checks(build_elevator("T3", "T3", (0, 0), 4.0, P.tube, [lobby_col]), P))     # 승강 로비에 기둥
    out = build_elevator("T3", "T3", (0, 0), 4.0, replace(P.tube, shaft_to_glass_m=0.0))
    assert "R3" in _ids(run_tube_checks(out, P))                                                              # 승강로가 유리 벽에 붙음
    thick = build_ramp("T1", "T1", (0, 0), 4.5, P.tube)
    assert "R3" in _ids(run_tube_checks(thick, replace(P, tube=replace(P.tube, glass_t_m=0.3))))              # 벽 두께 불일치

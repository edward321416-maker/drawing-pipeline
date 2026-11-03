# FILE: tests/test_geometry_checks.py
from checks.geometry import check_g1_columns, check_g2_fixtures, check_g4_zones, check_g5_walls
from engine_params import load_params
from extract.slicer import slice_model
from model_fixtures import box_mesh, cylinder_mesh, mk, sample_model

P = load_params()


def _sections(model):
    return slice_model(model, P.check_heights_m)


def _all(model):
    s = _sections(model)
    return (
        check_g1_columns(s, P) + check_g2_fixtures(s, P) + check_g4_zones(s, P) + check_g5_walls(s, P)
    )


def test_clean_model_has_no_geometry_violations():
    assert _all(sample_model()) == []


def test_g1_column_inside_void():
    m = sample_model()
    m.objects.append(mk("Col_bad", "column", "기둥 오류", cylinder_mesh(14.5, 9.0, 0.45, 0, 4.5)))
    v = check_g1_columns(_sections(m), P)
    assert len(v) == 1 and v[0].check == "G1"
    assert set(v[0].objects) == {"Col_bad", "Void_Esc"}


def test_g1_column_inside_tube_interior():
    m = sample_model()
    m.objects.append(mk("Col_bad", "column", "기둥 오류", cylinder_mesh(9.0, 9.0, 0.45, 0, 4.5)))
    v = check_g1_columns(_sections(m), P)
    assert len(v) == 1 and "Tube_T1" in v[0].objects


def test_g1_catches_column_that_only_crosses_void_above_floor():
    # 바닥(0.3 m)에서는 닿지 않고 1.5 m 이상에서만 보이드를 지나가는 기둥도 잡아야 한다 (복수 높이 절단)
    m = sample_model()
    m.objects.append(mk("Col_high", "column", "높은 기둥", cylinder_mesh(14.5, 9.0, 0.45, 1.0, 4.5)))
    v = check_g1_columns(_sections(m), P)
    assert len(v) == 1 and "Col_high" in v[0].objects


def test_g2_fixture_too_close_to_column():
    m = sample_model()
    m.objects.append(mk("Bench_near", "fixture", "가까운 벤치", box_mesh(1.0, 1.0, 2.0, 1.5, 0, 0.45)))
    v = check_g2_fixtures(_sections(m), P)
    assert len(v) == 1 and v[0].check == "G2"
    assert "Bench_near" in v[0].objects and "Col_0_0" in v[0].objects


def test_g2_fixture_overlaps_tube_interior():
    m = sample_model()
    m.objects.append(mk("Tree_in_tube", "fixture", "수목 벤치", box_mesh(8.0, 7.0, 10.0, 8.5, 0, 0.5)))
    v = check_g2_fixtures(_sections(m), P)
    assert any("Tube_T1" in x.objects for x in v)


def test_g4_overlapping_zones():
    m = sample_model()
    m.objects.append(mk("Zone_Mid", "zone", "겹친 존", box_mesh(8, 0, 10, 18, 0, 0.05)))
    v = check_g4_zones(_sections(m), P)
    assert v and all(x.check == "G4" for x in v)
    assert any("겹침" in x.message for x in v)


def test_g4_uncovered_floor():
    m = sample_model()
    m.objects = [o for o in m.objects if o.name != "Zone_East"]
    v = check_g4_zones(_sections(m), P)
    assert any("덮지 못한" in x.message for x in v)


def test_g4_zone_outside_slab():
    m = sample_model()
    m.objects.append(mk("Zone_Out", "zone", "슬래브 밖", box_mesh(18, 0, 20, 4, 0, 0.05)))
    v = check_g4_zones(_sections(m), P)
    assert any("벗어남" in x.message for x in v)


def test_g4_zones_without_slab_is_a_violation():
    m = sample_model()
    m.objects = [o for o in m.objects if o.kind != "slab"]
    v = check_g4_zones(_sections(m), P)
    assert len(v) == 1 and "슬래브" in v[0].message


def test_g5_wall_off_grid_and_exemption():
    m = sample_model()
    m.objects.append(mk("Wall_off", "partition_wall", "어긋난 벽", box_mesh(1, 3.0, 8, 3.2, 0, 3)))
    v = check_g5_walls(_sections(m), P)
    assert len(v) == 1 and v[0].check == "G5" and "Wall_off" in v[0].objects

    m2 = sample_model()
    m2.objects.append(
        mk("Wall_ok", "partition_wall", "예외 벽", box_mesh(1, 3.0, 8, 3.2, 0, 3), grid_exempt=1)
    )
    assert check_g5_walls(_sections(m2), P) == []

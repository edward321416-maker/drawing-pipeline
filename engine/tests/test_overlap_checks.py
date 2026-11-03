from checks.overlaps import check_g6_overlaps
from engine_params import load_params
from extract.slicer import slice_model
from model_fixtures import box_mesh, cylinder_mesh, mk, sample_model

P = load_params()


def _sections(model):
    return slice_model(model, P.check_heights_m)


def core_walls(core_id, x0, y0, x1, y1, t=0.25, height=4.5):
    h = t / 2
    meshes = [
        box_mesh(x0 - h, y0 - h, x0 + h, y1 + h, 0, height),
        box_mesh(x1 - h, y0 - h, x1 + h, y1 + h, 0, height),
        box_mesh(x0 - h, y0 - h, x1 + h, y0 + h, 0, height),
        box_mesh(x0 - h, y1 - h, x1 + h, y1 + h, 0, height),
    ]
    return [mk(f"Core_{core_id}_{i}", "core_wall", f"코어 {core_id}", m, core_id=core_id, grid_exempt=1)
            for i, m in enumerate(meshes)]


def test_clean_sample_has_no_overlaps():
    assert check_g6_overlaps(_sections(sample_model()), P) == []


def test_walls_of_one_core_do_not_conflict_with_each_other():
    m = sample_model()
    m.objects += core_walls("X", 0, 0, 6, 6)
    assert check_g6_overlaps(_sections(m), P) == []


def test_void_overlapping_core_interior_is_a_violation():
    m = sample_model()
    m.objects += core_walls("X", 0, 0, 6, 6)
    m.objects.append(mk("Void_bad", "void", "개구부", box_mesh(5.0, 1.0, 12.0, 5.0, 0, 4.5)))
    v = check_g6_overlaps(_sections(m), P)
    assert len(v) == 1 and v[0].check == "G6"
    assert set(v[0].objects) == {"core:X", "Void_bad"}


def test_void_clear_of_core_is_fine():
    m = sample_model()
    m.objects += core_walls("X", 0, 0, 6, 6)
    m.objects.append(mk("Void_ok", "void", "개구부", box_mesh(7.0, 1.0, 12.0, 5.0, 0, 4.5)))
    assert check_g6_overlaps(_sections(m), P) == []


def test_shaft_inside_tube_is_a_violation():
    m = sample_model()
    m.objects.append(mk("Shaft_bad", "shaft", "샤프트", cylinder_mesh(9.0, 9.0, 1.0, 0, 4.5)))
    v = check_g6_overlaps(_sections(m), P)
    assert len(v) == 1 and set(v[0].objects) == {"Tube_T1", "Shaft_bad"}

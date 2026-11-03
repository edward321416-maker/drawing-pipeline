import pytest

from checks.registry import run_model_checks, run_render_checks
from engine_params import load_params
from extract.schema import Model
from extract.slicer import slice_model
from master.build_master import build_master
from model_fixtures import box_mesh, mk
from render.annotations import Annotation
from render.plan_renderer import render_plan

P = load_params()
ANN = Annotation("시험", "부제", north_angle_deg=63.2)


@pytest.fixture(scope="module")
def master():
    return build_master()


def test_cores_are_assembled_from_the_approved_symbol(master):
    for cid in "ABCD":
        assert master.get(f"Core_{cid}_wall").props["core_id"] == cid
        flights = sorted((o for o in master.objects if o.name.startswith(f"Core_{cid}_flight")), key=lambda o: o.name)
        assert len(flights) == 4
        tops = [o.zmax for o in flights]
        assert tops == sorted(tops) and tops[-1] == pytest.approx(6.0)   # 한 바퀴가 층고 6 m를 오른다
        assert master.get(f"Core_{cid}_door_hall").kind == "door"
        assert master.get(f"Core_{cid}_door_stair").kind == "door"
        room = master.get(f"Room_Core_{cid}")
        assert room.props["symbol"] == "stair_core" and room.props["ves_side"] in {"S", "W", "E"}


def test_core_b_hall_door_is_moved_west_as_approved(master):
    assert master.get("Room_Core_B").props["hall_door_offset"] == pytest.approx(-2.3)
    door = master.get("Core_B_door_hall")
    assert door.verts[:, 0].min() == pytest.approx(47.6, abs=1e-6)   # 코어 B x 47~54, 문 중심 x 48.2, 폭 1.2
    assert door.verts[:, 0].max() == pytest.approx(48.8, abs=1e-6)
    for cid in "ACD":
        assert master.get(f"Room_Core_{cid}").props["hall_door_offset"] == 0.0


def test_assembled_master_passes_every_model_check_including_door_swings(master):
    assert run_model_checks(slice_model(master, P.check_heights_m), P) == []


def test_detail_plan_draws_the_symbol_details_and_passes_text_checks(master, tmp_path):
    res = render_plan(slice_model(master, P.check_heights_m), P, tmp_path / "d.png", annotation=ANN, detail=True)
    owners = {l.owner for l in res.lines}
    assert {f"{c}:arrow" for c in "ABCD"} <= owners
    assert {f"{c}:break" for c in "ABCD"} <= owners
    assert {f"{c}:홀문:arc" for c in "ABCD"} <= owners
    assert run_render_checks(res, P) == []


def test_plain_plan_keeps_the_single_line_look(master, tmp_path):
    res = render_plan(slice_model(master, P.check_heights_m), P, tmp_path / "p.png", annotation=ANN, detail=False)
    assert not any(l.owner.endswith(":arrow") or ":tread" in l.owner for l in res.lines)
    assert run_render_checks(res, P) == []


def test_model_level_g3_detects_a_door_swinging_through_a_column(master):
    from checks.overlaps import check_g3_model_doors

    col = master.by_kind("column")[0]
    lo, hi = col.verts.min(axis=0), col.verts.max(axis=0)
    bad = mk("Door_bad", "door", "잘못된 문", box_mesh(lo[0] - 0.3, lo[1] - 0.3, hi[0] + 0.3, hi[1] + 0.3, 0.0, 2.1))
    model = Model([*master.objects, bad], master.meta)
    v = check_g3_model_doors(slice_model(model, P.check_heights_m), P)
    assert v and v[0].check == "G3" and "Door_bad" in v[0].objects

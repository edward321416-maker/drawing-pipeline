import pytest
from shapely.geometry import box

from checks.registry import run_model_checks, run_render_checks
from engine_params import load_params
from extract.slicer import slice_model
from master.build_master import build_master
from render.annotations import Annotation
from render.plan_renderer import render_plan

P = load_params()
ANN = Annotation("시험", "부제", north_angle_deg=63.2)


@pytest.fixture(scope="module")
def master():
    return build_master()


def _wc(master, wid, kind):
    return [o for o in master.objects if o.name.startswith(f"WC_{wid}_") and o.kind == kind]


def test_restrooms_are_assembled_from_the_approved_symbol(master):
    # B = 공용·장애인 겸용 1실, C = 남/여/장애인 분리 (사용자 승인본)
    assert [o.props["unit"] for o in master.objects if o.name.startswith("Room_WC_B_")] == ["공용"]
    assert sorted(o.props["unit"] for o in master.objects if o.name.startswith("Room_WC_C_")) == ["남", "여", "장애인"]
    for wid in "BC":
        assert master.get(f"WC_{wid}_wall").props["wc_id"] == wid
        assert _wc(master, wid, "sanitary") and _wc(master, wid, "door")
    assert len(_wc(master, "B", "sanitary")) == 4 and len(_wc(master, "C", "sanitary")) == 11


def test_cubicle_partitions_are_thin_and_exempt_from_the_structural_grid(master):
    from master.build_master import load_source, restroom_world_bounds
    from symbols.restroom import PROGRAM_BY_ROOM, build_restroom

    thin = [o for o in master.objects if o.kind == "partition_wall" and o.props.get("thin")]
    expected = sum(len(build_restroom(w, b, PROGRAM_BY_ROOM[w], P.restroom).thin)
                   for w, b in restroom_world_bounds(load_source()).items())   # 기대 개수는 심볼에서 센다(숫자를 따로 적지 않는다)
    assert len(thin) == expected > 0
    assert all(o.props["grid_exempt"] for o in thin) and all(o.name.startswith("WC_") for o in thin)


def test_unit_labels_follow_the_program(master):
    assert master.get("Room_WC_B_공용").props["label_text"] == "화장실"        # 한 칸짜리는 '화장실'
    texts = {master.get(f"Room_WC_C_{u}").props["label_text"] for u in ("남", "여", "장애인")}
    assert texts == {"남", "여", "장애인"}                                    # 나뉜 칸은 칸 이름


def test_assembled_restrooms_pass_the_restroom_rules_with_the_real_columns(master):
    """마스터에 들어간 화장실을 실제 기둥 위치와 함께 R2·G3(화장실 문)로 다시 검사한다 — 승인 시트와 같은 기준."""
    from checks.registry import run_restroom_checks
    from master.build_master import load_source, restroom_world_bounds
    from symbols.restroom import PROGRAM_BY_ROOM, build_restroom

    s = slice_model(master, P.check_heights_m)
    cols = [s.footprint(o.name) for o in master.by_kind("column")]
    for wid, bx in restroom_world_bounds(load_source()).items():
        near = [c for c in cols if c.distance(box(*bx)) < 0.5]
        rr = build_restroom(wid, bx, PROGRAM_BY_ROOM[wid], P.restroom, columns=near)
        assert run_restroom_checks(rr, P) == [], wid


def test_restrooms_touch_their_neighbour_cores_as_approved(master):
    """사용자 승인(2026-11-01): 화장실을 이웃 코어에 맞닿게 옮겨 0.2~0.3 m 틈을 없앤다. 원본 데이터에는 틈이 있다."""
    from extract.schema import Model
    from master.build_master import build_objects, load_source

    def gap(m):
        b_wc, b_core = m.get("WC_B_wall").verts, m.get("Core_B_wall").verts
        c_wc, c_core = m.get("WC_C_wall").verts, m.get("Core_C_wall").verts
        return (b_core[:, 1].min() - b_wc[:, 1].max(),     # 코어 B(북쪽) 남쪽 면 - 화장실 B 북쪽 면
                c_wc[:, 1].min() - c_core[:, 1].max())     # 화장실 C 남쪽 면 - 코어 C(남쪽) 북쪽 면

    assert gap(master) == pytest.approx((0.0, 0.0), abs=1e-6)
    original = Model(build_objects(load_source(), adjustments={}))
    assert gap(original) == pytest.approx((0.225, 0.325), abs=1e-6)


def test_assembled_master_passes_every_model_check_with_restrooms(master):
    assert run_model_checks(slice_model(master, P.check_heights_m), P) == []


def test_detail_plan_draws_restroom_details_and_passes_text_checks(master, tmp_path):
    res = render_plan(slice_model(master, P.check_heights_m), P, tmp_path / "d.png", annotation=ANN, detail=True)
    owners = {l.owner for l in res.lines}
    assert "B:공용문:arc" in owners and "C:남자문:arc" in owners and "C:남자문:leaf" in owners
    assert run_render_checks(res, P) == []

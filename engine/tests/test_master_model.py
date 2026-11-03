from collections import Counter

import pytest
from shapely.geometry import box
from shapely.ops import unary_union

from checks.registry import run_model_checks, run_render_checks
from checks.tags import check_tags
from engine_params import load_params
from extract.loader import load_model
from extract.schema import CONTEXT_KINDS
from extract.run_blender import export_model, find_blender
from extract.slicer import filled_shell, slice_model
from extract.schema import Model
from master.build_master import ENGINE, build_master, build_objects, load_source
from render.plan_renderer import render_plan

P = load_params()
BLEND = ENGINE / "model" / "1F_master.blend"

# 중간발표 설계 원본 데이터에 들어 있던 간섭. 사용자 결정(2026-11-01, 해소안 A)으로 design_adjustments.json이 해소했다.
KNOWN_CONFLICTS = {
    ("G1", frozenset({"Col_9_0.6", "Void_SunkenLink"})),   # 기둥(9, 0.6)이 선큰 연결 개구부 모서리를 침범
    ("G6", frozenset({"core:D", "Void_SunkenLink"})),      # 개구부가 코어 D 벽 안으로 침범
    ("G3", frozenset({"Core_B_door_hall", "WC_B_wall"})),     # 코어 B 홀 쪽 문 스윙이 바로 아래 화장실 B 벽·칸막이·양변기와 겹침
    ("G3", frozenset({"Core_B_door_hall", "WC_B_thin1"})),   # (사용자 결정으로 코어 B 홀 문을 서쪽 2.3 m 옮겨 해소)
    ("G3", frozenset({"Core_B_door_hall", "WC_B_양변기 1"})),
    ("G3", frozenset({"Core_D_door_hall", "Void_SunkenLink"})),   # 코어 D 홀 쪽 문이 개구부 위로 열림
    ("G3", frozenset({"Core_D_door_stair", "Void_SunkenLink"})),  # (원본 개구부는 코어 D 안쪽까지 들어와 있다)
}


@pytest.fixture(scope="module")
def master():
    return build_master()


def test_inventory_matches_midterm_1f(master):
    kinds = Counter(o.kind for o in master.objects if o.kind not in CONTEXT_KINDS and not o.props.get("context"))   # 대지 맥락은 test_site_plan.py가 본다
    assert kinds == {
        "column": 34, "core_wall": 4, "door": 11, "partition_wall": 19, "room": 8, "sanitary": 15, "shaft": 6,
        "slab": 1, "stair": 16, "tube_wall": 5, "void": 1, "zone": 3,
    }   # 코어 4: 문 8·칸막이 4·방 4 / 화장실 B(방 1·위생기기 4·문 1) + C(방 3·위생기기 11·문 2)


def test_model_carries_the_true_north_angle(master):
    assert master.meta["north_angle_deg"] == pytest.approx(63.2, abs=0.05)  # 중간발표 s7.ANG = 63.2


def test_every_object_is_tagged(master):
    assert check_tags(master) == []


def test_zone_areas_match_the_numbers_in_the_midterm_drawing(master):
    s = slice_model(master, P.check_heights_m)
    market, service = s.footprint("Zone_Market").area, s.footprint("Zone_Service").area
    assert market == pytest.approx(1640.3, abs=0.5)    # DR_02: 시장 홀 1,640㎡
    assert service == pytest.approx(253.7, abs=0.5)    # DR_02: 하역 250㎡
    assert market + service == pytest.approx(1894.1, abs=0.6)  # DR_02: 바닥면적 1,894㎡


def test_master_passes_every_model_check(master):
    s = slice_model(master, P.check_heights_m)
    assert run_model_checks(s, P) == []


def test_original_midterm_data_has_exactly_the_two_known_conflicts():
    """사용자가 승인한 조정(개구부 축소)을 빼면 원본 데이터의 간섭 2건이 그대로 나온다 — 조정이 왜 필요한지의 기록."""
    original = Model(build_objects(load_source(), adjustments={}))
    s = slice_model(original, P.check_heights_m)
    got = {(v.check, frozenset(v.objects)) for v in run_model_checks(s, P)}
    assert got == KNOWN_CONFLICTS


def test_cores_and_toilets_are_labelled_with_their_polygon_areas(master, tmp_path):
    s = slice_model(master, P.check_heights_m)
    res = render_plan(s, P, tmp_path / "labels.png")
    texts = {t.text for t in res.texts}
    assert {"코어 A", "코어 B", "코어 C", "코어 D", "화장실"} <= texts
    assert {"42㎡", "49㎡", "36㎡"} <= texts  # 코어 A 6×7, 코어 B 7×7, 코어 C·D 6×6


def test_adjusted_opening_is_the_approved_box(master):
    void = slice_model(master, P.check_heights_m).footprint("Void_SunkenLink")
    assert void.bounds == pytest.approx((7.35, 1.1, 15.4, 5.2), abs=1e-4)   # 해소안 A 2회: 코어 D 벽·기둥, 코어 D 문 스윙을 비킴(윗변은 원본 값 5.199997)
    assert void.area == pytest.approx(8.05 * 4.1, abs=0.01)


def test_render_is_clean_and_zone_labels_stay_out_of_enclosures(master, tmp_path):
    s = slice_model(master, P.check_heights_m)
    res = render_plan(s, P, tmp_path / "master.png")
    assert run_render_checks(res, P) == []
    enclosure = unary_union([s.footprint(o.name) for o in master.objects if o.kind == "room"])  # 코어·화장실 방 전체
    for t in res.texts:
        if t.owner.startswith("Zone_"):  # 구획존 라벨은 코어·화장실 안쪽에 들어가면 안 된다 (room 라벨은 안쪽이 맞다)
            assert not box(*t.bbox).intersects(enclosure), f"'{t.text}' 라벨이 코어·화장실 안쪽에 놓임"


@pytest.mark.skipif(find_blender() is None or not BLEND.exists(), reason="Blender 또는 1F_master.blend 없음")
def test_saved_blend_matches_the_builder(master, tmp_path):
    """저장된 .blend가 빌더 출력과 같은지(오래된 파일이 아닌지) 태그와 범위로 확인한다."""
    back = load_model(export_model(BLEND, tmp_path / "m.json"))
    assert sorted(o.name for o in back.objects) == sorted(o.name for o in master.objects)
    for o in back.objects:
        ref = master.get(o.name)
        assert o.kind == ref.kind and o.name_ko == ref.name_ko
        assert o.verts.min(axis=0) == pytest.approx(ref.verts.min(axis=0), abs=1e-4)
        assert o.verts.max(axis=0) == pytest.approx(ref.verts.max(axis=0), abs=1e-4)

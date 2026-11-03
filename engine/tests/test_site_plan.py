from dataclasses import replace

import pytest
from shapely.geometry import box
from shapely.ops import unary_union

from build import paper_fit
from checks.registry import run_model_checks, run_render_checks
from engine_params import load_params
from extract.schema import CONTEXT_KINDS
from extract.slicer import slice_model
from master.build_master import build_master, build_objects, load_source
from master.pipeline import plan_annotation
from render.annotations import annotation_factor, scale_bar_spec
from render.plan_renderer import render_plan

P = load_params()
SITE_P = replace(P, scale_denominator=P.site_scale_denominator)


@pytest.fixture(scope="module")
def master():
    return build_master()


@pytest.fixture(scope="module")
def sections(master):
    return slice_model(master, P.check_heights_m)


def _of(master, sections, *kinds):
    return {o.name: sections.footprint(o.name) for o in master.objects if o.kind in kinds}


def test_scales_follow_the_users_rule():
    assert P.scale_denominator == 200 and P.site_scale_denominator == 400


def test_scale_bar_keeps_roughly_the_same_paper_length():
    assert scale_bar_spec(replace(P, scale_denominator=300))[0] == 20.0
    assert scale_bar_spec(P)[0] == 10.0 and scale_bar_spec(SITE_P)[0] == 20.0
    assert annotation_factor(SITE_P) == pytest.approx(4 / 3)


def test_every_kind_of_site_context_is_present(master):
    kinds = {o.kind for o in master.objects}
    assert CONTEXT_KINDS <= kinds    # 대지·건축한계선·도로·보행로·이웃 건물·외부공간·수목·지하철 출구
    names = {o.name for o in master.objects}
    assert {"Road_Carriageway", "Road_Markings", "Sidewalk_Verge", "Ext_Plaza", "Ext_Grove", "Ext_GrovePath", "Ext_GroveLawn",
            "Ext_Sunken", "Ext_FireLane", "Trees", "Sunken_Stair", "Entrance_Main", "Entrance_Subway", "Entrance_Service"} <= names
    assert sum(o.kind == "subway_exit" for o in master.objects) >= 1   # 실측 차도 위로 떨어지는 출구는 뺀다


def test_road_sidewalk_and_neighbour_faces_do_not_overlap(master, sections):
    geoms = _of(master, sections, "road", "sidewalk", "context_building")
    names = list(geoms)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if a.startswith("Ctx_") and b.startswith("Ctx_"):
                continue   # 이웃 건물끼리는 실측 윤곽이 벽을 맞대 약간 겹친다(자료 그대로)
            assert geoms[a].intersection(geoms[b]).area < 1e-3, (a, b)   # 메시 삼각분할 오차(약 1e-6 ㎡)보다 큰 겹침만 본다


def test_the_lot_is_free_of_roads_and_neighbours(master, sections):
    lot = sections.footprint("Site_Lot")
    for name, g in _of(master, sections, "road", "sidewalk", "context_building").items():
        assert g.intersection(lot).area < 1e-3, name


def test_exterior_spaces_sit_inside_the_lot_outside_the_building_and_apart(master, sections):
    lot, slab = sections.footprint("Site_Lot"), unary_union([sections.footprint(o.name) for o in master.by_kind("slab")])
    ext = _of(master, sections, "exterior_space")
    names = list(ext)
    for n in names:
        assert ext[n].difference(lot).area < 1e-3, n
        assert ext[n].intersection(slab).area < 1e-2, n   # 슬래브 가장자리 0.5 mm 오차
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert ext[a].intersection(ext[b]).area < 1e-3, (a, b)


def test_building_lies_inside_the_lot_and_the_buildable_line(master, sections):
    slab, lot, build = (sections.footprint(n) for n in ("Slab_1F", "Site_Lot", "Setback_Line"))
    assert slab.difference(build).area < 1e-6 and slab.difference(lot).area < 1e-6
    assert lot.area == pytest.approx(7792.7, abs=1.0) and build.area == pytest.approx(6993.5, abs=1.0)


def test_the_building_being_replaced_is_not_drawn_as_a_neighbour(master):
    assert not [o for o in master.objects if o.kind == "context_building" and "굿모닝" in o.name_ko]


def test_master_with_context_passes_every_model_check(sections):
    assert run_model_checks(sections, P) == []


def test_original_building_data_has_no_context_unless_asked():
    assert not [o for o in build_objects(load_source(), adjustments={}) if o.kind in CONTEXT_KINDS]


def test_building_plan_does_not_draw_the_site_but_site_plan_does(master, sections, tmp_path):
    b = render_plan(sections, P, tmp_path / "b.png", annotation=plan_annotation(master, P), detail=True)
    assert not any(l.owner.startswith(("Site_", "Road_", "Sidewalk_", "Ctx_", "Setback_", "Ext_", "Trees", "Subway_"))
                   for l in b.lines)
    w = render_plan(sections, SITE_P, tmp_path / "w.png", annotation=plan_annotation(master, SITE_P, site=True),
                    detail=True, scope="site")
    owners = {l.owner for l in w.lines}
    assert {"Site_Lot", "Setback_Line", "Road_Carriageway", "Ext_Grove", "Trees", "Sunken_Stair:tread0", "Entrance_Main"} <= owners
    assert "annot:frame" not in owners   # 참고 도면처럼 테두리 없음
    texts = {t.text for t in w.texts}
    assert {"대지", "7,793㎡", "을지로", "장충단로"} <= texts   # 면적은 폴리곤 계산값
    in_drawing = {t.text for t in w.texts if not t.owner.startswith("legend")}
    assert "시장 홀" not in in_drawing and "그늘 숲 마당" not in in_drawing   # 이름은 범례에만 있다
    assert run_render_checks(b, P) == [] and run_render_checks(w, SITE_P) == []
    assert (w.canvas[2] - w.canvas[0]) > (b.canvas[2] - b.canvas[0])


def test_site_and_exterior_labels_never_land_on_the_building(master, sections, tmp_path):
    w = render_plan(sections, SITE_P, tmp_path / "w.png", annotation=plan_annotation(master, SITE_P, site=True),
                    detail=True, scope="site")
    from shapely.geometry import Polygon
    building = Polygon(sections.footprint("Slab_1F").exterior)
    for t in w.texts:
        if t.owner.startswith(("Site_", "Ext_", "Road_", "Ctx_", "Subway_")):
            assert not box(*t.bbox).intersects(building), t.text


def test_paper_fit_is_computed_from_the_canvas():
    assert paper_fit((0, 0, 100, 60), 200)["smallest_iso_paper"] == "A2"        # 500 x 300 mm: A3(420x297)에는 회전해도 안 들어간다
    assert paper_fit((0, 0, 100, 60), 200)["drawing_mm"] == [500.0, 300.0]


def test_site_plan_uses_numbers_in_the_drawing_and_names_in_the_legend(master, sections, tmp_path):
    w = render_plan(sections, SITE_P, tmp_path / "w.png", annotation=plan_annotation(master, SITE_P, site=True),
                    detail=True, scope="site")
    legend = {t.owner: t.text for t in w.texts if t.owner.startswith("legend:")}
    names = {v for k, v in legend.items() if k.endswith(":name")}
    numbers = {v for k, v in legend.items() if k.endswith(":no")}
    assert {"시장 홀", "필로티 광장", "특별피난계단 코어", "화장실", "사거리 공개공지 광장", "그늘 숲 마당"} <= names
    assert not {"차도", "보도", "이웃 건물"} & names                              # 참고 도면: 견본·기호 항목 없이 번호 + 이름만
    assert numbers == {str(i) for i in range(1, len(numbers) + 1)}              # 번호는 1부터 빠짐없이
    in_plan = {t.text for t in w.texts if t.text.isdigit() and not t.owner.startswith(("legend", "annot"))}
    assert in_plan == numbers                                                   # 도면의 번호와 범례의 번호가 정확히 같다(양방향)
    assert "시장 홀" not in {t.text for t in w.texts if not t.owner.startswith("legend")}


def test_the_building_plan_keeps_names_not_numbers(master, sections, tmp_path):
    b = render_plan(sections, P, tmp_path / "b.png", annotation=plan_annotation(master, P), detail=True)
    texts = {t.text for t in b.texts}
    assert {"시장 홀", "필로티 광장"} <= texts and not any(t.owner.startswith("legend") for t in b.texts)


def test_hatch_is_used_only_for_the_plaza_like_the_reference_drawing():
    from render.style import HATCH, KIND_STYLE, LINE_CLASSES

    assert set(HATCH) == {"use:plaza"}
    for kind in ("road", "sidewalk", "context_building", "tree", "exterior_space"):
        klass, fill = KIND_STYLE[kind]
        assert klass == "context" and fill is None                # 맥락은 옅은 가는 선, 채움 없음
    assert LINE_CLASSES["context"].lw_max <= 0.4 and LINE_CLASSES["context"].color > "#aaaaaa"   # 건물 선보다 옅다


def test_every_footprint_survives_the_json_round_trip_at_any_slice_height(master, tmp_path):
    """코드 검토 지적: 기존 시험은 반올림 안 된 모델만 잘랐다. 저장·재적재한 전체 모델을 여러 높이에서 잘라 면적이 같은지 본다."""
    import numpy as np

    from checks.geometry import check_g7_footprints
    from extract import slicer
    from extract.loader import load_model
    from master.build_master import write_model_json

    reloaded = load_model(write_model_json(master, tmp_path / "m.json"))
    original = slice_model(master, P.check_heights_m)
    for frac in np.linspace(0.05, 0.95, 19):                                   # 정확한 중간(0.5)을 포함해 여러 높이
        for o in reloaded.objects:
            ref = slicer.section(master.get(o.name), master.get(o.name).zmin + frac * (o.zmax - o.zmin)).area
            got = slicer.section(o, o.zmin + frac * (o.zmax - o.zmin)).area
            assert got == pytest.approx(ref, rel=1e-4, abs=1e-4), (o.name, frac)
    assert check_g7_footprints(slice_model(reloaded, P.check_heights_m), P) == []
    assert original.footprint("Entrance_Main").area == pytest.approx(slice_model(reloaded, P.check_heights_m).footprint("Entrance_Main").area, rel=1e-4)


def test_g7_detects_partial_loss_of_a_footprint(master):
    from checks.geometry import check_g7_footprints
    from extract.schema import Model, ModelObject

    import numpy as np

    plate = master.get("Sidewalk_Verge")
    # 아랫면 삼각형 일부를 뺀다: 옆면은 그대로라 윤곽(면적)은 남지만 아랫면 면적이 줄어 서로 달라진다
    is_bottom = np.array([abs(plate.verts[t][:, 2] - plate.zmin).max() < 1e-9 for t in plate.tris])
    drop = np.flatnonzero(is_bottom)[::7]
    assert len(drop) > 0
    broken = ModelObject("깨진 보도", {"kind": "sidewalk", "name_ko": "깨진 보도"}, plate.verts, np.delete(plate.tris, drop, axis=0))
    s = slice_model(Model([broken]), P.check_heights_m)
    assert s.footprint("깨진 보도").area > 0                                    # 윤곽은 남아 있지만
    assert any(v.check == "G7" and "일부 손실" in v.message for v in check_g7_footprints(s, P))   # G7이 잡는다


def test_subway_exits_and_trees_do_not_sit_on_the_carriageway(master, sections):
    road = sections.footprint("Road_Carriageway")
    for o in master.objects:
        if o.kind in ("subway_exit", "tree"):
            g = sections.footprint(o.name)
            assert g.intersection(road).area < 0.05 * max(g.area, 1e-9), o.name

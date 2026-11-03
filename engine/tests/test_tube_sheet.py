import json

from checks.registry import run_render_checks, run_tube_checks
from engine_params import load_params
from master.build_master import load_source
from master.tube_sheet import build_tube_sheet, build_world_tubes, sheet_texts
from render.tube_sheet import place_on_sheet, render_tube_sheet

P = load_params()


def test_sheet_places_tubes_in_grid_and_capsule_on_the_right():
    tubes = {t.tube_id: t for t in place_on_sheet(build_world_tubes(load_source(), P))}
    assert tubes["T1"].center[1] > tubes["T3"].center[1] and tubes["T1"].center[0] < tubes["T2"].center[0]
    assert tubes["CAP_W"].outer.bounds[0] > tubes["T2"].outer.bounds[2]
    for t in tubes.values():
        assert len(t.columns) >= 1


def test_sheet_render_is_clean_and_labelled(tmp_path):
    tubes = place_on_sheet(build_world_tubes(load_source(), P))
    res = render_tube_sheet(tubes, P, tmp_path / "t.png", *sheet_texts(P))
    assert run_render_checks(res, P) == []
    texts = [t.text for t in res.texts]
    assert texts.count("승강 로비") == 2 and {"램프", "빛 튜브", "서측 캡슐"} <= set(texts)


def test_build_tube_sheet_passes_and_writes_a_report(tmp_path):
    report = build_tube_sheet(out_dir=tmp_path / "out", rejected_dir=tmp_path / "rej", name="tube")
    assert report.ok, report.violations
    data = json.loads((tmp_path / "out" / "tube.report.json").read_text(encoding="utf-8"))
    assert set(data["tubes"]) == {"T1", "T2", "T3", "T4", "CAP_W"} and data["violations"] == []
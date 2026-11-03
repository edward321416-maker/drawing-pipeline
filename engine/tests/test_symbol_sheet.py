import json

from checks.registry import run_render_checks, run_symbol_checks
from engine_params import load_params
from master.build_master import load_source
from master.core_sheet import build_core_sheet, sheet_texts
from render.symbol_sheet import build_sheet_cores, render_core_sheet

P = load_params()


def _sizes():
    return {cid: (b[2] - b[0], b[3] - b[1]) for cid, b in load_source()["stairs"].items()}


def test_sheet_places_four_cores_in_a_grid_without_overlap():
    cores = build_sheet_cores(_sizes(), P)
    assert [c.core_id for c in cores] == ["A", "B", "C", "D"]
    footprints = {c.core_id: c.bounds for c in cores}
    ax0, ay0, ax1, ay1 = footprints["A"]
    bx0, by0, bx1, by1 = footprints["B"]
    cx0, cy0, cx1, cy1 = footprints["C"]
    assert ax1 < bx0 and ay0 == by0 and cy1 < ay0   # A·B는 위 행에 나란히, C·D는 아래 행
    for c in cores:
        assert run_symbol_checks(c, P) == []


def test_sheet_render_is_clean_and_labelled(tmp_path):
    cores = build_sheet_cores(_sizes(), P)
    title, subtitle, legend = sheet_texts(P, cores[0].steps_required)
    res = render_core_sheet(cores, P, tmp_path / "sheet.png", title, subtitle, legend)
    assert run_render_checks(res, P) == []
    texts = [t.text for t in res.texts]
    assert {"코어 A", "코어 B", "코어 C", "코어 D", "부속실"} <= set(texts)
    assert texts.count("UP") == 4
    assert {"42㎡", "49㎡", "36㎡"} <= set(texts)
    assert any("34단" in t for t in texts)               # 부제: 층고 6 m → 34단 필요


def test_build_core_sheet_passes_and_writes_a_report(tmp_path):
    report = build_core_sheet(out_dir=tmp_path / "out", rejected_dir=tmp_path / "rej", name="sheet")
    assert report.ok, report.violations
    assert (tmp_path / "out" / "sheet.png").exists()
    data = json.loads((tmp_path / "out" / "sheet.report.json").read_text(encoding="utf-8"))
    assert set(data["cores"]) == {"A", "B", "C", "D"} and data["violations"] == []
    assert data["cores"]["B"]["steps_provided"] == 48 and data["cores"]["C"]["steps_provided"] == 36

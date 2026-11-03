import json

from checks.registry import run_render_checks, run_restroom_checks
from engine_params import load_params
from master.build_master import load_source
from master.restroom_sheet import build_restroom_sheet, room_columns, sheet_texts
from render.restroom_sheet import build_sheet_restrooms, render_restroom_sheet

P = load_params()


def _round(cols):
    return {k: [tuple(round(v, 3) for v in c) for c in cs] for k, cs in cols.items()}


def test_columns_found_in_the_two_rooms_match_the_midterm_plan():
    assert _round(room_columns(load_source(), {})) == {"B": [(3.9, 3.6)], "C": [(4.9, 2.6)]}   # 원본 위치


def test_columns_follow_the_approved_restroom_shift():
    # B는 북쪽으로 0.225 m, C는 남쪽으로 0.325 m 옮겼으므로 같은 기둥이 방 안에서 그만큼 반대로 보인다
    assert _round(room_columns(load_source())) == {"B": [(3.9, 3.375)], "C": [(4.9, 2.925)]}


def test_sheet_render_is_clean_and_labelled(tmp_path):
    src = load_source()
    sizes = {rid: (b[2] - b[0], b[3] - b[1]) for rid, b in src["wc"].items()}
    rooms = build_sheet_restrooms(sizes, P)
    for rr in rooms:
        assert run_restroom_checks(rr, P) == []
    res = render_restroom_sheet(rooms, P, tmp_path / "wc.png", *sheet_texts(P))
    assert run_render_checks(res, P) == []
    texts = {t.text for t in res.texts}
    assert {"공용·장애인 겸용", "남자 화장실", "여자 화장실", "장애인 화장실"} <= texts


def test_build_restroom_sheet_passes_and_writes_a_report(tmp_path):
    report = build_restroom_sheet(out_dir=tmp_path / "out", rejected_dir=tmp_path / "rej", name="wc")
    assert report.ok, report.violations
    data = json.loads((tmp_path / "out" / "wc.report.json").read_text(encoding="utf-8"))
    assert set(data["rooms"]) == {"B", "C"} and data["violations"] == []
    assert data["rooms"]["C"]["units"] == ["남", "여", "장애인"]

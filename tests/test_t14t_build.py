"""C-T14T: targeted corrections on top of the PR #29 floor plans (deterministic checks only, no architectural review)."""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from t14s import build, planner, source  # noqa: E402

COL_R = source.COL_R


def _plan(f):
    pl = planner.Planner2(source.load_floor(f), 7)
    pl.run()
    return pl


def _validator():
    spec = importlib.util.spec_from_file_location("t14t_validate", os.path.join(ROOT, "tools", "t14s", "validate_t14t.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_pinned_sources_are_unchanged():
    r = source.verify_sources()
    assert r["ok"], r["problems"]


def test_escalator_axes_come_from_the_pinned_slices():
    g = source.load_floor("3F")
    roles = {(e["label"], e["role"]) for e in g.esc_ends}
    assert any(l.startswith("2F") and r == "arrive" for l, r in roles) and any(l.startswith("3F") and r == "board" for l, r in roles)
    g8 = source.load_floor("8F")
    assert any(e["role"] == "through" and e["express"] for e in g8.esc_ends)


def test_elevator_car_objects_are_not_shafts_and_not_labelled():
    g = source.load_floor("2F")
    assert sorted(g.shafts) == ["EV1", "EV2"] and "A-VERT-ELEV_car_0" in g.cars
    pl = _plan("2F")
    assert all("car_" not in t.s for t in pl.d.texts)
    assert all("car_" not in v["name"] and "car_" not in v["id"] for v in pl.vertical)


def test_3f_has_a_complete_connected_circulation_graph():
    pl = _plan("3F")
    G = pl.graph
    assert G["unresolved"] == []
    assert all(u["reachable"] for u in G["unit_doors"])
    assert {n["id"] for n in G["nodes"]} >= {"core A", "core B", "core C", "core D", "tube T3", "tube T4"}


def test_t3_entry_is_turned_off_the_capsule():
    pl = _plan("3F")
    assert any(x.get("turn_deg") == 45.0 for x in pl.decisions.get("D-03", []))
    assert pl.graph["summary"]["connected"] == pl.graph["summary"]["visitor_nodes"]


def test_capsule_escalator_landing_is_reported_not_faked():
    pl = _plan("4F")
    items = {u["id"]: u for u in pl.graph["unresolved"]}
    assert items and all(u["decision"] == "D-01" and u["status"] == "AT_OPENING_EDGE" for u in items.values())
    assert all(x["gap_to_slab_m"] > 1.0 for x in pl.decisions["D-01"])


def test_cores_without_slab_are_closed_and_recorded():
    assert {x["core"] for x in _plan("2F").decisions["D-02"]} == {"D"}
    assert {x["core"] for x in _plan("7F").decisions["D-02"]} == {"C", "D"}
    assert "core C" not in {n["id"] for n in _plan("7F").graph["nodes"]}


def test_routes_keep_a_clear_band_at_columns_and_stay_on_slab():
    for f in ("7F", "12F", "15F"):
        pl = _plan(f)
        g = pl.g
        for _a, _b, ls, _p in pl.routes:
            assert min(ls.distance(__import__("shapely").geometry.Point(c)) for c in g.columns) - COL_R >= 0.55
            assert ls.difference(g.slab.buffer(0.05)).length < 0.01


def test_back_of_house_and_service_routes_exist_on_retail_and_fnb_floors():
    pl = _plan("3F")
    assert any(r["kind"] == "support" for r in pl.rooms) and pl.svc_routes
    assert pl.graph["service_root"] is not None


def test_garden_floor_has_walkways_beds_and_seating():
    pl = _plan("15F")
    gd = [r["garden"] for r in pl.rooms if r["kind"] == "garden"][0]
    assert gd["path_m"] > 50 and gd["beds"] >= 3 and gd["benches"] >= 3


def test_culture_floors_use_differentiated_concepts():
    names = {r["name"] for r in _plan("12F").rooms}
    assert not names & {"다목적 홀", "스튜디오", "체험 공방", "미디어랩", "라운지"}
    assert any("전시" in n or "미디어" in n or "큐레이션" in n for n in names)


def test_full_export_of_two_floors_passes_deterministic_checks(tmp_path):
    programs, levels = build.program_table()
    for f in ("3F", "7F"):
        build.build_floor(f, programs, levels, tmp_path)
    build.write_manifest(tmp_path)
    val = _validator()
    for f in ("3F", "7F"):
        res = val.check_floor(str(tmp_path), f)
        assert res["pass"], {k: v for k, v in res["checks"].items() if not v["pass"]}

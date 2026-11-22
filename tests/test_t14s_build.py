"""C-T14S: source pin, deterministic planning, and a full export of two representative floors (regular 3F + half-slab 7F)."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from t14s import layout, source  # noqa: E402


def test_source_slices_are_pinned_and_unchanged():
    r = source.verify_sources()
    assert r["ok"], r["problems"]
    assert r["files"] == 19


def test_target_floors_are_the_16_missing_ones():
    assert len(source.TARGET_FLOORS) == 16
    assert "1F" not in source.TARGET_FLOORS and source.TARGET_FLOORS[:2] == ["B2", "B1"]


def test_planning_is_deterministic():
    a, b = layout.plan_floor("5F"), layout.plan_floor("5F")
    assert [(r["name"], r["area_m2"]) for r in a.rooms] == [(r["name"], r["area_m2"]) for r in b.rooms]


@pytest.mark.parametrize("floor", ["3F", "7F"])
def test_geometry_is_taken_from_the_slice_and_rooms_do_not_overlap_openings(floor):
    g = source.load_floor(floor)
    d = layout.plan_floor(floor)
    for r in d.rooms:
        if r["kind"] in ("unit", "hall"):
            assert r["poly"].intersection(g.slab).area >= r["poly"].area - 0.5, "room %s leaves the slab" % r["id"]
    cols = [it for it in d.items if it.layer == "A-COLS"]
    assert len(cols) == len(g.columns)

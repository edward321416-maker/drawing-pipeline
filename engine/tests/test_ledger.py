# FILE: tests/test_ledger.py
import test_regression
from checks.registry import CHECK_IDS, MODEL_CHECKS, RENDER_CHECKS, RESTROOM_CHECKS, SYMBOL_CHECKS, TUBE_CHECKS
from ledger.ledger import audit_ledger, load_ledger


def test_registry_ids_are_complete():
    assert CHECK_IDS == {"TAG", "LAYOUT", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "R1", "R2", "R3", "T1", "T2", "T3", "T4"}
    assert set(SYMBOL_CHECKS) == {"R1", "G3"}
    assert set(RESTROOM_CHECKS) == {"R2", "G3"}
    assert set(TUBE_CHECKS) == {"R3"}
    assert set(MODEL_CHECKS) == {"G1", "G2", "G3", "G4", "G5", "G6", "G7"}
    assert set(RENDER_CHECKS) == {"T1", "T2", "T3", "T4"}


def test_project_ledger_is_consistent_with_registry():
    assert audit_ledger(load_ledger(), CHECK_IDS) == []


def test_every_active_defect_has_an_existing_regression_test():
    for d in load_ledger():
        if d.get("checks"):
            assert d.get("regression_test"), f"{d['id']}: regression_test 없음"
            assert hasattr(test_regression, d["regression_test"]), f"{d['id']}: {d['regression_test']} 없음"


def test_audit_detects_stale_and_missing_entries():
    defects = [
        {"id": "X-1", "title": "a", "checks": ["G9"], "planned_checks": []},
        {"id": "X-2", "title": "b", "checks": [], "planned_checks": ["G1"]},
        {"id": "X-3", "title": "c", "checks": [], "planned_checks": []},
        {"id": "X-3", "title": "dup", "checks": ["G1"], "planned_checks": []},
    ]
    problems = " | ".join(audit_ledger(defects, CHECK_IDS))
    assert "G9" in problems and "이미 구현" in problems and "연결된 검사가 없음" in problems and "중복" in problems

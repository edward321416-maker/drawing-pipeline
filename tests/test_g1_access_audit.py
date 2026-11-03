"""G1/T1.1 출입문 감사: 실제 문과 렌더러 그래픽의 혼동 방지 테스트."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.audit_g1_access_anchors import audit  # noqa: E402


def square_segments(x0: float, y0: float, x1: float, y1: float):
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    return [list(a + b) for a, b in zip(corners[:-1], corners[1:])]


class TestAccessAudit(unittest.TestCase):
    def setUp(self):
        self.source = {
            "columns": [None] * 34,
            "stairs": {"A": [], "B": []},
            "wc": {"C": []},
        }
        self.site = {"entrances": [{"key": key} for key in ("Main", "Subway", "Service")]}
        self.spec = {"anchors": [
            {"id": "PUBLIC_MARKET_DOOR", "status": "VERIFY_REQUIRED"},
            {"id": "CAPSULE_DOOR", "status": "VERIFY_REQUIRED"},
        ]}
        self.slice = {
            "floor": "1F",
            "zones": [{"name": "Zone_Market", "segments": square_segments(0, 0, 10, 10)}],
            "elements": [
                {"kind": "tube_wall", "name": "Capsule_W", "name_ko": "서측 캡슐",
                 "segments": square_segments(20, 0, 26, 10)}
            ],
            "symbols": [],
        }

    def test_without_slice_remains_unverified(self):
        result = audit(self.source, self.site, self.spec)
        self.assertTrue(result["ok_source_references"])
        self.assertFalse(result["raw_slice_read"])
        self.assertFalse(result["gate_passed"])
        self.assertFalse(result["anchors"]["PUBLIC_MARKET_DOOR"]["model_opening_verified"])

    def test_nearby_core_door_never_becomes_market_entry(self):
        data = copy.deepcopy(self.slice)
        data["symbols"].append(
            {"category": "door", "name": "Core_B_door_hall",
             "props": {"core_id": "B"}, "segments": square_segments(9.8, 4, 10.2, 5)}
        )
        result = audit(self.source, self.site, self.spec, data)
        self.assertTrue(result["model_door_symbols"][0]["near_market_boundary"])
        self.assertEqual(result["anchors"]["PUBLIC_MARKET_DOOR"]["source_door_candidates"], [])

    def test_other_model_door_is_candidate_not_verified_opening(self):
        data = copy.deepcopy(self.slice)
        data["symbols"].append(
            {"category": "door", "name": "Possible_Entry",
             "props": {"kind": "door"}, "segments": square_segments(9.8, 4, 10.2, 5)}
        )
        result = audit(self.source, self.site, self.spec, data)
        self.assertEqual(result["anchors"]["PUBLIC_MARKET_DOOR"]["source_door_candidates"], ["Possible_Entry"])
        self.assertFalse(result["anchors"]["PUBLIC_MARKET_DOOR"]["model_opening_verified"])
        self.assertFalse(result["gate_passed"])

    def test_capsule_door_nearby_is_candidate_only(self):
        data = copy.deepcopy(self.slice)
        data["symbols"].append(
            {"category": "door", "name": "Possible_Capsule_Door",
             "props": {}, "segments": square_segments(19.8, 4, 20.2, 5)}
        )
        result = audit(self.source, self.site, self.spec, data)
        self.assertEqual(result["anchors"]["CAPSULE_DOOR"]["source_door_candidates"], ["Possible_Capsule_Door"])
        self.assertFalse(result["gate_passed"])

    def test_wrong_floor_is_rejected(self):
        data = copy.deepcopy(self.slice)
        data["floor"] = "2F"
        self.assertFalse(audit(self.source, self.site, self.spec, data)["ok_source_references"])

    def test_known_site_marker_not_physical_door(self):
        result = audit(self.source, self.site, self.spec, self.slice)
        self.assertFalse(result["site_markers_are_physical_doors"])

    def test_preconfirmed_model_door_is_rejected(self):
        spec = copy.deepcopy(self.spec)
        spec["anchors"][0]["status"] = "SOURCE_CONFIRMED"
        self.assertFalse(audit(self.source, self.site, spec)["ok_source_references"])


if __name__ == "__main__":
    unittest.main()

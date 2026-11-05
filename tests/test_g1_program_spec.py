"""G1 계획 검사가 실제 오류 입력을 거부하는지 확인한다.

기준: 원본 1층 source JSON·대지 JSON (3D 렌더를 실행하지 않는 스키마 테스트).
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.validate_g1_program_spec import DEFAULT_MASTER, DEFAULT_SITE, DEFAULT_SPEC, read_json, validate  # noqa: E402


class TestG1ProgramSpec(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_spec = read_json(DEFAULT_SPEC)
        cls.master = read_json(DEFAULT_MASTER)
        cls.site = read_json(DEFAULT_SITE)

    def test_current_plan_is_structurally_consistent_but_unapproved(self):
        report = validate(self.original_spec, self.master, self.site)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["parent_programs"], 4)
        self.assertEqual(report["subprograms"], 18)
        self.assertFalse(report["user_final_freeze"])
        self.assertGreater(len(report["pending_geometry_and_legal_checks"]), 0)

    def test_detects_unbalanced_program_share(self):
        item = copy.deepcopy(self.original_spec)
        item["programs"][0]["subprograms"][0]["soft_target_share"] = 0.5
        report = validate(item, self.master, self.site)
        self.assertFalse(report["ok"])
        self.assertTrue(any("100%" in x for x in report["errors"]))

    def test_rejects_unsupported_absolute_geometry(self):
        item = copy.deepcopy(self.original_spec)
        item["programs"][0]["subprograms"][0]["coordinates"] = [0, 0]
        report = validate(item, self.master, self.site)
        self.assertFalse(report["ok"])
        self.assertTrue(any("절대좌표" in x for x in report["errors"]))

    def test_rejects_unknown_relationships(self):
        item = copy.deepcopy(self.original_spec)
        item["relationships"][0]["to"] = "UNKNOWN_PROGRAM"
        report = validate(item, self.master, self.site)
        self.assertFalse(report["ok"])

    def test_rejects_unverified_door_claimed_confirmed(self):
        item = copy.deepcopy(self.original_spec)
        for a in item["anchors"]:
            if a["id"] == "PUBLIC_MARKET_DOOR":
                a["status"] = "SOURCE_CONFIRMED"
                break
        report = validate(item, self.master, self.site)
        self.assertFalse(report["ok"])

    def test_fails_when_model_column_inventory_does_not_match(self):
        item = copy.deepcopy(self.master)
        item["columns"] = item["columns"][:-1]
        report = validate(self.original_spec, item, self.site)
        self.assertFalse(report["ok"])
        self.assertTrue(any("기둥" in x for x in report["errors"]))

    def test_rejects_loss_of_service_public_separation(self):
        item = copy.deepcopy(self.original_spec)
        item["relationships"] = [
            row for row in item["relationships"]
            if (row["from"], row["to"]) != ("S01", "P01")
        ]
        report = validate(item, self.master, self.site)
        self.assertFalse(report["ok"])
        self.assertTrue(any("하역-필로티" in x for x in report["errors"]))


if __name__ == "__main__":
    unittest.main()

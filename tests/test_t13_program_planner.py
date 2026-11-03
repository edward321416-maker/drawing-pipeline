"""C-T13 프로그램 계획기 단위 시험 (실모델 기하 덤프 tests/fixtures/t13_geom_1F.json 기준).

    python -m unittest tests.test_t13_program_planner -v
"""
import json
import os
import sys
import unittest

from shapely.ops import unary_union

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
import program_planner as PP  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "t13_geom_1F.json")


class PlannerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.I = PP.input_from_dump(json.load(open(FIX, encoding="utf-8")))
        cls.P = {v: PP.plan_program(v, cls.I) for v in "AB"}
        cls.Q = {v: PP.qa(cls.P[v], cls.I) for v in "AB"}

    def test_all_18_programs_present_and_nonempty_except_none(self):
        for v in "AB":
            self.assertEqual(set(self.P[v]["zones"]), set(PP.PROGRAMS))
            for k in ("M01", "M02", "M03", "M04", "M05", "M06", "P01", "S02", "C01", "C02", "C03", "C04"):
                self.assertGreater(self.P[v]["zones"][k].area, 1.0, (v, k))

    def test_zones_inside_parent_and_disjoint(self):
        for v in "AB":
            self.assertEqual(self.Q[v]["zone_outside_parent_m2_max"], 0.0)
            self.assertEqual(self.Q[v]["zone_overlap_m2_total"], 0.0)

    def test_no_unassigned_floor(self):
        for v in "AB":
            self.assertEqual(sum(self.Q[v]["unassigned_net_floor_m2"].values()), 0.0)

    def test_areas_come_from_polygons(self):
        for v in "AB":
            for k, a in self.Q[v]["area_table"].items():
                self.assertAlmostEqual(a, round(self.P[v]["zones"][k].area, 2), places=2)

    def test_furniture_clear_of_structure_and_each_other(self):
        for v in "AB":
            q = self.Q[v]
            self.assertEqual(q["furniture_hits_structure"], 0)
            self.assertEqual(q["furniture_outside_parent_zone"], 0)
            self.assertEqual(q["furniture_instance_overlaps"], 0)
            self.assertEqual(q["furniture_in_entry_clearance"], 0)

    def test_furniture_bodies_exist_per_program(self):
        for v in "AB":
            zs = {it["zone"] for it in self.P[v]["furniture"]}
            for k in ("M01", "M02", "M03", "M04", "M05", "C01", "C02", "C03"):
                self.assertIn(k, zs, (v, k))
            self.assertNotIn("M06", zs)                                              # 순환 구획에는 가구가 없다
            self.assertNotIn("P01", zs)

    def test_circulation_is_clear_of_furniture(self):
        for v in "AB":
            free = unary_union([self.P[v]["zones"]["M06"], self.P[v]["zones"]["P01"]])
            for it in self.P[v]["furniture"]:
                self.assertLess(it["fp"].intersection(free).area, 1e-6, (v, it["zone"], it["type"]))

    def test_entries_are_proposed_only(self):
        for v in "AB":
            for e in self.P[v]["entries"]:
                self.assertIn("PROPOSED_ONLY", e["status"])

    def test_variants_are_functionally_different(self):
        a, b = self.P["A"], self.P["B"]
        self.assertNotAlmostEqual(a["zones"]["M02"].area, b["zones"]["M02"].area, places=0)
        ta = sorted({it["type"] for it in a["furniture"] if it["zone"] == "M02"})
        tb = sorted({it["type"] for it in b["furniture"] if it["zone"] == "M02"})
        self.assertNotEqual(ta, tb)
        self.assertNotEqual(a["entries"][0]["center"], b["entries"][0]["center"])      # 주 진입 후보가 다르다
        self.assertNotEqual(a["door_pt"], b["door_pt"])                                 # 캡슐 입구 후보가 다르다

    def test_deterministic(self):
        again = PP.plan_program("A", self.I)
        for k in PP.PROGRAMS:
            self.assertAlmostEqual(again["zones"][k].area, self.P["A"]["zones"][k].area, places=6)
        self.assertEqual(len(again["furniture"]), len(self.P["A"]["furniture"]))

    def test_main_corridor_width_target(self):
        for v in "AB":
            c = self.P[v]["corr_main"]
            self.assertGreater(c.area, 50.0)
            # 주 통로 폭 2.4 m: 복도 안쪽 1.1 m 안으로 줄여도 비지 않는다 (좁은 구간은 막힌 틈이라 클리핑됨)
            self.assertFalse(c.buffer(-1.0).is_empty)


if __name__ == "__main__":
    unittest.main()

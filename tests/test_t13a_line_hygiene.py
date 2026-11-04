"""C-T13A 선 정리 단위 시험: 구조선은 모양이 그대로, 호·베지어는 편차 안에서만, 퇴화 호·오판정 없음.

    python tests/test_t13a_line_hygiene.py -v
"""
import math
import os
import sys
import unittest

from shapely.geometry import LineString, Point, box

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import furniture_library as FL  # noqa: E402
import line_hygiene as LH  # noqa: E402
import t13a_geometry_check as G  # noqa: E402


def dev(d, poly_pts):
    sub = LH.sample_path(d, n_arc=48, n_bez=24)
    worst = 0.0
    for s in sub:
        worst = max(worst, LH.poly_distance(s, poly_pts), LH.poly_distance(poly_pts, s))
    return worst


class CleanLineTest(unittest.TestCase):
    def test_circle_becomes_exact_arcs_within_tolerance(self):
        for r, q in ((0.18, 12), (0.45, 8), (4.49, 32)):
            c = Point(3, 4).buffer(r, quad_segs=q)
            log = []
            d = LH.build_path(list(c.exterior.coords), True, False, log, "walls")
            self.assertEqual([e["kind"] for e in log], ["circle"])
            self.assertLessEqual(dev(d, list(c.exterior.coords)), 0.0105, (r, q))

    def test_rounded_rectangle_keeps_straight_sides_and_gets_corner_arcs(self):
        rr = FL.rrect((0, 0), (1, 0), (0, 1), 0, 0, 3.2, 2.2, 0.15)
        log = []
        d = LH.build_path(list(rr.exterior.coords), True, False, log, "furn")
        self.assertEqual(sorted(e["kind"] for e in log), ["arc"] * 4)
        self.assertLessEqual(dev(d, list(rr.exterior.coords)), 0.002)

    def test_chair_seat_is_not_turned_into_a_circle(self):
        seat = FL.chair(0, 0, 1, 0)[0][0]                          # 둥근 네모: 모서리 꼭짓점만 한 원 위에 있다 — 원으로 오판하면 안 된다
        log = []
        d = LH.build_path(list(seat.exterior.coords), True, False, log, "furn")
        self.assertEqual(log, [])
        self.assertLessEqual(dev(d, list(seat.exterior.coords)), 0.001)           # 좌표 3자리 반올림 오차만

    def test_plain_rectangle_and_collinear_noise_unchanged(self):
        r = box(0, 0, 6, 6)
        log = []
        d = LH.build_path(list(r.exterior.coords), True, False, log, "walls")
        self.assertEqual(log, [])
        self.assertNotIn("A", d)
        pts = [(i * 1.0, 0.002 * ((-1) ** i)) for i in range(14)]
        log = []
        LH.build_path(pts, False, False, log, "walls")
        self.assertEqual(log, [])

    def test_capsule_gets_two_end_arcs(self):
        cap = LineString([(0, 0), (0, 13)]).buffer(4.0, quad_segs=16)
        log = []
        d = LH.build_path(list(cap.exterior.coords), True, False, log, "walls")
        self.assertEqual([e["kind"] for e in log], ["arc", "arc"])
        self.assertLessEqual(dev(d, list(cap.exterior.coords)), 0.01)

    def test_closed_polyline_is_not_a_degenerate_single_arc(self):
        c = Point(0, 0).buffer(2.0, quad_segs=16)
        pts = list(c.exterior.coords)                              # 시작=끝인 닫힌 폴리라인
        d = LH.build_path(pts, False, False, [], "walls")          # 열린 열로 들어와도 시작점=끝점인 단일 호가 나오면 안 된다
        arcs = [seg for seg in d.split("A")[1:]]
        for a in arcs:
            self.assertNotEqual(a.split()[-1].split(",")[0:2], [])  # 형식 확인
        self.assertLessEqual(dev(d, pts), 0.01)
        sub = LH.sample_path(d, 48)[0]
        self.assertGreater(LineString(sub).length, 0.9 * LineString(pts).length)

    def test_decorative_curve_smoothing_within_tolerance_and_corners_kept(self):
        pts = [(t, 2.0 * math.sin(t / 3.0)) for t in [i * 0.2 for i in range(0, 120)]]
        pts += [(24.0, 5.0), (24.0, 9.0)]                         # 90° 모서리
        log = []
        d = LH.build_path(pts, False, True, log, "landscape")
        self.assertTrue(any(e["kind"] == "smooth" for e in log))
        self.assertLessEqual(max(e["max_dev_m"] for e in log), LH.SMOOTH_TOL)
        self.assertLessEqual(dev(d, pts), LH.SMOOTH_TOL + 0.01)
        self.assertIn("L24,9", d)                                   # 마지막 모서리 이후 직선 보존

    def test_structure_layers_never_smoothed(self):
        pts = [(t, 2.0 * math.sin(t / 3.0)) for t in [i * 0.2 for i in range(0, 120)]]
        log = []
        d = LH.build_path(pts, False, False, log, "walls")         # smooth=False 가 구조 층의 설정
        self.assertNotIn("C", d)                                   # 베지어(평활) 없음
        self.assertLessEqual(dev(d, pts), 0.012)                    # 호 적합이 있어도 편차는 허용 안

    def test_geometry_check_detects_a_bent_element(self):
        before = '<g id="walls"><path d="M0,0 L10,0 L10,10 L0,10 Z" fill="none" stroke="#000"/></g>'
        after_ok = '<g id="walls"><path d="M0,0 L10,0 L10,10 L0,10 Z" fill="none" stroke="#000"/></g>'
        after_bad = '<g id="walls"><path d="M0,0 L10,0.5 L10,10 L0,10 Z" fill="none" stroke="#000"/></g>'
        self.assertEqual(G.compare(before, after_ok, ("walls",))["walls"]["over_tol"], 0)
        self.assertEqual(G.compare(before, after_bad, ("walls",))["walls"]["over_tol"], 1)


if __name__ == "__main__":
    unittest.main()

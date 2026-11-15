"""Synthetic-image tests for the C-T14R region index / focus crops."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from tools.t14r.export_visual_review import build_packet
from tools.t14r.region_index import build_index, verify_focus


class RegionIndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        pixels = np.random.default_rng(7).integers(0, 255, (900, 1300, 3), dtype=np.uint8)
        self.src = self.root / "final.png"
        Image.fromarray(pixels, "RGB").save(self.src)
        base = np.random.default_rng(8).integers(0, 255, (900, 1300, 3), dtype=np.uint8)
        self.base = self.root / "base.png"
        Image.fromarray(base, "RGB").save(self.base)
        self.packet = self.root / "pkt"
        build_packet([("FINAL", self.src)], self.packet, 60 * 1024)

    def test_focus_crops_are_pixel_exact_and_within_budget(self):
        idx = build_index(self.packet, {"FINAL": self.src}, {"FINAL": self.base}, 60 * 1024, [("F01_fins_right_upper", "R2_fins", 100, 120)])
        self.assertTrue(all(f["bytes"] <= 60 * 1024 for f in idx["focus"]))
        self.assertEqual(len(idx["focus"]), 2)  # final + reference crop of the same box
        v = verify_focus(self.packet, {"FINAL": self.src}, {"FINAL": self.base}, 60 * 1024)
        self.assertEqual(v["status"], "PASS_FOCUS_PIXELS_EXACT")

    def test_regions_list_only_intersecting_tiles(self):
        idx = build_index(self.packet, {"FINAL": self.src}, {}, 60 * 1024, [])
        for region in idx["regions"]:
            for t in region["tiles"]["FINAL"]:
                x0, y0, x1, y1 = t["bounds"]
                self.assertTrue(any(x0 < b[2] and b[0] < x1 and y0 < b[3] and b[1] < y1 for b in region["boxes"]))

    def test_corrupted_focus_crop_detected(self):
        idx = build_index(self.packet, {"FINAL": self.src}, {}, 60 * 1024, [("F01_fins_right_upper", "R2_fins", 100, 120)])
        p = self.packet / idx["focus"][0]["path"]
        p.write_bytes(p.read_bytes()[:-9] + b"corrupted")
        self.assertEqual(verify_focus(self.packet, {"FINAL": self.src}, {}, 60 * 1024)["status"], "FAIL")

    def test_second_run_does_not_overwrite(self):
        build_index(self.packet, {"FINAL": self.src}, {}, 60 * 1024, [("F01_fins_right_upper", "R2_fins", 100, 120)])
        with self.assertRaises(FileExistsError):
            build_index(self.packet, {"FINAL": self.src}, {}, 60 * 1024, [("F01_fins_right_upper", "R2_fins", 100, 120)])


if __name__ == "__main__":
    unittest.main()

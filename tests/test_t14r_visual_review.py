"""No actual user image here; synthetic data only, with pixel-exact round trips."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from tools.t14r.export_visual_review import (
    SCHEMA,
    build_packet,
    verify_packet,
    sha256_file,
)


class VisualReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        pixels = np.random.default_rng(1221).integers(0, 255, (751, 1051, 3), dtype=np.uint8)
        self.source = self.root / "original.png"
        Image.fromarray(pixels, "RGB").save(self.source)
        self.source_hash = sha256_file(self.source)
        self.packet = self.root / "review"

    def test_round_trip_with_lossless_tiles(self):
        m = build_packet([("DAYLIGHT", self.source)], self.packet, 40*1024)
        self.assertEqual(m["schema"], SCHEMA)
        self.assertEqual(m["assets"][0]["original_sha256"], self.source_hash)
        self.assertGreater(len(m["assets"][0]["tiles"]), 3)
        v = verify_packet(self.packet)
        self.assertEqual(v["status"], "PASS_BYTES_AND_PIXELS_ONLY")

    def test_no_source_mutation(self):
        build_packet([("A", self.source)], self.packet, 80*1024)
        self.assertEqual(sha256_file(self.source), self.source_hash)

    def test_no_overwrite(self):
        build_packet([("A", self.source)], self.packet, 80*1024)
        with self.assertRaises(FileExistsError):
            build_packet([("A", self.source)], self.packet, 80*1024)

    def test_missing_file_does_not_make_packet(self):
        with self.assertRaises(FileNotFoundError):
            build_packet([("A", self.root/"not_here.png")], self.packet)
        self.assertFalse(self.packet.exists())

    def test_duplicate_or_unsafe_label(self):
        for labels in [["A", "A"], ["../unsafe"], ["", "A"]]:
            with self.assertRaises(ValueError):
                build_packet([(x, self.source) for x in labels], self.packet)

    def test_corruption_detected(self):
        m = build_packet([("A", self.source)], self.packet, 80*1024)
        tile = self.packet/m["assets"][0]["tiles"][0]["path"]
        tile.write_bytes(tile.read_bytes()[:-14]+b"bad")
        with self.assertRaises(ValueError):
            verify_packet(self.packet)

    def test_overlap_detected(self):
        m = build_packet([("A", self.source)], self.packet, 80*1024)
        m["assets"][0]["tiles"].append(m["assets"][0]["tiles"][0])
        (self.packet/"manifest.json").write_text(json.dumps(m))
        with self.assertRaises(ValueError):
            verify_packet(self.packet)

    def test_path_traversal_detected(self):
        m = build_packet([("A", self.source)], self.packet, 80*1024)
        m["assets"][0]["tiles"][0]["path"] = "../../original.png"
        (self.packet/"manifest.json").write_text(json.dumps(m))
        with self.assertRaises(ValueError):
            verify_packet(self.packet)

    def test_pixel_reconstruction_mismatch_detected(self):
        m = build_packet([("A", self.source)], self.packet, 80*1024)
        m["assets"][0]["pixel_sha256"] = "0"*64
        (self.packet/"manifest.json").write_text(json.dumps(m))
        with self.assertRaises(ValueError):
            verify_packet(self.packet)

    def test_max_item_under_budget(self):
        m = build_packet([("A", self.source)], self.packet, 60*1024)
        objects = m["assets"][0]["tiles"] + [m["assets"][0]["preview"], m["overview"]]
        self.assertTrue(all(o["bytes"] <= 60*1024 for o in objects))

    def test_rgba_alpha_is_pixel_exact(self):
        pixels = np.random.default_rng(22).integers(0, 255, (64, 80, 4), dtype=np.uint8)
        rgba = self.root / "transparent.png"
        Image.fromarray(pixels, "RGBA").save(rgba)
        packet = build_packet([("TRANSPARENT", rgba)], self.packet, 80*1024)
        self.assertEqual(packet["assets"][0]["pixel_format"], "RGBA")
        self.assertEqual(verify_packet(self.packet)["status"], "PASS_BYTES_AND_PIXELS_ONLY")


if __name__ == "__main__":
    unittest.main()
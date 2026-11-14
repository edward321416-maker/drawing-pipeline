"""Regression tests for the C-T14M source-lock and vector-recomposition path.

These tests use synthetic images only.  A pass verifies mechanics, never
architectural approval of any real drawing.
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.t14m.retouch_assets import ingest_pilot, prepare_pilot


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class T14MRetouchAssetsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source.png"
        image = Image.new("RGB", (240, 160), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((30, 25, 210, 135), outline="black", width=4)
        draw.line((30, 80, 210, 80), fill="black", width=3)
        image.save(self.source)
        self.svg = self.root / "source.svg"
        self.svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="240" height="160"/>', encoding="utf-8")
        self.pdf = self.root / "source.pdf"
        self.pdf.write_bytes(b"%PDF-1.4\n% synthetic authority fixture\n")
        self.packet = self.root / "packet"

    def prepare(self, asset_id: str = "G-106") -> Path:
        prepare_pilot(asset_id, self.source, self.svg, self.pdf, self.packet)
        return self.packet / f"{asset_id.replace('-', '')}_packet_manifest.json"

    def test_prepare_preserves_authoritative_source_hashes(self) -> None:
        manifest_path = self.prepare()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["source_sha256"], digest(Path(manifest["source"])))
        self.assertEqual(manifest["authoritative_svg_sha256"], digest(self.svg))
        self.assertEqual(manifest["authoritative_pdf_sha256"], digest(self.pdf))
        self.assertEqual(manifest["status"], "AWAITING_EXTERNAL_AI_RETOUCH")

    def test_ingest_restores_locked_pixels_and_recomposites_vector(self) -> None:
        manifest_path = self.prepare()
        raw = self.root / "raw.png"
        Image.new("RGB", (149, 99), "#87a9c4").save(raw)
        result = ingest_pilot(self.packet, "G-106", raw)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        accuracy = json.loads(Path(manifest["automated_accuracy_report"]).read_text(encoding="utf-8"))
        self.assertTrue(accuracy["locked_pixel_identity_pass"])
        self.assertEqual(accuracy["locked_changed_pixel_count"], 0)
        self.assertFalse(accuracy["spatial_ai_pixels_used_in_final"])

        source = Image.open(manifest["source"]).convert("RGB")
        candidate = Image.open(result["candidate"]).convert("RGB")
        lock = Image.open(manifest["pixel_lock_mask"]).convert("L")
        locked_delta = ImageChops.multiply(ImageChops.difference(source, candidate).convert("L"), lock)
        self.assertIsNone(locked_delta.getbbox())

        overlay = Image.open(manifest["vector_overlay"]).convert("RGBA")
        expected = Image.alpha_composite(candidate.convert("RGBA"), overlay)
        actual = Image.open(result["final_composite"]).convert("RGBA")
        self.assertIsNone(ImageChops.difference(expected, actual).getbbox())

    def test_raw_ai_dimensions_are_evidence_not_layout_authority(self) -> None:
        manifest_path = self.prepare("G-103")
        raw = self.root / "raw.png"
        Image.new("RGB", (97, 61), "#d0c4aa").save(raw)
        ingest_pilot(self.packet, "G-103", raw)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        accuracy = json.loads(Path(manifest["automated_accuracy_report"]).read_text(encoding="utf-8"))
        self.assertEqual(accuracy["raw_ai_pixels"], [97, 61])
        self.assertEqual(accuracy["candidate_pixels"], [240, 160])
        self.assertTrue(accuracy["raw_direct_use_rejected"])
        self.assertFalse(accuracy["spatial_ai_pixels_used_in_final"])


if __name__ == "__main__":
    unittest.main()

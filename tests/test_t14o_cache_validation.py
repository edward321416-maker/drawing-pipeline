"""Synthetic-only source-cache guard tests; not proof of the real tower scene."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.t14o.cache_validation import validate_cache


class CacheValidationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.vertices = np.array([
            [0, 0, 0], [1, 0, 0], [0, 1, 0],
            [0, 0, 6], [1, 0, 6], [0, 1, 6],
        ], dtype=float)
        self.faces = np.array([[0, 1, 2], [3, 4, 5]], dtype=int)
        self.objects = [
            {"name":"slab1", "kind":"slab", "floor":"1F", "v0":0, "nv":3, "f0":0, "nf":1},
            {"name":"core1", "kind":"core_wall", "floor":"2F", "v0":3, "nv":3, "f0":1, "nf":1},
        ]
        self.meta = {"objects": self.objects, "floors":["1F", "2F"]}
        self.save()

    def save(self):
        np.savez_compressed(self.root / "model_world.npz", V=self.vertices, F=self.faces)
        (self.root / "model_objects.json").write_text(json.dumps(self.meta), encoding="utf-8")

    def test_valid_cache_indexes(self):
        r = validate_cache(self.root)
        self.assertEqual(r["status"], "CACHE_INDEX_VALID")
        self.assertEqual(r["triangle_count"], 2)
        self.assertEqual(r["floor_tag_count"], 2)
        self.assertFalse(r["model_completeness_and_materials_verified"])

    def test_missing_source_blocks(self):
        (self.root / "model_objects.json").unlink()
        self.assertEqual(validate_cache(self.root)["status"], "BLOCKED")

    def test_hash_mismatch_blocks(self):
        r = validate_cache(self.root, "0" * 64)
        self.assertTrue(any("SOURCE_HASH_MISMATCH" in e for e in r["errors"]))

    def test_object_registry_hash_mismatch_blocks(self):
        r = validate_cache(self.root, expected_objects_hash="0" * 64)
        self.assertTrue(any("OBJECT_METADATA_HASH_MISMATCH" in e for e in r["errors"]))

    def test_global_vertex_index_out_of_range(self):
        self.faces[1][2] = 999
        self.save()
        r = validate_cache(self.root)
        self.assertIn("GLOBAL_FACE_INDEX_OUT_OF_RANGE", r["errors"])

    def test_cross_object_triangle_detected(self):
        self.faces[1][2] = 1
        self.save()
        r = validate_cache(self.root)
        self.assertTrue(any("outside the object's window" in e for e in r["errors"]))

    def test_overlapping_object_ranges_block(self):
        self.objects[1].update(v0=0, nv=6, f0=0, nf=2)
        self.save()
        r = validate_cache(self.root)
        self.assertIn("VERTEX_OBJECT_WINDOWS_OVERLAP", r["errors"])
        self.assertIn("FACE_OBJECT_WINDOWS_OVERLAP", r["errors"])

    def test_nonfinite_geometry_blocks(self):
        self.vertices[0, 1] = np.nan
        self.save()
        r = validate_cache(self.root)
        self.assertIn("NONFINITE_VERTICES", r["errors"])

    def test_corrupted_binary_blocks(self):
        (self.root / "model_world.npz").write_bytes(b"bad bytes")
        r = validate_cache(self.root)
        self.assertEqual(r["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
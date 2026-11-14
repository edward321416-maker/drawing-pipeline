"""Static and small-image tests for the C-T14O PBR/QA delivery contract."""
from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from PIL import Image

from tools.t14o import render_qa


ROOT = Path(__file__).resolve().parents[1]
SCENE_SOURCE = (ROOT / "tools" / "t14o" / "blender_pbr_scene.py").read_text(encoding="utf-8")


class PbrSceneContractTests(unittest.TestCase):
    def test_authoritative_hashes_are_pinned(self):
        self.assertIn("992e2ec51ec17dc494ed2f99ddb11298671449dd6661d92df3b3536a0049537b", SCENE_SOURCE)
        self.assertIn("722dd7359e2f13534ff4ae91088ba8649e8a8f96b27c60f000ddb09c01106488", SCENE_SOURCE)

    def test_source_vertices_and_faces_are_reconstructed_not_redrawn(self):
        self.assertIn("verts = np.asarray(v[v0:v0 + nv]", SCENE_SOURCE)
        self.assertIn("faces = np.asarray(f[f0:f0 + nf]", SCENE_SOURCE)
        self.assertIn("mesh.from_pydata(verts.tolist(), [], faces.tolist())", SCENE_SOURCE)
        self.assertNotIn("ImageEnhance", SCENE_SOURCE)
        self.assertNotIn("hero_composite", SCENE_SOURCE)

    def test_semantic_facade_material_routing_is_explicit(self):
        self.assertIn('if "glass" in name:', SCENE_SOURCE)
        self.assertIn('("mullion", "louver", "rail")', SCENE_SOURCE)
        self.assertIn('if "band" in name:', SCENE_SOURCE)
        self.assertIn('if "spandrel" in name:', SCENE_SOURCE)

    def test_target_resolution_does_not_claim_design_approval(self):
        self.assertIn("PBR_TARGET_RENDER_COMPLETE__HUMAN_ARCHITECTURAL_APPROVAL_PENDING", SCENE_SOURCE)
        self.assertNotIn("DESIGN_APPROVED", SCENE_SOURCE)

    def test_small_qa_images_and_crops_are_real_pngs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            image = Image.new("RGB", (640, 360), (40, 80, 120))
            proxy = root / "proxy.png"
            render_qa.make_proxy(image, proxy)
            self.assertTrue(proxy.is_file())
            with Image.open(proxy) as decoded:
                self.assertEqual(decoded.size, (1600, 900))
                self.assertEqual(decoded.format, "PNG")
            crops = render_qa.crop_regions(image, "TEST", root / "crops")
            self.assertEqual(set(crops), {
                "upper_roof", "facade_glazing", "middle_void_tubes", "lower_ground_contact",
            })
            self.assertTrue(all(Path(item["path"]).is_file() for item in crops.values()))


if __name__ == "__main__":
    unittest.main()

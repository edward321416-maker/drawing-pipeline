"""Synthetic-only regression tests. Passing tests never means an actual AI retouch exists."""
from __future__ import annotations
import hashlib, json, sys, tempfile, unittest
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.t14l.retouch_gate import check

class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        a = Image.new("RGB", (120, 80), "#28374b")
        a.save(self.root / "source.png")
        b = Image.new("RGB", (120, 80), "#344458")
        b.save(self.root / "retouched.png")
        Image.new("RGB", (240, 80), "#344458").save(self.root / "compare.png")
        self.data = {"asset_id":"G-002", "kind":"exterior", "source":"source.png", "source_sha256":self.h("source.png"),
                     "retouched":"retouched.png", "retouched_sha256":self.h("retouched.png"),
                     "before_after_comparison":"compare.png", "ai_tool":"ChatGPT", "retouch_export_record":"test-only receipt",
                     "independent_review":{"decision":"APPROVE","reviewer":"synthetic reviewer", "reviewed_at":"2026-11-14",
                     "checklist":{k:True for k in ("camera","silhouette","floor_count","cores","tubes","voids","facade","roof")}},
                     "printed_width_mm":10, "pdf_page_render_inspected":True}
        self.manifest = self.root / "manifest.json"
    def h(self,name): return hashlib.sha256((self.root / name).read_bytes()).hexdigest()
    def go(self,print_gate=False):
        self.manifest.write_text(json.dumps(self.data),encoding="utf-8")
        return check(self.manifest,print_gate)
    def test_valid_candidate(self): self.assertEqual(self.go()["status"],"APPROVED_FOR_LAYOUT_NOT_DESIGN_APPROVED")
    def test_missing_download(self):
        self.data["retouched"]="missing.png"
        self.assertEqual(self.go()["status"],"AWAITING_EXTERNAL_AI_RETOUCH")
    def test_wrong_source_hash(self):
        self.data["source_sha256"]="0"*64
        self.assertIn("hash mismatch or missing expectation: source",self.go()["errors"])
    def test_wrong_edited_hash(self):
        self.data["retouched_sha256"]="0"*64
        self.assertEqual(self.go()["status"],"REJECTED_NOT_FOR_BOOK")
    def test_wrong_aspect(self):
        Image.new("RGB",(140,80),"red").save(self.root/"retouched.png")
        self.data["retouched_sha256"]=self.h("retouched.png")
        self.assertTrue(any("dimensions" in x for x in self.go()["errors"]))
    def test_missing_review(self):
        self.data["independent_review"]["decision"]="PENDING"
        self.assertEqual(self.go()["status"],"REJECTED_NOT_FOR_BOOK")
    def test_print_dpi_insufficient(self):
        self.data["printed_width_mm"]=100
        self.assertTrue(any("300" in x for x in self.go(True)["errors"]))
    def test_pixel_lock_violation(self):
        Image.new("L",(120,80),255).save(self.root/"lock.png")
        self.data["pixel_lock_mask"]="lock.png"
        self.assertIn("locked source pixels modified",self.go()["errors"])
    def test_technical_missing_vector(self):
        self.data["kind"]="technical"
        self.data["independent_review"]["checklist"]={k:True for k in ("source_geometry","grid","dimensions","labels","scale","vector_overlay")}
        self.assertTrue(any("vector_overlay" in x for x in self.go()["errors"]))
    def test_technical_valid_composite(self):
        self.data["kind"]="technical"
        self.data["independent_review"]["checklist"]={k:True for k in ("source_geometry","grid","dimensions","labels","scale","vector_overlay")}
        overlay=Image.new("RGBA",(120,80),(0,0,0,0))
        for x in range(20,100): overlay.putpixel((x,40),(0,0,0,255))
        overlay.save(self.root/"vector.png")
        edited=Image.open(self.root/"retouched.png").convert("RGBA")
        Image.alpha_composite(edited,overlay).save(self.root/"final.png")
        self.data.update(vector_overlay="vector.png",vector_overlay_sha256=self.h("vector.png"),
                         final_composite="final.png",final_composite_sha256=self.h("final.png"))
        self.assertEqual(self.go()["status"],"APPROVED_FOR_LAYOUT_NOT_DESIGN_APPROVED")
    def test_technical_faked_vector_composite(self):
        self.test_technical_valid_composite()
        Image.new("RGBA",(120,80),(255,0,0,255)).save(self.root/"final.png")
        self.data["final_composite_sha256"]=self.h("final.png")
        self.assertTrue(any("recomposition" in x for x in self.go()["errors"]))

if __name__ == "__main__": unittest.main()

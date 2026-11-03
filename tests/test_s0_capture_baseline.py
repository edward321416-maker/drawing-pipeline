"""S0 종이좌표·왜곡 방지·원본 불변 검사."""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from PIL import Image
from tools.s0_capture_baseline import capture,mm_to_px,fit_white

class S0Tests(unittest.TestCase):
    def test_crop_math(self):
        self.assertEqual((100,200,300,400),mm_to_px([42,59.4,126,118.8],[420,297],(1000,1000)))
    def test_out_of_bounds(self):
        with self.assertRaises(ValueError):
            mm_to_px([-1,0,10,10],[420,297],(1000,707))
    def test_aspect(self):
        out=fit_white(Image.new("RGB",(200,100),"black"),(800,800))
        self.assertEqual(out.getpixel((400,10)),(255,255,255))
        self.assertEqual(out.getpixel((400,400)),(0,0,0))
    def test_determinism_and_input_integrity(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            src=root/"a.png";ref=root/"r.png";cfg=root/"c.json"
            Image.new("RGB",(1400,990),"#cccccc").save(src)
            Image.new("RGB",(200,200),"#eeeeee").save(ref)
            cfg.write_text(json.dumps({"sheet_mm":[420,297],"crop_output_px":[800,800],
              "views":[{"id":"x","label":"중심","rect_mm":[100,50,200,150]}]}),encoding="utf-8")
            original=src.read_bytes()
            x=capture(src,ref,cfg,root/"one")
            y=capture(src,ref,cfg,root/"two")
            self.assertEqual(x["views"][0]["sha256"],y["views"][0]["sha256"])
            self.assertEqual(x["contact_sheet_sha256"],y["contact_sheet_sha256"])
            self.assertEqual(original,src.read_bytes())

if __name__=="__main__":
    unittest.main()

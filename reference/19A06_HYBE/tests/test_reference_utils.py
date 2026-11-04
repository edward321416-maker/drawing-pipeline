"""Offline tests for discovery, provenance and contact-sheet heuristics."""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]

def load(name):
    file = ROOT / 'scripts' / (name + '.py')
    spec = importlib.util.spec_from_file_location(name, file)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

cap = load('capture_reference')
ana = load('analyze_reference')

class ReferenceUtilsTest(unittest.TestCase):
    def test_normalize_abs_and_relative(self):
        self.assertEqual(cap.normalize_url('/assets/a.png', 'https://example.org/19a06'), 'https://example.org/assets/a.png')
        self.assertEqual(cap.normalize_url('https://images.prismic.io/z.png?width=300#x', 'https://example.org'),
                         'https://images.prismic.io/z.png?width=300')

    def test_rejects_data_and_javascript_urls(self):
        self.assertIsNone(cap.normalize_url('data:image/png;base64,123', 'https://x.org'))
        self.assertIsNone(cap.normalize_url('javascript:alert(1)', 'https://x.org'))

    def test_html_image_url_lookup(self):
        src='<img src="https://images.prismic.io/fhhh-friends/example.jpg?auto=format&amp;w=800">'
        self.assertIn('https://images.prismic.io/fhhh-friends/example.jpg?auto=format&w=800',
                      cap.extract_html_image_urls(src, 'https://fhhhfriends.com/19a06'))

    def test_source_url_extension(self):
        self.assertEqual(cap.image_ext('https://cdn.x/a.jpg?width=800', 'image/webp'), '.webp')
        self.assertEqual(cap.image_ext('https://cdn.x/a.jpg?width=800', ''), '.jpg')

    def test_drawing_candidate_not_fabricated_semantics(self):
        im=Image.new('RGB',(400,300),'white')
        draw=ImageDraw.Draw(im)
        draw.rectangle((50,30,350,250),outline='black',width=4)
        label,metrics=ana.classify_image(im)
        self.assertEqual(label,'DRAWING_CANDIDATE')
        self.assertGreater(metrics['near_white_fraction'],.55)

    def test_capture_manifest_generates_contact_sheet(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/'originals').mkdir()
            (root/'manifests').mkdir()
            Image.new('RGB',(300,180),'white').save(root/'originals'/'drawing.png')
            (root/'manifests'/'capture_manifest.json').write_text(json.dumps({
                'assets':[{'id':1,'status':'DOWNLOADED',
                           'file':'originals/drawing.png','url':'https://fhhhfriends.com/assets/drawing.png'}]}
            ),encoding='utf-8')
            ana.run(root)
            assert (root/'contact_sheets'/'contact_01.png').is_file()
            rep=json.loads((root/'manifests'/'analysis_manifest.json').read_text('utf-8'))
            self.assertEqual(rep['analyzed_items'],1)

if __name__=='__main__':
    unittest.main()

"""Same-position before/after panels: V2 page crop (left) | V3 page crop (right), captioned.

    python -I tools/t14g/before_after.py <V3 pdf> <out_dir>
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
ROOT = os.path.dirname(TOOLS)
sys.path.insert(0, TOOLS)
import pymupdf  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402
from t14f import fonts  # noqa: E402

MM = 72.0 / 25.4
V2 = os.path.join(ROOT, "docs", "t14e_v2", "drawing_set_candidate_v2.pdf")


def _crop(doc, pno, box, dpi):
    pg = doc[pno - 1]
    pm = pg.get_pixmap(dpi=dpi, clip=pymupdf.Rect(*[v * MM for v in box]))
    return Image.frombytes("RGB", (pm.width, pm.height), pm.samples)


def _around(doc, pno, text, rx, ry):
    hits = doc[pno - 1].search_for(text)
    if not hits:
        raise LookupError("%r not found on page %d" % (text, pno))
    r = hits[0]
    cx, cy = (r.x0 + r.x1) / 2 / MM, (r.y0 + r.y1) / 2 / MM
    return (max(0, cx - rx), max(0, cy - ry), min(420, cx + rx), min(297, cy + ry))


PANELS = [
    ("01_P-102_callout_D-407", 6, "D-407", (30, 14), 200, "P-102: callout to D-407 printed 1:50 (sheet is 1:100)"),
    ("02_P-105_callout_D-410", 9, "D-410", (30, 14), 200, "P-105: callout to D-410 printed 1:50 (sheet is 1:100)"),
    ("03_E-201_callout_D-410", 10, "D-410", (30, 14), 200, "E-201: callout to D-410 printed 1:50"),
    ("04_E-202_callout_D-410", 11, "D-410", (30, 14), 200, "E-202: callout to D-410 printed 1:50"),
    ("05_E-203_callout_D-410", 12, "D-410", (30, 14), 200, "E-203: callout to D-410 printed 1:50"),
    ("06_E-204_callout_D-410", 13, "D-410", (30, 14), 200, "E-204: callout to D-410 printed 1:50"),
    ("07_D-405_scale_bar", 23, (10, 196, 150, 262), None, 130, "D-405: V2 has no graphic scale bar; V3 draws 100 mm = 5 m (measured 99.999 mm)"),
    ("08_D-401_slab_thickness", 19, "t=", (40, 32), 170, "D-401: slab thickness printed 400 (window clipped a 500 mm slab); V3 prints 500"),
    ("09_D-407_incline", 25, (210, 20, 398, 258), None, 80, "D-407: incline printed 25.0 deg (rotated-rectangle artefact); V3 30.0 deg from the mesh"),
    ("10_S-302_title_block_clip", 15, (10, 222, 310, 278), None, 120, "S-302: EV shaft runs under the title block; V3 cuts at B2-1.5 m above it and says so"),
    ("11_A-901_floor_table", 30, "+31.001", (110, 14), 150, "A-901: 7F printed +31.001 / 6F program cell truncated; V3 rounded like the elevations, cell complete"),
    ("12_P-101_legend", 5, (303, 8, 412, 260), None, 95, "P-101: legend with real symbol shapes for the new element kinds; no overflow (claims)"),
    ("13_P-101_furniture_retail_A", 5, (125, 85, 300, 205), None, 110, "P-101 (3F retail A): one booth repeated -> typed units, counters, experience zone, pop-up ring, routes"),
    ("14_P-103_furniture_fnb", 7, (125, 85, 300, 205), None, 110, "P-103 (10F F&B): seating types, bar, service counter + queue, operations route"),
    ("15_P-104_furniture_culture", 8, (125, 85, 300, 205), None, 110, "P-104 (13F culture): stage, exhibition, pods in three configurations, info desk"),
    ("16_floor_coverage", 30, (10, 10, 410, 135), None, 70, "V2 covered 5 floors graphically; V3 adds A-902 (all 17 floors, right)"),
]


def main():
    v3 = pymupdf.open(sys.argv[1])
    v2 = pymupdf.open(V2)
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)
    fr, fb = ImageFont.truetype(fonts.resolve("regular")[0], 17), ImageFont.truetype(fonts.resolve("bold")[0], 20)
    made = []
    for name, pno, a, b, dpi, cap in PANELS:
        if isinstance(a, str):
            box = _around(v2, pno, a, *b)
        else:
            box = a
        left = _crop(v2, pno, box, dpi)
        if name.startswith("16_"):
            right = Image.frombytes("RGB", (0, 0), b"") if False else None
            pg = v3[30]                                                         # A-902 (page 31) whole sheet, scaled to the same height
            pm = pg.get_pixmap(dpi=int(dpi * 1.0))
            right = Image.frombytes("RGB", (pm.width, pm.height), pm.samples)
            right = right.resize((int(right.width * left.height / right.height), left.height))
        else:
            right = _crop(v3, pno, box, dpi)
        W, H = left.width + right.width + 36, max(left.height, right.height) + 70
        im = Image.new("RGB", (W, H), "#ffffff")
        d = ImageDraw.Draw(im)
        d.text((12, 8), cap, font=fb, fill="#111")
        d.text((12, 40), "BEFORE  Candidate V2 (p.%d)" % pno, font=fr, fill="#a33")
        d.text((left.width + 24, 40), "AFTER  Candidate V3 (p.%d)" % (31 if name.startswith("16_") else pno), font=fr, fill="#063")
        im.paste(left, (12, 66))
        im.paste(right, (left.width + 24, 66))
        d.rectangle([12, 66, 12 + left.width, 66 + left.height], outline="#999")
        d.rectangle([left.width + 24, 66, left.width + 24 + right.width, 66 + right.height], outline="#999")
        p = os.path.join(out, name + ".png")
        im.save(p, optimize=True)
        made.append(p)
    print("before/after panels:", len(made))


if __name__ == "__main__":
    main()

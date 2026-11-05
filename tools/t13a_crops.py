"""C-T13A: 같은 시트 mm 상자를 SVG(고해상도 래스터)·PNG·PDF에서 잘라 비교한다.

    python tools/t13a_crops.py --svg X.svg --out dir --prefix before [--png-width 12000]
"""
from __future__ import annotations

import argparse
import os

from PIL import Image

RECTS = {                                   # 시트 mm (왼쪽 위 원점, A3 420×297)
    "01_north_market": (160, 92, 252, 142),
    "02_central_hall": (198, 128, 268, 198),
    "03_west_capsule": (160, 112, 206, 178),
    "04_piloti_landscape": (70, 112, 200, 208),
    "05_legend_text": (338, 94, 414, 168),
}


def crops_from_image(im, out, prefix, width_px=1500):
    Image.MAX_IMAGE_PIXELS = None
    sx, sy = im.size[0] / 420.0, im.size[1] / 297.0
    paths = {}
    for k, r in RECTS.items():
        c = im.crop((int(r[0] * sx), int(r[1] * sy), int(r[2] * sx), int(r[3] * sy)))
        h = int(c.size[1] * width_px / c.size[0])
        c = c.resize((width_px, h), Image.LANCZOS)
        p = os.path.join(out, "%s_%s.png" % (prefix, k))
        c.save(p)
        paths[k] = p
    return paths


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--svg", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--png-width", type=int, default=12000)
    a = ap.parse_args()
    import cairosvg
    os.makedirs(a.out, exist_ok=True)
    tmp = os.path.join(a.out, "_tmp_%s.png" % a.prefix)
    cairosvg.svg2png(url=a.svg, write_to=tmp, output_width=a.png_width, background_color="white")
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(tmp)
    crops_from_image(im, a.out, a.prefix)
    im.close()
    os.remove(tmp)
    print("crops:", os.path.abspath(a.out))


if __name__ == "__main__":
    main()

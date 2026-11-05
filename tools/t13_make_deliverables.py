"""C-T13 산출물 도구: 표준 크롭 5장(A/B), V1 대비 before/after 비교판, SHA-256 manifest.

    python tools/t13_make_deliverables.py --out outputs/T13 --before <기존 1F A3 PNG>

크롭 좌표는 docs/baselines/S0-2026-11-03/crop_config.json 의 A3 시트 mm 상자(왼쪽 위 원점)를 그대로 쓴다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "docs", "baselines", "S0-2026-11-03", "crop_config.json")
SHEET_MM = (420.0, 297.0)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def crop(im, rect_mm, size=800):
    sx, sy = im.size[0] / SHEET_MM[0], im.size[1] / SHEET_MM[1]
    c = im.crop((int(rect_mm[0] * sx), int(rect_mm[1] * sy), int(rect_mm[2] * sx), int(rect_mm[3] * sy)))
    c.thumbnail((size, size), Image.LANCZOS)
    canvas = Image.new("RGB", (size, size), "white")
    canvas.paste(c, ((size - c.size[0]) // 2, (size - c.size[1]) // 2))
    return canvas


def font(sz):
    for f in ("malgun.ttf", "C:/Windows/Fonts/malgun.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(f, sz)
        except OSError:
            continue
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--before", required=True)
    ap.add_argument("--a", default=None)
    ap.add_argument("--b", default=None)
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    a_png = a.a or os.path.join(out, "1F_Program_Concept_V2_A.png")
    b_png = a.b or os.path.join(out, "1F_Program_Concept_V2_B.png")
    views = json.load(open(CFG, encoding="utf-8"))["views"]
    Image.MAX_IMAGE_PIXELS = None
    ims = {"before": Image.open(a.before).convert("RGB"), "A": Image.open(a_png).convert("RGB"), "B": Image.open(b_png).convert("RGB")}
    cdir = os.path.join(out, "crops")
    os.makedirs(cdir, exist_ok=True)
    files = {}
    for v in views:
        for key, im in ims.items():
            name = "crop_%s_%s.png" % (v["id"], {"before": "V1_before", "A": "V2_A", "B": "V2_B"}[key])
            crop(im, v["rect_mm"]).save(os.path.join(cdir, name))
            files[name] = os.path.join(cdir, name)
    # 비교판: 행 5(크롭) × 열 3(before, A, B)
    cell, pad, head, lab = 560, 14, 46, 150
    W = lab + 3 * (cell + pad) + pad
    H = head + len(views) * (cell + pad) + pad
    board = Image.new("RGB", (W, H), "white")
    dr = ImageDraw.Draw(board)
    f1, f2 = font(22), font(18)
    for ci, title in enumerate(("V1 기존 (before)", "V2-A 공공 통과축 + 군집", "V2-B 순환 고리 + 분산 군집")):
        dr.text((lab + pad + ci * (cell + pad) + 6, 10), title, fill="#111", font=f1)
    for ri, v in enumerate(views):
        y = head + ri * (cell + pad)
        dr.text((8, y + cell // 2 - 30), v["id"][:2] + "\n" + v["label"], fill="#333", font=f2)
        for ci, key in enumerate(("before", "A", "B")):
            name = "crop_%s_%s.png" % (v["id"], {"before": "V1_before", "A": "V2_A", "B": "V2_B"}[key])
            c = Image.open(os.path.join(cdir, name)).resize((cell, cell), Image.LANCZOS)
            board.paste(c, (lab + pad + ci * (cell + pad), y))
            dr.rectangle((lab + pad + ci * (cell + pad), y, lab + pad + ci * (cell + pad) + cell, y + cell), outline="#999")
    bp = os.path.join(out, "1F_Program_Concept_V2_before_after.png")
    board.save(bp)
    files[os.path.basename(bp)] = bp
    print("crops %d, board %s" % (len(views) * 3, os.path.abspath(bp)))


if __name__ == "__main__":
    main()

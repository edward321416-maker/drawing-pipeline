"""3F 방향 정정 전/후 비교 이미지.

    compare_3F_orientation_full.png     1층 기준(사용자 제공) | 3F 기존본(001) | 3F 방향 수정본(002)
    compare_3F_orientation_tile_t4.png  3F 기존본 t4 | 수정본 t4

3F 패널에는 같은 모델 요소(서측 캡슐·T1 나선 램프·T2 빛 튜브)와 진북 방향을 표시한다. 위치는 각 후보의 slice에서 읽는다.
"""
import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))
import pipeline_common as pc  # noqa: E402

FONT = r"C:\Windows\Fonts\malgun.ttf"
FONT_B = r"C:\Windows\Fonts\malgunbd.ttf"


def element_px(run, W, H):
    """1:200 시트(84×59.4 m, 건물 중심 창) 위의 요소 중심 픽셀."""
    sl = pc.load_json(os.path.join(run, "raw_slices", "floor_3F_slice.json"))
    lay = pc.load_json(os.path.join(run, "vector", "floor_3F_layout.json"))
    bx0, by0, bx1, by1 = lay["building"]
    b0, b3 = (bx0 + bx1) / 2 - 42.0, (by0 + by1) / 2 + 29.7
    out = {}
    for it, g in pc.cut_geometries(sl).get("tube_wall", []):
        nm = it["name_ko"]
        key = "캡슐" if "캡슐" in nm else ("T1 나선 램프" if nm.endswith("T1") else ("T2 빛 튜브" if nm.endswith("T2") else None))
        if key:
            c = g.centroid
            out[key] = ((c.x - b0) / 84.0 * W, (b3 - c.y) / 59.4 * H)
    nb = pc.load_json(os.path.join(run, "raw_slices", "camera_bounds.json"))["frame"]["north_deg"]
    return out, nb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-before", required=True)
    ap.add_argument("--run-after", required=True)
    ap.add_argument("--ref-png", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    from PIL import Image, ImageDraw, ImageFont
    Image.MAX_IMAGE_PIXELS = None
    f_t, f_s, f_m = ImageFont.truetype(FONT_B, 40), ImageFont.truetype(FONT, 28), ImageFont.truetype(FONT_B, 30)
    sd = lambda run, n: os.path.join(run, "3F_PILOT", n)
    pw = 1500
    panels = []
    ref = Image.open(a.ref_png).convert("RGB")
    ref = ref.resize((pw, int(ref.size[1] * pw / ref.size[0])), Image.LANCZOS)
    panels.append(("1층 기준 (사용자 제공 1F_CleanLine_FIXED)", "#222", ref, None))
    for run, title, col in ((a.run_before, "3F 기존본 (001) — 90° 좌회전됨", "#a33"), (a.run_after, "3F 방향 수정본 (002)", "#173")):
        im = Image.open(sd(run, "plan_3F_A3_1to200_cleanline.png")).convert("RGB")
        im = im.resize((pw, int(im.size[1] * pw / im.size[0])), Image.LANCZOS)
        pos, north = element_px(run, im.size[0], im.size[1])
        d = ImageDraw.Draw(im)
        for name, (x, y) in pos.items():
            d.ellipse([x - 16, y - 16, x + 16, y + 16], outline="#d22", width=6)
            d.text((x + 22, y - 18), name, font=f_m, fill="#d22")
        panels.append((title, col, im, north))
    H = max(p[2].size[1] for p in panels)
    sheet = Image.new("RGB", (pw * 3 + 80, H + 230), "white")
    d = ImageDraw.Draw(sheet)
    d.text((20, 14), "3F 도면 방향 비교 — 1층 기준 vs 기존본 vs 수정본", font=f_t, fill="#111")
    d.text((20, 70), "1층 기준: 서측 캡슐 = 왼쪽 세로 · 나선 램프(T1) = 좌하 · 빛 튜브(T2) = 우하 · 진북 화살표 = 우상향 (north 63.2°)", font=f_s, fill="#333")
    for i, (title, col, im, north) in enumerate(panels):
        x0 = 20 + i * (pw + 20)
        d.text((x0, 140), title + ("" if north is None else "   (진북 %.1f°)" % north), font=f_m, fill=col)
        sheet.paste(im, (x0, 200))
    os.makedirs(a.out_dir, exist_ok=True)
    p1 = os.path.join(a.out_dir, "compare_3F_orientation_full.png")
    sheet.save(p1)
    # t4
    tw = 1700
    ims = []
    for run in (a.run_before, a.run_after):
        im = Image.open(sd(run, "plan_3F_A3_1to100_t4_cleanline.png")).convert("RGB")
        ims.append(im.resize((tw, int(im.size[1] * tw / im.size[0])), Image.LANCZOS))
    sheet = Image.new("RGB", (tw * 2 + 60, ims[0].size[1] + 230), "white")
    d = ImageDraw.Draw(sheet)
    d.text((20, 14), "3F 1:100 타일 t4(우하) — 기존본 | 방향 수정본", font=f_t, fill="#111")
    d.text((20, 70), "t4는 건물의 오른쪽 아래 사분면이어야 한다. 기존본 t4는 90° 돌아간 건물의 같은 사분면, 수정본 t4는 1층과 같은 방향의 사분면.", font=f_s, fill="#333")
    d.text((20, 140), "기존본 t4 (001)", font=f_m, fill="#a33")
    d.text((tw + 40, 140), "수정본 t4 (002)", font=f_m, fill="#173")
    sheet.paste(ims[0], (20, 200))
    sheet.paste(ims[1], (tw + 40, 200))
    p2 = os.path.join(a.out_dir, "compare_3F_orientation_tile_t4.png")
    sheet.save(p2)
    print("COMPARE", os.path.abspath(p1))
    print("COMPARE", os.path.abspath(p2))


if __name__ == "__main__":
    main()

"""Blender base -> ChatGPT raw -> Photoshop final: overview and native-resolution crop sheets for one variant."""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = None
variant, base_png, gpt_png, final_png, out = sys.argv[1:6]
out = Path(out)
out.mkdir(parents=True, exist_ok=True)
base = Image.open(base_png).convert("RGB")
final = Image.open(final_png).convert("RGB")
W, H = base.size
gpt = Image.open(gpt_png).convert("RGB").resize((W, H), Image.LANCZOS)  # display-only upscale for comparison
try:
    font = ImageFont.truetype(r"C:\Windows\Fonts\malgunbd.ttf", 26)
except OSError:
    font = ImageFont.load_default()
labels = ["Blender base (locked)", "ChatGPT raw (x2.87 display upscale)", "Photoshop final"]
# overview: 3 stacked columns at reduced size
ov = Image.new("RGB", (1600 * 3 + 20, 900 + 40), "white")
for i, im in enumerate((base, gpt, final)):
    ov.paste(im.resize((1600, 900), Image.LANCZOS), (i * 1610, 40))
    ImageDraw.Draw(ov).text((i * 1610 + 8, 6), labels[i], fill="black", font=font)
ov.save(out / f"three_stage_overview_{variant}.png")
bbox = [1545, 37, 3287, 2271]
cx = (bbox[0] + bbox[2]) // 2
regions = {
    "roof": (cx - 400, 40, cx + 400, 480),
    "mid_garden": (cx - 400, 1000, cx + 400, 1440),
    "entrance_base": (cx - 400, 1780, cx + 400, 2220),
    "street_right": (3300, 1750, 4100, 2190),
    "plaza_left": (700, 1650, 1500, 2090),
}
for k, box in regions.items():
    sheet = Image.new("RGB", (800 * 3 + 20, 440 + 36), "white")
    for i, im in enumerate((base, gpt, final)):
        sheet.paste(im.crop(box), (i * 810, 36))
        ImageDraw.Draw(sheet).text((i * 810 + 6, 4), labels[i], fill="black", font=font)
    sheet.save(out / f"three_stage_{variant}_{k}.png")
print("ok", out)

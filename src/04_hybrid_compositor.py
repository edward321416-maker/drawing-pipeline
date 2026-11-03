"""STEP 4 — 벡터-래스터 샌드위치 합성기 (A1 가로 시트, SVG → PDF·PNG).

    python src/04_hybrid_compositor.py --raw output/drawing_pipeline/raw_slices --out output/drawing_pipeline [--floors 1F] [--scale 200] [--dpi 150]

층 구성 (아래에서 위로):
  1. 재질 바탕  ai_textures/floor_<층>_texture.png (불투명도 75 %, 약간 탈채도). 없으면 따뜻한 오프화이트 종이(--skip-ai와 같다).
  2. 깊이·그림자  floor_<층>_ao.png 를 곱하기(multiply)로 얹는다.
  3. 벡터 선  floor_<층>_vector.svg 를 같은 경계에 그대로 얹는다 (PDF에서도 벡터로 남는다). 구조·글자·치수는 이 층이 최상위다.
도곽: 제목, 진북 화살표(도면 회전을 반영), 그래픽 스케일(0·1·5·10 m), 면적표(모두 계산값).
"""
from __future__ import annotations

import argparse
import base64
import datetime
import io
import math
import os
import re
import sys

import numpy as np
from PIL import Image, ImageEnhance

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline_common as pc  # noqa: E402

SHEET_W, SHEET_H = 841.0, 594.0                     # A1 가로 (mm)
PAPER = (244, 241, 234)
FONT = "Malgun Gothic, 'Segoe UI', Arial, sans-serif"
PT = 0.3528


def floor_title(f: str) -> str:
    if f.startswith("B"):
        return "지하 %s층 평면도" % f[1:]
    return "%s층 평면도" % f[:-1]


def make_base(raw, out, floor, size, ao_strength=0.35):
    """재질 바탕 × AO. 텍스처가 없으면 종이색."""
    ao = Image.open(os.path.join(raw, "floor_%s_ao.png" % floor)).convert("RGB")
    if ao.size[0] != size:
        ao = ao.resize((size, size), Image.LANCZOS)
    tp = os.path.join(out, "ai_textures", "floor_%s_texture.png" % floor)
    paper = Image.new("RGB", ao.size, PAPER)
    if os.path.exists(tp):
        tx = Image.open(tp).convert("RGB").resize(ao.size, Image.LANCZOS)
        tx = ImageEnhance.Color(tx).enhance(0.7)                              # 약간 탈채도
        base = Image.blend(paper, tx, 0.75)                                  # 불투명도 75 %
        used = "texture"
    else:
        base, used = paper, "paper"
    a = np.asarray(base, dtype=np.float32) / 255.0
    m = np.asarray(ao.convert("L"), dtype=np.float32)[..., None] / 255.0
    # AO는 절단면 위로 솟은 코어·튜브가 가린 그림자까지 담고 있어 그대로 곱하면 바닥이 어두워진다. 건물 영역의 밝은 쪽(95 백분위)을
    # 기준으로 정규화하고 강도를 눌러 부드러운 깊이감만 남긴다. 배경(흰색)은 그대로 둔다.
    inside = m[m < 0.985]
    ref = float(np.percentile(inside, 95)) if inside.size else 1.0
    norm = np.clip(m / max(ref, 1e-3), 0.0, 1.0)
    m = np.where(m >= 0.985, 1.0, 1.0 - ao_strength * (1.0 - norm))
    res = Image.fromarray((a * m * 255).clip(0, 255).astype(np.uint8))      # multiply
    return res, used


def data_uri(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def inner_svg(path: str) -> str:
    txt = open(path, encoding="utf-8").read()
    m = re.search(r"<svg[^>]*>", txt)
    return txt[m.end():txt.rindex("</svg>")]


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")


def build_sheet_svg(raw, out, floor, scale, title, base_img, base_used):
    bounds = pc.load_bounds(raw)
    layout = pc.load_json(os.path.join(out, "vector", "floor_%s_layout.json" % floor))
    side_m = bounds["xmax"] - bounds["xmin"]
    k = 1000.0 / scale                              # 도면 1 m = 종이 k mm
    plan = side_m * k
    x0, y0 = 22.0, (SHEET_H - plan) / 2
    panel_x = x0 + plan + 22
    pw = SHEET_W - 14 - panel_x                     # 우측 도곽 폭
    theta = math.radians(bounds["frame"].get("north_deg", bounds["frame"]["theta_deg"]))        # 진북 = 도면 위쪽에서 시계 방향 각
    parts = []
    A = parts.append
    A('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="%gmm" height="%gmm" viewBox="0 0 %g %g">' %
      (SHEET_W, SHEET_H, SHEET_W, SHEET_H))
    A('<rect width="%g" height="%g" fill="#ffffff"/>' % (SHEET_W, SHEET_H))
    A('<rect x="7" y="7" width="%g" height="%g" fill="none" stroke="#111" stroke-width="0.5"/>' % (SHEET_W - 14, SHEET_H - 14))
    # 1·2층: 바탕 × AO (같은 경계)
    A('<image x="%.4f" y="%.4f" width="%.4f" height="%.4f" preserveAspectRatio="none" xlink:href="%s"/>' % (x0, y0, plan, plan, data_uri(base_img)))
    # 3층: 벡터 (미터 → 종이 mm)
    A('<g transform="translate(%.4f %.4f) scale(%.6f)">%s</g>' % (x0, y0, k, inner_svg(os.path.join(out, "vector", "floor_%s_vector.svg" % floor))))

    # 우측 도곽
    def T(x, y, s, size_pt, weight="normal", fill="#222", anchor="start"):
        A('<text x="%.3f" y="%.3f" font-family="%s" font-size="%.3f" font-weight="%s" fill="%s" text-anchor="%s">%s</text>' %
          (x, y, FONT, size_pt * PT, weight, fill, anchor, esc(s)))

    A('<line x1="%g" y1="14" x2="%g" y2="%g" stroke="#111" stroke-width="0.3"/>' % (panel_x - 11, panel_x - 11, SHEET_H - 14))
    T(panel_x, 28, title, 11, "bold", "#111")
    T(panel_x, 45, floor_title(floor), 24, "bold", "#111")
    T(panel_x, 56, "FLOOR PLAN · %s     1 : %d" % (floor, scale), 9, "normal", "#555")
    T(panel_x, 65, "절단 높이 FL+%.1f m (바닥 z = %.2f m)" % (layout["cut_z"] - layout["floor_z"], layout["floor_z"]), 6.5, "normal", "#555")
    T(panel_x, 72, "도면 생성 %s · 모델 단면에서 파생 (직접 작도 없음)" % datetime.date.today().isoformat(), 6.5, "normal", "#555")
    # 면적표
    ty = 92
    T(panel_x, ty, "면적 일람 (도형 계산값)", 8, "bold", "#222")
    A('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="#111" stroke-width="0.3"/>' % (panel_x, ty + 3, panel_x + pw, ty + 3))
    rows = [(z["name"], z["area_m2"]) for z in layout["zones"][:10]]
    rows.append(("슬래브 면적 (개구부 제외)", layout["slab_area_m2"]))
    y = ty + 11
    for name, area in rows:
        T(panel_x, y, name, 7.5)
        T(panel_x + pw, y, "%s ㎡" % format(area, ",.1f"), 7.5, anchor="end")
        y += 8
    A('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="#bbb" stroke-width="0.2"/>' % (panel_x, y - 4, panel_x + pw, y - 4))
    T(panel_x, y + 3, "코어·튜브 내부와 벽 두께는 모델에 없다. 층판·기둥·튜브·코어 외곽·프로그램 영역만 표시한다.", 6, "normal", "#777")
    ny = y + 10
    for cz in layout.get("covered_zones", []):
        T(panel_x, ny, "※ 코어 안에 겹친 '%s' 영역 %s ㎡는 표에서 제외 (모델의 볼륨 겹침)" % (cz["name"], format(cz["area_m2"], ",.1f")), 6, "normal", "#777")
        ny += 7
    T(panel_x, ny, "바탕: %s" % ("AI 재질 인필" if base_used == "texture" else "오프화이트 종이 (AI 인필 없음)"), 6, "normal", "#777")

    # 진북 화살표 (도면 +Y가 위, 진북은 도면에서 (sinθ, cosθ) 방향)
    cx, cy, r = panel_x + 22, SHEET_H - 62, 14
    dx, dy = math.sin(theta), -math.cos(theta)         # SVG는 y가 아래
    A('<circle cx="%g" cy="%g" r="%g" fill="none" stroke="#333" stroke-width="0.3"/>' % (cx, cy, r))
    tip = (cx + dx * r, cy + dy * r)
    tail = (cx - dx * r, cy - dy * r)
    px, py = -dy, dx
    A('<polygon points="%.3f,%.3f %.3f,%.3f %.3f,%.3f" fill="#111"/>' % (tip[0], tip[1], cx + px * 3.2, cy + py * 3.2, cx - px * 3.2, cy - py * 3.2))
    A('<line x1="%.3f" y1="%.3f" x2="%.3f" y2="%.3f" stroke="#333" stroke-width="0.3"/>' % (cx, cy, tail[0], tail[1]))
    T(tip[0] + dx * 4 - 1.2, tip[1] + dy * 4 + 1.0, "N", 9, "bold", "#111")
    # 그래픽 스케일 (0, 1, 5, 10 m)
    sx0, sy0 = panel_x + 60, SHEET_H - 62
    unit = k                                            # 1 m
    for a, b, fill in ((0, 1, "#111"), (1, 5, "#ffffff"), (5, 10, "#111")):
        A('<rect x="%.3f" y="%.3f" width="%.3f" height="2.2" fill="%s" stroke="#111" stroke-width="0.2"/>' % (sx0 + a * unit, sy0, (b - a) * unit, fill))
    for m in (0, 1, 5, 10):
        T(sx0 + m * unit, sy0 - 2.2, "0" if m == 0 else str(m) + (" m" if m == 10 else ""), 6, anchor="middle")
    T(sx0, sy0 + 9, "GRAPHIC SCALE  1 : %d" % scale, 6, "normal", "#555")
    A("</svg>")
    return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--floors", default="")
    ap.add_argument("--scale", type=int, default=200)
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--ao-strength", type=float, default=0.35, help="AO 곱하기 강도 0(없음)~1(원본)")
    ap.add_argument("--title", default="다층 상업시설 (중간발표 최종 설계)")
    a = ap.parse_args()
    import cairosvg
    raw, out = os.path.abspath(a.raw), os.path.abspath(a.out)
    sheets = os.path.join(out, "final_sheets")
    os.makedirs(sheets, exist_ok=True)
    floors = [f for f in a.floors.split(",") if f] or pc.list_floors(raw)
    for f in floors:
        ao_path = os.path.join(raw, "floor_%s_ao.png" % f)
        if not os.path.exists(ao_path):
            print("건너뜀 (AO 없음):", f)
            continue
        size = Image.open(ao_path).size[0]
        # 시트에 들어가는 밑그림은 시트 해상도에 맞춰 줄인다 (용량)
        base, used = make_base(raw, out, f, size, a.ao_strength)
        bd = pc.load_bounds(raw)
        plan_px = int(round((bd["xmax"] - bd["xmin"]) * 1000 / a.scale / 25.4 * a.dpi))
        if base.size[0] > plan_px:
            base = base.resize((plan_px, plan_px), Image.LANCZOS)
        svg = build_sheet_svg(raw, out, f, a.scale, a.title, base, used)
        svg_path = os.path.join(sheets, "floor_%s_sheet.svg" % f)
        with open(svg_path, "w", encoding="utf-8") as fh:
            fh.write(svg)
        pdf = os.path.join(sheets, "floor_%s_sheet.pdf" % f)
        png = os.path.join(sheets, "floor_%s_sheet.png" % f)
        cairosvg.svg2pdf(url=svg_path, write_to=pdf)
        cairosvg.svg2png(url=svg_path, write_to=png, dpi=a.dpi, background_color="white")
        k = 1000.0 / a.scale
        plan_mm = (bd["xmax"] - bd["xmin"]) * k
        with open(os.path.join(sheets, "floor_%s_sheet.json" % f), "w", encoding="utf-8") as fh:
            import json
            json.dump({"floor": f, "dpi": a.dpi, "scale": a.scale, "sheet_mm": [SHEET_W, SHEET_H], "plan_x_mm": 22.0,
                       "plan_y_mm": (SHEET_H - plan_mm) / 2, "plan_mm": plan_mm, "base": used}, fh, indent=1)
        print("SHEET", f, base.size, used, os.path.abspath(pdf))
    print("DONE_SHEETS", os.path.abspath(sheets))


if __name__ == "__main__":
    main()

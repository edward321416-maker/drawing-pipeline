"""C-T14S review packaging: GitHub review packet (T14R tool), 17-floor contact sheet, A3 landscape summary PDF.

    python -I tools/t14s/package_review.py
Inputs: outputs/T14S/<floor>/ (built + validated). Output: docs/t14s_floor_plans/...
The plan-region crops are native-pixel crops of the A1 PNG (no scaling) so tiles inspect the delivered pixels.
"""
import hashlib
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

import fitz  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
from t14s import source as SRC  # noqa: E402

OUT = os.path.join(ROOT, "outputs", "T14S")
DOC = os.path.join(ROOT, "docs", "t14s_floor_plans")
PACKET = os.path.join(DOC, "review_packet")
REF_1F = r"D:/Users/admin/Desktop/중간마감/drawing-pipeline-T14J/output/C_T14J_run/reference_1F/1F_CleanLine_FIXED_user_supplied_preview.png"
FONT = "C:/Windows/Fonts/malgun.ttf"
FONT_B = "C:/Windows/Fonts/malgunbd.ttf"
DPI = 200
K = DPI / 25.4
CROP_MM = (18, 14, 22 + 360 + 4, 18 + 370 + 4)          # plan window on the A1 sheet (mm), plus a 4 mm margin
ALL = ["B2", "B1", "1F"] + ["%dF" % i for i in range(2, 16)]


def sha(p):
    return SRC.sha256(p)


def meta(f):
    return json.load(open(os.path.join(OUT, f, "T14S_%s_plan_metadata.json" % f), encoding="utf-8"))


def crop(f, dst):
    im = Image.open(os.path.join(OUT, f, "T14S_%s_plan_A1_1to200.png" % f)).convert("RGB")
    box = tuple(int(v * K) for v in CROP_MM)
    c = im.crop(box)
    c.save(dst, optimize=True)
    return c


def label_of(f):
    return "FLOOR_" + f


def build_packet(tmp):
    from tools.t14r import export_visual_review as E
    os.makedirs(tmp, exist_ok=True)
    assets = []
    for f in SRC.TARGET_FLOORS:
        p = os.path.join(tmp, label_of(f) + ".png")
        crop(f, p)
        assets.append("%s=%s" % (label_of(f), p))
    if os.path.isdir(PACKET):
        shutil.rmtree(PACKET)
    sys.argv = ["export_visual_review", "pack", "--out", PACKET] + [x for a in assets for x in ("--asset", a)]
    E.main()
    sys.argv = ["export_visual_review", "verify", "--packet", PACKET]
    E.main()


def contact_sheet(tmp):
    cols, tw, th = 6, 470, 500
    rows = 3
    W, H = cols * (tw + 14) + 14, rows * (th + 46) + 70
    sheet = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(sheet)
    fb, fs = ImageFont.truetype(FONT_B, 22), ImageFont.truetype(FONT, 15)
    d.text((14, 12), "C-T14S — 17개 층 평면 개요 (B2~15F) · 16개 신규 후보 + 1F 보존 기준 · PROPOSED_DESIGN · NOT APPROVED", font=fb, fill="#111")
    d.text((14, 40), "READY_FOR_CHATGPT_INDEPENDENT_REVIEW · 축척 1:200 · 구조=MODEL_VERIFIED, 구획·문·실·가구·동선=PROPOSED_DESIGN", font=fs, fill="#555")
    for i, f in enumerate(ALL):
        r, c = divmod(i, cols)
        x, y = 14 + c * (tw + 14), 70 + r * (th + 46)
        if f == "1F":
            im = Image.open(REF_1F).convert("RGB")
            cap = "1F  기준 도면(보존·사용자 제공, 재생성 안 함)"
        else:
            im = Image.open(os.path.join(tmp, label_of(f) + ".png"))
            m = meta(f)
            cap = "%s  %+.1f m · 실 %d · %s" % (f, m["level_ffl_m"], len(m["design_proposed"]["rooms"]), "/".join(sorted({z["name_ko"] for z in m["geometry_verified"]["program_zones"]})))
        im = im.copy()
        im.thumbnail((tw, th))
        sheet.paste(im, (x + (tw - im.width) // 2, y + (th - im.height) // 2))
        d.rectangle([x, y, x + tw, y + th], outline="#bbbbbb")
        d.text((x, y + th + 6), cap, font=fs, fill="#222")
    out = os.path.join(DOC, "contact_sheet_17_floors.jpg")
    q = 86
    while True:
        sheet.save(out, quality=q, optimize=True)
        if os.path.getsize(out) <= 400 * 1024 or q <= 55:
            break
        q -= 5
    return out, q


def a3_pdf(tmp):
    W, H = 1190.55, 841.89
    doc = fitz.open()
    fonts = {"fontname": "malgun", "fontfile": FONT}

    def page():
        p = doc.new_page(width=W, height=H)
        p.insert_font(fontname="malgun", fontfile=FONT)
        p.insert_font(fontname="malgunb", fontfile=FONT_B)
        return p

    def txt(p, x, y, s, size=9, bold=False, color=(0.1, 0.1, 0.1), w=340):
        p.insert_textbox(fitz.Rect(x, y, x + w, y + size * 2.4 + 400), s, fontsize=size, fontname="malgunb" if bold else "malgun", color=color)

    p = page()
    txt(p, 24, 16, "C-T14S 층별 평면도 후보 — 검수용 개요 (A3 가로)", 16, True, w=900)
    txt(p, 24, 40, "상태: READY_FOR_CHATGPT_INDEPENDENT_REVIEW · PROPOSED_DESIGN · NOT APPROVED · NOT FROZEN · 건축/도면 품질 승인 아님", 10, False, (0.6, 0.1, 0.1), w=1100)
    cs = os.path.join(DOC, "contact_sheet_17_floors.jpg")
    im = Image.open(cs)
    r = fitz.Rect(24, 62, W - 24, 62 + (W - 48) * im.height / im.width)
    p.insert_image(r, filename=cs)
    y = r.y1 + 8
    rows = ["층 | FFL(m) | 프로그램 | 실 수 | 층판 순면적(㎡, 모델) | 제안 실 합계(㎡) | 메모"]
    for f in SRC.TARGET_FLOORS:
        m = meta(f)
        gv, dp = m["geometry_verified"], m["design_proposed"]
        rows.append("%s | %+.1f | %s | %d | %s | %s | %s" % (f, m["level_ffl_m"], "/".join(sorted({z["name_ko"] for z in gv["program_zones"]})), len(dp["rooms"]),
                                                       format(gv["slab_net_m2"], ",.1f"), format(sum(dp["room_area_by_program_m2"].values()), ",.1f"),
                                                       "; ".join(n.split(":")[0] for n in dp["notes"])[:70]))
    txt(p, 24, y, "\n".join(rows), 6.8, w=1140)
    # per floor pages
    for f in ["1F"] + SRC.TARGET_FLOORS:
        p = page()
        if f == "1F":
            im = Image.open(REF_1F)
            r = fitz.Rect(24, 40, 24 + 790, 40 + 790 * im.height / im.width)
            p.insert_image(r, filename=REF_1F)
            txt(p, 24, 12, "1F — 보존된 기준 도면(사용자 제공 CleanLine, 1:400 대지 포함)", 13, True, w=900)
            txt(p, 830, 40, "이 시트는 재생성·수정하지 않았다.\n\n원본 SHA256:\n%s\n\n상층 평면의 좌표계(슬라이스 틀)는 1층 마스터와 같다: 건물 54×54 m, x −9~45, y −18~36, 진북 63.2°.\n\n1F는 이번 작업 범위(16개 층) 밖이다." % sha(REF_1F), 9)
            continue
        m = meta(f)
        gv, dp = m["geometry_verified"], m["design_proposed"]
        c = Image.open(os.path.join(tmp, label_of(f) + ".png"))
        jp = os.path.join(tmp, "pg_%s.jpg" % f)
        c.resize((1500, int(1500 * c.height / c.width))).save(jp, quality=88)
        r = fitz.Rect(24, 36, 24 + 790, 36 + 790 * c.height / c.width)
        p.insert_image(r, filename=jp)
        txt(p, 24, 10, "%s 평면도 (제안 후보) · FFL %+.3f m · 1:200" % (f, m["level_ffl_m"]), 14, True, w=900)
        x = 830
        txt(p, x, 36, "상태: READY_FOR_CHATGPT_INDEPENDENT_REVIEW\nPROPOSED_DESIGN · NOT APPROVED", 9, True, (0.6, 0.1, 0.1))
        lines = [
            "모델 검증(MODEL_VERIFIED)",
            "· 층판 외곽 %s ㎡ / 개구 %s ㎡ (%d개) / 순면적 %s ㎡" % (format(gv["slab_gross_m2"], ",.1f"), format(gv["opening_m2"], ",.1f"), gv["openings"], format(gv["slab_net_m2"], ",.1f")),
            "· 기둥 %d · 코어 %s · 튜브 %s" % (gv["columns"], "".join(gv["cores"]), ",".join(gv["tubes"])),
            "· 프로그램 볼륨: " + ", ".join("%s %s㎡" % (z["name_ko"], format(z["area_m2"], ",.0f")) for z in gv["program_zones"]),
            "",
            "제안 설계(PROPOSED_DESIGN)",
            "· 실 %d개(점포 %d) · 문 %s개" % (len(dp["rooms"]), dp["unit_count"], dp["doors"]),
            "· 프로그램별 실 면적: " + ", ".join("%s %s㎡" % (k, format(v, ",.0f")) for k, v in dp["room_area_by_program_m2"].items()),
            "· 구획벽·문·가구·방문객 동선·코어 내부·화장실은 제안(1F 검증 심볼 재사용 포함)",
            "",
            "특이·미해결(자동 기록)",
        ] + ["· " + n[:95] for n in dp["notes"]] + [
            "",
            "산출물: outputs/T14S/%s/  (SVG · DXF · A1/A3 PDF · PNG · JSON)" % f,
            "검수 타일: docs/t14s_floor_plans/review_packet/images/FLOOR_%s/" % f,
            "",
            "※ 자동 검증은 파일·치수·축척·원본 해시 확인뿐이다. 건축·시각 검수와 승인은 하지 않았다.",
        ]
        txt(p, x, 82, "\n".join(lines), 8, w=345)
    out = os.path.join(DOC, "T14S_floor_plan_review_A3.pdf")
    doc.save(out)
    n = len(doc)
    doc.close()
    return out, n


def main():
    tmp = os.path.join(os.environ.get("TEMP", "."), "t14s_review_src")
    build_packet(tmp)
    os.makedirs(DOC, exist_ok=True)
    cs, q = contact_sheet(tmp)
    pdf, pages = a3_pdf(tmp)
    ref_dir = os.path.join(DOC, "reference_1F")
    os.makedirs(ref_dir, exist_ok=True)
    ref_dst = os.path.join(ref_dir, "1F_CleanLine_FIXED_user_supplied_preview.png")
    shutil.copyfile(REF_1F, ref_dst)
    info = {"contact_sheet": cs, "contact_sheet_bytes": os.path.getsize(cs), "jpeg_quality": q, "a3_pdf": pdf, "a3_pages": pages,
            "reference_1F_copy": ref_dst, "reference_1F_sha256": sha(ref_dst), "reference_1F_original_sha256": sha(REF_1F)}
    json.dump(info, open(os.path.join(DOC, "review_package_info.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    for k, v in info.items():
        print(k, "=", v)


if __name__ == "__main__":
    main()

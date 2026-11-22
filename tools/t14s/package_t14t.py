"""C-T14T review packaging: GitHub review packet (T14R tool), before/after previews, 17-floor contact sheet, Korean A3 PDF.

    python -I tools/t14s/package_t14t.py
Inputs: outputs/T14T/<floor>/ (built + validated), PR #29 previews in docs/t14s_floor_plans/review_packet (the "before" side).
Plan crops are native-pixel crops of the A1 PNG, so tiles inspect the delivered pixels.
"""
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

OUT = os.path.join(ROOT, "outputs", "T14T")
DOC = os.path.join(ROOT, "docs", "t14t_corrections")
PACKET = os.path.join(DOC, "review_packet")
BA = os.path.join(DOC, "before_after")
OLD_PACKET = os.path.join(ROOT, "docs", "t14s_floor_plans", "review_packet", "images")
REF_1F = os.path.join(ROOT, "docs", "t14s_floor_plans", "reference_1F", "1F_CleanLine_FIXED_user_supplied_preview.png")
FONT, FONT_B = "C:/Windows/Fonts/malgun.ttf", "C:/Windows/Fonts/malgunbd.ttf"
K = 200 / 25.4
CROP_MM = (18, 14, 22 + 360 + 4, 18 + 370 + 4)
ALL = ["B2", "B1", "1F"] + ["%dF" % i for i in range(2, 16)]
STATUS = "C_T14T_READY_FOR_CHATGPT_INDEPENDENT_REVIEW"


def meta(f):
    return json.load(open(os.path.join(OUT, f, "T14T_%s_plan_metadata.json" % f), encoding="utf-8"))


def label(f):
    return "FLOOR_" + f


def build_packet(tmp):
    from tools.t14r import export_visual_review as E
    os.makedirs(tmp, exist_ok=True)
    assets = []
    for f in SRC.TARGET_FLOORS:
        im = Image.open(os.path.join(OUT, f, "T14T_%s_plan_A1_1to200.png" % f)).convert("RGB")
        c = im.crop(tuple(int(v * K) for v in CROP_MM))
        p = os.path.join(tmp, label(f) + ".png")
        c.save(p, optimize=True)
        assets.append("%s=%s" % (label(f), p))
    if os.path.isdir(PACKET):
        shutil.rmtree(PACKET)
    sys.argv = ["export_visual_review", "pack", "--out", PACKET] + [x for a in assets for x in ("--asset", a)]
    E.main()
    sys.argv = ["export_visual_review", "verify", "--packet", PACKET]
    E.main()


def fit_text(d, xy, text, font, fill, width):
    """Greedy wrap by pixel width; returns the y after the last line."""
    x, y = xy
    line = ""
    for ch in text:
        if d.textlength(line + ch, font=font) > width:
            d.text((x, y), line, font=font, fill=fill)
            y += int(font.size * 1.35)
            line = ch
        else:
            line += ch
    if line:
        d.text((x, y), line, font=font, fill=fill)
        y += int(font.size * 1.35)
    return y


def before_after():
    os.makedirs(BA, exist_ok=True)
    fb, fs, ft = ImageFont.truetype(FONT_B, 34), ImageFont.truetype(FONT, 25), ImageFont.truetype(FONT_B, 28)
    out = {}
    for f in SRC.TARGET_FLOORS:
        b = Image.open(os.path.join(OLD_PACKET, label(f), "preview.jpg")).convert("RGB")
        a = Image.open(os.path.join(PACKET, "images", label(f), "preview.jpg")).convert("RGB")
        H = 1500
        b = b.resize((int(b.width * H / b.height), H))
        a = a.resize((int(a.width * H / a.height), H))
        corr = meta(f)["corrections_vs_pr29"]
        lines = ["[%s] %s → %s" % (c["area"], c["issue"], c["change"]) for c in corr]
        W = b.width + a.width + 60
        sheet = Image.new("RGB", (W, 110 + H + 40 + 10), "white")
        d = ImageDraw.Draw(sheet)
        d.text((20, 14), "%s — 정정 전/후 (before: PR #29 f2ba1d9 · after: C-T14T)" % f, font=fb, fill="#111")
        d.text((20, 62), "PROPOSED_DESIGN · NOT APPROVED · " + STATUS, font=fs, fill="#9b1c1c")
        sheet.paste(b, (20, 110))
        sheet.paste(a, (40 + b.width, 110))
        d.text((20, 112 + H), "BEFORE (PR #29)", font=ft, fill="#444")
        d.text((40 + b.width, 112 + H), "AFTER (C-T14T)", font=ft, fill="#444")
        # issue list under the pictures
        h2 = 0
        tmp = Image.new("RGB", (W, 1200), "white")
        dd = ImageDraw.Draw(tmp)
        y = 10
        for ln in lines:
            y = fit_text(dd, (20, y), ln, fs, "#222", W - 40) + 6
        h2 = y + 10
        full = Image.new("RGB", (W, sheet.height + h2), "white")
        full.paste(sheet, (0, 0))
        full.paste(tmp.crop((0, 0, W, h2)), (0, sheet.height))
        p = os.path.join(BA, "%s_before_after.jpg" % f)
        q = 82
        while True:
            full.save(p, quality=q, optimize=True)
            if os.path.getsize(p) <= 1100 * 1024 or q <= 55:
                break
            q -= 5
        out[f] = {"path": p, "bytes": os.path.getsize(p), "quality": q}
    return out


def after_img(f):
    return Image.open(os.path.join(PACKET, "images", label(f), "preview.jpg")).convert("RGB")


def contact_sheet():
    cols, tw, th, rows = 6, 470, 500, 3
    W, H = cols * (tw + 14) + 14, rows * (th + 46) + 70
    sheet = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(sheet)
    fb, fs = ImageFont.truetype(FONT_B, 22), ImageFont.truetype(FONT, 15)
    d.text((14, 12), "C-T14T — 17개 층 평면 (B2~15F) · 16개 정정 후보 + 1F 보존 기준 · PROPOSED_DESIGN · NOT APPROVED", font=fb, fill="#111")
    d.text((14, 40), STATUS + " · 축척 1:200 · 구조=MODEL_VERIFIED, 구획·문·실·가구·동선·난간=PROPOSED_DESIGN", font=fs, fill="#555")
    for i, f in enumerate(ALL):
        r, c = divmod(i, cols)
        x, y = 14 + c * (tw + 14), 70 + r * (th + 46)
        if f == "1F":
            im = Image.open(REF_1F).convert("RGB")
            cap = "1F  기준 도면(보존·사용자 제공, 변경 없음)"
        else:
            im = after_img(f)
            m = meta(f)
            G = m["design_proposed"]["circulation_graph"]["summary"]
            cap = "%s  실 %d · 미결 동선 %d" % (f, len(m["design_proposed"]["rooms"]), G["unresolved"])
        im = im.copy()
        im.thumbnail((tw, th))
        sheet.paste(im, (x + (tw - im.width) // 2, y + (th - im.height) // 2))
        d.rectangle([x, y, x + tw, y + th], outline="#bbbbbb")
        d.text((x, y + th + 6), cap, font=fs, fill="#222")
    p = os.path.join(DOC, "contact_sheet_17_floors_T14T.jpg")
    q = 86
    while True:
        sheet.save(p, quality=q, optimize=True)
        if os.path.getsize(p) <= 400 * 1024 or q <= 55:
            break
        q -= 5
    return p


def a3_pdf(decisions):
    W, H = 1190.55, 841.89
    doc = fitz.open()

    def page():
        p = doc.new_page(width=W, height=H)
        p.insert_font(fontname="malgun", fontfile=FONT)
        p.insert_font(fontname="malgunb", fontfile=FONT_B)
        return p

    def txt(p, x, y, s, size=9, bold=False, color=(0.1, 0.1, 0.1), w=340, h=700):
        p.insert_textbox(fitz.Rect(x, y, x + w, y + h), s, fontsize=size, fontname="malgunb" if bold else "malgun", color=color)

    red = (0.6, 0.1, 0.1)
    p = page()
    txt(p, 24, 14, "C-T14T 층별 평면도 정정 — 검수용 개요 (A3 가로)", 16, True, w=900)
    txt(p, 24, 38, "상태: %s · PROPOSED_DESIGN · NOT APPROVED · NOT FROZEN · 건축/도면 품질 승인 아님" % STATUS, 10, False, red, w=1140)
    cs = os.path.join(DOC, "contact_sheet_17_floors_T14T.jpg")
    im = Image.open(cs)
    r = fitz.Rect(24, 60, W - 24, 60 + (W - 48) * im.height / im.width)
    p.insert_image(r, filename=cs)
    y = r.y1 + 8
    rep = json.load(open(os.path.join(DOC, "build_test_report.json"), encoding="utf-8"))["summary"]
    rows = ["해결한 것: 방문객 동선 그래프(코어·화장실·승강기 로비·에스컬레이터 랜딩·FR 반입 접점·점포 문), 승강기 출입구 재배치, 개구부·바닥판 없음·난간 표기, 내부 식별자 제거, 판매/지원 분리, 서비스 동선, 문화 운영 개념, 정원 산책로.",
            "자동 검사(결정적): 기술 검사 %d/%d층 통과 · 원본 지오메트리 변경 없음=%s · 동선 완결 %s층 · 미결 동선 %d건 / %d개 층 (아래 결정 항목)." % (
                rep["floors_technical_pass"], rep["floors_tested"], rep["source_geometry_unchanged"], len(rep["floors_circulation_complete"]), rep["open_circulation_items"], len(rep["floors_circulation_pending_decision"])),
            "시각·건축 검수와 승인은 하지 않았다. ChatGPT 커넥터 판독은 시험하지 않았다(업로드·해시 대조만)."]
    txt(p, 24, y, "\n".join(rows), 10, w=1140, h=120)
    # decision page
    p = page()
    txt(p, 24, 14, "미결 설계 결정 (검증 지오메트리를 바꿔야 풀리는 항목 — 승인 필요)", 16, True, w=1100)
    yy = 44
    for k, v in decisions.items():
        n = len(v["rows"])
        block = "%s  %s\n%s\n" % (k, v["title"], v["fact"]) + "\n".join("   · " + a for a in v["alternatives"])
        if k == "D-01":
            block = block.replace(v["fact"], v["fact"] + " (층별 표는 decision_packet.md)")
        hh = 12 * (3 + block.count("\n") + len(block) // 160)
        if yy + hh > H - 20:
            p = page()
            yy = 20
        txt(p, 24, yy, block, 8.6, w=1140, h=hh)
        yy += hh + 6
    # per-floor pages
    for f in SRC.TARGET_FLOORS:
        m = meta(f)
        p = page()
        c = after_img(f)
        jp = os.path.join(os.environ.get("TEMP", "."), "t14t_pg_%s.jpg" % f)
        c.resize((1500, int(1500 * c.height / c.width))).save(jp, quality=88)
        rr = fitz.Rect(24, 36, 24 + 790, 36 + 790 * c.height / c.width)
        p.insert_image(rr, filename=jp)
        txt(p, 24, 10, "%s 평면도 (정정 후보) · FFL %+.3f m · 1:200" % (f, m["level_ffl_m"]), 14, True, w=900)
        G = m["design_proposed"]["circulation_graph"]
        lines = ["상태: " + STATUS, "PROPOSED_DESIGN · NOT APPROVED", "", "정정 내용 (PR #29 대비)"]
        for cr in m["corrections_vs_pr29"]:
            lines.append("· [%s] %s → %s" % (cr["area"], cr["issue"], cr["change"]))
        lines += ["", "미해결 / 결정 필요"]
        KO = {"AT_OPENING_EDGE": "에스컬레이터 끝이 개구 안: 검증 슬래브 가장자리까지만 연결(점선·빈 마름모)", "BLOCKED_BY_SOLID": "에스컬레이터 끝이 코어 외곽 안(모델 충돌)",
              "ENTRY_BLOCKED": "승강기 출입구 둘레에 설 자리 없음", "UNREACHABLE": "보행망에 연결되지 않음", "NO_LANDING": "FR 랜딩을 찾지 못함"}
        if G["unresolved"]:
            for u in G["unresolved"]:
                lines.append("· %s — %s%s" % (u["id"].replace("esc ", "에스컬 ").replace(" arrive", " 하차").replace(" board", " 승차").replace("core ", "코어 ").replace("tube ", "튜브 ").replace("wc ", "화장실 ").replace("door room", "점포 문 실").replace("service door room", "서비스 문 실"), KO.get(u.get("status"), u.get("status", "")), (" → " + u["decision"]) if u.get("decision") else ""))
        else:
            lines.append("· 없음 (방문객 동선 노드 전부 연결)")
        for nm in G.get("not_modeled", []):
            lines.append("· %s — 출입 지점이 모델·1F 심볼에 정의 없음(연결 여부 미판정) → %s" % (nm["id"], nm["decision"]))
        lines += ["", "산출물: outputs/T14T/%s/ (SVG · DXF · A1/A3 PDF · PNG · JSON)" % f, "검수 타일: docs/t14t_corrections/review_packet/images/FLOOR_%s/" % f,
                  "정정 전/후: docs/t14t_corrections/before_after/%s_before_after.jpg" % f]
        txt(p, 830, 36, "\n".join(lines), 7.8, w=345, h=780)
    out = os.path.join(DOC, "T14T_correction_review_A3.pdf")
    doc.save(out)
    n = len(doc)
    doc.close()
    return out, n


def main():
    sys.path.insert(0, os.path.join(ROOT, "tools", "t14s"))
    import decision_packet as DP
    tmp = os.path.join(os.environ.get("TEMP", "."), "t14t_review_src")
    os.makedirs(DOC, exist_ok=True)
    build_packet(tmp)
    ba = before_after()
    cs = contact_sheet()
    dec = DP.build()
    DP.write(dec)
    pdf, pages = a3_pdf(dec)
    info = {"contact_sheet": cs, "contact_sheet_bytes": os.path.getsize(cs), "a3_pdf": pdf, "a3_pages": pages, "before_after": {k: v["bytes"] for k, v in ba.items()},
            "review_packet": PACKET}
    json.dump(info, open(os.path.join(DOC, "review_package_info.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    for k, v in info.items():
        if k != "before_after":
            print(k, "=", v)
    print("before/after files:", len(ba), "max bytes", max(v["bytes"] for v in ba.values()))


if __name__ == "__main__":
    main()

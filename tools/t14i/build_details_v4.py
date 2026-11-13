"""Create V4 detail candidates by preserving the verified V3 vector sheets and
adding explicit truth-class overlays and the two missing relationship sections.

No geometry in the source sheets is edited.  D-404 and D-408 receive new vector
insets: model levels / master extents are green MODEL VERIFIED; unapproved
internal stair or step interpretations are orange CONCEPT PROPOSED / DERIVED.
"""
import argparse
import json
import math
import os

import pymupdf
import cairosvg

import t14i  # noqa: F401
from t14i import common as cm, config as cfg
from t14f import fonts
from t14g import registry as sheetreg
import pipeline_common as pc


MM = 72.0 / 25.4
COL = {cfg.MODEL_VERIFIED: (0.04, 0.42, 0.24),
       cfg.CONCEPT_PROPOSED: (0.71, 0.38, 0.04),
       cfg.UNRESOLVED: (0.64, 0.13, 0.13),
       "DERIVED": (0.18, 0.28, 0.63)}


def R(x0, y0, x1, y1):
    return pymupdf.Rect(x0 * MM, y0 * MM, x1 * MM, y1 * MM)


def P(x, y):
    return pymupdf.Point(x * MM, y * MM)


def add_text(page, rect, text, pt=6.0, bold=False, color=(0.12, 0.12, 0.12), align=0):
    name = "kbold" if bold else "kreg"
    page.insert_textbox(R(*rect), text, fontsize=max(6.0, pt), fontname=name,
                        color=color, align=align, lineheight=1.15, overlay=True)


def badge(page, x, y, text, color):
    w = 3.5 + len(text) * 1.65
    page.draw_rect(R(x, y, x + w, y + 5.2), color=color, fill=(1, 1, 1), width=0.3 * MM, overlay=True)
    add_text(page, (x + 1, y + 0.6, x + w - 1, y + 5.0), text, 6, True, color, 1)
    return x + w


def status_header(page, title, second, second_class):
    # Replace the old right-hand heading only; model drawing below remains intact.
    page.draw_rect(R(211.5, 5.0, 407.5, 20.5), color=(0.55, 0.55, 0.55), fill=(1, 1, 1), width=0.15 * MM, overlay=True)
    x = badge(page, 214.0, 7.0, cfg.MODEL_VERIFIED, COL[cfg.MODEL_VERIFIED]) + 2
    add_text(page, (x, 7.0, 405, 12.2), title, 6.2, True)
    x = badge(page, 214.0, 13.2, second_class, COL[second_class]) + 2
    add_text(page, (x, 13.2, 405, 19.3), second, 6.0, False)


def arrow(page, points, color, width=0.55, dashed=False):
    shape = page.new_shape()
    shape.draw_polyline([P(x, y) for x, y in points])
    shape.finish(color=color, width=width * MM, dashes="4 2" if dashed else None)
    shape.commit(overlay=True)
    (x0, y0), (x1, y1) = points[-2], points[-1]
    ang = math.atan2(y1 - y0, x1 - x0)
    L = 3.0
    a = P(x1, y1)
    b = P(x1 - L * math.cos(ang - 0.55), y1 - L * math.sin(ang - 0.55))
    c = P(x1 - L * math.cos(ang + 0.55), y1 - L * math.sin(ang + 0.55))
    page.draw_polyline([b, a, c], color=color, width=width * MM, overlay=True)


def overlay_404(page, floors):
    # The former blank "section none" field becomes a one-storey relationship section.
    page.draw_rect(R(211.5, 5.0, 407.5, 219.0), color=(0.65, 0.65, 0.65), fill=(1, 1, 1), width=0.2 * MM, overlay=True)
    add_text(page, (215, 8, 403, 15), "코어 D 수직 관계 단면 · 1F→2F", 8, True)
    x = badge(page, 215, 17, cfg.MODEL_VERIFIED, COL[cfg.MODEL_VERIFIED]) + 2
    add_text(page, (x, 17, 403, 23), "코어 외곽·층 레벨·층고", 6.3, True)
    x = badge(page, 215, 24, cfg.CONCEPT_PROPOSED, COL[cfg.CONCEPT_PROPOSED]) + 2
    add_text(page, (x, 24, 403, 31), "내부 계단 관계(개념, 승인 치수 아님)", 6.0)
    z1, z2 = floors["1F"], floors["2F"]
    story = z2 - z1
    k = 20.0  # 1:50 -> 20 mm per model metre
    y_base = 187.0
    y_top = y_base - story * k
    x0, x1 = 245.0, 365.0
    green, orange = COL[cfg.MODEL_VERIFIED], COL[cfg.CONCEPT_PROPOSED]
    # model envelope and level slabs
    page.draw_rect(R(x0, y_top, x0 + 5, y_base), color=green, fill=None, width=0.65 * MM, overlay=True)
    page.draw_rect(R(x1 - 5, y_top, x1, y_base), color=green, fill=None, width=0.65 * MM, overlay=True)
    for yy, fl, z in ((y_base, "1F", z1), (y_top, "2F", z2)):
        page.draw_line(P(x0 - 18, yy), P(x1 + 18, yy), color=green, width=0.6 * MM, overlay=True)
        add_text(page, (x0 - 17, yy - 7, x0 + 25, yy - 1), "%s  %+.3f" % (fl, z - z1), 6.2, True, green)
    # explicitly conceptual folded stair line, with no riser count/dimensions
    land_y = (y_top + y_base) / 2
    arrow(page, [(x0 + 12, y_base - 8), (x1 - 12, land_y + 6), (x0 + 12, land_y - 6), (x1 - 12, y_top + 8)], orange, 0.45, True)
    add_text(page, (258, land_y - 6, 352, land_y + 7), "개념 계단 동선\n(CONCEPT ONLY)", 6.0, True, orange, 1)
    # physical dimension from model floor levels
    page.draw_line(P(382, y_top), P(382, y_base), color=green, width=0.25 * MM, overlay=True)
    page.draw_line(P(378, y_top), P(386, y_top), color=green, width=0.25 * MM, overlay=True)
    page.draw_line(P(378, y_base), P(386, y_base), color=green, width=0.25 * MM, overlay=True)
    add_text(page, (383, (y_top + y_base) / 2 - 9, 405, (y_top + y_base) / 2 + 9), "층고\n%d mm" % round(story * 1000), 6.2, True, green)
    add_text(page, (215, 197, 403, 215), "UNRESOLVED  상층 부속실·방화문·계단 형식·피난 치수는 모델에 없어 확정하지 않음.", 6.2, True, COL[cfg.UNRESOLVED])


def overlay_408(page, run):
    page.draw_rect(R(211.5, 5.0, 407.5, 219.0), color=(0.65, 0.65, 0.65), fill=(1, 1, 1), width=0.2 * MM, overlay=True)
    add_text(page, (215, 8, 403, 15), "선큰 계단·마당 관계 단면", 8, True)
    x = badge(page, 215, 17, cfg.MODEL_VERIFIED, COL[cfg.MODEL_VERIFIED]) + 2
    add_text(page, (x, 17, 403, 23), "윤곽 14,000×16,500 · 12단 · FL −5.500", 6.1, True)
    x = badge(page, 215, 24, "DERIVED", COL["DERIVED"]) + 2
    add_text(page, (x, 24, 403, 31), "5500÷12=458 mm — 승인된 보행계단 단높이 아님", 6.0, True, COL["DERIVED"])
    green, orange, blue = COL[cfg.MODEL_VERIFIED], COL[cfg.CONCEPT_PROPOSED], COL["DERIVED"]
    x0, x1 = 231.0, 371.0  # 14 m at 1:100
    y0, y1 = 75.0, 130.0   # 5.5 m at 1:100
    page.draw_line(P(x0 - 12, y0), P(x1 + 16, y0), color=green, width=0.65 * MM, overlay=True)
    page.draw_line(P(x0 - 12, y1), P(x1 + 16, y1), color=green, width=0.65 * MM, overlay=True)
    add_text(page, (215, y0 - 8, 253, y0 - 2), "1F ±0.000", 6.2, True, green)
    add_text(page, (215, y1 + 2, 255, y1 + 8), "B1 −5.500", 6.2, True, green)
    # Derived 12-step interpretation: shown dashed/blue and separated from model lines.
    dx, dy = (x1 - x0) / 12.0, (y1 - y0) / 12.0
    pts = [(x0, y0)]
    for i in range(12):
        pts.extend([(x0 + (i + 1) * dx, y0 + i * dy), (x0 + (i + 1) * dx, y0 + (i + 1) * dy)])
    shape = page.new_shape(); shape.draw_polyline([P(x, y) for x, y in pts]); shape.finish(color=blue, width=0.32 * MM, dashes="3 1.5"); shape.commit(overlay=True)
    page.draw_line(P(386, y0), P(386, y1), color=green, width=0.25 * MM, overlay=True)
    add_text(page, (388, 94, 405, 113), "5500\nmm", 6.3, True, green)
    add_text(page, (253, 140, 398, 159), "DERIVED 관계도: 12등분 시 458 mm/단.\n일반 보행계단 승인치수로 사용 금지.", 6.5, True, blue)
    add_text(page, (215, 169, 403, 187), "UNRESOLVED  실제 디딤판·중간참·난간·지반·배수·피난 적합성은 원본 모델에 없음.", 6.2, True, COL[cfg.UNRESOLVED])
    x = badge(page, 215, 193, cfg.CONCEPT_PROPOSED, orange) + 2
    add_text(page, (x, 193, 403, 207), "단면 관계만 제안; 건축·피난 치수 확정 아님", 6.0, True, orange)


def extra_diagram(page, sid):
    orange = COL[cfg.CONCEPT_PROPOSED]
    blue = (0.08, 0.38, 0.70)
    if sid == "D-401":
        arrow(page, [(84, 142), (105, 154), (126, 141)], orange, 0.45, True)
        add_text(page, (76, 157, 136, 166), "상행 동선(모델 램프 관계)", 6.0, True, orange, 1)
    elif sid == "D-402":
        for x in (275, 310, 345):
            arrow(page, [(x, 48), (x, 115)], blue, 0.4, True)
        add_text(page, (245, 118, 375, 128), "채광 경로 원리 — 정량 성능은 UNRESOLVED", 6.0, True, blue, 1)
    elif sid == "D-403":
        for y in (46, 96, 146):
            page.draw_line(P(230, y), P(270, y), color=orange, width=0.4 * MM, dashes="4 2", overlay=True)
        add_text(page, (232, 151, 308, 160), "승강장 관계 CONCEPT", 6.0, True, orange)
    elif sid == "D-405":
        page.draw_rect(R(268, 86, 348, 132), color=orange, fill=(1, 1, 1), width=0.35 * MM, dashes="4 2", overlay=True)
        add_text(page, (272, 91, 344, 126), "접속 원리\n층판—캡슐 외피 연속\n문·방수·구조 접합 UNRESOLVED", 6.2, True, orange, 1)
    elif sid == "D-406":
        arrow(page, [(306, 96), (330, 96), (346, 108)], orange, 0.4, True)
        add_text(page, (285, 111, 372, 121), "외피—층판 접합 원리 CONCEPT", 6.0, True, orange, 1)
    elif sid == "D-407":
        add_text(page, (305, 181, 382, 195), "30.0° MODEL VERIFIED\n난간·기계·승하차 안전거리 UNRESOLVED", 6.0, True, COL[cfg.UNRESOLVED], 1)
    elif sid == "D-409":
        arrow(page, [(170, 45), (150, 62), (126, 92), (106, 112)], orange, 0.5, True)
        add_text(page, (121, 54, 196, 67), "하역→보관→FR 승강로\n운영 동선 CONCEPT", 6.0, True, orange, 1)
    elif sid == "D-410":
        for a in (0, 2.1, 4.2):
            x, y = 104 + 40 * math.cos(a), 100 + 40 * math.sin(a)
            arrow(page, [(104, 100), (x, y)], orange, 0.38, True)
        add_text(page, (75, 142, 150, 156), "배수 방향 개념\n지붕 개방/폐쇄 UNRESOLVED", 6.0, True, orange, 1)


def update_titleblock(page, sid, scale):
    """Replace the V3 project/revision cells while preserving the drawing title."""
    page.draw_rect(R(10, 262, 38, 287), color=(0.15, 0.15, 0.15), fill=(1, 1, 1), width=0.2 * MM, overlay=True)
    add_text(page, (14, 266, 36, 274), sid, 10.0, True)
    page.draw_rect(R(300, 262, 410, 287), color=(0.15, 0.15, 0.15), fill=(1, 1, 1), width=0.2 * MM, overlay=True)
    page.draw_line(P(358, 262), P(358, 287), color=(0.15, 0.15, 0.15), width=0.2 * MM, overlay=True)
    add_text(page, (304, 266, 354, 272), "축척 1:%d (A3)" % scale, 7.0, True)
    add_text(page, (304, 273, 354, 279), "V4 TRUTH-CLASS REVIEW", 6.0, True, COL[cfg.UNRESOLVED])
    add_text(page, (304, 280, 354, 286), "후보 · FREEZE 아님", 6.0)
    add_text(page, (362, 266, 406, 272), "C-T14I", 7.0, True)
    add_text(page, (362, 273, 406, 279), "개정 R4 (V4)", 6.0)
    add_text(page, (362, 280, 406, 286), "출력 %s" % cfg.ISSUE_DATE, 6.0)


def update_scale_bar(page, scale):
    """Searchable V4 scale bar; the pathified V3 bar remains only as graphics."""
    meters = [0, 1, 2, 5] if scale == 50 else [0, 2, 5, 10]
    x, y = 17.0, 212.0
    k = 1000.0 / scale
    L = meters[-1] * k
    page.draw_rect(R(12, 203, 132, 220), color=(0.75, 0.75, 0.75), fill=(1, 1, 1), width=0.1 * MM, overlay=True)
    for i, (a, b) in enumerate(zip(meters, meters[1:])):
        page.draw_rect(R(x + a * k, y, x + b * k, y + 1.6), color=(0.1, 0.1, 0.1),
                       fill=(0.08, 0.08, 0.08) if i % 2 == 0 else (1, 1, 1), width=0.15 * MM, overlay=True)
    for m in meters:
        add_text(page, (x + m * k - 5, y - 5.8, x + m * k + 5, y - 0.4), "%d%s" % (m, " m" if m == meters[-1] else ""), 6.0, False, (0.2, 0.2, 0.2), 1)
    add_text(page, (x, y + 3.0, x + L + 18, y + 9.0), "1:%d · A3 420×297 mm · 100%% 인쇄" % scale, 6.0)


STATUS = {
    "D-401": ("램프 형상·층 레벨", "경사 승인·난간·보행 적합성 미확정", cfg.UNRESOLVED),
    "D-402": ("T2 튜브·층판 개구", "채광 원리 제안 · 정량 성능 미확정", cfg.CONCEPT_PROPOSED),
    "D-403": ("T3/T4 튜브·승강로 형상", "승강장 문·기계·안전거리 미확정", cfg.UNRESOLVED),
    "D-405": ("캡슐·층판 형상", "출입문·방수·구조 접합 미확정", cfg.UNRESOLVED),
    "D-406": ("외피·층판·입면 부재", "접합·재료·단열 원리 제안", cfg.CONCEPT_PROPOSED),
    "D-407": ("경사 30.0°·층간 형상", "난간·기계·승하차 치수 미확정", cfg.UNRESOLVED),
    "D-409": ("FR 샤프트·층 레벨", "하역 운영 동선 제안 · 장비 미확정", cfg.CONCEPT_PROPOSED),
    "D-410": ("지붕 슬래브·구조 표식", "방수·배수 제안 · 개방/폐쇄 미결", cfg.UNRESOLVED),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=cm.RUN_DEFAULT)
    args = ap.parse_args()
    run = os.path.abspath(args.run)
    src_dir = os.path.join(run, "details")
    out_dir = cm.v4_dir(run, "details")
    source_reg = cm.jl(os.path.join(src_dir, "detail_registry.json"))["details"]
    src_by = {r["sheet"]: r for r in source_reg}
    model = cm.load_model(run)
    facts = []
    rows = []
    for n in range(401, 411):
        sid = "D-%d" % n
        src = os.path.join(src_dir, sid + "_detail.pdf")
        # Turn legacy text into vector outlines first.  The verified geometry
        # remains vector, while the new V4 text is the only searchable text and
        # therefore follows the >=6 pt edition policy exactly.
        source_doc = pymupdf.open(src)
        legacy_svg = source_doc[0].get_svg_image(text_as_path=True)
        source_doc.close()
        path_pdf = os.path.join(out_dir, sid + "_legacy_paths.tmp.pdf")
        cairosvg.svg2pdf(bytestring=legacy_svg.encode("utf-8"), write_to=path_pdf)
        # CairoSVG interprets the SVG's point width at 96 dpi (315 x 222.75 mm).
        # Place that vector page onto an explicit ISO A3 MediaBox before adding
        # any V4 coordinate-based overlay.
        a3_pdf = os.path.join(out_dir, sid + "_legacy_paths_a3.tmp.pdf")
        source_paths = pymupdf.open(path_pdf)
        a3_doc = pymupdf.open()
        a3_page = a3_doc.new_page(width=cfg.PAPER_A3[0] * MM, height=cfg.PAPER_A3[1] * MM)
        a3_page.show_pdf_page(a3_page.rect, source_paths, 0)
        a3_doc.save(a3_pdf, garbage=4, deflate=True)
        a3_doc.close(); source_paths.close()
        doc = pymupdf.open(a3_pdf)
        page = doc[0]
        page.insert_font(fontname="kreg", fontfile=fonts.resolve("regular")[0])
        page.insert_font(fontname="kbold", fontfile=fonts.resolve("bold")[0])
        if sid == "D-404":
            overlay_404(page, model.floors)
        elif sid == "D-408":
            overlay_408(page, run)
        else:
            t1, t2, cls = STATUS[sid]
            status_header(page, t1, t2, cls)
            extra_diagram(page, sid)
        update_titleblock(page, sid, sheetreg.detail_scale(sid))
        update_scale_bar(page, sheetreg.detail_scale(sid))
        base = os.path.join(out_dir, sid + "_detail_v4")
        doc.set_metadata({**doc.metadata, "subject": "C-T14I V4 detail truth overlay; candidate, not frozen", "creator": "t14i/build_details_v4.py"})
        doc.subset_fonts()
        doc.save(base + ".pdf", garbage=4, deflate=True)
        # Export the final PDF page, not the source, so PDF/SVG/PNG are the same candidate.
        final = pymupdf.open(base + ".pdf")
        svg = final[0].get_svg_image(text_as_path=False)
        open(base + ".svg", "w", encoding="utf-8").write(svg)
        pix = final[0].get_pixmap(dpi=180, alpha=False)
        pix.save(base + ".png")
        final.close(); doc.close()
        os.remove(path_pdf)
        os.remove(a3_pdf)
        old = src_by[sid]
        scale = sheetreg.detail_scale(sid)
        classes = [cfg.MODEL_VERIFIED, cfg.CONCEPT_PROPOSED, cfg.UNRESOLVED]
        grade = "MODEL VERIFIED BASE · CONCEPT PROPOSED OVERLAY · UNRESOLVED ITEMS"
        files = {e: {"path": base + "." + e, "sha256": cm.sha_file(base + "." + e)} for e in ("svg", "pdf", "png")}
        rows.append({"sheet": sid, "title": old["title"] + " · V4 검토", "scale": "1:%d" % scale,
                     "grade": grade, "folder": "details", "paper": list(cfg.PAPER_A3),
                     "status_class": " + ".join(classes), "classes": classes, "part": "II", "kind": "detail",
                     "scale_bars": old.get("scale_bars", []), "files": files,
                     "source_v3_pdf": src, "source_v3_sha256": cm.sha_file(src),
                     "v4_change": "missing section added" if sid in ("D-404", "D-408") else "truth-class header + relationship overlay"})
        facts.append({"sheet": sid, "scale": scale, "source": os.path.basename(src),
                      "model_cache": "model_world.npz", "glb": "BLOCKED_MISSING_SOURCE",
                      "assertions": [cfg.MODEL_VERIFIED, cfg.CONCEPT_PROPOSED, cfg.UNRESOLVED]})
        print(sid, os.path.abspath(base + ".pdf"))
    cm.jd(rows, os.path.join(out_dir, "detail_registry.json"))
    cm.jd({"details": facts, "rule": "base geometry retained; overlays explicitly classed; D-404/D-408 sections added"},
          os.path.join(out_dir, "details_v4_facts.json"))
    print("DETAIL REGISTRY", os.path.abspath(os.path.join(out_dir, "detail_registry.json")))


if __name__ == "__main__":
    main()

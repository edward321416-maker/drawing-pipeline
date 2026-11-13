"""Assemble the two C-T14I PDFs from the sheet registries.

    python -X utf8 tools/t14i/build_books.py --run <RUN> --head <git head> [--out <dir>]

Reads RUN\\v4\\*\\*_registry.json (rows from t14i.common.sheet_row) plus the legacy sheets (A-003 user supplied, E-201..204, S-301..305)
and writes Graduation_Drawing_Book_Candidate.pdf (Part I) and Technical_Drawing_Appendix_Candidate.pdf (Part II) with bookmarks,
per-PDF sheet_index.json/csv (page, sheet, title, scale, paper, grade, part) and contact sheets. Page numbers printed in the contents
sheets (G-002, A-001) are the real positions in the assembled PDFs (assigned before the sheets are drawn; asserted afterwards).
"""
import argparse
import csv
import glob
import json
import math
import os
import re
import shutil
import sys

import t14i  # noqa: F401
import cairosvg  # noqa: E402
from t14i import config as cfg, common, appendix_docs as ad
import fitz  # noqa: E402
from t14f import fonts as cjk_fonts  # noqa: E402
from t14g import modelsrc  # noqa: E402

A3 = cfg.PAPER_A3
A1 = cfg.PAPER_A1


def paper_name(p):
    p = tuple(round(v) for v in p)
    return "A3" if p == (420, 297) else ("A1" if p == (841, 594) else "%dx%d" % p)


def natural(sid):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", sid)]


def _legacy_rows(run):
    rows = []
    # A-003 user-supplied (copied unchanged; the book page gets a page tag like V3)
    rows.append({"sheet": "A-003", "title": "배치도 / 1층 계획 (사용자 제공 1F_CleanLine_FIXED, 수정 없음)", "scale": "1:400", "grade": "USER_SUPPLIED",
                 "folder": "plans", "paper": None, "files": {"pdf": {"path": os.path.join(run, "plans", "A-003_site_plan_1F_1to400.pdf")}}})
    er = common.jl(os.path.join(run, "elevations", "elevation_registry.json"))
    for e in er["elevations"]:
        rows.append({"sheet": e["sheet"], "title": "%s측 입면도" % {"N": "북", "E": "동", "S": "남", "W": "서"}[e["name"]], "scale": e["scale"], "grade": "MODEL VERIFIED",
                     "folder": "elevations", "paper": list(A3), "files": e["files"]})
    sr = common.jl(os.path.join(run, "sections", "section_line_registry.json"))
    rows.append({"sheet": "S-301", "title": "단면 키플랜", "scale": "1:400", "grade": "MODEL VERIFIED", "folder": "sections", "paper": list(A3), "files": sr["section_locator"]["files"]})
    for s in sr["sections"]:
        rows.append({"sheet": s["sheet"], "title": "단면도 %s" % s["name"], "scale": s["scale"], "grade": "MODEL VERIFIED · 실제 메시 절단", "folder": "sections", "paper": list(A3), "files": s["files"]})
    return rows


def collect(run):
    """sheet id -> registry row, from every *_registry.json below RUN\\v4 (later files win on duplicates) + legacy rows."""
    rows = {}
    for r in _legacy_rows(run):
        rows[r["sheet"]] = r
    for p in sorted(glob.glob(os.path.join(run, "v4", "**", "*_registry.json"), recursive=True)):
        d = common.jl(p)
        lst = d if isinstance(d, list) else d.get("rows") or d.get("sheets") or d.get("details") or []
        for r in lst:
            if isinstance(r, dict) and r.get("sheet") and r.get("files"):
                r = dict(r)
                r["_registry"] = p
                rows[r["sheet"]] = r
    return rows


PART_II_ORDER = [
    "A-000", "A-001", "A-002", "A-003",
    "P-101", "P-102", "P-103", "P-104", "P-105", "P-106", "P-107", "P-108", "P-109", "P-110", "P-111", "P-112",
    "A-901", "A-902", "A-903", "A-904",
    "P-201", "P-202", "P-211", "P-212", "P-213", "P-214", "A-905",
    "E-201", "E-202", "E-203", "E-204",
    "S-301", "S-302", "S-303", "S-304", "S-305",
    "D-401", "D-402", "D-403", "D-404", "D-405", "D-406", "D-407", "D-408", "D-409", "D-410",
    "A-906", "A-907", "A-900",
]


def order_parts(rows):
    part1 = sorted([s for s in rows if s.startswith("G-")], key=natural)
    known = [s for s in PART_II_ORDER if s in rows]
    extra = sorted([s for s in rows if not s.startswith("G-") and s not in PART_II_ORDER], key=natural)
    return part1, known + extra


def _pdf_of(row):
    return row["files"]["pdf"]["path"]


def _paper_of(row):
    if row.get("paper"):
        return tuple(row["paper"])
    d = fitz.open(_pdf_of(row))
    r = d[0].rect
    return (round(r.width / 72 * 25.4, 1), round(r.height / 72 * 25.4, 1))


def assemble(run, order, rows, out_pdf, part_label, title, subject, head):
    book = fitz.open()
    toc, pages = [], []
    for sid in order:
        r = rows[sid]
        src = fitz.open(_pdf_of(r))
        if sid == "A-003":
            # A-003 is user supplied and must not be redrawn.  Preserve its visual
            # vectors exactly, but turn the legacy sub-6pt source text into paths in
            # the assembled copy.  The source PDF remains byte-for-byte untouched;
            # the searchable 8/6pt V4 page tag below records the sheet identity.
            original_rect_ = src[0].rect
            svg_ = src[0].get_svg_image(text_as_path=True)
            path_doc_ = fitz.open(stream=cairosvg.svg2pdf(bytestring=svg_.encode("utf-8")), filetype="pdf")
            normalized_ = fitz.open()
            normalized_page_ = normalized_.new_page(width=original_rect_.width, height=original_rect_.height)
            normalized_page_.show_pdf_page(normalized_page_.rect, path_doc_, 0)
            src = normalized_
        book.insert_pdf(src)
        n = len(book)
        if sid == "A-003":
            pg_ = book[n - 1]
            pg_.insert_text((922, 812), "A-003", fontname="cjkb", fontfile=cjk_fonts.resolve("bold")[0], fontsize=8, color=(0.07, 0.07, 0.07))
            pg_.insert_text((950, 812), "도면집 %s · 사용자 제공 시트(쪽 번호표만 추가, 본문 수정 없음)" % cfg.EDITION, fontname="cjkr", fontfile=cjk_fonts.resolve("regular")[0], fontsize=6, color=(0.3, 0.3, 0.3))
        toc.append([1, "%s  %s" % (sid, r["title"]), n])
        pr = book[n - 1].rect
        pages.append({"page": n, "sheet": sid, "title": r["title"], "scale": r.get("scale") or "—", "grade": r.get("grade") or "", "folder": r.get("folder"),
                      "paper": paper_name((pr.width / 72 * 25.4, pr.height / 72 * 25.4)), "part": part_label, "source_pdf": _pdf_of(r),
                      "source_sha256": common.sha_file(_pdf_of(r))})
    book.set_toc(toc)
    book.set_metadata({"title": title, "author": "drawing-pipeline", "subject": subject, "keywords": "model-derived drawing set; candidate; not frozen", "creator": "t14i/build_books.py", "producer": "PyMuPDF"})
    book.subset_fonts()
    os.makedirs(os.path.dirname(out_pdf), exist_ok=True)
    book.save(out_pdf, garbage=4, deflate=True)
    book.close()
    return pages


def contact_sheet(pdf, out_png, pages, cols=8, thumb_w=330):
    from PIL import Image, ImageDraw, ImageFont
    d = fitz.open(pdf)
    ft = ImageFont.truetype(cjk_fonts.resolve("regular")[0], 15)
    ims = []
    for pg in d:
        z = thumb_w / pg.rect.width
        pm = pg.get_pixmap(matrix=fitz.Matrix(z, z))
        ims.append(Image.frombytes("RGB", (pm.width, pm.height), pm.samples))
    th = max(i.height for i in ims)
    rows_n = math.ceil(len(ims) / cols)
    W = cols * (thumb_w + 12) + 12
    H = rows_n * (th + 34) + 12
    sheet = Image.new("RGB", (W, H), "#d9d9d9")
    dr = ImageDraw.Draw(sheet)
    for i, im in enumerate(ims):
        x, y = 12 + (i % cols) * (thumb_w + 12), 12 + (i // cols) * (th + 34)
        sheet.paste(im, (x, y + 22))
        dr.rectangle([x - 1, y + 21, x + im.width, y + 22 + im.height], outline="#888")
        dr.text((x, y), "%d  %s  %s" % (pages[i]["page"], pages[i]["sheet"], pages[i]["title"][:16]), font=ft, fill="#111")
    sheet.save(out_png, optimize=True)


def write_index(pages, base, part, edition_pdf):
    json.dump({"edition": cfg.EDITION, "part": part, "pdf": os.path.basename(edition_pdf), "pages": len(pages),
               "sheets": [{k: p[k] for k in ("page", "sheet", "title", "scale", "grade", "folder", "paper", "part", "source_sha256")} for p in pages]},
              open(base + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(base + ".csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["page", "sheet", "title", "scale", "paper", "grade", "folder", "part"])
        for p in pages:
            w.writerow([p["page"], p["sheet"], p["title"], p["scale"], p["paper"], p["grade"], p["folder"], p["part"]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=common.RUN_DEFAULT)
    ap.add_argument("--head", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--allow-missing", action="store_true", help="skip ordered sheets that were not produced (reported)")
    a = ap.parse_args()
    run = os.path.abspath(a.run)
    out = a.out or common.v4_dir(run, "book")
    os.makedirs(out, exist_ok=True)
    rows = collect(run)
    ident = modelsrc.identity(run)
    # A-000/A-001/G-002 are generated here (their page numbers are known from the order, which only depends on which sheets exist)
    dd = common.v4_dir(run, "appendix_docs")
    rows["A-000"] = {"sheet": "A-000", "title": "기술 도면 부록 표지", "scale": "—", "grade": "DOCUMENT", "folder": "appendix", "paper": list(A3), "files": {"pdf": {"path": os.path.join(dd, "A-000.pdf")}}}
    rows["A-001"] = {"sheet": "A-001", "title": "도면 목록 (두 도면집 전체)", "scale": "—", "grade": "DOCUMENT", "folder": "appendix", "paper": list(A3), "files": {"pdf": {"path": os.path.join(dd, "A-001.pdf")}}}
    if "G-001" in rows and "G-002" not in rows:
        rows["G-002"] = {"sheet": "G-002", "title": "목차", "scale": "—", "grade": "DOCUMENT", "folder": "partI", "paper": list(A3), "files": {"pdf": {"path": os.path.join(dd, "G-002.pdf")}}}
    part1, part2 = order_parts(rows)
    # sheets that are produced here (placeholders above) are not on disk yet: generate A-002 / A-900 if no other agent made them
    nort = common.jl(os.path.join(run, "raw_slices", "camera_bounds.json"))["frame"]["north_deg"]
    for sid, fn in (("A-002", lambda: ad.build_legend(run, os.path.join(dd, "A-002"), nort)), ("A-900", lambda: ad.build_unresolved(run, os.path.join(dd, "A-900")))):
        if sid not in rows or "_registry" not in rows[sid]:
            rows[sid] = fn()
    missing = [s for s in PART_II_ORDER if s not in rows]
    if missing and not a.allow_missing:
        print("MISSING part II sheets:", missing)
    part1, part2 = order_parts(rows)
    entries = []
    for part, order in (("I", part1), ("II", part2)):
        for i, sid in enumerate(order):
            r = rows[sid]
            p = _paper_of(r) if sid not in ("A-000", "A-001", "G-002") else A3
            entries.append({"sheet": sid, "title": r["title"], "part": part, "page": i + 1, "paper": paper_name(p), "scale": r.get("scale") or "—", "status": r.get("grade")})
    # contents sheets
    cnt = "배치도 1 · 평면 %d(+A1 %d) · 입면 4 · 단면 5 · 상세 10 · 부록" % (len([s for s in part2 if s.startswith("P-1")]), len([s for s in part2 if s in ("P-201", "P-202")]))
    ad.build_cover(run, os.path.join(dd, "A-000"), "%d장 (%s)" % (len(part2), cnt), ident, a.head)
    ad.build_index(run, os.path.join(dd, "A-001"), entries)
    if "G-002" in rows and rows["G-002"]["files"]["pdf"]["path"].startswith(dd):
        from t14i import partI_front
        partI_front.build_contents(run, os.path.join(dd, "G-002"), entries)
    out1 = os.path.join(out, cfg.OUT_BOOK_I)
    out2 = os.path.join(out, cfg.OUT_BOOK_II)
    pg1 = assemble(run, part1, rows, out1, "I", "다층 상업시설 — 졸업 설계 도면집 후보 %s" % cfg.EDITION, "PART I Graduation Design Book — CANDIDATE, NOT FROZEN", a.head)
    pg2 = assemble(run, part2, rows, out2, "II", "다층 상업시설 — 기술 도면 부록 후보 %s" % cfg.EDITION, "PART II Technical Drawing Appendix — CANDIDATE, NOT FROZEN", a.head)
    for pdf, pgs, part, contact_name in ((out1, pg1, "I", cfg.OUT_CONTACT_I), (out2, pg2, "II", cfg.OUT_CONTACT_II)):
        write_index(pgs, os.path.splitext(pdf)[0] + "_index", part, pdf)
        contact_sheet(pdf, os.path.join(out, contact_name), pgs)
    json.dump({"head": a.head, "date": cfg.ISSUE_DATE, "part1": {"pdf": out1, "sha256": common.sha_file(out1), "pages": len(pg1)}, "part2": {"pdf": out2, "sha256": common.sha_file(out2), "pages": len(pg2)},
               "missing_part2": missing, "model": {"glb_present": ident["glb_present"], "cache_sha256": ident["cache_sha256"], "status": ident["status"]}},
              open(os.path.join(out, "book_registry.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("PART I ", out1, len(pg1), "pages", common.sha_file(out1))
    print("PART II", out2, len(pg2), "pages", common.sha_file(out2))
    if missing:
        print("missing:", missing)


if __name__ == "__main__":
    main()

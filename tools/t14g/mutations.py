"""Deliberate defect injection into a copy of the finished PDF. Each mutation must be caught by the check named in MUTATIONS.

    python -I tools/t14g/mutations.py <pdf> <sheet_index.json> <out_report.json>

A mutation 'passes' when (a) the clean PDF has no finding for that check and (b) the mutated PDF has at least one.
"""
import json
import os
import re
import sys
import tempfile

import pymupdf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from t14g import qa_pdf  # noqa: E402
from t14f import fonts  # noqa: E402

MM = qa_pdf.MM


def _page(doc, rows, sheet):
    return doc[next(r["page"] for r in rows if r["sheet"] == sheet) - 1]


def _font(page, name="mutR"):
    page.insert_font(fontname=name, fontfile=fonts.resolve("regular")[0])
    return name


def _find_line(page, pattern):
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            t = re.sub(r"\s+", "", "".join(sp["text"] for sp in ln["spans"]))
            if re.search(pattern, t):
                sp = ln["spans"][0]
                return pymupdf.Rect(ln["bbox"]), sp
    raise LookupError(pattern)


def _replace_line(page, pattern, new_text):
    rect, sp = _find_line(page, pattern)
    page.add_redact_annot(rect)
    page.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)
    fn = _font(page)
    page.insert_text((rect.x0, sp["origin"][1]), new_text, fontname=fn, fontsize=sp["size"], color=(0.6, 0.4, 0.0))


def m_wrong_callout_scale(doc, rows):
    _replace_line(_page(doc, rows, "P-105"), r"D-410·1:100", "D-410 · 1:50")


def m_callout_unknown_sheet(doc, rows):
    _replace_line(_page(doc, rows, "P-102"), r"D-407·1:100", "D-499 · 1:100")


def _bar_rect(page):
    ch = max(qa_pdf._bars(page), key=lambda c: c[1] - c[0])
    return pymupdf.Rect((ch[0] - 1) * MM, (ch[2] - 0.5) * MM, (ch[1] + 1) * MM, (ch[2] + 2.3) * MM), ch


def m_missing_scale_bar(doc, rows):
    pg = _page(doc, rows, "D-405")
    r, _ = _bar_rect(pg)
    pg.add_redact_annot(r)
    pg.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED, text=pymupdf.PDF_REDACT_TEXT_NONE)


def m_scale_bar_wrong_length(doc, rows):
    pg = _page(doc, rows, "D-405")
    r, ch = _bar_rect(pg)
    pg.add_redact_annot(r)
    pg.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED, text=pymupdf.PDF_REDACT_TEXT_NONE)
    pg.draw_rect(pymupdf.Rect(ch[0] * MM, ch[2] * MM, (ch[0] + 80.0) * MM, (ch[2] + 1.6) * MM), color=(0.07,) * 3, fill=(0.07,) * 3)   # 100 mm bar replaced by 80 mm


def m_clipped_legend(doc, rows):
    pg = _page(doc, rows, "P-101")
    pg.insert_text((406 * MM, 120 * MM), "범례가 용지 밖으로 잘림", fontname=_font(pg), fontsize=6)


def m_text_into_title_block(doc, rows):
    pg = _page(doc, rows, "P-101")
    pg.insert_text((120 * MM, 262.6 * MM), "도면 문자가 제목란을 침범", fontname=_font(pg), fontsize=7)


def m_missing_referenced_sheet(doc, rows):
    doc.delete_page(next(r["page"] for r in rows if r["sheet"] == "D-407") - 1)


def m_duplicate_vector_items(doc, rows):
    pg = _page(doc, rows, "P-101")
    for _ in range(30):
        pg.draw_rect(pymupdf.Rect(150 * MM, 100 * MM, 160 * MM, 104 * MM), color=(0.3, 0.3, 0.3), width=0.3)


def m_wrong_north(doc, rows):
    _replace_line(_page(doc, rows, "P-101"), r"진북63\.2°", "진북 243.2°")


def m_unembedded_font(doc, rows):
    pg = _page(doc, rows, "P-101")
    pg.insert_text((150 * MM, 245 * MM), "ABC non-embedded font", fontname="helv", fontsize=7)


def m_text_overlap(doc, rows):
    pg = _page(doc, rows, "P-101")
    rect, sp = _find_line(pg, r"LEGEND")
    pg.insert_text((rect.x0 + 2, sp["origin"][1] - 1), "겹침 문자 OVERLAP", fontname=_font(pg), fontsize=9)


def m_stale_reference(doc, rows):
    pg = _page(doc, rows, "P-101")
    pg.insert_text((310 * MM, 240 * MM), "층고 정보는 A-002 참조", fontname=_font(pg), fontsize=5.5)


def m_wrong_page_size(doc, rows):
    doc[0].set_mediabox(pymupdf.Rect(0, 0, 595, 842))


def m_wrong_printed_dimension(doc, rows):
    _replace_line(_page(doc, rows, "P-101"), r"^54000$", "54100")


MUTATIONS = [
    ("wrong detail callout scale (D-410 1:50)", m_wrong_callout_scale, "callouts"),
    ("callout to a sheet that does not exist", m_callout_unknown_sheet, "callouts"),
    ("graphic scale bar missing", m_missing_scale_bar, "scale_bars"),
    ("graphic scale bar wrong physical length", m_scale_bar_wrong_length, "scale_bars"),
    ("legend text clipped by the sheet edge", m_clipped_legend, "text_bounds"),
    ("drawing text running into the title block", m_text_into_title_block, "text_bounds"),
    ("referenced sheet removed from the PDF", m_missing_referenced_sheet, "index"),
    ("stacked duplicate vector items", m_duplicate_vector_items, "duplicates"),
    ("wrong north angle printed", m_wrong_north, "north"),
    ("non-embedded font", m_unembedded_font, "fonts"),
    ("overlapping text lines", m_text_overlap, "text_overlap"),
    ("stale cross reference (A-002 for floor heights)", m_stale_reference, "stale_refs"),
    ("wrong page size", m_wrong_page_size, "page_size"),
]


def run(pdf, rows, north_deg=63.2):
    clean = qa_pdf.run_all(pdf, rows, north_deg)
    out = []
    for name, fn, check in MUTATIONS:
        doc = pymupdf.open(pdf)
        try:
            fn(doc, rows)
            res = qa_pdf.run_all(doc, rows if "removed" not in name else rows, north_deg, only={check})
            n = len(res[check])
            err = None
        except Exception as e:                                   # noqa: BLE001 - a mutation that cannot be applied is reported, not hidden
            n, err = 0, "%s: %s" % (type(e).__name__, e)
        out.append({"mutation": name, "expected_check": check, "clean_findings": len(clean[check]), "mutated_findings": n, "detected": bool(n > 0 and len(clean[check]) == 0), "error": err})
    return {"pdf": pdf, "clean_total_findings": sum(len(v) for v in clean.values()), "mutations": out, "detected": sum(1 for m in out if m["detected"]), "total": len(out)}


if __name__ == "__main__":
    rows = json.load(open(sys.argv[2], encoding="utf-8"))["sheets"]
    rep = run(sys.argv[1], rows)
    json.dump(rep, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("mutations detected %d / %d (clean PDF findings: %d)" % (rep["detected"], rep["total"], rep["clean_total_findings"]))
    for m in rep["mutations"]:
        print("  %-52s %-12s %s %s" % (m["mutation"], m["expected_check"], "DETECTED" if m["detected"] else "MISSED", m["error"] or ""))

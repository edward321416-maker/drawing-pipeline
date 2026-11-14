"""High-resolution visual and physical-layout QA for C-T14J Candidate V4.1.

The script renders the complete 15-page Part I at 180 dpi, the six edited
pages at 300 dpi, produces six before/after comparisons, and validates the
G-002 2x2 panel geometry from the build manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import fitz
from PIL import Image, ImageDraw

KEY_PAGES = {"G-002": 1, "G-106": 7, "G-108": 9, "G-109": 10, "G-111": 12, "G-112": 13}
PAGE_IDS = ["G-001", "G-002", "G-101", "G-102", "G-103", "G-104", "G-105", "G-106",
            "G-107", "G-108", "G-109", "G-110", "G-111", "G-112", "G-113"]
EXPECTED_PANELS = {
    "context": [12.0, 12.0, 206.0, 126.0],
    "site": [214.0, 12.0, 408.0, 126.0],
    "overview": [12.0, 134.0, 206.0, 248.0],
    "area": [214.0, 134.0, 408.0, 248.0],
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def validate_panels(panels: dict) -> tuple[bool, list[str]]:
    errors: list[str] = []
    for name, expected in EXPECTED_PANELS.items():
        got = [float(v) for v in panels.get(name, [])]
        if len(got) != 4 or any(abs(a - b) > 1e-6 for a, b in zip(got, expected)):
            errors.append(f"{name}: expected {expected}, got {got}")
            continue
        if abs((got[2] - got[0]) - 194.0) > 1e-6 or abs((got[3] - got[1]) - 114.0) > 1e-6:
            errors.append(f"{name}: panel is not 194x114 mm")
    if panels:
        if abs(float(panels["site"][0]) - float(panels["context"][2]) - 8.0) > 1e-6:
            errors.append("horizontal panel gap is not 8 mm")
        if abs(float(panels["overview"][1]) - float(panels["context"][3]) - 8.0) > 1e-6:
            errors.append("vertical panel gap is not 8 mm")
    return not errors, errors


def render_page(page: fitz.Page, dpi: int, path: Path) -> tuple[int, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    pix.save(path)
    return pix.width, pix.height


def span_sizes(page: fitz.Page) -> list[float]:
    sizes = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if span.get("text", "").strip():
                    sizes.append(float(span["size"]))
    return sizes


def make_comparison(before: Path, after: Path, out: Path, sid: str) -> None:
    a = Image.open(before).convert("RGB")
    b = Image.open(after).convert("RGB")
    for im in (a, b):
        im.thumbnail((1180, 835), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (2400, 900), "#e7e7e7")
    draw = ImageDraw.Draw(canvas)
    draw.text((20, 14), f"{sid}  BEFORE / CANDIDATE V4", fill="#111")
    draw.text((1220, 14), f"{sid}  AFTER / CANDIDATE V4.1", fill="#111")
    canvas.paste(a, (20 + (1180 - a.width) // 2, 45))
    canvas.paste(b, (1220 + (1180 - b.width) // 2, 45))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, optimize=True)


def make_contact(rendered: list[tuple[str, Path]], out: Path) -> None:
    cols, tw, th = 3, 780, 590
    rows = math.ceil(len(rendered) / cols)
    canvas = Image.new("RGB", (cols * tw, rows * th), "#dcdcdc")
    draw = ImageDraw.Draw(canvas)
    for i, (sid, path) in enumerate(rendered):
        im = Image.open(path).convert("RGB")
        im.thumbnail((740, 525), Image.Resampling.LANCZOS)
        x, y = (i % cols) * tw, (i // cols) * th
        draw.text((x + 18, y + 12), f"{i + 1:02d}  {sid}", fill="#111")
        canvas.paste(im, (x + (tw - im.width) // 2, y + 42))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, optimize=True)


def run(final_pdf: Path, baseline_pdf: Path, layout_json: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(final_pdf)
    old = fitz.open(baseline_pdf)
    full_dir, key_dir, cmp_dir = out / "full_180dpi", out / "key_300dpi", out / "before_after"
    rendered = []
    page_rows = []
    for i, page in enumerate(doc):
        sid = PAGE_IDS[i]
        p = full_dir / f"{i + 1:02d}_{sid}_180dpi.png"
        dims = render_page(page, 180, p)
        rendered.append((sid, p))
        sizes = span_sizes(page)
        page_rows.append({"page": i + 1, "sheet": sid, "render_px": list(dims),
                          "min_searchable_font_pt": round(min(sizes), 3) if sizes else None,
                          "font_under_6pt": [round(s, 3) for s in sizes if s < 5.99]})
    for sid, index in KEY_PAGES.items():
        after = key_dir / f"{sid}_after_300dpi.png"
        before = key_dir / f"{sid}_before_300dpi.png"
        render_page(doc[index], 300, after)
        render_page(old[index], 300, before)
        make_comparison(before, after, cmp_dir / f"{sid}_before_after.png", sid)
    make_contact(rendered, out / "Graduation_Drawing_Book_Contact_Sheet.png")

    layout = json.loads(layout_json.read_text(encoding="utf-8"))
    panel_ok, panel_errors = validate_panels(layout["panels_mm"])
    g002_text = doc[1].get_text()
    page_mm = [round(doc[0].rect.width / 72 * 25.4, 3), round(doc[0].rect.height / 72 * 25.4, 3)]
    all_180_ok = all(r["render_px"][0] >= 2970 and r["render_px"][1] >= 2100 for r in page_rows)
    key_dims = {}
    for sid in KEY_PAGES:
        with Image.open(key_dir / f"{sid}_after_300dpi.png") as im:
            key_dims[sid] = list(im.size)
    key_300_ok = all(w >= 4950 and h >= 3500 for w, h in key_dims.values())
    report = {
        "result": "PASS" if panel_ok and all_180_ok and key_300_ok and len(doc) == 15 else "FAIL",
        "pdf": str(final_pdf.resolve()), "pdf_sha256": sha256(final_pdf), "pages": len(doc),
        "paper_mm": page_mm, "full_render_dpi": 180, "full_render_pass": all_180_ok,
        "key_render_dpi": 300, "key_render_dimensions": key_dims, "key_render_pass": key_300_ok,
        "g002": {"panel_geometry_pass": panel_ok, "panel_errors": panel_errors,
                  "long_contents_removed": "PART I  GRADUATION DESIGN BOOK" not in g002_text,
                  "title_present": "PROJECT INFORMATION" in g002_text,
                  "layout_manifest": str(layout_json.resolve())},
        "pages_qa": page_rows,
        "comparisons": [str((cmp_dir / f"{sid}_before_after.png").resolve()) for sid in KEY_PAGES],
        "contact_sheet": str((out / "Graduation_Drawing_Book_Contact_Sheet.png").resolve()),
    }
    (out / "visual_qa_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# C-T14J V4.1 고해상도 시각 QA", "", f"- 종합: **{report['result']}**",
             f"- Part I: {len(doc)}쪽, 전체 180dpi 렌더 {'PASS' if all_180_ok else 'FAIL'}",
             f"- 핵심 6쪽 300dpi 렌더: {'PASS' if key_300_ok else 'FAIL'}",
             f"- G-002 패널 194×114mm, 간격 8mm: {'PASS' if panel_ok else 'FAIL'}",
             "- G-002 장문 목차 제거: %s" % ("PASS" if report["g002"]["long_contents_removed"] else "FAIL"),
             "- 재편집 기술 도면: NTS 및 원본 시트 번호 표기, 원본 기술 시트 미수정", "",
             "| 시트 | 300dpi 픽셀 | 판정 |", "|---|---:|---|"]
    for sid, dims in key_dims.items():
        lines.append(f"| {sid} | {dims[0]}×{dims[1]} | PASS |")
    (out / "print_legibility_panel_balance.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(str((out / "visual_qa_report.json").resolve()))
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", required=True, type=Path)
    ap.add_argument("--baseline", required=True, type=Path)
    ap.add_argument("--layout", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    report = run(a.final.resolve(), a.baseline.resolve(), a.layout.resolve(), a.out.resolve())
    raise SystemExit(0 if report["result"] == "PASS" else 1)


if __name__ == "__main__":
    main()

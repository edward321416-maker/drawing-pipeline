from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _font(size: int, bold: bool = False):
    path = Path(r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf")
    return ImageFont.truetype(str(path), size) if path.exists() else ImageFont.load_default()


def qa(pdf: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    document = fitz.open(pdf)
    pages = []
    thumbs = []
    for index, page in enumerate(document):
        dpi = 160
        pixmap = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), alpha=False)
        render = output / f"page_{index + 1:02d}_{dpi}dpi.png"
        pixmap.save(render)
        image = Image.open(render).convert("RGB")
        thumb = image.copy()
        thumb.thumbnail((720, 510), Image.Resampling.LANCZOS)
        thumbs.append((index + 1, thumb))
        highres = None
        if index in (1, 2):
            high_dpi = 300
            high_pixmap = page.get_pixmap(matrix=fitz.Matrix(high_dpi / 72, high_dpi / 72), alpha=False)
            highres = output / f"page_{index + 1:02d}_{high_dpi}dpi.png"
            high_pixmap.save(highres)
        pages.append({
            "page": index + 1,
            "width_pt": page.rect.width,
            "height_pt": page.rect.height,
            "text_chars": len(page.get_text()),
            "render": str(render.resolve()),
            "highres_300dpi": str(highres.resolve()) if highres else None,
        })

    sheet = Image.new("RGB", (1520, 1120), (226, 227, 229))
    draw = ImageDraw.Draw(sheet)
    draw.text((40, 25), "C-T14N G-002 A/B REVIEW — CONTACT SHEET", font=_font(32, True), fill=(25, 27, 30))
    for idx, (number, thumb) in enumerate(thumbs):
        x = 40 + (idx % 2) * 740
        y = 90 + (idx // 2) * 510
        sheet.paste(thumb, (x, y + 35))
        draw.text((x, y), f"PAGE {number:02d}", font=_font(20, True), fill=(50, 53, 57))
    contact = output / "C_T14N_G002_Hero_Render_AB_Review_Contact_Sheet.png"
    sheet.save(contact, format="PNG", optimize=True)

    report = {
        "pdf": str(pdf.resolve()),
        "pdf_sha256": _sha256(pdf),
        "page_count": document.page_count,
        "expected_page_size_mm": [420, 297],
        "page_size_pass": all(abs(item["width_pt"] - 420 / 25.4 * 72) < 0.5 and abs(item["height_pt"] - 297 / 25.4 * 72) < 0.5 for item in pages),
        "pages": pages,
        "contact_sheet": str(contact.resolve()),
        "visual_status": "VISUAL_QUALITY_NOT_APPROVED",
    }
    (output / "C_T14N_G002_Hero_Render_AB_Review_PDF_QA.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    document.close()
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(qa(args.pdf.resolve(), args.output.resolve()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

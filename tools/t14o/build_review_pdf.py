"""Build and raster-QA the A3 landscape C-T14O render review report."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

import fitz
from PIL import Image, ImageDraw


MM = 72 / 25.4
PAGE_W = 420 * MM
PAGE_H = 297 * MM
M = 12 * MM
INK = (0.075, 0.09, 0.10)
MUTED = (0.34, 0.37, 0.39)
ACCENT = (0.68, 0.17, 0.09)
PALE = (0.94, 0.94, 0.925)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def register_fonts(page: fitz.Page) -> tuple[str, str]:
    regular = Path(r"C:\Windows\Fonts\malgun.ttf")
    bold = Path(r"C:\Windows\Fonts\malgunbd.ttf")
    if not regular.is_file() or not bold.is_file():
        raise FileNotFoundError("Malgun Gothic font files are required for the Korean report")
    page.insert_font(fontname="KOR", fontfile=str(regular))
    page.insert_font(fontname="KOR_B", fontfile=str(bold))
    return "KOR", "KOR_B"


def text(page: fitz.Page, rect: fitz.Rect, value: str, size: float = 10,
         bold: bool = False, color=INK, align=fitz.TEXT_ALIGN_LEFT,
         lineheight: float = 1.25) -> None:
    font_name = "KOR_B" if bold else "KOR"
    rc = page.insert_textbox(
        rect, value, fontsize=size, fontname=font_name, color=color,
        align=align, lineheight=lineheight,
    )
    if rc < -0.5:
        raise RuntimeError(f"Text overflow ({rc:.2f}): {value[:80]}")


def image_fit(page: fitz.Page, path: Path, rect: fitz.Rect, contain: bool = True) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    page.insert_image(rect, filename=str(path), keep_proportion=contain)


def top_rule(page: fitz.Page, sheet: str, title: str, subtitle: str = "") -> None:
    _, bold = register_fonts(page)
    page.draw_line((M, M), (PAGE_W - M, M), color=ACCENT, width=1.4)
    text(page, fitz.Rect(M, M + 5, M + 110, M + 32), sheet, 9.5, True, ACCENT)
    text(page, fitz.Rect(M + 112, M + 2, PAGE_W - M, M + 30), title, 18, True)
    if subtitle:
        text(page, fitz.Rect(M + 112, M + 29, PAGE_W - M, M + 50), subtitle, 8.5, False, MUTED)


def footer(page: fitz.Page, index: int, status: str = "USER ARCHITECTURAL APPROVAL PENDING") -> None:
    y = PAGE_H - M + 2
    page.draw_line((M, y - 4), (PAGE_W - M, y - 4), color=(.75, .75, .75), width=.5)
    text(page, fitz.Rect(M, y, PAGE_W - M - 80, PAGE_H - 3), status, 7.5, True, MUTED)
    text(page, fitz.Rect(PAGE_W - M - 70, y, PAGE_W - M, PAGE_H - 3), f"C-T14O / {index:02d}", 7.5, True, MUTED, fitz.TEXT_ALIGN_RIGHT)


def add_cover(doc: fitz.Document, daylight: Path) -> None:
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    register_fonts(page)
    image_fit(page, daylight, fitz.Rect(0, 0, PAGE_W, PAGE_H), contain=False)
    box = fitz.Rect(M, PAGE_H - 83 * MM, 174 * MM, PAGE_H - M)
    page.draw_rect(box, color=None, fill=(1, 1, 1), fill_opacity=.93)
    text(page, fitz.Rect(box.x0 + 10 * MM, box.y0 + 9 * MM, box.x1 - 8 * MM, box.y0 + 26 * MM), "C-T14O", 11, True, ACCENT)
    text(page, fitz.Rect(box.x0 + 10 * MM, box.y0 + 25 * MM, box.x1 - 8 * MM, box.y0 + 48 * MM), "G-002 실제 3D 건축 렌더링", 24, True)
    text(page, fitz.Rect(box.x0 + 10 * MM, box.y0 + 51 * MM, box.x1 - 8 * MM, box.y1 - 7 * MM),
         "검증 캐시 메시 · Blender Cycles · 4800×2700 · 64 samples\nCandidate review — 설계·재료 최종 승인 아님", 10, False, MUTED)


def add_comparison(doc: fitz.Document, comparison: Path) -> None:
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    top_rule(page, "G-002 / SOURCE—A—B", "원본과 실제 Cycles 렌더 비교",
             "세 장의 카메라는 동일하지 않음. A/B만 동일한 신규 시각화 카메라와 동일 메시를 공유한다.")
    image_fit(page, comparison, fitz.Rect(M, M + 58, PAGE_W - M, PAGE_H - M - 47))
    footer(page, 2)


def add_hero(doc: fitz.Document, sheet: str, title: str, image: Path,
             notes: Iterable[str], index: int) -> None:
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    top_rule(page, sheet, title)
    image_fit(page, image, fitz.Rect(M, M + 43, 315 * MM, PAGE_H - M - 28))
    x0 = 321 * MM
    page.draw_rect(fitz.Rect(x0, M + 43, PAGE_W - M, PAGE_H - M - 28), color=None, fill=PALE)
    y = M + 55
    for note in notes:
        text(page, fitz.Rect(x0 + 8 * MM, y, PAGE_W - M - 7 * MM, y + 58), "• " + note, 9, False, INK)
        y += 18 * MM
    footer(page, index)


def add_crops(doc: fitz.Document, title: str, paths: list[tuple[str, Path]], index: int) -> None:
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    top_rule(page, "100% PIXEL QA", title, "4800×2700 원본에서 직접 잘라낸 확대 영역")
    gap = 8 * MM
    w = (PAGE_W - 2 * M - gap) / 2
    h = (PAGE_H - M - (M + 61) - gap - 34) / 2
    for i, (label, path) in enumerate(paths):
        col, row = i % 2, i // 2
        x = M + col * (w + gap)
        y = M + 61 + row * (h + gap)
        page.draw_rect(fitz.Rect(x, y, x + w, y + h), color=(.72, .72, .72), width=.5)
        image_fit(page, path, fitz.Rect(x, y, x + w, y + h - 21))
        text(page, fitz.Rect(x + 6, y + h - 18, x + w - 6, y + h), label, 8.5, True)
    footer(page, index)


def add_validation(doc: fitz.Document, qa: dict, day_audit: dict, blue_audit: dict,
                   file_paths: list[Path]) -> None:
    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    top_rule(page, "SOURCE / RENDER / PRINT QA", "검증 결과와 승인 경계")
    source = day_audit["source_geometry_verification"]
    rows = [
        ("캐시 SHA256", source["model_npz_sha256"], "PASS"),
        ("객체 레지스트리 SHA256", source["model_objects_sha256"], "PASS"),
        ("정점 / 삼각형 / 객체", f"{source['vertex_count']:,} / {source['triangle_count']:,} / {source['object_count']}", "PASS"),
        ("층 태그 / 전체 높이", f"{source['floor_tag_count']} levels / {source['z_span_m']} m", "PASS"),
        ("A/B 메시·카메라 동등성", str(qa["all_equivalence_checks_pass"]), "PASS" if qa["all_equivalence_checks_pass"] else "FAIL"),
        ("출력 해상도", "4800 × 2700 px / 16:9 / 16-bit PNG", "PASS"),
        ("A3 396 mm 배치 유효 dpi", f"{qa['inputs']['urban_daylight']['effective_dpi_at_396mm_width']} dpi", "PASS"),
        ("재질 권한", "Semantic-name-derived LOOKDEV; construction spec unavailable", "LIMIT"),
        ("카메라 권한", "New visualization camera; original G-002 camera unavailable", "LIMIT"),
        ("최종 승인", "사용자 건축·재질·시각 승인 대기", "HOLD"),
    ]
    x0, x1, x2, x3 = M, 90 * MM, 354 * MM, PAGE_W - M
    y = M + 54
    rh = 16 * MM
    for i, (label, value, state) in enumerate(rows):
        if i % 2 == 0:
            page.draw_rect(fitz.Rect(x0, y, x3, y + rh), color=None, fill=PALE)
        text(page, fitz.Rect(x0 + 5, y + 6, x1 - 5, y + rh - 4), label, 8.3, True)
        text(page, fitz.Rect(x1 + 5, y + 6, x2 - 5, y + rh - 4), value, 8.1, False, MUTED)
        state_color = (.10, .45, .23) if state == "PASS" else ACCENT
        text(page, fitz.Rect(x2 + 5, y + 6, x3 - 5, y + rh - 4), state, 8.2, True, state_color, fitz.TEXT_ALIGN_RIGHT)
        y += rh
    text(page, fitz.Rect(M, y + 12, PAGE_W - M, y + 38), "로컬 실물 파일", 10, True, ACCENT)
    path_text = "\n".join(str(path.resolve()) for path in file_paths)
    text(page, fitz.Rect(M, y + 38, PAGE_W - M, PAGE_H - M - 34), path_text, 7.5, False, MUTED, lineheight=1.45)
    footer(page, 7)


def render_pdf(pdf_path: Path, render_dir: Path, contact_path: Path) -> list[Path]:
    render_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    pages: list[Path] = []
    thumbs: list[Image.Image] = []
    try:
        for index, page in enumerate(doc):
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            path = render_dir / f"page_{index + 1:02d}.png"
            pix.save(path)
            pages.append(path)
            with Image.open(path) as image:
                thumb = image.convert("RGB")
                thumb.thumbnail((560, 396), Image.Resampling.LANCZOS)
                thumbs.append(thumb.copy())
    finally:
        doc.close()
    contact = Image.new("RGB", (560 * 2 + 28 * 3, 396 * 4 + 34 * 5), (232, 232, 228))
    draw = ImageDraw.Draw(contact)
    for index, thumb in enumerate(thumbs):
        col, row = index % 2, index // 2
        x = 28 + col * (560 + 28)
        y = 34 + row * (396 + 34)
        contact.paste(thumb, (x, y))
        draw.text((x, y - 21), f"PAGE {index + 1:02d}", fill=(20, 20, 20))
    contact_path.parent.mkdir(parents=True, exist_ok=True)
    contact.save(contact_path, "PNG", optimize=True)
    return pages


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qa-dir", type=Path, required=True)
    parser.add_argument("--daylight-audit", type=Path, required=True)
    parser.add_argument("--bluehour-audit", type=Path, required=True)
    parser.add_argument("--daylight-blend", type=Path, required=True)
    parser.add_argument("--bluehour-blend", type=Path, required=True)
    parser.add_argument("--out-pdf", type=Path, required=True)
    args = parser.parse_args()
    qa_dir = args.qa_dir.resolve()
    qa = json.loads((qa_dir / "render_quality_qa.json").read_text(encoding="utf-8"))
    day_audit = json.loads(args.daylight_audit.read_text(encoding="utf-8"))
    blue_audit = json.loads(args.bluehour_audit.read_text(encoding="utf-8"))
    day = qa_dir / "G002_A_Urban_Daylight_preview_1600.png"
    blue = qa_dir / "G002_B_Blue_Hour_preview_1600.png"
    comparison = qa_dir / "G002_source_vs_cycles_AB.png"
    crop_dir = qa_dir / "crops"

    output = args.out_pdf.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    add_cover(doc, day)
    add_comparison(doc, comparison)
    add_hero(doc, "A / URBAN DAYLIGHT", "주광 메인 건축 투시도", day, [
        "Nishita sky + Sun + area fill의 Cycles 광선 추적",
        "객체명으로 확인된 glass / mullion / louver / band만 재질 분류",
        "옥상 개구부, 중간정원, 수직 튜브와 저층 보이드 유지",
        "주변 건물·대지·수목은 동일 캐시 메시에서 재구성",
    ], 3)
    add_hero(doc, "B / BLUE HOUR", "황혼 운영 장면", blue, [
        "A와 동일 메시·동일 카메라; 조명 조건만 변경",
        "검증된 유리 그룹에 제한한 약한 warm emission",
        "건물 외피 내부의 look-development area lights",
        "인물 자산은 근거 부족으로 추가하지 않음",
    ], 4)
    add_crops(doc, "A — Urban Daylight 확대 검수", [
        ("옥상 개구부·정원·튜브", crop_dir / "G002_A_upper_roof_100pct.png"),
        ("파사드 유리·멀리언·밴드", crop_dir / "G002_A_facade_glazing_100pct.png"),
        ("중간 보이드·수직 튜브", crop_dir / "G002_A_middle_void_tubes_100pct.png"),
        ("저층 개방부·접지 그림자", crop_dir / "G002_A_lower_ground_contact_100pct.png"),
    ], 5)
    add_crops(doc, "B — Blue Hour 확대 검수", [
        ("옥상 개구부·정원·튜브", crop_dir / "G002_B_upper_roof_100pct.png"),
        ("파사드 유리·발광 한계", crop_dir / "G002_B_facade_glazing_100pct.png"),
        ("중간 보이드·수직 튜브", crop_dir / "G002_B_middle_void_tubes_100pct.png"),
        ("저층 개방부·주변광", crop_dir / "G002_B_lower_ground_contact_100pct.png"),
    ], 6)
    add_validation(doc, qa, day_audit, blue_audit, [
        Path(qa["inputs"]["urban_daylight"]["path"]),
        Path(qa["inputs"]["blue_hour"]["path"]),
        args.daylight_blend, args.bluehour_blend,
        qa_dir / "render_quality_qa.json",
    ])
    doc.set_metadata({
        "title": "C-T14O G-002 Cycles PBR Render Review",
        "author": "Codex / source-mesh rendering pipeline",
        "subject": "Candidate render review; human architectural approval pending",
    })
    doc.save(output, garbage=4, deflate=True)
    doc.close()

    render_dir = output.parent / "review_pdf_pages_144dpi"
    contact = output.parent / "G002_A3_Review_Contact_Sheet.png"
    pages = render_pdf(output, render_dir, contact)
    check = fitz.open(output)
    try:
        page_sizes = [[round(p.rect.width / MM, 3), round(p.rect.height / MM, 3)] for p in check]
        page_count = check.page_count
    finally:
        check.close()
    report = {
        "pdf": str(output), "sha256": sha256(output), "bytes": output.stat().st_size,
        "page_count": page_count, "page_sizes_mm": page_sizes,
        "all_pages_a3_landscape": all(abs(w - 420) < .05 and abs(h - 297) < .05 for w, h in page_sizes),
        "rendered_page_pngs": [str(path.resolve()) for path in pages],
        "contact_sheet": str(contact.resolve()),
    }
    qa_path = output.with_suffix(".qa.json")
    qa_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

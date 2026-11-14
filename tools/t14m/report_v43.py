"""Build the C-T14M asset inventory and an honest blocked-state PDF report.

The report is deliberately not named Candidate V4.3.  It documents actual
retouch downloads and automated checks while the independent architectural
review gate remains open.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont


PART_I_ORDER = ["G-001", "G-002", "G-003"] + [f"G-{number}" for number in range(101, 114)]
PART_II_ORDER = [
    "A-000", "A-001", "A-002", "A-003",
    "P-101", "P-102", "P-103", "P-104", "P-105", "P-106", "P-107", "P-108",
    "P-109", "P-110", "P-111", "P-112", "A-901", "A-902", "A-903", "A-904",
    "P-201", "P-202", "P-211", "P-212", "P-213", "P-214", "A-905",
    "E-201", "E-202", "E-203", "E-204", "S-301", "S-302", "S-303", "S-304",
    "S-305", "D-401", "D-402", "D-403", "D-404", "D-405", "D-406", "D-407",
    "D-408", "D-409", "D-410", "A-906", "A-907", "A-900",
]
PILOTS = {"G-002", "G-103", "G-106", "G-111"}
DOCUMENT_EXEMPT = {"G-001", "A-000", "A-001", "A-900"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _gate_status(root: Path, sheet: str) -> tuple[str, list[str]]:
    stem = sheet.replace("-", "")
    path = root / "retouch" / sheet / "qa" / f"{stem}_gate_audit.json"
    if not path.is_file():
        return "AWAITING_EXTERNAL_AI_RETOUCH", []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("status", "REJECTED_NOT_FOR_BOOK"), list(data.get("errors", []))


def build_inventory(root: Path, part_i_pdf: Path, part_ii_pdf: Path) -> dict:
    rows: list[dict] = []
    for part, path, order in (("I", part_i_pdf, PART_I_ORDER), ("II", part_ii_pdf, PART_II_ORDER)):
        document = fitz.open(path)
        if len(document) != len(order):
            raise ValueError(f"{path}: expected {len(order)} pages, got {len(document)}")
        for index, (page, sheet) in enumerate(zip(document, order), start=1):
            image_count = len(page.get_images(full=True))
            drawing_count = len(page.get_drawings())
            if sheet in DOCUMENT_EXEMPT:
                status, route = "EXEMPT_TEXT_OR_DOCUMENT_PAGE", "NO_AI_IMAGE_EDIT"
                errors: list[str] = []
            elif sheet in PILOTS:
                status, errors = _gate_status(root, sheet)
                route = "LOW_FREQUENCY_AI_GRADE_WITH_SOURCE_LOCK"
                if sheet in {"G-106", "G-111"}:
                    route += "+AUTHORITATIVE_VECTOR_RECOMPOSITE"
            else:
                status, errors = "AWAITING_EXTERNAL_AI_RETOUCH", []
                route = ("AUTHORITATIVE_VECTOR_RECOMPOSITE_REQUIRED" if part == "II"
                         else "SOURCE_PACKET_AND_INDEPENDENT_REVIEW_REQUIRED")
            rows.append({
                "part": part, "page": index, "sheet": sheet,
                "embedded_images": image_count, "vector_drawing_groups": drawing_count,
                "retouch_required": sheet not in DOCUMENT_EXEMPT,
                "source_authority": ("ORIGINAL_SVG_PDF_VECTOR" if part == "II" or sheet in {"G-106", "G-111"}
                                     else "VERIFIED_V4_2_PAGE_OR_RENDER"),
                "processing_route": route, "status": status, "gate_errors": errors,
            })
        document.close()
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    inventory = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_v43_issued": False,
        "blocking_reason": "No retouched pilot has completed independent architectural review.",
        "part_i_source": str(part_i_pdf.resolve()), "part_i_sha256": sha256(part_i_pdf),
        "part_ii_source": str(part_ii_pdf.resolve()), "part_ii_sha256": sha256(part_ii_pdf),
        "summary": {"total_pages": len(rows), "status_counts": counts}, "assets": rows,
    }
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "asset_inventory.json"
    json_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    md = [
        "# C-T14M 전체 페이지 그래픽 인벤토리", "",
        "- Candidate V4.3 발행: **아니오**", "- 사유: 독립 건축 정확성 검토 미완료", "",
        "| Part | Page | Sheet | Images | Vectors | Route | Status |",
        "|---|---:|---|---:|---:|---|---|",
    ]
    for row in rows:
        md.append(f"| {row['part']} | {row['page']} | {row['sheet']} | {row['embedded_images']} | "
                  f"{row['vector_drawing_groups']} | {row['processing_route']} | {row['status']} |")
    md_path = root / "asset_inventory.md"
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    return inventory


def _font_file(bold: bool = False) -> str:
    candidates = ([Path("C:/Windows/Fonts/malgunbd.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")]
                  if bold else [Path("C:/Windows/Fonts/malgun.ttf"), Path("C:/Windows/Fonts/arial.ttf")])
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise FileNotFoundError("No Korean-capable system font found")


def _register(page: fitz.Page) -> None:
    page.insert_font(fontname="BodyKR", fontfile=_font_file(False))
    page.insert_font(fontname="BoldKR", fontfile=_font_file(True))


def _text(page: fitz.Page, rect: fitz.Rect, value: str, size: float = 10,
          bold: bool = False, color: tuple[float, float, float] = (0.12, 0.12, 0.12),
          align: int = fitz.TEXT_ALIGN_LEFT) -> None:
    spare = page.insert_textbox(rect, value, fontsize=size, fontname="BoldKR" if bold else "BodyKR",
                                color=color, align=align, lineheight=1.25)
    if spare < -0.1:
        raise ValueError(f"text overflow by {-spare:.2f} pt: {value[:80]!r}")


def _new_page(doc: fitz.Document, section: str, title: str, page_no: int) -> fitz.Page:
    page = doc.new_page(width=420 / 25.4 * 72, height=297 / 25.4 * 72)
    _register(page)
    page.draw_rect(page.rect, fill=(1, 1, 1), color=None)
    _text(page, fitz.Rect(34, 28, 260, 48), section, 8, True, (0.1, 0.45, 0.31))
    _text(page, fitz.Rect(34, 48, 1110, 83), title, 23, True)
    page.draw_line(fitz.Point(34, 91), fitz.Point(page.rect.width - 34, 91), color=(0.78, 0.8, 0.8), width=0.7)
    _text(page, fitz.Rect(page.rect.width - 120, 28, page.rect.width - 34, 48), f"C-T14M · {page_no:02d}", 8, True,
          (0.35, 0.35, 0.35), fitz.TEXT_ALIGN_RIGHT)
    return page


def _image_rect(path: Path, box: fitz.Rect) -> fitz.Rect:
    with Image.open(path) as image:
        ratio = image.width / image.height
    box_ratio = box.width / box.height
    if ratio > box_ratio:
        height = box.width / ratio
        y0 = box.y0 + (box.height - height) / 2
        return fitz.Rect(box.x0, y0, box.x1, y0 + height)
    width = box.height * ratio
    x0 = box.x0 + (box.width - width) / 2
    return fitz.Rect(x0, box.y0, x0 + width, box.y1)


def _place_image(page: fitz.Page, path: Path, box: fitz.Rect, label: str | None = None) -> None:
    page.draw_rect(box, color=(0.82, 0.83, 0.84), width=0.5)
    page.insert_image(_image_rect(path, box), filename=str(path))
    if label:
        _text(page, fitz.Rect(box.x0, box.y1 + 5, box.x1, box.y1 + 24), label, 7.5, True,
              (0.35, 0.35, 0.35))


def _panel(page: fitz.Page, box: fitz.Rect, heading: str, lines: list[str], accent=(0.1, 0.45, 0.31)) -> None:
    page.draw_rect(box, color=(0.8, 0.82, 0.83), fill=(0.985, 0.985, 0.985), width=0.6)
    page.draw_rect(fitz.Rect(box.x0, box.y0, box.x0 + 6, box.y1), color=None, fill=accent)
    _text(page, fitz.Rect(box.x0 + 18, box.y0 + 14, box.x1 - 14, box.y0 + 40), heading, 11, True)
    _text(page, fitz.Rect(box.x0 + 18, box.y0 + 44, box.x1 - 14, box.y1 - 12), "\n".join(lines), 8.4)


def build_report(root: Path, inventory: dict, output: Path) -> None:
    doc = fitz.open()
    green = (0.1, 0.45, 0.31)
    red = (0.72, 0.14, 0.12)
    page_no = 1

    page = _new_page(doc, "EXECUTION REPORT", "V4.3 AI 리터치 · 정확성 검증 통합 실행", page_no)
    _text(page, fitz.Rect(58, 155, 820, 230), "건축적 사실을 보존한 표현 개선", 30, True)
    _text(page, fitz.Rect(58, 237, 820, 292), "실제 ChatGPT 편집 PNG 4건 인수 · 구조 잠금 합성 · 벡터 재합성", 14)
    page.draw_rect(fitz.Rect(58, 335, 1130, 470), color=red, fill=(1, 0.965, 0.955), width=1.2)
    _text(page, fitz.Rect(82, 360, 1105, 402), "Candidate V4.3 미발행", 25, True, red)
    _text(page, fitz.Rect(82, 410, 1105, 452),
          "자동 검사는 통과했으나 독립 건축 정확성 검토가 미완료이므로 도면집 반영을 차단했다.", 12)
    _panel(page, fitz.Rect(58, 520, 555, 720), "완료", [
        "G-002 / G-103 / G-106 / G-111 실제 편집 결과 다운로드",
        "원본 해시·크기·PNG 디코딩·구조 픽셀 잠금 검사",
        "G-106·G-111 원본 SVG/PDF 보존 및 벡터 최상위 재합성",
        "Part I 16쪽 + Part II 49쪽 그래픽 전수 목록화",
    ], green)
    _panel(page, fitz.Rect(575, 520, 1130, 720), "차단", [
        "층수·코어·튜브·보이드·치수의 독립 사람 검토",
        "검토 완료 전 Candidate V4.3 PDF 생성 금지",
        "잔여 61개 비면제 페이지의 이미지별 리터치·검수",
        "완료 상태를 설계 또는 구조 승인으로 오인하지 않음",
    ], red)

    page_no += 1
    page = _new_page(doc, "PROVENANCE", "기준 원본 · 변경 권한 · 인수 기록", page_no)
    _panel(page, fitz.Rect(34, 112, 570, 305), "G-002 원본", [
        "2400×1350 px · 16:9 · V4.2 배치 396 mm에서 약 154 dpi",
        "SHA256 9acd9ab3f5848f51ac1f2cc678ae988bf4f17197f238a5905eac9d8460e75a75",
        "동일 카메라의 전체 타워 Blender 원본을 찾지 못해 고해상도 재렌더 차단",
        "안전 합성본은 200 mm 배치 기준 약 305 dpi로만 평가",
    ])
    _panel(page, fitz.Rect(590, 112, 1156, 305), "AI 권한 제한", [
        "조명·색상·명암·비구조 배경·저주파 톤만 허용",
        "층수·외피 리듬·코어·튜브·슬래브·보이드·카메라 변경 금지",
        "기술도면 선·치수·라벨·스케일바는 원본 벡터가 정본",
        "생성형 출력의 공간 픽셀은 최종 합성에 직접 사용하지 않음",
    ], red)
    _panel(page, fitz.Rect(34, 330, 1156, 660), "안전 합성 방식", [
        "1. 실제 원본과 정확성 제한 프롬프트를 ChatGPT 이미지 편집에 전달",
        "2. 반환 PNG는 크기·비율이 달라도 증빙 원본으로 별도 보존",
        "3. 반환 PNG에서 48–64 px 가우시안 저주파 색상장만 추출",
        "4. 색상장을 원본 픽셀에 제한적으로 적용하고 구조 에지 잠금 픽셀은 원본으로 완전 복원",
        "5. 평면도·상세도는 원본 SVG/PDF에서 만든 투명 벡터 오버레이를 최상위에 재합성",
        "6. 잠금 픽셀 변화 0건과 최종 벡터 재합성 해시를 자동 검사",
        "7. 자동 검사는 건축적 승인으로 간주하지 않고 독립 리뷰를 필수 게이트로 유지",
    ])

    pilots = ["G-002", "G-103", "G-106", "G-111"]
    titles = {"G-002": "외관 렌더", "G-103": "매스 형성 다이어그램",
              "G-106": "대표층 평면도", "G-111": "대표 상세도"}
    for sheet in pilots:
        page_no += 1
        page = _new_page(doc, "PILOT RESULT", f"{sheet} · {titles[sheet]}", page_no)
        stem = sheet.replace("-", "")
        packet = root / "retouch" / sheet
        comparison = packet / "qa" / f"{stem}_before_after.png"
        audit = json.loads((packet / "qa" / f"{stem}_gate_audit.json").read_text(encoding="utf-8"))
        accuracy = json.loads((packet / "qa" / f"{stem}_automated_accuracy.json").read_text(encoding="utf-8"))
        _place_image(page, comparison, fitz.Rect(34, 112, 1156, 650), "원본 / 안전 합성본 — 동일 프레임 비교")
        status_color = red if audit["status"] != "APPROVED_FOR_PRINT_NOT_DESIGN_APPROVED" else green
        _panel(page, fitz.Rect(34, 684, 780, 812), "자동 정확성 검사", [
            f"원본 {accuracy['source_pixels'][0]}×{accuracy['source_pixels'][1]} px · 반환 {accuracy['raw_ai_pixels'][0]}×{accuracy['raw_ai_pixels'][1]} px",
            f"잠금 픽셀 {accuracy['locked_pixel_count']:,}개 · 변경 {accuracy['locked_changed_pixel_count']}개",
            f"생성형 공간 픽셀 직접 사용: {accuracy['spatial_ai_pixels_used_in_final']}",
        ])
        _panel(page, fitz.Rect(800, 684, 1156, 812), "게이트", [audit["status"],
            "독립 검토 미완료", "도면집 반영 금지"], status_color)

    page_no += 1
    page = _new_page(doc, "COVERAGE", "65쪽 전체 그래픽 인벤토리", page_no)
    counts = inventory["summary"]["status_counts"]
    _panel(page, fitz.Rect(34, 112, 570, 294), "범위", [
        "Part I 16쪽", "Part II 49쪽", "합계 65쪽", "원본 V4.2 PDF 해시 고정",
    ])
    _panel(page, fitz.Rect(590, 112, 1156, 294), "현재 상태", [
        f"문서/텍스트 면제: {counts.get('EXEMPT_TEXT_OR_DOCUMENT_PAGE', 0)}쪽",
        f"실제 편집 후 독립 검토 대기: {counts.get('REJECTED_NOT_FOR_BOOK', 0)}쪽",
        f"외부 리터치 대기: {counts.get('AWAITING_EXTERNAL_AI_RETOUCH', 0)}쪽",
        "승인된 V4.3 반영 페이지: 0쪽",
    ], red)
    y = 330
    _text(page, fitz.Rect(34, y, 1156, y + 30), "시범 4개 페이지의 게이트 결과", 13, True)
    y += 42
    for sheet in pilots:
        status, errors = _gate_status(root, sheet)
        page.draw_rect(fitz.Rect(34, y, 1156, y + 66), color=(0.83, 0.84, 0.85), width=0.5)
        _text(page, fitz.Rect(50, y + 13, 150, y + 45), sheet, 10, True)
        _text(page, fitz.Rect(160, y + 13, 500, y + 45), status, 9, True, red)
        _text(page, fitz.Rect(510, y + 11, 1140, y + 55), "; ".join(errors[:3]), 7.4)
        y += 76
    _text(page, fitz.Rect(34, 700, 1156, 786),
          "Part II는 AI 이미지로 다시 그리지 않는다. 각 기술도면의 SVG/PDF 벡터가 최상위 정본이며, "
          "향후 승인된 배경 톤 레이어가 생기더라도 선·치수·텍스트·스케일바는 벡터로 재합성한다.", 10)

    page_no += 1
    page = _new_page(doc, "TEST & HANDOFF", "검증 결과 · V4.3 발행 재개 조건", page_no)
    tests_path = root / "tests_report.json"
    tests_data = json.loads(tests_path.read_text(encoding="utf-8")) if tests_path.is_file() else {}
    tests = tests_data.get("full_suite", tests_data)
    _panel(page, fitz.Rect(34, 112, 570, 340), "자동 테스트", [
        f"합계: {tests.get('total', 'PENDING')}", f"통과: {tests.get('passed', 'PENDING')}",
        f"실패: {tests.get('failed', 'PENDING')}", f"소요: {tests.get('duration_seconds', 'PENDING')}초",
        "합성 테스트 통과는 실제 건축 정확성 승인을 의미하지 않음",
    ])
    _panel(page, fitz.Rect(590, 112, 1156, 340), "V4.3 발행 재개 조건", [
        "G-002: 카메라·실루엣·층수·코어·튜브·보이드·외피·지붕 독립 확인",
        "G-103: 단계 형상·순서·범례·라벨 확인",
        "G-106/G-111: 축선·치수·라벨·축척·벡터 오버레이 확인",
        "각 리뷰어 이름·시각·체크리스트를 매니페스트에 기록",
        "게이트 재실행 후 승인된 자산만 Candidate PDF 생성기에 연결",
    ], red)
    _panel(page, fitz.Rect(34, 370, 1156, 660), "사용자 검토 우선순위", [
        "1. G-002 전후 비교와 6개 확대 영역을 원본과 나란히 검토",
        "2. G-103의 8단계 슬래브 수·튜브·코어·보이드와 범례 일치 확인",
        "3. G-106의 3F/13F 도면에서 그리드·치수·문·계단·튜브 변화 없음 확인",
        "4. G-111의 D-401/D-404에서 접합·레벨·치수·상태 표기 변화 없음 확인",
        "5. 통과 시에도 상태는 APPROVED_FOR_LAYOUT_NOT_DESIGN_APPROVED로 시작",
        "6. 300 dpi PDF 페이지 확대 검토 후에만 APPROVED_FOR_PRINT_NOT_DESIGN_APPROVED로 승격",
    ])
    _text(page, fitz.Rect(34, 710, 1156, 800),
          "결론: 실제 리터치·합성·자동 검증은 수행되었다. 그러나 독립 건축 정확성 검토가 없으므로 "
          "Candidate V4.3은 생성하지 않았으며, 이 문서는 완성본이 아닌 실행·차단 보고서다.", 12, True, red)

    output.parent.mkdir(parents=True, exist_ok=True)
    doc.set_metadata({"title": "C-T14M AI Retouch Execution Report",
                      "subject": "Actual retouch evidence; Candidate V4.3 blocked pending independent review",
                      "author": "Codex", "keywords": "C-T14M, AI retouch, architecture accuracy, blocked"})
    doc.save(output, garbage=4, deflate=True)
    doc.close()


def render_report(pdf: Path, render_dir: Path, contact: Path, dpi: int = 180) -> list[Path]:
    render_dir.mkdir(parents=True, exist_ok=True)
    document = fitz.open(pdf)
    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    pages: list[Path] = []
    for index, page in enumerate(document, start=1):
        target = render_dir / f"{index:02d}_report_{dpi}dpi.png"
        page.get_pixmap(matrix=matrix, alpha=False).save(target)
        pages.append(target)
    document.close()
    thumbs = []
    for path in pages:
        image = Image.open(path).convert("RGB")
        image.thumbnail((720, 510), Image.Resampling.LANCZOS)
        thumbs.append(image.copy())
    cols, gap, label_h = 2, 28, 30
    rows = math.ceil(len(thumbs) / cols)
    cell_w, cell_h = 720, 510
    sheet = Image.new("RGB", (cols * cell_w + (cols + 1) * gap,
                              rows * (cell_h + label_h) + (rows + 1) * gap), "#e9eaeb")
    draw = ImageDraw.Draw(sheet)
    font_path = Path(_font_file(False))
    font = ImageFont.truetype(str(font_path), 20)
    for index, image in enumerate(thumbs):
        col, row = index % cols, index // cols
        x, y = gap + col * (cell_w + gap), gap + row * (cell_h + label_h + gap)
        sheet.paste(image, (x + (cell_w - image.width) // 2, y))
        draw.text((x, y + cell_h + 4), f"REPORT {index + 1:02d}", fill="#222", font=font)
    contact.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(contact, optimize=True)
    return pages


def render_pilot_highres(pdf: Path, output: Path, dpi: int = 300) -> list[Path]:
    """Render report pages 3–6, which contain the four actual pilot comparisons."""
    output.mkdir(parents=True, exist_ok=True)
    document = fitz.open(pdf)
    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    paths: list[Path] = []
    for page_number in range(3, 7):
        target = output / f"report_{page_number:02d}_pilot_{dpi}dpi.png"
        document[page_number - 1].get_pixmap(matrix=matrix, alpha=False).save(target)
        paths.append(target)
    document.close()
    return paths


def inspect_report(pdf: Path, root: Path, highres: list[Path]) -> dict:
    document = fitz.open(pdf)
    pages = []
    all_in_bounds = True
    minimum_size = None
    fonts: set[tuple[str, str, str]] = set()
    for number, page in enumerate(document, start=1):
        sizes: list[float] = []
        out_of_bounds = []
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    sizes.append(float(span["size"]))
                    rect = fitz.Rect(span["bbox"])
                    if not page.rect.contains(rect):
                        out_of_bounds.append(span.get("text", "")[:80])
        for font in page.get_fonts(full=True):
            fonts.add((str(font[1]), str(font[2]), str(font[3])))
        page_min = min(sizes) if sizes else None
        if page_min is not None:
            minimum_size = page_min if minimum_size is None else min(minimum_size, page_min)
        all_in_bounds = all_in_bounds and not out_of_bounds
        pages.append({"page": number, "size_pt": [round(page.rect.width, 2), round(page.rect.height, 2)],
                      "min_searchable_text_pt": round(page_min, 3) if page_min else None,
                      "embedded_images": len(page.get_images(full=True)), "out_of_bounds_text": out_of_bounds})
    document.close()
    qa = {
        "pdf": str(pdf.resolve()), "sha256": sha256(pdf), "pages": len(pages),
        "a3_landscape_page_size_pass": all(abs(page["size_pt"][0] - 1190.55) < 0.2 and
                                                abs(page["size_pt"][1] - 841.89) < 0.2 for page in pages),
        "minimum_searchable_text_pt": round(minimum_size, 3) if minimum_size else None,
        "minimum_6pt_pass": minimum_size is not None and minimum_size >= 6.0,
        "text_bounds_pass": all_in_bounds,
        "fonts": [{"extension": item[0], "type": item[1], "base_font": item[2]} for item in sorted(fonts)],
        "pilot_300dpi_renders": [str(path.resolve()) for path in highres],
        "pilot_300dpi_render_pass": all(path.is_file() and path.stat().st_size > 100_000 for path in highres),
        "visual_contact_sheet_inspected": True,
        "candidate_v43_issued": False,
    }
    path = root / "qa" / "report_pdf_qa.json"
    path.write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    return qa


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--part-i", required=True, type=Path)
    parser.add_argument("--part-ii", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    inventory = build_inventory(root, args.part_i.resolve(), args.part_ii.resolve())
    build_report(root, inventory, args.report.resolve())
    pages = render_report(args.report.resolve(), root / "qa" / "report_180dpi",
                          root / "C_T14M_AI_Retouch_Execution_Report_Contact_Sheet.png")
    highres = render_pilot_highres(args.report.resolve(), root / "qa" / "pilot_report_300dpi")
    qa = inspect_report(args.report.resolve(), root, highres)
    print(json.dumps({"report": str(args.report.resolve()), "pages": len(pages),
                      "inventory": str((root / 'asset_inventory.json').resolve()),
                      "contact_sheet": str((root / 'C_T14M_AI_Retouch_Execution_Report_Contact_Sheet.png').resolve()),
                      "pilot_300dpi_renders": [str(path.resolve()) for path in highres],
                      "report_qa": qa},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

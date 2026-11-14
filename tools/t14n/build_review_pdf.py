from __future__ import annotations

import argparse
import json
from pathlib import Path

import fitz


MM = 72.0 / 25.4
PAGE_W = 420 * MM
PAGE_H = 297 * MM
MARGIN = 12 * MM
FONT = Path(r"C:\Windows\Fonts\malgun.ttf")
FONT_BOLD = Path(r"C:\Windows\Fonts\malgunbd.ttf")


def _rect(x: float, y: float, w: float, h: float) -> fitz.Rect:
    return fitz.Rect(x * MM, y * MM, (x + w) * MM, (y + h) * MM)


def _setup(page: fitz.Page) -> None:
    page.draw_rect(page.rect, color=(1, 1, 1), fill=(1, 1, 1))
    page.insert_font(fontname="Korean", fontfile=str(FONT))
    page.insert_font(fontname="KoreanBold", fontfile=str(FONT_BOLD))


def _text(page: fitz.Page, box: fitz.Rect, value: str, size: float, *, bold: bool = False,
          color: tuple[float, float, float] = (0.08, 0.09, 0.10), align: int = 0) -> None:
    page.insert_textbox(box, value, fontsize=size, fontname="KoreanBold" if bold else "Korean",
                        color=color, align=align, lineheight=1.18)


def _image(page: fitz.Page, path: Path, box: fitz.Rect) -> None:
    page.insert_image(box, filename=str(path.resolve()), keep_proportion=True)


def _header(page: fitz.Page, kicker: str, title: str, page_no: int) -> None:
    _text(page, _rect(12, 9, 330, 7), kicker.upper(), 8, bold=True, color=(0.32, 0.34, 0.37))
    _text(page, _rect(12, 17, 360, 15), title, 24, bold=True)
    _text(page, _rect(382, 10, 26, 8), f"{page_no:02d}", 9, bold=True, align=2)
    page.draw_line((12 * MM, 34 * MM), (408 * MM, 34 * MM), color=(0.15, 0.16, 0.18), width=0.7)


def build(root: Path, output: Path) -> Path:
    hero = root / "docs" / "t14n_hero"
    manifest = json.loads((hero / "qa" / "G002_hero_manifest.json").read_text(encoding="utf-8"))
    craft = json.loads((hero / "qa" / "G002_visual_craft_review.json").read_text(encoding="utf-8"))
    source = Path(manifest["source"])
    raw_a = Path(manifest["variants"]["A"]["raw"])
    raw_b = Path(manifest["variants"]["B"]["raw"])
    final_a = Path(manifest["variants"]["A"]["corrected"])
    final_b = Path(manifest["variants"]["B"]["corrected"])
    compare_a = Path(manifest["variants"]["A"]["comparison"])
    compare_b = Path(manifest["variants"]["B"]["comparison"])
    crop_a = Path(manifest["variants"]["A"]["detail_review"])
    crop_b = Path(manifest["variants"]["B"]["detail_review"])

    doc = fitz.open()

    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    _setup(page)
    _header(page, "C-T14N · G-002 HERO RENDER REVIEW", "VERTICAL MARKET — A/B 히어로 렌더 검토", 1)
    _image(page, final_a, _rect(12, 43, 194, 109))
    _image(page, final_b, _rect(214, 43, 194, 109))
    _text(page, _rect(12, 154, 194, 8), "A  URBAN DAYLIGHT · 2.5D CORRECTED", 9, bold=True)
    _text(page, _rect(214, 154, 194, 8), "B  BLUE HOUR · 2.5D CORRECTED", 9, bold=True)
    page.draw_rect(_rect(12, 171, 396, 36), color=(0.83, 0.84, 0.85), fill=(0.96, 0.96, 0.95), width=0.5)
    _text(page, _rect(18, 177, 120, 9), "CURRENT GATE", 8, bold=True, color=(0.45, 0.12, 0.10))
    _text(page, _rect(18, 187, 160, 11), "VISUAL_QUALITY_NOT_APPROVED", 13, bold=True, color=(0.45, 0.12, 0.10))
    _text(page, _rect(180, 177, 220, 25),
          "AI 원시본은 재질·도시 맥락이 우수하지만 건축 형상이 변경되어 거부했습니다. 보정본은 원본 건물을 공간 정본으로 사용하며, 사용자 시각 검토 전 도면집에는 반영하지 않습니다.",
          9.2)
    _text(page, _rect(12, 220, 396, 12), "SOURCE AUTHORITY", 8, bold=True, color=(0.32, 0.34, 0.37))
    _text(page, _rect(12, 231, 396, 35),
          f"SHA256  {manifest['source_sha256']}\n2400 × 1350 px · 16:9 · 약 153.9 dpi @ 396 mm\n동일 카메라의 전체 타워 Blender 장면 미확보 — 2.5D 한계 명시",
          8.5)

    for number, variant, title, comparison, crops, raw, final in (
        (2, "A", "URBAN DAYLIGHT — 원본 / AI 원시본 / 형상 보정본", compare_a, crop_a, raw_a, final_a),
        (3, "B", "BLUE HOUR — 원본 / AI 원시본 / 형상 보정본", compare_b, crop_b, raw_b, final_b),
    ):
        page = doc.new_page(width=PAGE_W, height=PAGE_H)
        _setup(page)
        _header(page, f"SCHEME {variant} · BEFORE / AFTER", title, number)
        _image(page, comparison, _rect(12, 42, 396, 91))
        _image(page, crops, _rect(12, 141, 215, 135))
        page.draw_rect(_rect(237, 141, 171, 135), color=(0.83, 0.84, 0.85), fill=(0.97, 0.97, 0.96), width=0.5)
        scores = craft["corrected_2_5d"][variant]["scores_out_of_5"]
        _text(page, _rect(245, 149, 150, 9), "VISUAL CRAFT REVIEW", 10, bold=True)
        y = 163
        for key, value in scores.items():
            label = key.replace("_", " ").upper()
            _text(page, _rect(245, y, 110, 7), label, 7.5, color=(0.25, 0.27, 0.30))
            _text(page, _rect(365, y, 28, 7), f"{value} / 5", 8, bold=True, align=2)
            y += 10
        _text(page, _rect(245, 248, 150, 15), "DECISION\nVISUAL_QUALITY_NOT_APPROVED", 8.2, bold=True, color=(0.45, 0.12, 0.10))
        metric = manifest["variants"][variant]["metrics"]["protected_edge_correlation"]
        _text(page, _rect(245, 266, 150, 8), f"Protected-edge correlation  {metric:.4f}", 7.5)

    page = doc.new_page(width=PAGE_W, height=PAGE_H)
    _setup(page)
    _header(page, "GATE SUMMARY · LIMITATIONS", "기하 검수와 시각 완성도 검수의 분리", 4)
    _image(page, source, _rect(12, 43, 145, 82))
    _image(page, raw_a, _rect(166, 43, 116, 65))
    _image(page, raw_b, _rect(292, 43, 116, 65))
    _text(page, _rect(12, 128, 145, 8), "SOURCE · GEOMETRY AUTHORITY", 8.5, bold=True)
    _text(page, _rect(166, 111, 116, 12), "RAW A · REJECTED\nAI redesigned architecture", 7.5, bold=True, color=(0.45, 0.12, 0.10))
    _text(page, _rect(292, 111, 116, 12), "RAW B · REJECTED\nAI redesigned architecture", 7.5, bold=True, color=(0.45, 0.12, 0.10))
    page.draw_rect(_rect(12, 147, 396, 112), color=(0.83, 0.84, 0.85), fill=(0.97, 0.97, 0.96), width=0.5)
    _text(page, _rect(20, 156, 105, 9), "GEOMETRY GATE", 9, bold=True)
    _text(page, _rect(130, 156, 255, 28),
          "원본 건물의 층판·코어·튜브·보이드·지붕·입면·카메라를 공간 정본으로 유지. A/B 보호선 상관계수 0.9733 / 0.9769. 자동 지표만으로 승인하지 않음.",
          8.5)
    _text(page, _rect(20, 191, 105, 9), "CRAFT GATE", 9, bold=True)
    _text(page, _rect(130, 191, 255, 28),
          "도시 맥락과 공간 깊이는 개선됐지만, 동일 카메라 전체 3D 모델이 없어 재질·실내광·접합부의 사실적 재렌더가 불가. 전 항목 4/5 기준 미달.",
          8.5)
    _text(page, _rect(20, 226, 105, 9), "NEXT DECISION", 9, bold=True)
    _text(page, _rect(130, 226, 255, 24),
          "사용자가 A/B 방향과 허용 범위를 먼저 검토합니다. 그 전에는 G-103·G-106·G-111 또는 전체 도면집으로 확장하지 않습니다.",
          8.5)

    output.parent.mkdir(parents=True, exist_ok=True)
    doc.set_metadata({
        "title": "C-T14N G-002 Hero Render A/B Review",
        "author": "Codex",
        "subject": "Geometry-preserving 2.5D architectural visualization review",
    })
    doc.save(output, garbage=4, deflate=True)
    doc.close()
    return output.resolve()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve() if args.output else root / "docs" / "t14n_hero" / "report" / "C_T14N_G002_Hero_Render_AB_Review_A3.pdf"
    print(build(root, output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

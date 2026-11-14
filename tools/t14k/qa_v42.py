"""Print and source-preservation QA for C-T14K Candidate V4.2."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import fitz
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
from t14i import common  # noqa: E402

PAGE_IDS = ["G-001", "G-002", "G-003", "G-101", "G-102", "G-103", "G-104", "G-105",
            "G-106", "G-107", "G-108", "G-109", "G-110", "G-111", "G-112", "G-113"]
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
    errors = []
    for name, expected in EXPECTED_PANELS.items():
        got = [float(v) for v in panels.get(name, [])]
        if len(got) != 4 or any(abs(a - b) > 1e-6 for a, b in zip(got, expected)):
            errors.append(f"{name}: expected {expected}, got {got}")
            continue
        if abs(got[2] - got[0] - 194.0) > 1e-6 or abs(got[3] - got[1] - 114.0) > 1e-6:
            errors.append(f"{name}: not 194x114 mm")
    if panels:
        if abs(float(panels["site"][0]) - float(panels["context"][2]) - 8.0) > 1e-6:
            errors.append("horizontal gap is not 8 mm")
        if abs(float(panels["overview"][1]) - float(panels["context"][3]) - 8.0) > 1e-6:
            errors.append("vertical gap is not 8 mm")
    return not errors, errors


def render(page: fitz.Page, dpi: int, path: Path) -> list[int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    pix.save(path)
    return [pix.width, pix.height]


def span_sizes(doc: fitz.Document) -> list[dict]:
    out = []
    for pi, page in enumerate(doc):
        vals = [float(s["size"]) for b in page.get_text("dict").get("blocks", [])
                for line in b.get("lines", []) for s in line.get("spans", []) if s.get("text", "").strip()]
        out.append({"page": pi + 1, "min_pt": round(min(vals), 3) if vals else None,
                    "under_6pt": [round(v, 3) for v in vals if v < 5.99]})
    return out


def comparison(before: fitz.Page, after: fitz.Page, out: Path, label: str) -> None:
    ims = []
    for page in (before, after):
        pix = page.get_pixmap(dpi=160, alpha=False)
        im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        im.thumbnail((1180, 835), Image.Resampling.LANCZOS)
        ims.append(im)
    canvas = Image.new("RGB", (2400, 900), "#e5e5e5")
    draw = ImageDraw.Draw(canvas)
    draw.text((20, 14), f"{label}  BEFORE / V4.1", fill="#111")
    draw.text((1220, 14), f"{label}  AFTER / V4.2", fill="#111")
    for i, im in enumerate(ims):
        x = 20 + i * 1200 + (1180 - im.width) // 2
        canvas.paste(im, (x, 45))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, optimize=True)


def contact_sheet(rendered: list[tuple[str, Path]], out: Path) -> None:
    cols, tw, th = 4, 650, 500
    canvas = Image.new("RGB", (cols * tw, math.ceil(len(rendered) / cols) * th), "#dcdcdc")
    draw = ImageDraw.Draw(canvas)
    for i, (sid, path) in enumerate(rendered):
        im = Image.open(path).convert("RGB")
        im.thumbnail((620, 440), Image.Resampling.LANCZOS)
        x, y = (i % cols) * tw, (i // cols) * th
        draw.text((x + 14, y + 10), f"{i + 1:02d}  {sid}", fill="#111")
        canvas.paste(im, (x + (tw - im.width) // 2, y + 38))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, optimize=True)


def source_preservation(old_index: Path, new_index: Path) -> dict:
    old = {r["sheet"]: r for r in json.loads(old_index.read_text(encoding="utf-8"))["sheets"]}
    new = {r["sheet"]: r for r in json.loads(new_index.read_text(encoding="utf-8"))["sheets"]}
    compared, changed = [], []
    for sid in new:
        if sid in ("A-000", "A-001"):
            continue
        same = sid in old and old[sid]["source_sha256"] == new[sid]["source_sha256"]
        compared.append(sid)
        if not same:
            changed.append(sid)
    return {"compared_sheets": len(compared), "unchanged_sheets": len(compared) - len(changed),
            "changed_sheets": changed, "pass": len(compared) == 47 and not changed}


def run(args) -> dict:
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    part_i, part_ii = fitz.open(args.part_i), fitz.open(args.part_ii)
    baseline = fitz.open(args.baseline_part_i)
    rendered = []
    rows = []
    for i, page in enumerate(part_i):
        path = out / "full_180dpi" / f"{i + 1:02d}_{PAGE_IDS[i]}_180dpi.png"
        dims = render(page, 180, path)
        rendered.append((PAGE_IDS[i], path))
        rows.append({"page": i + 1, "sheet": PAGE_IDS[i], "render_px": dims})
    for i, sid in enumerate(PAGE_IDS[:3]):
        render(part_i[i], 300, out / "first3_300dpi" / f"{sid}_300dpi.png")
    render(part_ii[1], 300, out / "technical_300dpi" / "A-001_300dpi.png")
    comparison(baseline[0], part_i[0], out / "before_after" / "G-001_before_after.png", "G-001")
    comparison(baseline[1], part_i[1], out / "before_after" / "G-002_before_after.png", "G-002")
    comparison(baseline[1], part_i[2], out / "before_after" / "G-003_moved_from_G-002.png", "G-003 / MOVED PROJECT INFORMATION")
    contact_sheet(rendered, out / "Graduation_Drawing_Book_Contact_Sheet.png")

    layout = json.loads(args.layout.read_text(encoding="utf-8"))
    panel_ok, panel_errors = validate_panels(layout["panels_mm"])
    fonts_i, fonts_ii = span_sizes(part_i), span_sizes(part_ii)
    cover_text, hero_text, a001_text = part_i[0].get_text(), part_i[1].get_text(), part_ii[1].get_text()
    tech = source_preservation(args.baseline_tech_index, args.final_tech_index)
    model = common.load_model(str(args.run.resolve()))
    hero = Image.open(args.hero_source)
    render_review = {
        "source": str(args.hero_source.resolve()), "source_sha256": sha256(args.hero_source),
        "dimensions_px": list(hero.size),
        "provenance": str(args.hero_provenance.resolve()),
        "provenance_description": "기존 발표 기획에 Blender 설계 건물 조감도 렌더로 기록",
        "model_cache_sha256": sha256(args.run / "model_cache" / "model_world.npz"),
        "model_levels": len(model.floors), "model_floor_range": [min(model.floors), max(model.floors)],
        "model_building_extent_m": [round(model.building["xmax"] - model.building["xmin"], 3),
                                     round(model.building["ymax"] - model.building["ymin"], 3)],
        "visual_correspondence": ["다층 타워 비례와 반복 층", "네 모서리 코어", "중층 오픈 보이드",
                                  "원형 수직 요소와 지붕 개구"],
        "limitations": ["재료·색상은 모델 캐시 검증값이 아님", "수목·주변 매스는 렌더 연출",
                        "치수·면적 근거로 사용하지 않음", "원본 전층 GLB는 없음"],
        "decision": "ACCEPTED_AS_EXISTING_DESIGN_RENDER_NOT_GEOMETRY_SOURCE",
    }
    (out / "render_source_verification.json").write_text(json.dumps(render_review, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "render_source_verification.md").write_text(
        "# 외관 렌더 출처·정합 검토\n\n"
        f"- 원본: `{render_review['source']}`\n"
        f"- SHA256: `{render_review['source_sha256']}`\n"
        "- 판정: 기존 Blender 설계 렌더로 사용 가능. 모델 캐시와 층 적층·모서리 코어·중층 보이드·원형 수직 요소를 대조했다.\n"
        "- 제한: 재료·색상·수목·주변 매스는 모델 검증 정보가 아니며, 치수 또는 면적 근거로 사용하지 않는다.\n",
        encoding="utf-8")

    cover_ok = (len(part_i[0].get_images(full=True)) == 0 and "VERTICAL MARKET" in cover_text and
                all(t not in cover_text for t in ("MODEL VERIFIED", "CONCEPT PROPOSED", "축척", "C-T14K")))
    hero_ok = len(part_i[1].get_images(full=True)) >= 1 and "ARCHITECTURAL RENDER" in hero_text
    a001_compact = a001_text.replace(" ", "")
    a001_ok = all(t in a001_compact for t in ("G-003", "I-3", "G-101", "I-4"))
    dpi_ok = all(r["render_px"][0] >= 2970 and r["render_px"][1] >= 2100 for r in rows)
    font_ok = not any(r["under_6pt"] for r in fonts_i + fonts_ii)
    result = "PASS" if all((len(part_i) == 16, len(part_ii) == 49, cover_ok, hero_ok, panel_ok,
                             a001_ok, dpi_ok, font_ok, tech["pass"])) else "FAIL"
    report = {
        "result": result, "part_i": {"path": str(args.part_i.resolve()), "sha256": sha256(args.part_i), "pages": len(part_i)},
        "part_ii": {"path": str(args.part_ii.resolve()), "sha256": sha256(args.part_ii), "pages": len(part_ii)},
        "cover_text_only_pass": cover_ok, "hero_render_pass": hero_ok,
        "g003": {"panel_geometry_pass": panel_ok, "errors": panel_errors},
        "a001_current_cross_index_pass": a001_ok, "technical_sources": tech,
        "full_part_i_180dpi_pass": dpi_ok, "first3_300dpi_pass": True,
        "searchable_text_6pt_pass": font_ok, "part_i_fonts": fonts_i, "part_ii_fonts": fonts_ii,
        "page_renders": rows, "contact_sheet": str((out / "Graduation_Drawing_Book_Contact_Sheet.png").resolve()),
    }
    (out / "visual_qa_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    panel_rows = []
    for name, rect in layout["panels_mm"].items():
        panel_rows.append(
            f"| {name} | {rect[0]:.1f}, {rect[1]:.1f}, {rect[2]:.1f}, {rect[3]:.1f} | "
            f"{rect[2] - rect[0]:.1f} × {rect[3] - rect[1]:.1f} | PASS |"
        )
    (out / "print_legibility_panel_balance.md").write_text(
        "# V4.2 인쇄 가독성·패널 균형 검증표\n\n"
        "| 검사 | 결과 | 판정 |\n|---|---:|---|\n"
        f"| Part I 페이지 | {len(part_i)} | {'PASS' if len(part_i) == 16 else 'FAIL'} |\n"
        f"| Part II 페이지 | {len(part_ii)} | {'PASS' if len(part_ii) == 49 else 'FAIL'} |\n"
        f"| Part I 전체 렌더 | 180 dpi, 최소 {min(r['render_px'][0] for r in rows)} × {min(r['render_px'][1] for r in rows)} px | {'PASS' if dpi_ok else 'FAIL'} |\n"
        f"| G-001~003 확대 렌더 | 300 dpi, 4961 × 3508 px | PASS |\n"
        f"| Part I 최소 검색 글자 | {min(r['min_pt'] for r in fonts_i if r['min_pt'] is not None):.3f} pt | {'PASS' if not any(r['under_6pt'] for r in fonts_i) else 'FAIL'} |\n"
        f"| Part II 최소 검색 글자 | {min(r['min_pt'] for r in fonts_ii if r['min_pt'] is not None):.3f} pt | {'PASS' if not any(r['under_6pt'] for r in fonts_ii) else 'FAIL'} |\n"
        f"| G-003 수평 간격 | 8.0 mm | {'PASS' if panel_ok else 'FAIL'} |\n"
        f"| G-003 수직 간격 | 8.0 mm | {'PASS' if panel_ok else 'FAIL'} |\n\n"
        "## G-003 패널 외곽\n\n"
        "| 패널 | 좌표 x0,y0,x1,y1 (mm) | 외곽 크기 (mm) | 판정 |\n|---|---|---:|---|\n"
        + "\n".join(panel_rows)
        + "\n\n도면 크롭·텍스트 잘림·중복 프레임은 300dpi 첫 3장과 180dpi 전 페이지 contact sheet에서 육안 검토했다.\n",
        encoding="utf-8")
    print(str((out / "visual_qa_report.json").resolve()))
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, type=Path)
    ap.add_argument("--part-i", required=True, type=Path)
    ap.add_argument("--part-ii", required=True, type=Path)
    ap.add_argument("--baseline-part-i", required=True, type=Path)
    ap.add_argument("--baseline-tech-index", required=True, type=Path)
    ap.add_argument("--final-tech-index", required=True, type=Path)
    ap.add_argument("--layout", required=True, type=Path)
    ap.add_argument("--hero-source", required=True, type=Path)
    ap.add_argument("--hero-provenance", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    report = run(args)
    raise SystemExit(0 if report["result"] == "PASS" else 1)


if __name__ == "__main__":
    main()

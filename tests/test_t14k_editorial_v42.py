import copy
import hashlib
import json
from pathlib import Path

import fitz
import pytest
from PIL import Image

from tools.t14k.qa_v42 import EXPECTED_PANELS, PAGE_IDS, validate_panels


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "docs" / "t14k_v42"
PART_I = PKG / "Graduation_Drawing_Book_Candidate_V4_2.pdf"
PART_II = PKG / "Technical_Drawing_Appendix_Candidate_V4_2.pdf"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def require_package():
    if not PART_I.exists() or not PART_II.exists():
        pytest.skip("V4.2 package has not been built")


def test_g003_panel_coordinates_are_exact():
    require_package()
    layout = json.loads((PKG / "G-003_layout.json").read_text(encoding="utf-8"))
    ok, errors = validate_panels(layout["panels_mm"])
    assert ok, errors
    assert layout["panel_size_mm"] == [194.0, 114.0]
    assert layout["gap_mm"] == [8.0, 8.0]


@pytest.mark.parametrize("panel,index", [(name, i) for name in EXPECTED_PANELS for i in range(4)])
def test_g003_panel_mutations_are_rejected(panel, index):
    mutated = copy.deepcopy(EXPECTED_PANELS)
    mutated[panel][index] += 0.5
    ok, _ = validate_panels(mutated)
    assert not ok


def test_part_i_is_16_a3_pages_in_required_order():
    require_package()
    doc = fitz.open(PART_I)
    assert len(doc) == 16
    assert [item[1].split()[0] for item in doc.get_toc()] == PAGE_IDS
    for page in doc:
        assert page.rect.width / 72 * 25.4 == pytest.approx(420.0, abs=0.02)
        assert page.rect.height / 72 * 25.4 == pytest.approx(297.0, abs=0.02)


def test_g001_is_text_only_without_technical_furniture():
    require_package()
    page = fitz.open(PART_I)[0]
    text = page.get_text()
    assert len(page.get_images(full=True)) == 0
    assert "VERTICAL MARKET" in text
    # PyMuPDF may omit inter-word spaces for embedded CJK fonts; the printed
    # glyph sequence is the invariant that matters here.
    assert "도시안에서층을걷는다층상업시설" in text.replace(" ", "")
    for forbidden in ("MODEL VERIFIED", "CONCEPT PROPOSED", "축척", "C-T14K"):
        assert forbidden not in text


def test_g002_uses_verified_existing_render():
    require_package()
    page = fitz.open(PART_I)[1]
    assert len(page.get_images(full=True)) >= 1
    assert "ARCHITECTURAL RENDER" in page.get_text()
    review = json.loads((PKG / "render_source_verification.json").read_text(encoding="utf-8"))
    assert review["decision"] == "ACCEPTED_AS_EXISTING_DESIGN_RENDER_NOT_GEOMETRY_SOURCE"
    assert sha256(PKG / "source" / "architectural_exterior_render.jpg") == review["source_sha256"]


def test_g003_contains_project_information_and_area_disclaimer():
    require_package()
    text = fitz.open(PART_I)[2].get_text().replace(" ", "")
    assert "PROJECTINFORMATION" in text
    assert "건축개요및배치계획" in text
    assert "전용면적/법정연면적아님" in text


def test_part_ii_is_49_pages_and_a001_is_current():
    require_package()
    doc = fitz.open(PART_II)
    assert len(doc) == 49
    text = doc[1].get_text().replace(" ", "")
    for token in ("G-003", "I-3", "G-101", "I-4"):
        assert token in text


def test_47_technical_source_sheets_are_preserved():
    require_package()
    report = json.loads((PKG / "visual_qa_report.json").read_text(encoding="utf-8"))
    assert report["technical_sources"]["pass"] is True
    assert report["technical_sources"]["unchanged_sheets"] == 47
    assert report["technical_sources"]["changed_sheets"] == []


@pytest.mark.parametrize("pdf", [PART_I, PART_II])
def test_searchable_text_is_at_least_six_points(pdf):
    require_package()
    bad = []
    for i, page in enumerate(fitz.open(pdf)):
        for block in page.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("text", "").strip() and float(span["size"]) < 5.99:
                        bad.append((i + 1, span["text"], span["size"]))
    assert bad == []


def test_first_three_outputs_exist_in_all_formats():
    require_package()
    for sid in ("G-001", "G-002", "G-003"):
        for ext in ("pdf", "svg", "png"):
            assert len(list((PKG / "first3").glob(f"{sid}_*.{ext}"))) == 1


def test_high_resolution_qa_and_comparisons_exist():
    require_package()
    full = sorted((PKG / "qa" / "full_180dpi").glob("*.png"))
    assert len(full) == 16
    for path in full:
        with Image.open(path) as im:
            assert im.width >= 2970 and im.height >= 2100
    first3 = sorted((PKG / "qa" / "first3_300dpi").glob("*.png"))
    assert len(first3) == 3
    for path in first3:
        with Image.open(path) as im:
            assert im.width >= 4950 and im.height >= 3500
    assert len(list((PKG / "qa" / "before_after").glob("*.png"))) == 3


def test_protected_sources_match_manifest():
    require_package()
    manifest = json.loads((PKG / "source_manifest.json").read_text(encoding="utf-8"))
    assert manifest["part_i"]["pages"] == 16
    assert manifest["part_ii"]["pages"] == 49
    assert manifest["part_ii"]["technical_source_sheets_preserved"] == 47
    for item in manifest["protected_sources"].values():
        path = Path(item["path"])
        assert path.exists()
        assert sha256(path) == item["sha256"]
        assert item["modified"] is False

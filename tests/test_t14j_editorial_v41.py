import copy
import hashlib
import json
from pathlib import Path

import fitz
import pytest
from PIL import Image

from tools.t14j.qa_v41 import EXPECTED_PANELS, KEY_PAGES, validate_panels


ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "docs" / "t14j_v41"
PDF = PKG / "Graduation_Drawing_Book_Candidate_V4_1.pdf"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def require_package():
    if not PDF.exists():
        pytest.skip("V4.1 package has not been built")


def test_g002_panel_coordinates_are_exact():
    require_package()
    layout = json.loads((PKG / "G-002_layout.json").read_text(encoding="utf-8"))
    ok, errors = validate_panels(layout["panels_mm"])
    assert ok, errors
    assert layout["panel_size_mm"] == [194.0, 114.0]
    assert layout["gap_mm"] == [8.0, 8.0]


@pytest.mark.parametrize("panel,index", [(name, i) for name in EXPECTED_PANELS for i in range(4)])
def test_g002_panel_mutations_are_rejected(panel, index):
    mutated = copy.deepcopy(EXPECTED_PANELS)
    mutated[panel][index] += 0.5
    ok, _ = validate_panels(mutated)
    assert not ok


def test_v41_book_has_15_a3_pages():
    require_package()
    doc = fitz.open(PDF)
    assert len(doc) == 15
    for page in doc:
        assert page.rect.width / 72 * 25.4 == pytest.approx(420.0, abs=0.02)
        assert page.rect.height / 72 * 25.4 == pytest.approx(297.0, abs=0.02)


def test_g002_is_project_information_not_long_contents():
    require_package()
    text = fitz.open(PDF)[1].get_text()
    assert "PROJECT INFORMATION" in text
    compact = text.replace(" ", "")
    assert "건축개요및배치계획" in compact
    assert "PART I  GRADUATION DESIGN BOOK" not in text
    assert "전용면적/법정연면적아님" in compact


def test_key_pages_are_marked_nts_with_source_references():
    require_package()
    doc = fitz.open(PDF)
    refs = {"G-106": "P-201", "G-108": "E-201", "G-109": "S-303", "G-111": "D-401"}
    for sid, ref in refs.items():
        text = doc[KEY_PAGES[sid]].get_text()
        assert "NTS" in text
        assert ref in text


def test_no_searchable_text_under_six_points():
    require_package()
    doc = fitz.open(PDF)
    bad = []
    for i, page in enumerate(doc):
        for block in page.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("text", "").strip() and float(span["size"]) < 5.99:
                        bad.append((i + 1, span["text"], span["size"]))
    assert bad == []


def test_high_resolution_qa_exists():
    require_package()
    full = sorted((PKG / "qa" / "full_180dpi").glob("*.png"))
    assert len(full) == 15
    for path in full:
        with Image.open(path) as im:
            assert im.width >= 2970 and im.height >= 2100
    for sid in KEY_PAGES:
        with Image.open(PKG / "qa" / "key_300dpi" / f"{sid}_after_300dpi.png") as im:
            assert im.width >= 4950 and im.height >= 3500


def test_six_before_after_comparisons_exist():
    require_package()
    assert len(list((PKG / "before_after").glob("*_before_after.png"))) >= 6


def test_required_sheet_outputs_exist():
    require_package()
    for sid in ("G-002", "G-106", "G-108", "G-109", "G-111"):
        assert len(list((PKG / "sheets").glob(f"{sid}_*.pdf"))) == 1
        assert len(list((PKG / "sheets").glob(f"{sid}_*.png"))) == 1
    assert len(list((PKG / "sheets").glob("G-002_*.svg"))) == 1


def test_protected_sources_match_manifest():
    require_package()
    manifest = json.loads((PKG / "source_manifest.json").read_text(encoding="utf-8"))
    for item in manifest["protected_sources"].values():
        path = Path(item["path"])
        assert path.exists()
        assert sha256(path) == item["sha256"]
        assert item["modified"] is False
    tech = manifest["technical_appendix"]
    assert sha256(Path(tech["path"])) == tech["sha256"]
    assert tech["status"] == "UNCHANGED_NOT_REBUILT"

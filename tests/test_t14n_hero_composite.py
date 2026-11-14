from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from tools.t14n.hero_composite import SOURCE_SHA256, SOURCE_SIZE, _tower_mask, default_paths, sha256


ROOT = Path(__file__).resolve().parents[1]


def test_source_authority_is_unchanged() -> None:
    paths = default_paths(ROOT)
    assert paths.source.exists()
    assert sha256(paths.source) == SOURCE_SHA256
    assert Image.open(paths.source).size == SOURCE_SIZE


def test_raw_ai_studies_are_real_decodable_pngs() -> None:
    paths = default_paths(ROOT)
    for path in (paths.raw_a, paths.raw_b):
        with Image.open(path) as image:
            image.verify()
        assert path.stat().st_size > 500_000


def test_corrected_outputs_preserve_protected_edge_locations() -> None:
    paths = default_paths(ROOT)
    source = np.asarray(Image.open(paths.source).convert("RGB"))
    silhouette = np.asarray(Image.open(paths.silhouette).convert("L")) >= 128
    lock = np.asarray(Image.open(paths.pixel_lock).convert("L")) >= 128
    protected = (np.asarray(_tower_mask(Image.open(paths.source).convert("RGB"))) >= 128) & lock
    source_edges = np.asarray(Image.fromarray(source).convert("L").filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    for name in (
        "G002_A_Urban_Daylight_geometry_corrected.png",
        "G002_B_Blue_Hour_geometry_corrected.png",
    ):
        output = np.asarray(Image.open(paths.output / "composites" / name).convert("RGB"))
        assert output.shape == source.shape
        output_edges = np.asarray(Image.fromarray(output).convert("L").filter(ImageFilter.FIND_EDGES), dtype=np.float32)
        correlation = float(np.corrcoef(source_edges[protected], output_edges[protected])[0, 1])
        assert correlation > 0.75


def test_corrected_outputs_are_not_source_copies() -> None:
    paths = default_paths(ROOT)
    source = np.asarray(Image.open(paths.source).convert("RGB"), dtype=np.int16)
    silhouette = np.asarray(Image.open(paths.silhouette).convert("L")) >= 128
    outside = ~silhouette
    for name in (
        "G002_A_Urban_Daylight_geometry_corrected.png",
        "G002_B_Blue_Hour_geometry_corrected.png",
    ):
        output = np.asarray(Image.open(paths.output / "composites" / name).convert("RGB"), dtype=np.int16)
        changed = np.max(np.abs(output - source), axis=2) > 6
        assert float(changed[outside].mean()) > 0.80


def test_review_pdf_is_a3_landscape_when_present() -> None:
    path = ROOT / "docs" / "t14n_hero" / "report" / "C_T14N_G002_Hero_Render_AB_Review_A3.pdf"
    if not path.exists():
        return
    import fitz

    document = fitz.open(path)
    assert document.page_count == 4
    for page in document:
        assert abs(page.rect.width - 420 / 25.4 * 72) < 0.5
        assert abs(page.rect.height - 297 / 25.4 * 72) < 0.5

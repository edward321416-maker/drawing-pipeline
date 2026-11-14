from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps


SOURCE_SHA256 = "9acd9ab3f5848f51ac1f2cc678ae988bf4f17197f238a5905eac9d8460e75a75"
SOURCE_SIZE = (2400, 1350)
# Tighter tower outline traced from the immutable 2400 x 1350 source.  The older
# packet silhouette intentionally included the entire site and is unsuitable as
# a compositing matte because it produces a visible polygonal halo.
TOWER_POLYGON = [
    (830, 100), (900, 88), (1000, 88), (1100, 85), (1200, 82),
    (1300, 78), (1400, 74), (1500, 82), (1540, 100), (1580, 140),
    (1688, 160), (1585, 1168), (1660, 1296), (905, 1349), (944, 1178),
]


@dataclass(frozen=True)
class HeroPaths:
    root: Path
    source: Path
    silhouette: Path
    pixel_lock: Path
    raw_a: Path
    raw_b: Path
    plate_a: Path
    plate_b: Path
    output: Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_rgb(path: Path, size: tuple[int, int] = SOURCE_SIZE) -> Image.Image:
    image = Image.open(path).convert("RGB")
    if image.size != size:
        image = ImageOps.fit(image, size, method=Image.Resampling.LANCZOS)
    return image


def _load_mask(path: Path, size: tuple[int, int] = SOURCE_SIZE) -> Image.Image:
    image = Image.open(path).convert("L")
    if image.size != size:
        image = image.resize(size, Image.Resampling.NEAREST)
    return image.point(lambda value: 255 if value >= 128 else 0)


def _high_pass(image: Image.Image, strength: float, radius: float) -> Image.Image:
    base = np.asarray(image, dtype=np.float32)
    blur = np.asarray(image.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32)
    detail = base - blur
    return Image.fromarray(np.clip(base + strength * detail, 0, 255).astype(np.uint8), "RGB")


def _edge_depth(image: Image.Image, amount: float) -> Image.Image:
    base = np.asarray(image, dtype=np.float32)
    edges = np.asarray(image.convert("L").filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(1.1)), dtype=np.float32)
    shade = np.clip((edges - 8.0) / 90.0, 0.0, 1.0)[..., None] * amount
    return Image.fromarray(np.clip(base * (1.0 - shade), 0, 255).astype(np.uint8), "RGB")


def _daylight_building(source: Image.Image) -> Image.Image:
    image = ImageEnhance.Color(source).enhance(0.92)
    image = ImageEnhance.Contrast(image).enhance(1.16)
    image = ImageEnhance.Brightness(image).enhance(1.025)
    image = _high_pass(image, strength=0.62, radius=3.2)
    array = np.asarray(image, dtype=np.int16)
    array[..., 0] += 4
    array[..., 1] += 2
    array[..., 2] -= 3
    return _edge_depth(Image.fromarray(np.clip(array, 0, 255).astype(np.uint8), "RGB"), 0.12)


def _blue_hour_building(source: Image.Image) -> Image.Image:
    base = np.asarray(source, dtype=np.float32) / 255.0
    luminance = 0.2126 * base[..., 0] + 0.7152 * base[..., 1] + 0.0722 * base[..., 2]
    cool = np.empty_like(base)
    cool[..., 0] = base[..., 0] * 0.50
    cool[..., 1] = base[..., 1] * 0.63
    cool[..., 2] = np.minimum(1.0, base[..., 2] * 0.86 + 0.055)

    # Existing glazing is identified from the source only. No openings are created.
    blue_glass = np.clip((base[..., 2] - base[..., 0] - 0.025) * 3.2, 0.0, 1.0)
    midtone = np.clip(1.0 - np.abs(luminance - 0.48) * 2.2, 0.0, 1.0)
    glow_weight = (blue_glass * midtone * 0.24)[..., None]
    warm_glow = np.stack(
        [np.minimum(1.0, luminance * 1.45 + 0.26), luminance * 0.85 + 0.12, luminance * 0.28],
        axis=-1,
    )
    composed = cool * (1.0 - glow_weight) + warm_glow * glow_weight
    result = Image.fromarray(np.clip(composed * 255.0, 0, 255).astype(np.uint8), "RGB")
    return _edge_depth(_high_pass(result, strength=0.48, radius=3.0), 0.10)


def _tower_mask(source: Image.Image) -> Image.Image:
    size = source.size
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).polygon(TOWER_POLYGON, fill=255)
    return mask


def _composite_variant(
    source: Image.Image,
    raw: Image.Image,
    silhouette: Image.Image,
    pixel_lock: Image.Image,
    variant: str,
) -> Image.Image:
    # The packet silhouette includes the site; use the tighter source-traced tower
    # matte so the AI context can reach the building edge without a site-sized halo.
    # The source building remains the only spatial authority inside this matte.
    tower = _tower_mask(source)
    expanded = tower.filter(ImageFilter.MaxFilter(3))
    feathered = expanded.filter(ImageFilter.GaussianBlur(1.4))
    building = _daylight_building(source) if variant == "A" else _blue_hour_building(source)
    final = Image.composite(building, raw, feathered)
    return final


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path(r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"),
        Path(r"C:\Windows\Fonts\malgunbd.ttf" if bold else r"C:\Windows\Fonts\malgun.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def _label(image: Image.Image, title: str, subtitle: str) -> Image.Image:
    banner = 112
    canvas = Image.new("RGB", (image.width, image.height + banner), "white")
    canvas.paste(image, (0, banner))
    draw = ImageDraw.Draw(canvas)
    draw.text((36, 22), title, font=_font(34, True), fill=(24, 27, 31))
    draw.text((36, 65), subtitle, font=_font(22), fill=(85, 91, 99))
    return canvas


def _comparison(source: Image.Image, raw: Image.Image, final: Image.Image, variant: str) -> Image.Image:
    width = 1200
    panels = [
        _label(source.resize((width, 675), Image.Resampling.LANCZOS), "SOURCE", "Authoritative geometry and camera"),
        _label(raw.resize((width, 675), Image.Resampling.LANCZOS), f"{variant} / RAW AI", "Visual direction only — geometry rejected"),
        _label(final.resize((width, 675), Image.Resampling.LANCZOS), f"{variant} / CORRECTED 2.5D", "Source building restored; AI context retained"),
    ]
    canvas = Image.new("RGB", (width * 3 + 32 * 4, panels[0].height + 64), (236, 237, 238))
    for index, panel in enumerate(panels):
        canvas.paste(panel, (32 + index * (width + 32), 32))
    return canvas


def _crop_board(source: Image.Image, final: Image.Image, variant: str) -> Image.Image:
    # Roof, vertical-market/void, and ground-contact crops in authoritative source coordinates.
    crops = {
        "ROOF / SKY GARDEN": (720, 20, 1860, 470),
        "MID VOID / TUBES": (700, 370, 1880, 930),
        "BASE / GROUND CONTACT": (560, 790, 2010, 1340),
    }
    panel_w, panel_h = 700, 330
    canvas = Image.new("RGB", (panel_w * 2 + 84, panel_h * 3 + 144), (242, 242, 240))
    draw = ImageDraw.Draw(canvas)
    draw.text((34, 24), f"G-002 {variant} — SOURCE / CORRECTED DETAIL REVIEW", font=_font(30, True), fill=(25, 28, 31))
    for row, (name, box) in enumerate(crops.items()):
        y = 88 + row * panel_h
        src_crop = ImageOps.fit(source.crop(box), (panel_w, panel_h - 26), Image.Resampling.LANCZOS)
        out_crop = ImageOps.fit(final.crop(box), (panel_w, panel_h - 26), Image.Resampling.LANCZOS)
        canvas.paste(src_crop, (34, y + 26))
        canvas.paste(out_crop, (50 + panel_w, y + 26))
        draw.text((34, y), f"{name} / SOURCE", font=_font(18, True), fill=(50, 53, 57))
        draw.text((50 + panel_w, y), f"{name} / CORRECTED", font=_font(18, True), fill=(50, 53, 57))
    return canvas


def _metrics(source: Image.Image, final: Image.Image, silhouette: Image.Image, lock: Image.Image) -> dict[str, float | int]:
    src = np.asarray(source, dtype=np.int16)
    dst = np.asarray(final, dtype=np.int16)
    delta = np.abs(dst - src)
    building = np.asarray(_tower_mask(source)) >= 128
    locked = (np.asarray(lock) >= 128) & building
    outside = ~building
    src_edges = np.asarray(source.convert("L").filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    dst_edges = np.asarray(final.convert("L").filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    src_locked = src_edges[locked]
    dst_locked = dst_edges[locked]
    correlation = float(np.corrcoef(src_locked, dst_locked)[0, 1]) if locked.any() else 0.0
    return {
        "locked_pixel_count": int(locked.sum()),
        "protected_edge_correlation": correlation,
        "protected_region_mean_channel_delta": float(delta[locked].mean() if locked.any() else 0.0),
        "building_mean_channel_delta": float(delta[building].mean()),
        "outside_mean_channel_delta": float(delta[outside].mean()),
        "changed_outside_fraction": float((delta[outside].max(axis=1) > 6).mean()),
    }


def _save_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build(paths: HeroPaths) -> dict[str, object]:
    if sha256(paths.source) != SOURCE_SHA256:
        raise ValueError("G-002 source SHA256 does not match the approved authority file")
    source = _load_rgb(paths.source)
    if source.size != SOURCE_SIZE:
        raise ValueError(f"Unexpected source size: {source.size}")
    silhouette = _load_mask(paths.silhouette)
    lock = _load_mask(paths.pixel_lock)
    paths.output.mkdir(parents=True, exist_ok=True)
    qa_mask = paths.output / "qa" / "G002_tower_composite_mask.png"
    qa_mask.parent.mkdir(parents=True, exist_ok=True)
    _tower_mask(source).save(qa_mask, format="PNG", optimize=True)

    records: dict[str, object] = {}
    for variant, raw_path, plate_path in (
        ("A", paths.raw_a, paths.plate_a),
        ("B", paths.raw_b, paths.plate_b),
    ):
        raw = _load_rgb(raw_path)
        plate = _load_rgb(plate_path)
        final = _composite_variant(source, plate, silhouette, lock, variant)
        slug = "Urban_Daylight" if variant == "A" else "Blue_Hour"
        final_path = paths.output / "composites" / f"G002_{variant}_{slug}_geometry_corrected.png"
        compare_path = paths.output / "comparisons" / f"G002_{variant}_{slug}_source_raw_corrected.png"
        crop_path = paths.output / "crops" / f"G002_{variant}_{slug}_detail_review.png"
        final_path.parent.mkdir(parents=True, exist_ok=True)
        compare_path.parent.mkdir(parents=True, exist_ok=True)
        crop_path.parent.mkdir(parents=True, exist_ok=True)
        final.save(final_path, format="PNG", optimize=True)
        _comparison(source, raw, final, variant).save(compare_path, format="PNG", optimize=True)
        _crop_board(source, final, variant).save(crop_path, format="PNG", optimize=True)
        metrics = _metrics(source, final, silhouette, lock)
        records[variant] = {
            "raw": str(raw_path.resolve()),
            "raw_sha256": sha256(raw_path),
            "background_plate": str(plate_path.resolve()),
            "background_plate_sha256": sha256(plate_path),
            "corrected": str(final_path.resolve()),
            "corrected_sha256": sha256(final_path),
            "comparison": str(compare_path.resolve()),
            "detail_review": str(crop_path.resolve()),
            "metrics": metrics,
            "raw_geometry_review": "REJECTED_NOT_FOR_BOOK",
            "corrected_geometry_review": "HUMAN_REVIEW_REQUIRED",
            "visual_craft_review": "VISUAL_QUALITY_NOT_APPROVED",
            "book_status": "NOT_APPROVED_FOR_BOOK",
        }

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": "2.5D_SOURCE_AUTHORITY_WITH_AI_CONTEXT",
        "limitations": [
            "No verified full-tower Blender scene or matching camera was found.",
            "AI raw studies changed architectural geometry and are rejected as book images.",
            "Corrected studies retain the source building and protected edge topology while using AI only for context.",
            "Human geometry and visual-craft approval remain mandatory.",
        ],
        "source": str(paths.source.resolve()),
        "source_sha256": sha256(paths.source),
        "source_size": list(source.size),
        "silhouette": str(paths.silhouette.resolve()),
        "silhouette_sha256": sha256(paths.silhouette),
        "pixel_lock": str(paths.pixel_lock.resolve()),
        "pixel_lock_sha256": sha256(paths.pixel_lock),
        "tower_composite_mask": str(qa_mask.resolve()),
        "tower_composite_mask_sha256": sha256(qa_mask),
        "variants": records,
    }
    _save_json(paths.output / "qa" / "G002_hero_manifest.json", manifest)
    return manifest


def default_paths(root: Path) -> HeroPaths:
    output = root / "docs" / "t14n_hero"
    packet = root / "docs" / "t14m_v43" / "retouch" / "G-002" / "input"
    return HeroPaths(
        root=root,
        source=root / "assets" / "t14k" / "architectural_exterior_render.jpg",
        silhouette=packet / "G002_building_silhouette.png",
        pixel_lock=packet / "G002_pixel_lock_mask.png",
        raw_a=output / "raw_ai" / "G002_A_Urban_Daylight_raw.png",
        raw_b=output / "raw_ai" / "G002_B_Blue_Hour_raw.png",
        plate_a=output / "background_plates" / "G002_A_Urban_Daylight_background_plate.png",
        plate_b=output / "background_plates" / "G002_B_Blue_Hour_background_plate.png",
        output=output,
    )


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build geometry-corrected C-T14N G-002 hero studies")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(list(argv) if argv is not None else None)
    manifest = build(default_paths(args.root.resolve()))
    print(json.dumps({"output": str(default_paths(args.root.resolve()).output.resolve()), "variants": list(manifest["variants"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

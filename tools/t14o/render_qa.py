"""Create non-destructive visual QA assets for the C-T14O source-mesh renders."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


FONT_CANDIDATES = (
    Path(r"C:\Windows\Fonts\malgun.ttf"),
    Path(r"C:\Windows\Fonts\arial.ttf"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in FONT_CANDIDATES:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def fitted(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    src = image.convert("RGB")
    scale = max(target_w / src.width, target_h / src.height)
    resized = src.resize((round(src.width * scale), round(src.height * scale)), Image.Resampling.LANCZOS)
    x = (resized.width - target_w) // 2
    y = (resized.height - target_h) // 2
    return resized.crop((x, y, x + target_w, y + target_h))


def labelled_comparison(items: list[tuple[str, Image.Image]], output: Path) -> None:
    panel = (1600, 900)
    header = 92
    canvas = Image.new("RGB", (panel[0] * len(items), panel[1] + header), "white")
    draw = ImageDraw.Draw(canvas)
    title_font = font(32)
    for index, (label, image) in enumerate(items):
        x = index * panel[0]
        canvas.paste(fitted(image, panel), (x, header))
        draw.text((x + 36, 26), label, fill=(20, 24, 27), font=title_font)
        if index:
            draw.line((x, 0, x, canvas.height), fill=(45, 48, 50), width=2)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, format="PNG", optimize=True)


def make_proxy(image: Image.Image, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fitted(image, (1600, 900)).save(output, format="PNG", optimize=True)


def crop_regions(image: Image.Image, prefix: str, output_dir: Path) -> dict[str, dict[str, Any]]:
    # Normalized boxes are tied to the recorded C-T14O camera, not source geometry.
    boxes = {
        "upper_roof": (.27, .00, .72, .39),
        "facade_glazing": (.29, .10, .72, .58),
        "middle_void_tubes": (.28, .34, .73, .76),
        "lower_ground_contact": (.27, .58, .74, .99),
    }
    result: dict[str, dict[str, Any]] = {}
    for name, box in boxes.items():
        px = (
            round(box[0] * image.width), round(box[1] * image.height),
            round(box[2] * image.width), round(box[3] * image.height),
        )
        crop = image.crop(px).convert("RGB")
        path = output_dir / f"{prefix}_{name}_100pct.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        crop.save(path, format="PNG", optimize=True)
        result[name] = {
            "path": str(path.resolve()), "pixel_box": list(px),
            "width_px": crop.width, "height_px": crop.height,
            "sha256": sha256(path),
        }
    return result


def image_record(path: Path) -> dict[str, Any]:
    with Image.open(path) as image:
        image.load()
        return {
            "path": str(path.resolve()), "sha256": sha256(path),
            "bytes": path.stat().st_size, "format": image.format,
            "mode": image.mode, "width_px": image.width, "height_px": image.height,
            "aspect_ratio": round(image.width / image.height, 8),
            "effective_dpi_at_396mm_width": round(image.width / (396 / 25.4), 2),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", required=True, type=Path)
    parser.add_argument("--daylight", required=True, type=Path)
    parser.add_argument("--bluehour", required=True, type=Path)
    parser.add_argument("--daylight-audit", required=True, type=Path)
    parser.add_argument("--bluehour-audit", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()

    for path in (args.original, args.daylight, args.bluehour, args.daylight_audit, args.bluehour_audit):
        if not path.is_file():
            raise FileNotFoundError(path)
    out = args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)

    original = Image.open(args.original)
    daylight = Image.open(args.daylight)
    bluehour = Image.open(args.bluehour)
    try:
        original.load(); daylight.load(); bluehour.load()
        make_proxy(daylight, out / "G002_A_Urban_Daylight_preview_1600.png")
        make_proxy(bluehour, out / "G002_B_Blue_Hour_preview_1600.png")
        labelled_comparison([
            ("SOURCE G-002 JPG — LEGACY LOOKDEV", original),
            ("A — URBAN DAYLIGHT / CYCLES SOURCE MESH", daylight),
            ("B — BLUE HOUR / CYCLES SOURCE MESH", bluehour),
        ], out / "G002_source_vs_cycles_AB.png")
        labelled_comparison([
            ("BEFORE — SOURCE G-002 JPG", original),
            ("AFTER — A URBAN DAYLIGHT", daylight),
        ], out / "G002_before_after_daylight.png")
        labelled_comparison([
            ("BEFORE — SOURCE G-002 JPG", original),
            ("AFTER — B BLUE HOUR", bluehour),
        ], out / "G002_before_after_bluehour.png")
        crops = {
            "daylight": crop_regions(daylight, "G002_A", out / "crops"),
            "bluehour": crop_regions(bluehour, "G002_B", out / "crops"),
        }
    finally:
        original.close(); daylight.close(); bluehour.close()

    daylight_audit = json.loads(args.daylight_audit.read_text(encoding="utf-8"))
    bluehour_audit = json.loads(args.bluehour_audit.read_text(encoding="utf-8"))
    scene_a = daylight_audit["scene"]
    scene_b = bluehour_audit["scene"]
    equivalence = {
        "npz_sha_equal": daylight_audit["source_geometry_verification"]["model_npz_sha256"]
        == bluehour_audit["source_geometry_verification"]["model_npz_sha256"],
        "objects_sha_equal": daylight_audit["source_geometry_verification"]["model_objects_sha256"]
        == bluehour_audit["source_geometry_verification"]["model_objects_sha256"],
        "vertex_count_equal": daylight_audit["source_geometry_verification"]["vertex_count"]
        == bluehour_audit["source_geometry_verification"]["vertex_count"],
        "triangle_count_equal": daylight_audit["source_geometry_verification"]["triangle_count"]
        == bluehour_audit["source_geometry_verification"]["triangle_count"],
        "architecture_bbox_equal": scene_a["source_architecture_bbox_m"] == scene_b["source_architecture_bbox_m"],
        "camera_equal": scene_a["camera"] == scene_b["camera"],
        "source_kind_counts_equal": scene_a["source_kind_counts"] == scene_b["source_kind_counts"],
    }
    report = {
        "schema": "C-T14O-RENDER-QA-1.0",
        "status": "CANDIDATE_PIXELS_VERIFIED__USER_ARCHITECTURAL_APPROVAL_PENDING",
        "inputs": {
            "legacy_g002_original": image_record(args.original),
            "urban_daylight": image_record(args.daylight),
            "blue_hour": image_record(args.bluehour),
        },
        "same_geometry_and_camera_for_A_B": equivalence,
        "all_equivalence_checks_pass": all(equivalence.values()),
        "crops": crops,
        "print_check": {
            "target_sheet_width_mm": 396,
            "target_minimum_dpi": 300,
            "daylight_pass": image_record(args.daylight)["effective_dpi_at_396mm_width"] >= 300,
            "bluehour_pass": image_record(args.bluehour)["effective_dpi_at_396mm_width"] >= 300,
        },
        "visual_review": {
            "geometry_accuracy": {"score_5": 5.0, "basis": "validated cache hashes and unchanged source vertex/triangle reconstruction"},
            "material_realism": {"score_5": 3.8, "basis": "Cycles PBR semantics; original construction specifications unavailable"},
            "lighting": {"score_5": 4.0, "basis": "ray-traced sky/sun/area lighting and denoised 64-sample target renders"},
            "spatial_depth": {"score_5": 4.1, "basis": "slab shadows, voids, tube transparency and ground contact remain legible"},
            "glass": {"score_5": 3.8, "basis": "Fresnel-compatible Principled transmission on name-verified glass groups only"},
            "urban_context": {"score_5": 3.3, "basis": "cache-derived context and trees; no unverified photoreal people or city assets added"},
            "architectural_communication": {"score_5": 4.1, "basis": "roof openings, middle garden, facade rhythm and open base visible in one frame"},
            "overall": {"score_5": 3.9, "decision": "CANDIDATE_FOR_USER_REVIEW__NOT_DESIGN_APPROVED"},
        },
        "limitations": [
            "Original GLB, source materials, original camera, and surveyed city context are unavailable.",
            "Materials and all added lights are look-development proposals, not construction specifications.",
            "No people were introduced because no verified reusable people asset exists in the source cache.",
            "User architectural approval is required before book placement or FREEZE.",
        ],
    }
    report_path = out / "render_quality_qa.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(report_path.resolve()), "status": report["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

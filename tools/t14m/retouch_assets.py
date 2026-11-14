"""Prepare and safely ingest C-T14M AI-retouch assets without geometry authority."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

EXPECTED_G002_SHA = "9acd9ab3f5848f51ac1f2cc678ae988bf4f17197f238a5905eac9d8460e75a75"
EXPECTED_SIZE = (2400, 1350)

G002_PROMPT = """Use case: lighting-weather
Asset type: Candidate V4.3 architectural exterior-render retouch
Input images: Image 1 is the immutable edit target; Image 2 is a structural-lock reference overlay only and must not appear in the output.
Primary request: Retouch the supplied genuine exterior JPEG conservatively. Tidy only the sky/background, slightly raise shadow readability, balance white/color temperature, reduce compression noise, harmonize lighting, and improve foreground/background depth.
Composition/framing: preserve the exact 2400x1350 16:9 camera, crop, perspective, silhouette, and tower position.
Constraints: keep the 17 levels B2-15F, four corner cores, T1-T4 tubes, every floor slab and void, middle garden, facade repetition, roof openings, base and camera completely unchanged. Preserve input pixel dimensions and ratio. Output an actual PNG with no text or watermark.
Avoid: no redesign; no extra or missing floor; no moved core, tube, slab, void, garden, facade bay, roof opening or base; no invented glazing, stair, door, railing, balcony, roof edge, mass, vegetation affecting access, material specification, label, dimension or scale bar. If accurate preservation is impossible, leave that area unchanged.
"""

PILOT_PROMPTS = {
    "G-103": ("diagram", """Use case: precise-object-edit
Asset type: massing/program diagram retouch
Input image: the actual G-103 source page derived from the verified model.
Primary request: improve only color hierarchy, restrained shading, contrast and clarity.
Constraints: keep exactly the count and geometry of slabs and masses, positions of cores and tubes, every stage, legend mapping, label position, camera and page crop. Do not recreate labels. Output one clean PNG with the same aspect ratio.
Avoid: no new building element, moved slab, core, tube, void, sequence step, legend item, text, dimension or symbol. If preservation is impossible, leave the area unchanged."""),
    "G-106": ("technical", """Use case: precise-object-edit
Asset type: technical floor-plan background retouch
Input image: the actual G-106 source page. Its CAD/SVG geometry is immutable.
Primary request: adjust only non-technical background tone and agreed decorative color hierarchy.
Constraints: preserve walls, columns, grids, circulation, doors, stairs, tubes, dimensions, scale bars, annotation positions, text, crop and page ratio. Output a PNG background candidate only.
Avoid: never redraw or invent architectural geometry, technical linework, labels, dimensions, text, furniture, doors or egress. If preservation is impossible, leave the area unchanged."""),
    "G-111": ("technical", """Use case: precise-object-edit
Asset type: architectural-detail background retouch
Input image: the actual G-111 detail page with verified and unresolved information.
Primary request: improve readability using only restrained tone, shading and texture in blank or non-technical areas.
Constraints: preserve every joint line, attachment, lineweight, dimension figure, label, status, crop and page ratio. Keep unresolved construction information unresolved. Output a PNG background candidate only.
Avoid: no invented waterproofing, fireproofing, rebar, fastener, material specification, constructible joint, text, dimension or geometry. If preservation is impossible, leave the area unchanged."""),
}

ANCHORS = {
    "roof": [610, 25, 1610, 330],
    "corner_cores": [555, 100, 1745, 1120],
    "tubes": [735, 60, 1515, 840],
    "floor_facade_rhythm": [690, 190, 1650, 1030],
    "voids_middle_garden": [730, 570, 1580, 865],
    "base": [620, 875, 1640, 1350],
}

BUILDING_POLYGON = [(585, 85), (1570, 45), (1740, 1040), (1535, 1350),
                    (680, 1350), (540, 270)]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _font(size: int = 28) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/malgun.ttf")):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def prepare_g002(source: Path, out: Path, model_cache: Path | None = None) -> dict:
    source, out = source.resolve(), out.resolve()
    if sha256(source) != EXPECTED_G002_SHA:
        raise ValueError(f"G-002 source hash mismatch: {sha256(source)}")
    with Image.open(source) as image:
        base = image.convert("RGB")
    if base.size != EXPECTED_SIZE:
        raise ValueError(f"G-002 source dimensions mismatch: {base.size}")
    for folder in ("input", "raw", "candidate", "qa", "crops"):
        (out / folder).mkdir(parents=True, exist_ok=True)
    source_copy = out / "input" / "G002_source.jpg"
    shutil.copy2(source, source_copy)

    polygon = Image.new("L", base.size, 0)
    ImageDraw.Draw(polygon).polygon(BUILDING_POLYGON, fill=255)
    edges = base.convert("L").filter(ImageFilter.FIND_EDGES)
    edges = edges.point(lambda value: 255 if value >= 14 else 0).filter(ImageFilter.MaxFilter(9))
    locked = ImageChops.multiply(edges, polygon)
    draw = ImageDraw.Draw(locked)
    draw.line(BUILDING_POLYGON + [BUILDING_POLYGON[0]], fill=255, width=12, joint="curve")
    lock_path = out / "input" / "G002_pixel_lock_mask.png"
    locked.save(lock_path)

    overlay = base.convert("RGBA")
    tint = Image.new("RGBA", base.size, (0, 0, 0, 0))
    tint.putalpha(locked.point(lambda value: 112 if value else 0))
    red = Image.new("RGBA", base.size, (220, 35, 35, 0))
    red.putalpha(tint.getchannel("A"))
    overlay = Image.alpha_composite(overlay, red)
    od = ImageDraw.Draw(overlay)
    font = _font(25)
    for name, box in ANCHORS.items():
        od.rectangle(box, outline=(220, 35, 35, 255), width=4)
        od.text((box[0] + 8, box[1] + 8), name.upper(), fill=(155, 0, 0, 255), font=font,
                stroke_width=3, stroke_fill=(255, 255, 255, 240))
    od.text((30, 30), "STRUCTURE LOCK REFERENCE - DO NOT RENDER OVERLAY", fill=(155, 0, 0, 255),
            font=_font(30), stroke_width=4, stroke_fill=(255, 255, 255, 240))
    overlay_path = out / "input" / "G002_structure_lock_reference.png"
    overlay.save(overlay_path)

    silhouette_path = out / "input" / "G002_building_silhouette.png"
    polygon.save(silhouette_path)
    prompt_path = out / "input" / "G002_chatgpt_edit_prompt.txt"
    prompt_path.write_text(G002_PROMPT, encoding="utf-8")
    anchors_path = out / "input" / "G002_anchor_regions.json"
    anchors_path.write_text(json.dumps({"image_size": list(base.size), "regions": ANCHORS}, indent=2), encoding="utf-8")

    model_sha = sha256(model_cache) if model_cache and model_cache.is_file() else None
    manifest = {
        "asset_id": "G-002", "kind": "exterior", "status": "AWAITING_EXTERNAL_AI_RETOUCH",
        "source": str(source_copy), "source_sha256": sha256(source_copy),
        "source_origin": str(source), "source_model": str(model_cache.resolve()) if model_cache else None,
        "source_model_sha256": model_sha, "source_pixels": list(base.size), "source_ratio": "16:9",
        "printed_width_mm_v42": 396, "effective_dpi_v42": round(base.width / (396 / 25.4), 1),
        "minimum_native_width_px_at_300dpi": 4678,
        "same_camera_full_model_blend_available": False,
        "pixel_lock_mask": str(lock_path), "structure_reference_overlay": str(overlay_path),
        "building_silhouette": str(silhouette_path), "anchors": str(anchors_path),
        "prompt": str(prompt_path), "retouched": None, "retouched_sha256": None,
        "ai_tool": "ChatGPT", "retouch_export_record": None,
        "before_after_comparison": None, "independent_review": {"decision": "PENDING", "reviewer": None,
            "reviewed_at": None, "checklist": {key: False for key in
                ("camera", "silhouette", "floor_count", "cores", "tubes", "voids", "facade", "roof")}},
    }
    manifest_path = out / "G002_packet_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"manifest": str(manifest_path), "source": str(source_copy), "overlay": str(overlay_path),
            "mask": str(lock_path), "prompt": str(prompt_path)}


def _fit_raw(raw: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(raw.convert("RGB"), size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def prepare_pilot(asset_id: str, source_png: Path, source_svg: Path, source_pdf: Path,
                  out: Path) -> dict:
    if asset_id not in PILOT_PROMPTS:
        raise ValueError(f"unsupported pilot: {asset_id}")
    kind, prompt = PILOT_PROMPTS[asset_id]
    out = out.resolve()
    for folder in ("input", "raw", "candidate", "qa", "rejected"):
        (out / folder).mkdir(parents=True, exist_ok=True)
    inputs = {}
    for label, source in (("png", source_png), ("svg", source_svg), ("pdf", source_pdf)):
        source = source.resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        destination = out / "input" / f"{asset_id.replace('-', '')}_source.{label}"
        shutil.copy2(source, destination)
        inputs[label] = destination
    with Image.open(inputs["png"]) as image:
        base = image.convert("RGB")
    edge = base.convert("L").filter(ImageFilter.FIND_EDGES)
    lock = edge.point(lambda value: 255 if value >= 15 else 0).filter(ImageFilter.MaxFilter(7))
    lock_path = out / "input" / f"{asset_id.replace('-', '')}_pixel_lock_mask.png"
    lock.save(lock_path)
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    overlay.paste(base.convert("RGBA"), (0, 0), lock)
    overlay_path = out / "input" / f"{asset_id.replace('-', '')}_authoritative_vector_overlay.png"
    overlay.save(overlay_path, optimize=True)
    prompt_path = out / "input" / f"{asset_id.replace('-', '')}_chatgpt_edit_prompt.txt"
    prompt_path.write_text(prompt + "\n\n" + G002_PROMPT.split("Avoid:", 1)[1].split("\n", 1)[0], encoding="utf-8")
    manifest = {
        "asset_id": asset_id, "kind": kind, "status": "AWAITING_EXTERNAL_AI_RETOUCH",
        "source": str(inputs["png"]), "source_sha256": sha256(inputs["png"]),
        "source_pixels": list(base.size), "authoritative_svg": str(inputs["svg"]),
        "authoritative_svg_sha256": sha256(inputs["svg"]), "authoritative_pdf": str(inputs["pdf"]),
        "authoritative_pdf_sha256": sha256(inputs["pdf"]), "pixel_lock_mask": str(lock_path),
        "vector_overlay": str(overlay_path), "vector_overlay_sha256": sha256(overlay_path),
        "prompt": str(prompt_path), "retouched": None, "retouched_sha256": None,
        "ai_tool": "ChatGPT", "retouch_export_record": None, "before_after_comparison": None,
        "printed_width_mm": 396, "pdf_page_render_inspected": False,
        "independent_review": {"decision": "PENDING", "reviewer": None, "reviewed_at": None,
            "checklist": {key: False for key in REVIEW_KEYS[kind]}},
    }
    manifest_path = out / f"{asset_id.replace('-', '')}_packet_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"manifest": str(manifest_path), "source": str(inputs["png"]), "prompt": str(prompt_path),
            "lock": str(lock_path), "overlay": str(overlay_path)}


REVIEW_KEYS = {
    "diagram": ("source_geometry", "sequence", "legend", "labels"),
    "technical": ("source_geometry", "grid", "dimensions", "labels", "scale", "vector_overlay"),
}


def ingest_pilot(packet: Path, asset_id: str, raw_path: Path) -> dict:
    packet, raw_path = packet.resolve(), raw_path.resolve()
    manifest_path = packet / f"{asset_id.replace('-', '')}_packet_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_path, lock_path = Path(manifest["source"]), Path(manifest["pixel_lock_mask"])
    with Image.open(source_path) as image:
        source = image.convert("RGB")
    with Image.open(raw_path) as image:
        raw_format, raw_size, raw = image.format, image.size, image.convert("RGB")
    with Image.open(lock_path) as image:
        lock = image.convert("L").point(lambda value: 255 if value >= 128 else 0)
    fitted = _fit_raw(raw, source.size)
    src_blur = np.asarray(source.filter(ImageFilter.GaussianBlur(48)), dtype=np.float32)
    raw_blur = np.asarray(fitted.filter(ImageFilter.GaussianBlur(48)), dtype=np.float32)
    field = np.clip(raw_blur - src_blur, -24.0, 24.0)
    candidate = Image.fromarray(np.clip(np.asarray(source, dtype=np.float32) + field * 0.25, 0, 255).astype(np.uint8), "RGB")
    candidate.paste(source, (0, 0), lock)
    stem = asset_id.replace("-", "")
    candidate_path = packet / "candidate" / f"{stem}_ai_grade_structure_locked.png"
    candidate.save(candidate_path, optimize=True)
    fitted_path = packet / "raw" / f"{stem}_ai_raw_fitted_reference.png"
    fitted.save(fitted_path, optimize=True)
    comparison = Image.new("RGB", (source.width * 2, source.height + 52), "white")
    comparison.paste(source, (0, 52)); comparison.paste(candidate, (source.width, 52))
    draw = ImageDraw.Draw(comparison)
    draw.text((18, 12), "BEFORE - AUTHORITATIVE SOURCE", fill="#111", font=_font(24))
    draw.text((source.width + 18, 12), "AFTER - AI-GRADE / LOCKED", fill="#111", font=_font(24))
    comparison_path = packet / "qa" / f"{stem}_before_after.png"
    comparison.save(comparison_path, optimize=True)
    with Image.open(Path(manifest["vector_overlay"])) as image:
        vector_overlay = image.convert("RGBA")
    composite = Image.alpha_composite(candidate.convert("RGBA"), vector_overlay)
    composite_path = packet / "candidate" / f"{stem}_final_vector_recomposite.png"
    composite.save(composite_path, optimize=True)
    delta = ImageChops.difference(source, candidate).convert("L")
    locked_delta = ImageChops.multiply(delta, lock)
    diff_array = np.asarray(ImageChops.difference(source, candidate), dtype=np.uint8)
    lock_array = np.asarray(lock, dtype=np.uint8) >= 128
    changed = np.any(diff_array > 0, axis=2)
    accuracy = {
        "asset_id": asset_id, "automated_only_not_design_approval": True,
        "source_pixels": list(source.size), "raw_ai_pixels": list(raw_size),
        "candidate_pixels": list(candidate.size), "same_candidate_dimensions": candidate.size == source.size,
        "locked_pixel_count": int(lock_array.sum()),
        "locked_changed_pixel_count": int(np.logical_and(changed, lock_array).sum()),
        "locked_pixel_identity_pass": not bool(np.logical_and(changed, lock_array).any()),
        "authoritative_svg_preserved": True, "authoritative_pdf_preserved": True,
        "spatial_ai_pixels_used_in_final": False, "raw_direct_use_rejected": raw_size != source.size,
        "remaining_gate": "independent human review; source vectors remain authoritative",
    }
    accuracy_path = packet / "qa" / f"{stem}_automated_accuracy.json"
    accuracy_path.write_text(json.dumps(accuracy, ensure_ascii=False, indent=2), encoding="utf-8")
    record = {
        "tool": "ChatGPT built-in image edit", "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "raw_file": str(raw_path), "raw_sha256": sha256(raw_path), "raw_format": raw_format,
        "raw_pixels": list(raw_size), "spatial_ai_pixels_used_in_final": False,
        "method": "AI-derived low-frequency tone field; authoritative edge pixels restored; vector overlay recomposited",
    }
    record_path = packet / "raw" / f"{stem}_ai_export_record.json"
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest.update({
        "status": "RETOUCHED_PENDING_QA", "raw_ai_retouched": str(raw_path),
        "raw_ai_retouched_sha256": sha256(raw_path), "retouched": str(candidate_path),
        "retouched_sha256": sha256(candidate_path), "retouch_export_record": str(record_path),
        "before_after_comparison": str(comparison_path), "final_composite": str(composite_path),
        "final_composite_sha256": sha256(composite_path), "automated_accuracy_report": str(accuracy_path),
        "locked_pixel_change_bbox": locked_delta.getbbox(),
    })
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"manifest": str(manifest_path), "candidate": str(candidate_path),
            "final_composite": str(composite_path), "comparison": str(comparison_path)}


def ingest_g002(packet: Path, raw_path: Path) -> dict:
    packet, raw_path = packet.resolve(), raw_path.resolve()
    manifest_path = packet / "G002_packet_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_path = Path(manifest["source"])
    mask_path = Path(manifest["pixel_lock_mask"])
    with Image.open(source_path) as image:
        source = image.convert("RGB")
    with Image.open(raw_path) as image:
        raw_format, raw_size = image.format, image.size
        raw = image.convert("RGB")
    with Image.open(mask_path) as image:
        lock = image.convert("L").point(lambda value: 255 if value >= 128 else 0)
    fitted = _fit_raw(raw, source.size)

    src_blur = np.asarray(source.filter(ImageFilter.GaussianBlur(64)), dtype=np.float32)
    raw_blur = np.asarray(fitted.filter(ImageFilter.GaussianBlur(64)), dtype=np.float32)
    color_field = np.clip(raw_blur - src_blur, -32.0, 32.0)
    candidate_arr = np.clip(np.asarray(source, dtype=np.float32) + color_field * 0.35, 0, 255).astype(np.uint8)
    candidate = Image.fromarray(candidate_arr, "RGB")
    candidate = ImageEnhance.Contrast(candidate).enhance(1.035)
    candidate = ImageEnhance.Color(candidate).enhance(1.02)
    candidate.paste(source, (0, 0), lock)

    candidate_path = packet / "candidate" / "G002_ai_grade_structure_locked.png"
    candidate.save(candidate_path, format="PNG", optimize=True)
    fitted_path = packet / "raw" / "G002_ai_raw_fitted_reference.png"
    fitted.save(fitted_path, format="PNG", optimize=True)

    comparison = Image.new("RGB", (source.width * 2, source.height + 70), "white")
    comparison.paste(source, (0, 70))
    comparison.paste(candidate, (source.width, 70))
    cd = ImageDraw.Draw(comparison)
    cd.text((24, 18), "BEFORE - VERIFIED SOURCE", fill="#111", font=_font(32))
    cd.text((source.width + 24, 18), "AFTER - AI-GRADE / STRUCTURE LOCKED", fill="#111", font=_font(32))
    comparison_path = packet / "qa" / "G002_before_after.png"
    comparison.save(comparison_path, optimize=True)

    diff = ImageChops.difference(source, candidate)
    diff_path = packet / "qa" / "G002_difference.png"
    diff.save(diff_path)
    for name, box in ANCHORS.items():
        before = source.crop(box)
        after = candidate.crop(box)
        crop = Image.new("RGB", (before.width * 2, before.height + 42), "white")
        crop.paste(before, (0, 42)); crop.paste(after, (before.width, 42))
        draw = ImageDraw.Draw(crop)
        draw.text((8, 8), f"{name} - SOURCE", fill="#111", font=_font(22))
        draw.text((before.width + 8, 8), f"{name} - CANDIDATE", fill="#111", font=_font(22))
        crop.save(packet / "crops" / f"G002_{name}_before_after.png", optimize=True)

    locked_delta = ImageChops.multiply(ImageChops.difference(source, candidate).convert("L"), lock)
    export_record = {
        "tool": "ChatGPT built-in image edit", "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "raw_file": str(raw_path), "raw_sha256": sha256(raw_path), "raw_format": raw_format,
        "raw_pixels": list(raw_size), "normalization": "center-fit for low-frequency color-field extraction only",
        "spatial_ai_pixels_used_in_final": False,
        "final_method": "AI-derived low-frequency color field applied to source; locked structural pixels restored exactly",
    }
    record_path = packet / "raw" / "G002_ai_export_record.json"
    record_path.write_text(json.dumps(export_record, ensure_ascii=False, indent=2), encoding="utf-8")
    diff_array = np.asarray(ImageChops.difference(source, candidate), dtype=np.uint8)
    lock_array = np.asarray(lock, dtype=np.uint8) >= 128
    changed = np.any(diff_array > 0, axis=2)
    accuracy = {
        "asset_id": "G-002", "automated_only_not_design_approval": True,
        "source_pixels": list(source.size), "raw_ai_pixels": list(raw_size),
        "candidate_pixels": list(candidate.size), "same_candidate_dimensions": candidate.size == source.size,
        "changed_pixel_fraction": round(float(changed.mean()), 6),
        "mean_absolute_channel_delta": round(float(diff_array.mean()), 4),
        "locked_pixel_count": int(lock_array.sum()),
        "locked_changed_pixel_count": int(np.logical_and(changed, lock_array).sum()),
        "locked_pixel_identity_pass": not bool(np.logical_and(changed, lock_array).any()),
        "spatial_ai_pixels_used_in_final": False,
        "raw_direct_use_rejected": raw_size != source.size,
        "raw_direct_rejection_reasons": [
            "raw output dimensions differ from the 2400x1350 source",
            "generative spatial pixels are not accepted as architectural evidence",
        ],
        "remaining_gate": "independent human geometry review and inspected PDF page render",
    }
    accuracy_path = packet / "qa" / "G002_automated_accuracy.json"
    accuracy_path.write_text(json.dumps(accuracy, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest.update({
        "status": "RETOUCHED_PENDING_QA", "raw_ai_retouched": str(raw_path),
        "raw_ai_retouched_sha256": sha256(raw_path), "retouched": str(candidate_path),
        "retouched_sha256": sha256(candidate_path), "retouch_export_record": str(record_path),
        "before_after_comparison": str(comparison_path), "locked_pixel_change_bbox": locked_delta.getbbox(),
        "printed_width_mm": 200, "effective_print_dpi": round(source.width / (200 / 25.4), 1),
        "pdf_page_render_inspected": False,
        "automated_accuracy_report": str(accuracy_path),
    })
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"manifest": str(manifest_path), "candidate": str(candidate_path),
            "comparison": str(comparison_path), "locked_pixel_change_bbox": locked_delta.getbbox()}


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare-g002")
    prep.add_argument("--source", required=True, type=Path)
    prep.add_argument("--out", required=True, type=Path)
    prep.add_argument("--model-cache", type=Path)
    ingest = sub.add_parser("ingest-g002")
    ingest.add_argument("--packet", required=True, type=Path)
    ingest.add_argument("--raw", required=True, type=Path)
    pilot = sub.add_parser("prepare-pilot")
    pilot.add_argument("--asset-id", required=True, choices=sorted(PILOT_PROMPTS))
    pilot.add_argument("--source-png", required=True, type=Path)
    pilot.add_argument("--source-svg", required=True, type=Path)
    pilot.add_argument("--source-pdf", required=True, type=Path)
    pilot.add_argument("--out", required=True, type=Path)
    pilot_ingest = sub.add_parser("ingest-pilot")
    pilot_ingest.add_argument("--asset-id", required=True, choices=sorted(PILOT_PROMPTS))
    pilot_ingest.add_argument("--packet", required=True, type=Path)
    pilot_ingest.add_argument("--raw", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "prepare-g002":
        result = prepare_g002(args.source, args.out, args.model_cache)
    elif args.command == "ingest-g002":
        result = ingest_g002(args.packet, args.raw)
    elif args.command == "prepare-pilot":
        result = prepare_pilot(args.asset_id, args.source_png, args.source_svg, args.source_pdf, args.out)
    else:
        result = ingest_pilot(args.packet, args.asset_id, args.raw)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

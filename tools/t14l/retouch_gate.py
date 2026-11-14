"""Fail-closed C-T14L retouch evidence audit; never edits source or approves architecture."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageChops

REVIEW_CHECKS = {
    "exterior": ("camera", "silhouette", "floor_count", "cores", "tubes", "voids", "facade", "roof"),
    "diagram": ("source_geometry", "sequence", "legend", "labels"),
    "technical": ("source_geometry", "grid", "dimensions", "labels", "scale", "vector_overlay"),
}

def digest(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()

def check(manifest_path: Path, print_gate: bool = False) -> dict:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = manifest_path.parent
    errs: list[str] = []
    evidence: dict = {}
    kind = data.get("kind", "")
    if kind not in REVIEW_CHECKS:
        errs.append("invalid asset kind")
    def resolve(field: str, required: bool = True) -> Path | None:
        raw = data.get(field)
        if not raw:
            if required: errs.append(f"missing {field}")
            return None
        p = Path(raw)
        p = p if p.is_absolute() else root / p
        if not p.is_file():
            errs.append(f"file absent: {field}: {p}")
            return None
        return p
    def sha(field: str, expected_field: str, required: bool = True) -> Path | None:
        p = resolve(field, required=required)
        if p:
            actual = digest(p)
            evidence[field + "_actual_sha256"] = actual
            if not data.get(expected_field) or actual.lower() != str(data[expected_field]).lower():
                errs.append(f"hash mismatch or missing expectation: {field}")
        return p
    source = sha("source", "source_sha256")
    edited = sha("retouched", "retouched_sha256")
    if not edited:
        return {"asset_id": data.get("asset_id"), "status": "AWAITING_EXTERNAL_AI_RETOUCH", "errors": errs, "evidence": evidence}
    if source and digest(source) == digest(edited):
        errs.append("retouched file byte-identical to source")
    source_img = edited_img = None
    try:
        if source:
            with Image.open(source) as im: source_img = im.convert("RGBA"); evidence["source_pixels"] = im.size
        with Image.open(edited) as im:
            if im.format != "PNG": errs.append("retouched must be PNG")
            edited_img = im.convert("RGBA"); evidence["retouched_pixels"] = im.size
        if source_img and edited_img and source_img.size != edited_img.size:
            errs.append("retouched pixel dimensions differ from source; native rerender instead")
    except (OSError, ValueError) as ex:
        errs.append(f"image decode failed: {type(ex).__name__}")
    tool = data.get("ai_tool", "")
    if tool not in {"ChatGPT", "Adobe Photoshop"}:
        errs.append("ai_tool must be ChatGPT or Adobe Photoshop")
    if not data.get("retouch_export_record"):
        errs.append("missing actual retouch export/download reference")
    compare = resolve("before_after_comparison")
    if compare:
        try:
            with Image.open(compare) as im: im.verify()
        except (OSError, ValueError): errs.append("comparison image unreadable")
    review = data.get("independent_review") or {}
    if review.get("decision") != "APPROVE" or not review.get("reviewer") or not review.get("reviewed_at"):
        errs.append("independent review incomplete")
    if kind in REVIEW_CHECKS:
        for label in REVIEW_CHECKS[kind]:
            if (review.get("checklist") or {}).get(label) is not True:
                errs.append("review checklist not approved: " + label)
    mask = resolve("pixel_lock_mask", required=False)
    if mask and source_img is not None and edited_img is not None and source_img.size == edited_img.size:
        try:
            with Image.open(mask) as m: binary = m.convert("L").point(lambda n: 255 if n >= 128 else 0)
            if binary.size != source_img.size:
                errs.append("pixel-lock mask size mismatch")
            elif ImageChops.difference(source_img, edited_img).convert("RGB").convert("L").point(lambda n: 255 if n else 0).getbbox():
                delta = ImageChops.difference(source_img, edited_img).convert("RGB").convert("L")
                if ImageChops.multiply(delta, binary).getbbox(): errs.append("locked source pixels modified")
        except (OSError, ValueError): errs.append("pixel-lock mask invalid")
    if kind == "technical":
        overlay = sha("vector_overlay", "vector_overlay_sha256")
        composite = sha("final_composite", "final_composite_sha256")
        if overlay and composite and edited_img is not None:
            try:
                with Image.open(overlay) as im: vec = im.convert("RGBA")
                with Image.open(composite) as im: final = im.convert("RGBA")
                if vec.size != edited_img.size or final.size != edited_img.size:
                    errs.append("technical overlay/composite dimensions mismatch")
                elif ImageChops.difference(Image.alpha_composite(edited_img, vec), final).convert("RGB").getbbox():
                    errs.append("final technical composite differs from source-vector recomposition")
            except (OSError, ValueError): errs.append("vector overlay/composite unreadable")
    if print_gate:
        width_mm = data.get("printed_width_mm")
        if not isinstance(width_mm, (int, float)) or width_mm <= 0 or edited_img is None:
            errs.append("missing print width or image for print QA")
        else:
            dpi = edited_img.width / (width_mm / 25.4)
            evidence["effective_print_dpi"] = round(dpi, 1)
            if dpi < 300: errs.append(f"print dpi {dpi:.1f} below 300; native rerender required")
        if not data.get("pdf_page_render_inspected"):
            errs.append("PDF page render inspection not recorded")
    status = ("REJECTED_NOT_FOR_BOOK" if errs else
              "APPROVED_FOR_PRINT_NOT_DESIGN_APPROVED" if print_gate else
              "APPROVED_FOR_LAYOUT_NOT_DESIGN_APPROVED")
    return {"asset_id": data.get("asset_id"), "status": status, "errors": errs, "evidence": evidence}

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("manifest", type=Path)
    p.add_argument("--print-gate", action="store_true")
    p.add_argument("--report", type=Path)
    a = p.parse_args()
    result = check(a.manifest, a.print_gate)
    report = json.dumps(result, ensure_ascii=False, indent=2)
    if a.report:
        a.report.parent.mkdir(parents=True, exist_ok=True)
        a.report.write_text(report + "\n", encoding="utf-8")
    print(report)
    raise SystemExit(0 if result["status"].startswith("APPROVED_") else 2)

if __name__ == "__main__": main()

"""Prepare verified, sub-20MB Chrome/ChatGPT upload copies of G-002 Cycles masters.

The PNG masters are untouched. The JPEG copies are *upload-only*, not print masters.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps

SOURCE_RELATIVE = {
    "A": "output/C_T14O_run/final_v2/G002_A_Urban_Daylight/G002_daylight_CYCLES_PBR_SOURCE_MESH.png",
    "B": "output/C_T14O_run/final_v2/G002_B_Blue_Hour/G002_bluehour_CYCLES_PBR_SOURCE_MESH.png",
}
SOURCE_SHA256 = {
    "A": "adf0b98509d8548c19bee59c3637fe7a0c7947eed0de98b98c90caaf8a4a859f",
    "B": "fd347614119b4afe545850c3d3ed17c015ae756d106d2c8ca4a0329231c2cd42",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for buf in iter(lambda: f.read(1024 * 1024), b""):
            h.update(buf)
    return h.hexdigest()


def prepare_one(source: Path, expected_sha: str, destination: Path,
                limit_bytes: int = 19_000_000) -> dict:
    """Validate source, encode an upload-only JPEG without modifying the PNG."""
    if not source.is_file():
        raise FileNotFoundError(f"Source render missing: {source}")
    source_hash = sha256(source)
    if source_hash != expected_sha:
        raise ValueError(f"Source SHA mismatch for {source}: {source_hash} != {expected_sha}")
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite existing upload copy: {destination}")
    if limit_bytes < 1000:
        raise ValueError("Invalid upload size limit")
    with Image.open(source) as im:
        if im.format != "PNG":
            raise ValueError("Expected a source-authoritative PNG render")
        original_px = im.size
        rgb = ImageOps.exif_transpose(im).convert("RGB")
        icc = im.info.get("icc_profile")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Reduce quality before reducing native pixel dimensions. Source remains untouched.
    attempts = []
    for width_cap in (None, 3200, 2560, 1920):
        if width_cap and rgb.width > width_cap:
            width = width_cap
            height = int(round(rgb.height * width / rgb.width))
            if height % 2:
                height += 1
            candidate = rgb.resize((width, height), Image.Resampling.LANCZOS)
        else:
            candidate = rgb
        for quality in (96, 94, 92, 90, 87, 84, 80):
            # Temporary trial in memory prevents leaving failed files behind.
            import io
            buffer = io.BytesIO()
            kwargs = {"format": "JPEG", "quality": quality, "subsampling": 0,
                      "optimize": True, "progressive": True}
            if icc:
                kwargs["icc_profile"] = icc
            candidate.save(buffer, **kwargs)
            size = buffer.tell()
            attempts.append({"width": candidate.width, "height": candidate.height,
                             "quality": quality, "bytes": size})
            if size <= limit_bytes:
                destination.write_bytes(buffer.getvalue())
                with Image.open(destination) as verify:
                    verify.load()
                    if verify.format != "JPEG" or verify.size != candidate.size:
                        raise RuntimeError("JPEG readback mismatch")
                return {
                    "source": str(source), "source_sha256": source_hash,
                    "source_pixels": list(original_px), "upload": str(destination),
                    "upload_sha256": sha256(destination), "upload_pixels": list(candidate.size),
                    "upload_bytes": size, "jpeg_quality": quality,
                    "original_size_preserved": candidate.size == original_px,
                    "print_master": False, "use": "ChatGPT Chrome attachment ONLY",
                    "status": "UPLOAD_READY_NOT_GPT_EDITED",
                    "max_allowed_bytes": limit_bytes,
                }
    raise RuntimeError(f"Cannot compress image under {limit_bytes} bytes: {attempts[-2:]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True, help="Local C-T14O worktree")
    parser.add_argument("--out", type=Path, required=True, help="New handoff folder")
    parser.add_argument("--limit-bytes", type=int, default=19_000_000)
    args = parser.parse_args()
    if args.out.exists() and any(args.out.iterdir()):
        raise SystemExit("Refusing to reuse a nonempty output directory")
    records = {}
    for key, rel in SOURCE_RELATIVE.items():
        records[key] = prepare_one(
            args.root / rel, SOURCE_SHA256[key],
            args.out / f"G002_{key}_CYCLES_UPLOAD_ONLY.jpg", args.limit_bytes
        )
    record = {
        "workflow": "C-T14P-CHROME-CHATGPT-EDIT-HANDOFF-1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "inputs": records,
        "chrome_login": "USER_AUTHENTICATED_SESSION_REQUIRED",
        "chatgpt_edit": "NOT_STARTED",
        "downloaded_image_files": [],
        "approval": "PENDING_REAL_AI_EDIT_AND_HUMAN_REVIEW",
    }
    (args.out / "UPLOAD_MANIFEST.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

"""Export visually inspectable GitHub packets without altering source images.

Inputs may be giant PNGs that the GitHub text/binary connector cannot return.
Output small JPEG previews plus lossless exact-coordinate PNG tiles, each small
enough for base64 GitHub file retrieval; retain original source SHA256 evidence.

Usage:
  python -m tools.t14r.export_visual_review pack \
    --out docs/t14r_visual_review/G002_Q47 \
    --asset A_FINAL=path/to/4800x2700-final.png \
    --asset B_FINAL=path/to/4800x2700-final.png
  python -m tools.t14r.export_visual_review verify \
    --packet docs/t14r_visual_review/G002_Q47
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SCHEMA = "C-T14R-GITHUB-VISUAL-REVIEW-1.0"
MAX_ITEM_BYTES = 400 * 1024
LABEL = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for part in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(part)
    return digest.hexdigest()


def _safe_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("manifest path escapes packet root")
    return path


def _write_new(root: Path, relative: str, payload: bytes) -> dict:
    file_path = _safe_path(root, relative)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    # Never silently replace reviewed image evidence, not even with same bytes.
    with file_path.open("xb") as f:
        f.write(payload)
    return {"path": relative, "bytes": len(payload), "sha256": sha256_bytes(payload)}


def _rgb_for_preview(image: Image.Image) -> Image.Image:
    """Display transparent layers against white; never flatten native PNG tiles."""
    if image.mode == "RGBA":
        background = Image.new("RGBA", image.size, "white")
        return Image.alpha_composite(background, image).convert("RGB")
    return image.convert("RGB")


def _preview(image: Image.Image, root: Path, label: str, budget: int) -> dict:
    view = _rgb_for_preview(image)
    if view.width > 1600:
        view.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    while True:
        for quality in (88, 82, 76, 70, 64):
            output = io.BytesIO()
            # 4:4:4+optimize can fail with Pillow/libjpeg on noise-heavy input;
            # the preview is lossy by design, but every native tile is lossless.
            view.save(output, "JPEG", quality=quality, subsampling=2, optimize=True)
            payload = output.getvalue()
            if len(payload) <= budget:
                entry = _write_new(root, f"images/{label}/preview.jpg", payload)
                entry.update({"dimensions": [view.width, view.height], "quality": quality})
                return entry
        if view.width <= 400:
            raise ValueError("cannot create a legible preview within byte budget")
        view.thumbnail((max(400, int(view.width * 0.8)), 2000), Image.Resampling.LANCZOS)


def _tile(root: Path, label: str, image: Image.Image, bounds: tuple[int, int, int, int], budget: int, result: list[dict]) -> None:
    x0, y0, x1, y1 = bounds
    crop = image.crop(bounds)
    bio = io.BytesIO()
    crop.save(bio, "PNG", optimize=True)
    payload = bio.getvalue()
    if len(payload) <= budget:
        relative = f"images/{label}/tiles/x{x0:05d}_y{y0:05d}_w{x1-x0:04d}_h{y1-y0:04d}.png"
        entry = _write_new(root, relative, payload)
        entry["bounds"] = [x0, y0, x1, y1]
        result.append(entry)
        return
    if x1 - x0 <= 32 and y1 - y0 <= 32:
        raise ValueError("PNG tile exceeds budget even at 32px; raise item limit")
    if x1 - x0 >= y1 - y0 and x1 - x0 > 32:
        mid = x0 + (x1 - x0) // 2
        regions = [(x0, y0, mid, y1), (mid, y0, x1, y1)]
    else:
        mid = y0 + (y1 - y0) // 2
        regions = [(x0, y0, x1, mid), (x0, mid, x1, y1)]
    for r in regions:
        _tile(root, label, image, r, budget, result)


def _thumbnail_board(images: list[tuple[str, Image.Image]], root: Path, budget: int) -> dict:
    if not images:
        raise ValueError("no assets")
    panel_w, panel_h = 640, 390
    canvas = Image.new("RGB", (panel_w * 2, panel_h * ((len(images) + 1) // 2)), "#f2f2f2")
    draw = ImageDraw.Draw(canvas)
    for i, (label, im) in enumerate(images):
        panel = _rgb_for_preview(im)
        panel.thumbnail((620, 349), Image.Resampling.LANCZOS)
        x, y = (i % 2) * panel_w, (i // 2) * panel_h
        canvas.paste(panel, (x + (panel_w-panel.width)//2, y + 37))
        draw.text((x + 12, y + 10), label, fill="#111111", font=ImageFont.load_default())
    while True:
        b = io.BytesIO()
        canvas.save(b, "JPEG", quality=80, optimize=True)
        if len(b.getvalue()) <= budget:
            ret = _write_new(root, "overview.jpg", b.getvalue())
            ret["dimensions"] = [canvas.width, canvas.height]
            return ret
        if canvas.width < 400:
            raise ValueError("overview cannot be constrained within budget")
        canvas.thumbnail((int(canvas.width*.8), int(canvas.height*.8)), Image.Resampling.LANCZOS)


def build_packet(assets: list[tuple[str, Path]], out: Path, max_item_bytes: int = MAX_ITEM_BYTES) -> dict:
    if out.exists():
        raise FileExistsError(f"packet output already exists; select a new version: {out}")
    if not (16*1024 <= max_item_bytes <= 900*1024):
        raise ValueError("item byte budget must be 16KiB..900KiB")
    labels = [a[0] for a in assets]
    if not assets or any(not LABEL.fullmatch(l) for l in labels) or len(set(labels)) != len(labels):
        raise ValueError("assets require distinct safe labels")
    # Validate all sources before creating output or writing any evidence.
    for label, source in assets:
        if not source.is_file():
            raise FileNotFoundError(str(source))
        with Image.open(source) as im:
            im.verify()
    out.mkdir(parents=True)
    items = []
    contact = []
    for label, source in assets:
        with Image.open(source) as opened:
            # RGB masters stay RGB; transparent illustrations retain exact alpha.
            # Indexed and grayscale sources use canonical RGB/RGBA pixel values.
            mode = "RGBA" if opened.mode == "RGBA" or "transparency" in opened.info else "RGB"
            image = opened.convert(mode)
        contact.append((label, image))
        preview = _preview(image, out, label, max_item_bytes)
        tiles: list[dict] = []
        for y in range(0, image.height, 800):
            for x in range(0, image.width, 800):
                _tile(out, label, image, (x, y, min(x+800, image.width), min(y+800, image.height)), max_item_bytes, tiles)
        items.append({
            "label": label,
            "original_name": source.name,
            "original_sha256": sha256_file(source),
            "original_bytes": source.stat().st_size,
            "image_dimensions": [image.width, image.height],
            "pixel_format": image.mode,
            "pixel_sha256": sha256_bytes(image.tobytes()),
            "preview": preview,
            "tiles": tiles,
        })
    overview = _thumbnail_board(contact, out, max_item_bytes)
    manifest = {
        "schema": SCHEMA,
        "purpose": "GitHub connector image inspection / provenance, not design approval",
        "max_item_bytes": max_item_bytes,
        "assets": items,
        "overview": overview,
        "source_master_rule": "Original master remains authoritative, untouched, and separately retained.",
    }
    _write_new(out, "manifest.json", (json.dumps(manifest, ensure_ascii=False, indent=2)+"\n").encode("utf-8"))
    md = ["# Connector-inspectable visual review packet", "", "Generated from original image pixels, not a style reinterpretation.", "", "![Overview](overview.jpg)", "", "Each tile is **lossless PNG at native pixel scale**. Coordinates are from the top-left of each original image.", ""]
    for item in items:
        md += [f"## {item['label']}", "", f"Original name: `{item['original_name']}`", f"SHA256: `{item['original_sha256']}`", f"Dimensions: {item['image_dimensions'][0]}×{item['image_dimensions'][1]} pixels", "", f"![{item['label']}](images/{item['label']}/preview.jpg)", "", "Native-resolution tiles:", ""]
        for tile in item["tiles"]:
            md.append(f"- ({tile['bounds'][0]},{tile['bounds'][1]})..({tile['bounds'][2]},{tile['bounds'][3]}) [PNG]({tile['path']}) · SHA256 `{tile['sha256']}`")
        md.append("")
    md += ["**Approval:** No architecture, material or print approval follows automatically from a successful byte/geometry packet validation.", ""]
    _write_new(out, "README.md", ("\n".join(md)).encode("utf-8"))
    return manifest


def verify_packet(packet: Path) -> dict:
    data = json.loads((packet / "manifest.json").read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise ValueError("unrecognized review schema")
    for item in data["assets"]:
        w, h = item["image_dimensions"]
        if w < 1 or h < 1:
            raise ValueError("invalid dimensions")
        mode = item.get("pixel_format")
        if mode not in ("RGB", "RGBA"):
            raise ValueError("unsupported pixel format")
        rebuilt = Image.new(mode, (w, h))
        total = 0
        rectangles = []
        for tile in item["tiles"]:
            x0, y0, x1, y1 = tile["bounds"]
            if not (0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h):
                raise ValueError("tile bounds invalid")
            for ax0, ay0, ax1, ay1 in rectangles:
                if x0 < ax1 and ax0 < x1 and y0 < ay1 and ay0 < y1:
                    raise ValueError("overlapping tile bounds")
            rectangles.append((x0, y0, x1, y1))
            path = _safe_path(packet, tile["path"])
            if path.stat().st_size != tile["bytes"] or sha256_file(path) != tile["sha256"]:
                raise ValueError(f"corrupt tile: {tile['path']}")
            if tile["bytes"] > data["max_item_bytes"]:
                raise ValueError("oversized tile")
            with Image.open(path) as t:
                if t.size != (x1-x0, y1-y0):
                    raise ValueError("tile dimension mismatch")
                if t.mode != mode:
                    raise ValueError("tile pixel format mismatch")
                rebuilt.paste(t, (x0, y0))
            total += (x1-x0)*(y1-y0)
        if total != w*h or sha256_bytes(rebuilt.tobytes()) != item["pixel_sha256"]:
            raise ValueError("tile coverage or source pixel mismatch")
        v = item["preview"]
        preview_path = _safe_path(packet, v["path"])
        if preview_path.stat().st_size != v["bytes"] or sha256_file(preview_path) != v["sha256"]:
            raise ValueError("preview integrity mismatch")
        if v["bytes"] > data["max_item_bytes"]:
            raise ValueError("oversized preview")
    v = data["overview"]
    fp = _safe_path(packet, v["path"])
    if fp.stat().st_size != v["bytes"] or sha256_file(fp) != v["sha256"]:
        raise ValueError("overview integrity mismatch")
    return {"schema": SCHEMA, "assets": len(data["assets"]), "tiles": sum(len(i["tiles"]) for i in data["assets"]), "status": "PASS_BYTES_AND_PIXELS_ONLY"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    pack = commands.add_parser("pack")
    pack.add_argument("--out", type=Path, required=True)
    pack.add_argument("--asset", action="append", required=True, help="LABEL=absolute source image path")
    pack.add_argument("--max-item-kib", type=int, default=400)
    verify = commands.add_parser("verify")
    verify.add_argument("--packet", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "pack":
        assets = []
        for spec in args.asset:
            if "=" not in spec:
                parser.error("asset must be LABEL=/path/to/image")
            label, path = spec.split("=", 1)
            assets.append((label, Path(path)))
        result = build_packet(assets, args.out.resolve(), args.max_item_kib * 1024)
        print(json.dumps({"out": str(args.out.resolve()), "assets": len(result["assets"]), **verify_packet(args.out.resolve())}, ensure_ascii=False))
    else:
        print(json.dumps(verify_packet(args.packet.resolve()), ensure_ascii=False))


if __name__ == "__main__":
    main()
"""Stage the Photoshop finishing inputs for one variant (ASCII working folder).

Inputs : Blender beauty (4800x2700), ID pass, DEPTH pass, ChatGPT raw edit (1672x941), CC0 textures.
Outputs: blender_base.png, gpt_raw.png, relit_tower.png, mask_*.png, tex_*.png into --work-dir.

relit_tower = Blender exact geometry x (blurred ChatGPT tone / blurred Blender tone): it keeps the verified
facade rhythm (fins, slab edges, columns) and borrows only the photographic low-frequency light/colour.
Run with system Python (Pillow + numpy):  python tools/t14q/prepare_photoshop_inputs.py ...
"""
from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

Image.MAX_IMAGE_PIXELS = None
CLASS_RGB = {  # ID pass colours after the Standard view transform (sRGB-encoded linear 0/0.3/0.5/0.6/0.8/1)
    "design_architecture": (255, 0, 0), "design_site": (255, 188, 0), "context_building": (0, 0, 255),
    "context_road": (188, 188, 188), "context_sidewalk": (231, 231, 231), "context_ground": (149, 149, 149),
    "context_green": (0, 203, 0), "context_tree": (0, 255, 0),
}


def class_mask(idm: np.ndarray, name: str, tol: int = 30) -> np.ndarray:
    return np.abs(idm.astype(np.int16) - np.array(CLASS_RGB[name], dtype=np.int16)).sum(2) < tol


def save_gray(a: np.ndarray, path: Path, blur: float = 0.0) -> None:
    im = Image.fromarray(np.clip(a * 255.0, 0, 255).astype(np.uint8), "L")
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    im.save(path)


def hp_texture(jpg: Path, scale: float, size: tuple[int, int]) -> Image.Image:
    t = Image.open(jpg).convert("L")
    t = t.resize((max(8, int(t.width * scale)), max(8, int(t.height * scale))), Image.LANCZOS)
    a = np.asarray(t, dtype=np.float32)
    low = np.asarray(t.filter(ImageFilter.GaussianBlur(max(2, 14 * scale))), dtype=np.float32)
    hp = np.clip(128 + (a - low) * 1.8, 0, 255).astype(np.uint8)
    tile = Image.fromarray(hp, "L")
    out = Image.new("L", size, 128)
    for y in range(0, size[1], tile.height):
        for x in range(0, size[0], tile.width):
            out.paste(tile, (x, y))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True)
    ap.add_argument("--base", type=Path, required=True)
    ap.add_argument("--id", type=Path, required=True)
    ap.add_argument("--depth", type=Path, required=True)
    ap.add_argument("--gpt", type=Path, required=True)
    ap.add_argument("--tex-dir", type=Path, required=True)
    ap.add_argument("--work-dir", type=Path, required=True)
    ap.add_argument("--blur", type=float, default=28.0)
    a = ap.parse_args()
    w = a.work_dir
    w.mkdir(parents=True, exist_ok=True)
    base = Image.open(a.base).convert("RGB")
    W, H = base.size
    base.save(w / "blender_base.png")
    shutil.copyfile(a.gpt, w / "gpt_raw.png")
    idm = np.asarray(Image.open(a.id).convert("RGB"))
    dep = np.asarray(Image.open(a.depth).convert("RGB"))[..., 0].astype(np.float32) / 255.0

    tower = class_mask(idm, "design_architecture", 60)
    road = class_mask(idm, "context_road")
    walk = class_mask(idm, "context_sidewalk") | class_mask(idm, "context_ground")
    save_gray(tower.astype(np.float32), w / "mask_tower.png", blur=1.2)
    save_gray(road.astype(np.float32), w / "mask_road.png", blur=1.0)
    save_gray(walk.astype(np.float32), w / "mask_walk.png", blur=1.0)
    # distance haze mask: nearer = 0, farther = 1 (depth pass maps 150..1800 m to 0..1)
    far = np.clip((dep - 0.12) / 0.70, 0.0, 1.0) ** 1.4
    save_gray(far, w / "mask_depth.png", blur=4.0)
    # edge vignette (white at the frame edge) for lens softening / darkening
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2)) / math.sqrt(2)
    save_gray(np.clip((r - 0.45) / 0.55, 0, 1) ** 1.8, w / "mask_vignette.png", blur=20.0)

    # --- relit tower: exact Blender detail x photographic low-frequency tone from ChatGPT ---
    gpt_up = Image.open(a.gpt).convert("RGB").resize((W, H), Image.LANCZOS)
    gb = np.asarray(base.filter(ImageFilter.GaussianBlur(a.blur)), dtype=np.float32) + 6.0
    gg = np.asarray(gpt_up.filter(ImageFilter.GaussianBlur(a.blur)), dtype=np.float32) + 6.0
    ratio = np.clip(gg / gb, 0.35, 2.6)
    relit = np.clip(np.asarray(base, dtype=np.float32) * ratio, 0, 255).astype(np.uint8)
    Image.fromarray(relit).save(w / "relit_tower.png")
    # facade (non-concrete) part of the tower: concrete = bright and desaturated in the Blender base
    b = np.asarray(base, dtype=np.float32) / 255.0
    mx, mn = b.max(2), b.min(2)
    sat = (mx - mn) / (mx + 1e-4)
    concrete = tower & (mx > 0.5) & (sat < 0.14)
    facade = tower & ~concrete
    fm = facade.astype(np.float32)
    if a.variant == "bluehour":
        # night: do not let the restore layer overwrite dark openings / glowing lobbies (ChatGPT's light stays there)
        lum = 0.299 * b[..., 0] + 0.587 * b[..., 1] + 0.114 * b[..., 2]
        fm *= np.clip((lum - 0.11) / 0.28, 0.0, 1.0)
    save_gray(fm, w / "mask_facade.png", blur=1.5)
    # --- CC0 scanned micro-texture (high-pass, mid-grey based) ---
    save = {"asphalt": a.tex_dir / "asphalt_02_diffuse_2k.jpg", "paving": a.tex_dir / "concrete_pavement_02_diffuse_2k.jpg"}
    for k, p in save.items():
        hp_texture(p, 0.5, (W, H)).save(w / f"tex_{k}.png")
    info = {"variant": a.variant, "size": [W, H], "tower_px": int(tower.sum()), "facade_px": int(facade.sum()),
            "concrete_px": int(concrete.sum()), "road_px": int(road.sum()), "walk_px": int(walk.sum()),
            "relight_blur_px": a.blur, "ratio_p5_p95": [float(np.percentile(ratio, 5)), float(np.percentile(ratio, 95))]}
    (w / "prep_info.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    print(json.dumps(info, indent=1))
    print("work dir:", w.resolve())


if __name__ == "__main__":
    main()

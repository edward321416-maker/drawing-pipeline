"""Region index + pixel-exact focus crops for a C-T14R packet (additive; never rewrites packet evidence).

For every named review region it lists the packet tiles that intersect it, and it exports small lossless PNG focus
crops (<= byte budget) cut from the ORIGINAL images at native pixel scale.  Region boxes are in the original image's
pixel coordinates (top-left origin).  Boxes were placed by visual inspection and are approximate, not CAD references.

  python -m tools.t14r.region_index --packet docs/t14r_visual_review/G002_C_T14Q_R1 \
      --source DAYLIGHT_FINAL=<png> --source BLUEHOUR_FINAL=<png> [--reference DAYLIGHT_FINAL=<png> ...]
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None
BUDGET = 400 * 1024

# (id, Korean name, [boxes], what to look for)
REGIONS = [
    ("R1_roof", "지붕 원형 개구부와 옥상 정원", [(1560, 30, 3300, 480)], "원형 개구 4개, 옥상 원통 구조물, 옥상 정원 윤곽, 지붕 모서리"),
    ("R2_fins", "상층부 수직 파사드 핀", [(1650, 480, 2230, 1250), (2380, 480, 3260, 1250)], "수직 핀 간격·개수와 수평 띠 위치. C-T14Q 검수의 미해결 항목"),
    ("R3_mid_void", "중층부 보이드와 정원", [(1700, 1150, 3250, 1480)], "중층 개방 슬롯, 기둥, 정원 식재, 슬롯 안 원통"),
    ("R4_cores", "코너 코어", [(2140, 280, 2380, 2280), (3150, 200, 3300, 1900), (1540, 60, 1690, 1750)], "화면에서 보이는 코어 3개. 네 번째 코어는 이 카메라에서 가려짐"),
    ("R5_tubes", "수직 튜브 (T1–T4 계열, 지붕·중층·지상)", [(2150, 100, 3050, 430), (2450, 1200, 3150, 1480), (2500, 1780, 2800, 2080)], "원통형 튜브의 지붕 상단, 중층 슬롯, 지상 진입부. T1–T4 번호 대응은 도면 대조가 필요"),
    ("R6_entrance", "저층부 진입 램프와 1층 기둥", [(2150, 1750, 3000, 2330)], "램프 쐐기, 1층 기둥열, 캐노피, 선큰 진입"),
    ("R7_streets", "건물 주변 도로·횡단보도", [(500, 2000, 4800, 2700)], "차로, 차선, 횡단보도, 보도, 가로수 배치"),
    ("R8_context", "실제 위치와 연결되는 도시 맥락", [(0, 0, 1560, 900), (3300, 150, 4800, 1800)], "이웃 건물 규모감, 스카이라인, 유리 커튼월 건물. 높이 다수는 가정값"),
]
# focus crops: (id, region, x, y, size) ; same coordinates for both variants (same camera)
FOCUS = [
    ("F01_fins_right_upper", "R2_fins", 2544, 544), ("F02_fins_right_lower", "R2_fins", 2500, 1560), ("F03_fins_left_upper", "R2_fins", 1700, 700),
    ("F04_roof_left_opening", "R1_roof", 1760, 20), ("F05_roof_tubes", "R5_tubes", 2300, 100), ("F06_roof_right_cylinder_garden", "R1_roof", 2780, 40),
    ("F07_mid_slot_right", "R3_mid_void", 2450, 1150), ("F08_mid_notch_left", "R3_mid_void", 1850, 1150),
    ("F09_core_front", "R4_cores", 2004, 900), ("F10_core_right", "R4_cores", 2980, 600),
    ("F11_tube_ground", "R5_tubes", 2450, 1760), ("F12_entrance_ramp", "R6_entrance", 2200, 1900),
    ("F13_crosswalk_plaza_edge", "R7_streets", 1700, 2188), ("F14_avenue_trees_cars", "R7_streets", 3500, 2000),
    ("F15_context_skyline", "R8_context", 300, 100), ("F16_context_glass_tower", "R8_context", 3600, 700),
]
REFERENCE_FOCUS = ("F01_fins_right_upper", "F02_fins_right_lower", "F03_fins_left_upper")  # final vs Blender base


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _png_under_budget(image: Image.Image, x: int, y: int, size: int, budget: int) -> tuple[bytes, tuple[int, int, int, int]]:
    while True:
        box = (x, y, min(x + size, image.width), min(y + size, image.height))
        crop = image.crop(box)
        buf = io.BytesIO()
        crop.save(buf, "PNG", optimize=True)
        if buf.tell() <= budget or size <= 64:
            return buf.getvalue(), box
        size = int(size * 0.92)


def _intersects(a: tuple, b: tuple) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def build_index(packet: Path, sources: dict[str, Path], references: dict[str, Path], budget: int = BUDGET, focus: list = FOCUS) -> dict:
    manifest = json.loads((packet / "manifest.json").read_text(encoding="utf-8"))
    out: dict = {"schema": "C-T14R-REGION-INDEX-1.0", "note": "Boxes are approximate (visual placement). Focus crops are pixel-exact cuts of the originals.",
                 "regions": [], "focus": []}
    tiles_by_asset = {a["label"]: a["tiles"] for a in manifest["assets"]}
    for rid, name, boxes, look in REGIONS:
        entry = {"id": rid, "name_ko": name, "look_for": look, "boxes": [list(b) for b in boxes], "tiles": {}}
        for label, tiles in tiles_by_asset.items():
            hit = [t for t in tiles if any(_intersects(tuple(t["bounds"]), b) for b in boxes)]
            entry["tiles"][label] = [{"path": t["path"], "bounds": t["bounds"], "sha256": t["sha256"]} for t in hit]
        out["regions"].append(entry)
    focus_dir = packet / "focus"
    focus_dir.mkdir(exist_ok=False)
    cache: dict[Path, Image.Image] = {}

    def load(path: Path) -> Image.Image:
        if path not in cache:
            with Image.open(path) as im:
                cache[path] = im.convert("RGB")
        return cache[path]

    for fid, rid, x, y in focus:
        for label, src in list(sources.items()) + [(k + "__REFERENCE_BLENDER_BASE", v) for k, v in references.items() if fid in REFERENCE_FOCUS]:
            image = load(src)
            payload, box = _png_under_budget(image, x, y, 512, budget)
            name = f"{fid}__{label}__x{box[0]:05d}_y{box[1]:05d}_w{box[2]-box[0]:04d}_h{box[3]-box[1]:04d}.png"
            (focus_dir / name).write_bytes(payload)
            out["focus"].append({"id": fid, "region": rid, "asset": label, "path": f"focus/{name}", "bounds": list(box), "bytes": len(payload),
                                 "sha256": _sha(payload), "role": "reference (Blender base, same pixels box)" if "REFERENCE" in label else "final"})
    (packet / "regions.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return out


def verify_focus(packet: Path, sources: dict[str, Path], references: dict[str, Path], budget: int = BUDGET) -> dict:
    data = json.loads((packet / "regions.json").read_text(encoding="utf-8"))
    paths = {**{k: v for k, v in sources.items()}, **{k + "__REFERENCE_BLENDER_BASE": v for k, v in references.items()}}
    bad = 0
    for f in data["focus"]:
        p = packet / f["path"]
        raw = p.read_bytes()
        if _sha(raw) != f["sha256"] or len(raw) > budget:
            bad += 1
            continue
        with Image.open(paths[f["asset"]]) as src, Image.open(p) as crop:
            if crop.convert("RGB").tobytes() != src.convert("RGB").crop(tuple(f["bounds"])).tobytes():
                bad += 1
    return {"focus_crops": len(data["focus"]), "mismatches": bad, "status": "PASS_FOCUS_PIXELS_EXACT" if bad == 0 else "FAIL"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--packet", type=Path, required=True)
    ap.add_argument("--source", action="append", required=True, help="LABEL=final image path (labels as in manifest)")
    ap.add_argument("--reference", action="append", default=[], help="LABEL=Blender base image path (fin comparison crops)")
    a = ap.parse_args()
    sources = dict(s.split("=", 1) for s in a.source)
    refs = dict(s.split("=", 1) for s in a.reference)
    sources = {k: Path(v) for k, v in sources.items()}
    refs = {k: Path(v) for k, v in refs.items()}
    packet = a.packet.resolve()
    build_index(packet, sources, refs)
    print(json.dumps(verify_focus(packet, sources, refs), ensure_ascii=False))


if __name__ == "__main__":
    main()

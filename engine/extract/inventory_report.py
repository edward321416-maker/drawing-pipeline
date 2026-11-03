# FILE: extract/inventory_report.py
from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path

INVENTORY_SCRIPT = Path(__file__).with_name("blender_inventory.py")


def group_prefix(name: str) -> str:
    """이름에서 숫자 성분을 지워 같은 종류의 객체끼리 묶는다 (CafeSet_2_Chair_3 -> CafeSet_Chair)."""
    return re.sub(r"[_.]\d+(?=[_.]|$)", "", name)


def group_inventory(items) -> list[dict]:
    groups: dict[str, dict] = {}
    for it in items:
        g = groups.setdefault(group_prefix(it["name"]), {
            "prefix": group_prefix(it["name"]), "count": 0, "types": set(), "tagged": 0,
            "kinds": set(), "bbox_min": None, "bbox_max": None,
        })
        g["count"] += 1
        g["types"].add(it["type"])
        kind = (it.get("props") or {}).get("kind")
        if kind:
            g["tagged"] += 1
            g["kinds"].add(str(kind))
        if "bbox_min" in it:
            if g["bbox_min"] is None:
                g["bbox_min"], g["bbox_max"] = list(it["bbox_min"]), list(it["bbox_max"])
            else:
                g["bbox_min"] = [min(a, b) for a, b in zip(g["bbox_min"], it["bbox_min"])]
                g["bbox_max"] = [max(a, b) for a, b in zip(g["bbox_max"], it["bbox_max"])]
    out = []
    for g in groups.values():
        g["types"] = sorted(g["types"])
        g["kinds"] = sorted(g["kinds"])
        out.append(g)
    return sorted(out, key=lambda g: (-g["count"], g["prefix"]))


def _range(lo, hi, axis):
    return "-" if lo is None else f"{lo[axis]:.1f} ~ {hi[axis]:.1f}"


def render_markdown(groups, blend_path) -> str:
    total = sum(g["count"] for g in groups)
    tagged = sum(g["tagged"] for g in groups)
    lines = [
        "# Blender 모델 감사 보고서",
        "",
        f"- 대상 파일: `{blend_path}`",
        f"- 총 객체: {total} / 태그됨: {tagged} / 태그 없음: {total - tagged}",
        "",
        "| 이름 묶음 | 개수 | 타입 | 태그됨 | kind | X 범위(m) | Y 범위(m) | Z 범위(m) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for g in groups:
        lines.append(
            f"| {g['prefix']} | {g['count']} | {','.join(g['types'])} | {g['tagged']} | "
            f"{','.join(g['kinds']) or '-'} | {_range(g['bbox_min'], g['bbox_max'], 0)} | "
            f"{_range(g['bbox_min'], g['bbox_max'], 1)} | {_range(g['bbox_min'], g['bbox_max'], 2)} |"
        )
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    from extract.run_blender import run_blender_script

    ap = argparse.ArgumentParser(description="기존 .blend의 객체 목록과 태그 현황을 감사한다")
    ap.add_argument("--blend", required=True)
    ap.add_argument("--out-md", required=True)
    args = ap.parse_args(argv)

    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "inventory.json"
        run_blender_script(args.blend, INVENTORY_SCRIPT, raw)
        items = json.loads(raw.read_text(encoding="utf-8"))["objects"]
    groups = group_inventory(items)
    out = Path(args.out_md)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown(groups, os.path.abspath(args.blend)), encoding="utf-8")
    print(f"감사 보고서: {os.path.abspath(out)}")
    return 0


if __name__ == "__main__":
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    raise SystemExit(main())

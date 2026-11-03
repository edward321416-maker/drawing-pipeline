"""G1/T1.1: 1층 출입문 앵커의 출처를 보수적으로 분류한다.

문을 생성하거나 3D 마스터를 수정하지 않는다. 실제 1F 절단 JSON이 없으면
출처만 검사하며, 기하 검증 통과로 표시하지 않는다. 렌더러에서 생성한
커튼월·캡슐 출입문은 물리 3D 모델의 문으로 간주하지 않는다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_SOURCE = ROOT / "engine" / "model" / "m_1f_source.json"
DEFAULT_SITE = ROOT / "engine" / "model" / "m_site_source.json"
DEFAULT_SPEC = ROOT / "docs" / "plans" / "2026-11-03_1f_program_spec.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _polygon_from_segments(segments: list):
    """저장소의 기존 벡터 절단 복원 함수를 재사용한다."""
    from src.pipeline_common import polygons_from_segments
    return polygons_from_segments(segments)


def _zone_geom(sl: dict, name: str):
    for item in sl.get("zones", []):
        if item.get("name") == name:
            return _polygon_from_segments(item.get("segments", []))
    return Polygon()


def _capsule_geom(sl: dict):
    """캡슐의 tube_wall 모델 객체에서 외곽선만 얻는다."""
    for item in sl.get("elements", []):
        if item.get("kind") != "tube_wall":
            continue
        if item.get("name") == "Capsule_W" or "서측 캡슐" in item.get("name_ko", ""):
            g = _polygon_from_segments(item.get("segments", []))
            if g.is_empty:
                continue
            polys = [g] if g.geom_type == "Polygon" else list(getattr(g, "geoms", []))
            polys = [p for p in polys if p.geom_type == "Polygon"]
            if polys:
                return Polygon(max(polys, key=lambda x: x.area).exterior)
    return Polygon()


def audit(source: dict, site: dict, spec: dict, slice_data: dict | None = None) -> dict:
    """문 객체와 외피의 근접성을 조사하되 물리적 출입문을 단정하지 않는다."""
    errors: list[str] = []
    notes: list[str] = []
    ref_entries = {e.get("key") for e in site.get("entrances", [])}
    proposed = {x.get("id"): x for x in spec.get("anchors", [])}
    if len(source.get("columns", [])) != 34:
        errors.append("기준 구조기둥 34개와 불일치 (소스 변경 여부 확인 필요)")
    for key in ("Main", "Subway", "Service"):
        if key not in ref_entries:
            errors.append(f"대지 진입 참조 누락: {key}")
    for key in ("PUBLIC_MARKET_DOOR", "CAPSULE_DOOR"):
        if proposed.get(key, {}).get("status") != "VERIFY_REQUIRED":
            errors.append(f"미검증 문 앵커를 확정한 것처럼 표기: {key}")

    anchors = {
        "PUBLIC_MARKET_DOOR": {
            "status": "UNVERIFIED_MODEL_OPENING",
            "source": "renderer_computed_curtainwall_doors",
            "source_door_candidates": [],
            "model_opening_verified": False,
        },
        "CAPSULE_DOOR": {
            "status": "UNVERIFIED_MODEL_OPENING",
            "source": "renderer_projected_capsule_entry",
            "source_door_candidates": [],
            "model_opening_verified": False,
        },
    }
    result = {
        "phase": "G1_T1_1_SOURCE_ANCHOR_AUDIT",
        "state": "BLOCKED_PENDING_PHYSICAL_DOOR_VERIFICATION",
        "floor": "1F",
        "model_inventory": {
            "columns": len(source.get("columns", [])),
            "cores": sorted(source.get("stairs", {})),
            "toilets": sorted(source.get("wc", {})),
        },
        "site_entry_markers": sorted(ref_entries),
        "site_markers_are_physical_doors": False,
        "raw_slice_read": slice_data is not None,
        "model_door_symbols": [],
        "anchors": anchors,
        "errors": errors,
        "notes": notes,
    }

    if slice_data is None:
        notes.append("원본 1층 floor_1F_slice.json 미제공: 실제 문 위치/외피 기하 미검증")
    elif slice_data.get("floor") != "1F":
        errors.append("1층이 아닌 절단 데이터 입력")
    else:
        hall = _zone_geom(slice_data, "Zone_Market")
        cap = _capsule_geom(slice_data)
        if hall.is_empty:
            errors.append("1층 절단 데이터에서 Zone_Market 구역을 찾지 못함")
        if cap.is_empty:
            errors.append("1층 절단 데이터에서 Capsule_W 외피를 찾지 못함")
        for symbol in slice_data.get("symbols", []):
            if symbol.get("category") != "door":
                continue
            props = symbol.get("props") or {}
            geom = _polygon_from_segments(symbol.get("segments", []))
            record = {
                "name": symbol.get("name"),
                "kind": "door",
                "core_id": props.get("core_id"),
                "wc_id": props.get("wc_id"),
                "has_footprint": not geom.is_empty,
                "near_market_boundary": False,
                "near_capsule_boundary": False,
                "classification": (
                    "INTERIOR_DOOR" if props.get("core_id") or props.get("wc_id")
                    else "OTHER_MODEL_DOOR"
                ),
            }
            if not geom.is_empty:
                if not hall.is_empty:
                    record["near_market_boundary"] = bool(geom.distance(hall.boundary) <= 0.35)
                if not cap.is_empty:
                    record["near_capsule_boundary"] = bool(geom.distance(cap.boundary) <= 0.35)
            result["model_door_symbols"].append(record)
            if record["classification"] == "OTHER_MODEL_DOOR":
                if record["near_market_boundary"]:
                    anchors["PUBLIC_MARKET_DOOR"]["source_door_candidates"].append(record["name"])
                if record["near_capsule_boundary"]:
                    anchors["CAPSULE_DOOR"]["source_door_candidates"].append(record["name"])
        notes.append("문 근접 후보가 존재해도 외피의 실제 개구/연속성이 증명되기 전에는 미확정")
        notes.append("코어·화장실 문을 시장·캡슐 출입문 후보로 승격하지 않음")

    notes.append("1층 도면 QA의 커튼월 문 5개는 렌더러 산출 통계이지 3D 마스터 문 개수가 아님")
    notes.append("시장/캡슐 출입문은 실제 모델 개구/문을 만들어 검증하거나 원본에서 증거를 확보해야 함")
    result["ok_source_references"] = not errors
    result["gate_passed"] = False
    result["user_final_freeze"] = False
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--site", type=Path, default=DEFAULT_SITE)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--slice", type=Path, help="1F 실제 절단 JSON. 없으면 소스만 검사")
    parser.add_argument("--out", type=Path, help="선택: 보고서 JSON. 기존 모델/출력은 변경하지 않음")
    args = parser.parse_args()
    report = audit(
        load_json(args.source),
        load_json(args.site),
        load_json(args.spec),
        load_json(args.slice) if args.slice else None,
    )
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report["ok_source_references"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

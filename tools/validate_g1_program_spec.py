"""1층 프로그램 G1 데이터의 출처·참조 무결성을 검사한다.

주의: 이 검사는 프로그램 기획 데이터 검사이며 실측 기하/피난 법규 판정이 아니다.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SPEC = ROOT / "docs" / "plans" / "2026-11-03_1f_program_spec.json"
DEFAULT_MASTER = ROOT / "engine" / "model" / "m_1f_source.json"
DEFAULT_SITE = ROOT / "engine" / "model" / "m_site_source.json"


def read_json(path: Path) -> dict:
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def validate(spec: dict, master: dict, site: dict) -> dict:
    """모델에서 확인할 수 있는 원천 참조와 제안 스펙의 내부 일관성만 확인한다."""
    errors: list[str] = []
    pending: list[str] = []
    checks = 0

    def expect(condition: bool, label: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            errors.append(label)

    expect(spec.get("schema") == "G1_PROGRAM_V1", "지원하지 않는 프로그램 스키마")
    expect(spec.get("state") == "PROPOSED_UNAPPROVED", "승인되지 않은 기획이 승인된 것처럼 표시됨")
    expect(spec.get("floor") == "1F", "1F 전용 설계 계획이 아님")
    rules = spec.get("safety_and_geometry") or {}
    expect(rules.get("absolute_drawing_coordinates_allowed") is False, "그림 코드의 절대 좌표 금지 원칙 누락")
    expect(rules.get("area_source") == "DERIVE_FROM_COMPUTED_SHAPELY_POLYGONS_ONLY",
           "면적 계산은 Shapely 모델 폴리곤을 사용해야 함")
    expect(rules.get("source_model_modification_authorized") is False, "승인되지 않은 원천 모델 수정 허용")
    expect(rules.get("program_polygons_computed") is False, "미생성 구획을 이미 계산했다고 표기함")
    expect(rules.get("physical_doors_resolved") is False, "검증 전 도어 위치가 확정됐다고 표기함")

    inv = spec.get("verified_model_inventory") or {}
    expect(inv.get("column_count") == len(master.get("columns", [])),
           "기둥 개수가 마스터 소스와 불일치")
    expect(set(inv.get("cores", [])) == set(master.get("stairs", {})),
           "코어 ID가 마스터와 불일치")
    expect(set(inv.get("toilets", [])) == set(master.get("wc", {})),
           "화장실 ID가 마스터와 불일치")
    expect(set(inv.get("tubes", [])) == {x for x in master.get("tubes", {}) if x.startswith("T")},
           "T1~T4 구성이 마스터와 불일치")
    expect(set(inv.get("shafts", [])) == set(master.get("small", [])),
           "소형 샤프트 목록이 마스터와 불일치")
    actual_entries = {e.get("key") for e in site.get("entrances", [])}
    expect(set(inv.get("entrance_keys", [])) == actual_entries,
           "진입 경로가 실제 대지 마스터와 불일치")

    anchors = spec.get("anchors", [])
    anchor_ids: set[str] = set()
    for a in anchors:
        aid = a.get("id")
        expect(bool(aid) and aid not in anchor_ids, f"중복/누락 앵커 ID {aid}")
        anchor_ids.add(aid)
        kind, ref = a.get("kind"), a.get("model_ref")
        if kind == "SITE_ENTRANCE":
            expect(ref in actual_entries, f"대지 진입 앵커 없음: {aid}")
        elif kind == "TUBE":
            expect(ref in master.get("tubes", {}), f"원형 튜브 앵커 없음: {aid}")
        elif kind == "SHAFT":
            expect(ref in master.get("small", []), f"샤프트 앵커 없음: {aid}")
        elif kind == "DOOR_FROM_ACTUAL_SLICE":
            expect(ref is None and a.get("status") == "VERIFY_REQUIRED",
                   f"실측하지 않은 문을 확인된 것으로 표기: {aid}")
            pending.append(f"{aid}: 실제 1F 도어·커튼월 절단 결과 확인 필요")
        else:
            errors.append(f"지원하지 않는 앵커 종류: {aid}/{kind}")

    valid_parents = {
        "MARKET": "Zone_Market",
        "PILOTI": "Zone_Piloti",
        "SERVICE": "Zone_Service",
        "CAPSULE": "Capsule_W",
    }
    seen_ids: set[str] = set(anchor_ids)
    parents: set[str] = set()
    for group in spec.get("programs", []):
        gid = group.get("id")
        expect(gid in valid_parents and gid not in parents, f"부모 프로그램 ID 오류: {gid}")
        parents.add(gid)
        expect(group.get("source_zone") == valid_parents.get(gid), f"모델 구역 매핑 불일치: {gid}")
        children = group.get("subprograms", [])
        expect(bool(children), f"하위 프로그램이 없음: {gid}")
        total = 0.0
        for item in children:
            sid = item.get("id")
            expect(bool(sid) and sid not in seen_ids, f"중복/누락 하위 ID: {sid}")
            seen_ids.add(sid)
            val = item.get("soft_target_share")
            expect(isinstance(val, (int, float)) and not isinstance(val, bool) and 0 < val <= 1,
                   f"면적 배분 가중치 오류: {sid}")
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                total += val
            expect(bool(item.get("activities")) and bool(item.get("spatial_rule")),
                   f"공간 활동/배치 근거 누락: {sid}")
            expect(bool(item.get("allowable_furniture")), f"가구 요구(없음도 명시) 누락: {sid}")
            expect("area_m2" not in item and "coordinates" not in item,
                   f"미검증 면적/절대좌표 입력 금지: {sid}")
            for aid in item.get("anchors", []):
                expect(aid in anchor_ids, f"정의되지 않은 앵커 참조: {sid}->{aid}")
        expect(abs(total - 1.0) < 1.0e-8, f"{gid} 연성 분배 비율 합이 100%가 아님: {total}")
    expect(parents == set(valid_parents), "필수 부모 구역이 누락되었거나 추가됨")

    valid_relations = {"MUST_CONNECT", "SHOULD_CONNECT", "SHOULD_NEAR", "MUST_SEPARATE", "CONTROLLED_ONLY"}
    edges = set()
    for rel in spec.get("relationships", []):
        left, right, kind = rel.get("from"), rel.get("to"), rel.get("kind")
        expect(left in seen_ids and right in seen_ids and left != right,
               f"연결 관계 참조 오류: {left}->{right}")
        expect(kind in valid_relations, f"관계 종류 오류: {kind}")
        ident = (left, right, kind)
        expect(ident not in edges, f"연결 관계 중복: {ident}")
        edges.add(ident)
        expect(rel.get("evidence") == "PENDING_REAL_GEOMETRY",
               f"기하 검증 전 관계 확인을 선언함: {ident}")

    expect(("S01", "P01", "MUST_SEPARATE") in edges, "하역-필로티 공공 통로 분리 규칙 누락")
    expect(("S02", "M02", "CONTROLLED_ONLY") in edges, "하역-시장 통제 동선 규칙 누락")
    expect(("PUBLIC_MARKET_DOOR", "M01", "MUST_CONNECT") in edges,
           "실제 시장 출입문과 정보 구역의 연결 누락")

    pending += [
        "실제 source .blend SHA 및 재절단 미확인",
        "하위 구역 polygon/㎡ 미생성 (해당 단계에서는 합격 불가)",
        "입구→전망승강기 접근·피난/무장애 경로 검증 필요",
        "기둥 11개 도면 생략 및 계단 형식 불일치 별도 해결 필요",
    ]
    return {
        "ok": not errors,
        "phase": "G1_INTENT_PRECHECK_ONLY",
        "checks": checks,
        "parent_programs": len(parents),
        "subprograms": len(seen_ids - anchor_ids),
        "errors": errors,
        "pending_geometry_and_legal_checks": pending,
        "user_final_freeze": False,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    p.add_argument("--master", type=Path, default=DEFAULT_MASTER)
    p.add_argument("--site", type=Path, default=DEFAULT_SITE)
    a = p.parse_args()
    report = validate(read_json(a.spec), read_json(a.master), read_json(a.site))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

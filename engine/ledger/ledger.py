# FILE: ledger/ledger.py
from __future__ import annotations

from pathlib import Path

import yaml

DEFAULT_PATH = Path(__file__).with_name("ledger.yaml")


def load_ledger(path=None) -> list[dict]:
    raw = yaml.safe_load(Path(path or DEFAULT_PATH).read_text(encoding="utf-8"))
    return list(raw["defects"])


def audit_ledger(defects, registered_ids) -> list[str]:
    problems, seen = [], set()
    for d in defects:
        did = d.get("id", "?")
        if did in seen:
            problems.append(f"{did}: 장부 번호 중복")
        seen.add(did)
        checks, planned = d.get("checks") or [], d.get("planned_checks") or []
        if not checks and not planned:
            problems.append(f"{did}: 연결된 검사가 없음")
        for c in checks:
            if c not in registered_ids:
                problems.append(f"{did}: 검사 {c}가 등록되지 않음")
        for c in planned:
            if c in registered_ids:
                problems.append(f"{did}: 검사 {c}는 이미 구현됨 — planned_checks에서 checks로 옮길 것")
    return problems

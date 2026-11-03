# FILE: checks/base.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Violation:
    check: str
    message: str
    where: tuple[float, float] | None = None
    objects: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "check": self.check,
            "message": self.message,
            "where": list(self.where) if self.where else None,
            "objects": list(self.objects),
        }


def dedupe(violations):
    """같은 (검사, 객체쌍)의 위반은 첫 건만 남긴다(여러 높이에서 중복 보고 방지)."""
    seen, out = set(), []
    for v in violations:
        key = (v.check, v.objects)
        if key in seen:
            continue
        seen.add(key)
        out.append(v)
    return out

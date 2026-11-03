# FILE: checks/tags.py
from __future__ import annotations

from checks.base import Violation
from extract.schema import KINDS, REQUIRED_TAGS


def check_tags(model) -> list[Violation]:
    out = []
    for o in model.objects:
        where = o.center_xy if len(o.verts) else None
        for tag in REQUIRED_TAGS:
            value = o.props.get(tag)
            if value is None or str(value).strip() == "":
                out.append(Violation("TAG", f"객체 '{o.name}': 필수 태그 '{tag}' 없음", where, (o.name,)))
        if o.kind is not None and o.kind not in KINDS:
            out.append(Violation("TAG", f"객체 '{o.name}': 알 수 없는 kind '{o.kind}'", where, (o.name,)))
    return out

# FILE: checks/text.py
from __future__ import annotations

from shapely.geometry import box

from checks.base import Violation, dedupe
from render.style import LINE_CLASSES, TEXT_ROLES

EPS = 1e-6


def _text_box(t):
    return box(*t.bbox)


def _drawn_geometry(rec):
    # 채움 도형은 면 전체, 윤곽만 그린 도형은 경계선, 선은 그대로
    if rec.filled or rec.geom.geom_type in ("LineString", "MultiLineString"):
        return rec.geom
    return rec.geom.boundary


def _where(geom):
    c = geom.centroid
    return (round(c.x, 2), round(c.y, 2))


def check_t1_text_overlap(render, params) -> list[Violation]:
    out = []
    texts = render.texts
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            a, b = texts[i], texts[j]
            inter = _text_box(a).intersection(_text_box(b))
            if inter.area > params.text_collision_tolerance_m2:
                out.append(Violation(
                    "T1", f"텍스트 '{a.text}'와 '{b.text}' 겹침 ({inter.area:.2f} ㎡)",
                    _where(inter), (f"{a.owner}:{a.text}", f"{b.owner}:{b.text}")))
    return dedupe(out)


def check_t2_text_on_line(render, params) -> list[Violation]:
    """텍스트가 선(벽·기둥·계단·호·윤곽·치수선) 위에 얹히면 위반. 구조 격자는 흰 배경 박스로 가려지므로 제외."""
    out = []
    for t in render.texts:
        tb = _text_box(t)
        for rec in render.lines:
            if rec.klass == "grid":
                continue
            if rec.leader and rec.owner == t.owner:
                continue
            geom = _drawn_geometry(rec)
            if tb.intersects(geom):
                out.append(Violation(
                    "T2", f"텍스트 '{t.text}'가 {rec.klass} 선('{rec.owner}')과 겹침",
                    _where(tb.intersection(geom)), (f"{t.owner}:{t.text}", rec.owner)))
    return dedupe(out)


def check_t3_canvas(render, params) -> list[Violation]:
    out = []
    cx0, cy0, cx1, cy1 = render.canvas
    for t in render.texts:
        x0, y0, x1, y1 = t.bbox
        if x0 < cx0 - EPS or y0 < cy0 - EPS or x1 > cx1 + EPS or y1 > cy1 + EPS:
            out.append(Violation(
                "T3", f"텍스트 '{t.text}'가 캔버스 밖으로 잘림", (round((x0 + x1) / 2, 2), round((y0 + y1) / 2, 2)),
                (f"{t.owner}:{t.text}",)))
    return out


def check_t4_style(render, params) -> list[Violation]:
    out = []
    for t in render.texts:
        spec = TEXT_ROLES.get(t.role)
        if spec is None:
            out.append(Violation("T4", f"알 수 없는 텍스트 위계 '{t.role}'", None, (f"{t.owner}:{t.text}",)))
        elif not (spec.size_min - EPS <= t.size <= spec.size_max + EPS):
            out.append(Violation(
                "T4", f"텍스트 '{t.text}' 크기 {t.size} pt가 {t.role} 범위 {spec.size_min}~{spec.size_max} pt를 벗어남",
                None, (f"{t.owner}:{t.text}",)))
    for rec in render.lines:
        spec = LINE_CLASSES.get(rec.klass)
        if spec is None:
            out.append(Violation("T4", f"알 수 없는 선종 '{rec.klass}'", None, (rec.owner,)))
        elif not (spec.lw_min - EPS <= rec.lw <= spec.lw_max + EPS):
            out.append(Violation(
                "T4", f"'{rec.owner}' 선 두께 {rec.lw}가 {rec.klass} 범위 {spec.lw_min}~{spec.lw_max}를 벗어남",
                None, (rec.owner, rec.klass)))
    return dedupe(out)

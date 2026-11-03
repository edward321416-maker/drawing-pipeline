"""1F 마스터 모델 한 번에 만들기: 고정 데이터 -> 태그 모델 JSON -> .blend -> 3D 검토 렌더 -> 엔진 검사·평면 절단.

사용: python master\\pipeline.py
출력 폴더: 도면\\01_과정\\01_기획_구획_베이스 (통과) 또는 00_엔진\\_rejected (검사 실패). 02_최종결과물에는 쓰지 않는다.
"""
from __future__ import annotations

import os
import sys
from dataclasses import replace
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import numpy as np  # noqa: E402

from build import build  # noqa: E402
from engine_params import load_params  # noqa: E402
from extract.run_blender import run_blender_script  # noqa: E402
from master.build_master import build_master, write_model_json  # noqa: E402
from render.annotations import Annotation  # noqa: E402

MAKE_BLEND = Path(__file__).with_name("make_blend.py")
RENDER_REVIEW = Path(__file__).with_name("render_review.py")
BLEND = ENGINE / "model" / "1F_master.blend"
OUT_DIR = ENGINE.parent / "01_과정" / "01_기획_구획_베이스"
REJECTED = ENGINE / "_rejected"


PLAN_NAME = "1F_상세평면_마스터파생"  # 2단계(상세): 건물만, 1:200. 승인된 심볼만 상세로 조립. 승인된 1단계 단선 평면 파일은 건드리지 않는다
SITE_PLAN_NAME = "1F_전체도면_대지포함_마스터파생"  # 전체 1층 도면: 대지·도로·이웃 건물 포함, 1:400 (사용자 지시 2026-11-01)


def plan_annotation(model, params, site: bool = False) -> Annotation:
    """표제·방위표 내용. 치수와 각도는 모델에서 읽는다(직접 적지 않는다). 용지 크기는 적지 않는다(보고서에 계산해 둔다)."""
    slabs = model.by_kind("slab")
    lo = np.min([o.verts.min(axis=0) for o in slabs], axis=0)
    hi = np.max([o.verts.max(axis=0) for o in slabs], axis=0)
    w, d = round((hi[0] - lo[0]) * 1000, -1), round((hi[1] - lo[1]) * 1000, -1)  # 10 mm 단위로 반올림
    angle = float(model.meta["north_angle_deg"])
    if site:
        return Annotation(
            title="1F 전체 평면도 (대지 포함)",
            subtitle=f"리미노스케이프 | 건물 {w:,.0f} × {d:,.0f} mm | 1:{params.scale_denominator:g} | 쇄선 = 대지경계선 · 점선 = 건축한계선",
            north_angle_deg=angle,
        )
    return Annotation(
        title="1F 상세 평면도 (1F Detailed Plan)",
        subtitle=f"리미노스케이프 | {w:,.0f} × {d:,.0f} mm | 9 m 격자 | 1:{params.scale_denominator:g} | 상세 적용: 코어·화장실",
        north_angle_deg=angle,
    )


def main() -> int:
    params = load_params()
    model = build_master()
    model_json = write_model_json(model)
    run_blender_script(None, MAKE_BLEND, model_json, BLEND)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    run_blender_script(BLEND, RENDER_REVIEW, OUT_DIR)
    # 건물만(나머지 도면: 1:200)과 대지 포함 전체 1층 도면(1:400)을 같은 모델에서 각각 절단한다
    site_params = replace(params, scale_denominator=params.site_scale_denominator)
    reports = [
        ("건물 상세 평면", build(model_json, OUT_DIR, REJECTED, PLAN_NAME, params=params,
                                annotation=plan_annotation(model, params), detail=True)),
        ("전체 1층 도면(대지 포함)", build(model_json, OUT_DIR, REJECTED, SITE_PLAN_NAME, params=site_params,
                                        annotation=plan_annotation(model, site_params, site=True), detail=True,
                                        scope="site")),
    ]
    print(f"마스터 .blend: {os.path.abspath(BLEND)}")
    print(f"3D 검토 렌더 폴더: {os.path.abspath(OUT_DIR)}")
    for label, report in reports:
        print(f"[{label}] 엔진 검사: {'통과' if report.ok else '거부'}")
        if report.png_path:
            print(f"  평면 절단: {os.path.abspath(report.png_path)}")
        print(f"  보고서: {os.path.abspath(report.report_path)}")
        for v in report.violations:
            where = f" @ {v.where}" if v.where else ""
            print(f"  [{v.check}] {v.message}{where}")
    return 0 if all(r.ok for _l, r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())

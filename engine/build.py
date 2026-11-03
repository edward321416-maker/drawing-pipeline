# FILE: build.py
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from checks.base import Violation
from checks.registry import MODEL_CHECKS, RENDER_CHECKS, run_model_checks, run_render_checks
from checks.tags import check_tags
from engine_params import load_params
from extract.loader import load_model
from extract.slicer import slice_model
from layout.labels import LabelPlacementError
from render.plan_renderer import render_plan

ENGINE_ROOT = Path(__file__).parent
DEFAULT_OUT = ENGINE_ROOT.parent / "01_과정" / "01_기획_구획_베이스"
DEFAULT_REJECTED = ENGINE_ROOT / "_rejected"


@dataclass
class BuildReport:
    ok: bool
    violations: list
    png_path: Path | None
    report_path: Path
    checks_run: list


ISO_LANDSCAPE_MM = (("A4", 297, 210), ("A3", 420, 297), ("A2", 594, 420), ("A1", 841, 594), ("A0", 1189, 841))


def paper_fit(canvas, scale_denominator) -> dict:
    """캔버스(m)가 해당 축척에서 차지하는 종이 크기(mm)와, 그것이 들어가는 가장 작은 ISO 용지(가로 또는 세로)."""
    w = (canvas[2] - canvas[0]) / scale_denominator * 1000.0
    h = (canvas[3] - canvas[1]) / scale_denominator * 1000.0
    fit = next((n for n, pw, ph in ISO_LANDSCAPE_MM if (w <= pw and h <= ph) or (h <= pw and w <= ph)), "A0 초과")
    return {"scale": f"1:{scale_denominator:g}", "drawing_mm": [round(w, 1), round(h, 1)], "smallest_iso_paper": fit}


def build(model_json, out_dir, rejected_dir, name, params=None, annotation=None, detail=False,
          scope="building") -> BuildReport:
    params = params or load_params()
    model = load_model(model_json)
    violations = list(check_tags(model))
    checks_run = ["TAG"]
    rendered = None
    paper = None

    with tempfile.TemporaryDirectory() as tmp:
        if not violations:
            sections = slice_model(model, params.check_heights_m)
            violations += run_model_checks(sections, params)
            checks_run += list(MODEL_CHECKS)
            try:
                render = render_plan(sections, params, Path(tmp) / f"{name}.png", annotation=annotation, detail=detail,
                                     scope=scope)
                violations += run_render_checks(render, params)
                checks_run += list(RENDER_CHECKS)
                rendered = render.png_path
                paper = paper_fit(render.canvas, params.scale_denominator)   # 도면마다 호출하는 쪽이 축척을 정해 넘긴다
            except LabelPlacementError as exc:
                violations.append(Violation("LAYOUT", str(exc)))

        ok = not violations
        target = Path(out_dir if ok else rejected_dir)
        target.mkdir(parents=True, exist_ok=True)
        png_path = None
        if rendered is not None:
            png_path = target / f"{name}.png"
            shutil.copyfile(rendered, png_path)
        report_path = target / f"{name}.report.json"
        report_path.write_text(
            json.dumps(
                {
                    "name": name,
                    "ok": ok,
                    "source": os.path.abspath(model_json),
                    "scope": scope,
                    "paper": paper,
                    "checks_run": checks_run,
                    "violations": [v.to_dict() for v in violations],
                },
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )
    return BuildReport(ok, violations, png_path, report_path, checks_run)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="태그된 Blender 모델에서 검증된 평면도를 생성한다")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--blend", help="마스터 .blend 파일")
    src.add_argument("--model-json", help="이미 추출한 모델 JSON")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="통과본 저장 폴더")
    ap.add_argument("--rejected", default=str(DEFAULT_REJECTED), help="거부본 저장 폴더")
    ap.add_argument("--name", default="1F_plan")
    args = ap.parse_args(argv)

    with tempfile.TemporaryDirectory() as tmp:
        if args.blend:
            from extract.run_blender import export_model

            model_json = export_model(args.blend, Path(tmp) / "model.json")
        else:
            model_json = Path(args.model_json)
        report = build(model_json, args.out, args.rejected, args.name)

    print(f"결과: {'통과' if report.ok else '거부'}")
    if report.png_path:
        print(f"도면: {os.path.abspath(report.png_path)}")
    print(f"보고서: {os.path.abspath(report.report_path)}")
    for v in report.violations:
        where = f" @ {v.where}" if v.where else ""
        print(f"  [{v.check}] {v.message}{where}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())

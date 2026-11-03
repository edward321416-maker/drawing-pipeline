"""코어 심볼 시트 만들기: 중간발표 코어 4개의 치수로 심볼을 만들고, R1·G3·T 검사를 통과하면 01_과정에 저장한다.

사용: python master\\core_sheet.py
출력: 도면\\01_과정\\01_기획_구획_베이스\\1F_코어심볼_시트.png (+ .report.json). 실패하면 00_엔진\\_rejected에 저장한다.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

from build import BuildReport  # noqa: E402
from checks.registry import run_render_checks, run_symbol_checks  # noqa: E402
from engine_params import load_params  # noqa: E402
from master.build_master import load_adjustments, load_source  # noqa: E402
from render.symbol_sheet import build_sheet_cores, render_core_sheet  # noqa: E402

OUT_DIR = ENGINE.parent / "01_과정" / "01_기획_구획_베이스"
REJECTED = ENGINE / "_rejected"
SHEET_NAME = "1F_코어심볼_시트"


def sheet_texts(params, steps_required: int):
    p = params.stair
    title = "특별피난계단 코어 심볼 시트 (4갈래 ㅁ자)"
    subtitle = (f"유효폭 {p.flight_w_m * 1000:,.0f} mm · 디딤판 {p.tread_m * 1000:,.0f} mm · 챌면 {p.riser_m * 1000:,.0f} mm"
                f" · 층고 {p.floor_height_m:g} m → {steps_required}단 필요 · 축척 1:{p.sheet_scale_denominator:g}")
    legend = (f"실선 = 절단선({p.cut_height_m:g} m) 아래 디딤판 · 점선 = 절단선 위 · Z선 = 절단선 · "
              "호 = 문 열림(피난 방향) · 화살표 = 오름")
    return title, subtitle, legend


def build_core_sheet(out_dir=OUT_DIR, rejected_dir=REJECTED, name=SHEET_NAME, params=None) -> BuildReport:
    params = params or load_params()
    src = load_source()
    sizes = {cid: (b[2] - b[0], b[3] - b[1]) for cid, b in src["stairs"].items()}
    offsets = {cid: v["offset_m"] for cid, v in load_adjustments().get("core_hall_door_offset", {}).items()}
    cores = build_sheet_cores(sizes, params, offsets)
    violations, checks_run = [], ["R1", "G3"]
    for c in cores:
        violations += run_symbol_checks(c, params)
    title, subtitle, legend = sheet_texts(params, cores[0].steps_required)
    with tempfile.TemporaryDirectory() as tmp:
        render = render_core_sheet(cores, params, Path(tmp) / f"{name}.png", title, subtitle, legend)
        violations += run_render_checks(render, params)
        checks_run += ["T1", "T2", "T3", "T4"]
        ok = not violations
        target = Path(out_dir if ok else rejected_dir)
        target.mkdir(parents=True, exist_ok=True)
        png = target / f"{name}.png"
        shutil.copyfile(render.png_path, png)
        report = target / f"{name}.report.json"
        report.write_text(json.dumps({
            "name": name, "ok": ok, "checks_run": checks_run,
            "cores": {c.core_id: {"bounds": list(c.bounds), "ves_side": c.ves_side, "steps_provided": c.steps_provided,
                                  "steps_required": c.steps_required, "vestibule_m2": round(c.vestibule.area, 2)}
                      for c in cores},
            "violations": [v.to_dict() for v in violations],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    return BuildReport(ok, violations, png, report, checks_run)


def main() -> int:
    report = build_core_sheet()
    print(f"코어 심볼 시트: {'통과' if report.ok else '거부'}")
    print(f"도면: {os.path.abspath(report.png_path)}")
    print(f"보고서: {os.path.abspath(report.report_path)}")
    for v in report.violations:
        where = f" @ {v.where}" if v.where else ""
        print(f"  [{v.check}] {v.message}{where}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

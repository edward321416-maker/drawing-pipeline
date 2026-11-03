"""화장실 심볼 시트 만들기: 중간발표 화장실 두 방의 치수와 기둥으로 심볼을 만들고, R2·G3·T 검사를 통과하면 01_과정에 저장한다.

사용: python master\\restroom_sheet.py
출력: 도면\\01_과정\\01_기획_구획_베이스\\1F_화장실심볼_시트.png (+ .report.json). 실패하면 00_엔진\\_rejected에 저장한다.
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

from shapely.affinity import translate  # noqa: E402
from shapely.geometry import Point  # noqa: E402

from build import BuildReport  # noqa: E402
from checks.registry import run_render_checks, run_restroom_checks  # noqa: E402
from engine_params import load_params  # noqa: E402
from master.build_master import DU, DV, load_source, restroom_world_bounds  # noqa: E402
from render.restroom_sheet import build_sheet_restrooms, render_restroom_sheet  # noqa: E402

OUT_DIR = ENGINE.parent / "01_과정" / "01_기획_구획_베이스"
REJECTED = ENGINE / "_rejected"
SHEET_NAME = "1F_화장실심볼_시트"


def room_columns(src: dict, adjustments: dict | None = None) -> dict:
    """방 안(또는 벽가)의 구조 기둥을 방 외곽 기준 로컬 좌표로 돌려준다 (시트에서 방 위치에 맞춰 옮긴다).
    방 위치는 승인된 이동(restroom_shift)을 반영한다. adjustments={}이면 중간발표 원본 위치다."""
    out = {}
    for rid, (x0, y0, x1, y1) in restroom_world_bounds(src, adjustments).items():
        out[rid] = [(u + DU - x0, v + DV - y0) for u, v, *_ in src["columns"]
                    if x0 - 0.5 <= u + DU <= x1 + 0.5 and y0 - 0.5 <= v + DV <= y1 + 0.5]
    return out


def sheet_texts(params):
    p = params.restroom
    title = "화장실 심볼 시트 (B 공용·장애인 겸용, C 남·여·장애인)"
    subtitle = (f"큐비클 {p.cubicle_general_m[0]}×{p.cubicle_general_m[1]} m 이상 · 장애인 {p.cubicle_accessible_m[0]}×"
                f"{p.cubicle_accessible_m[1]} m 이상 · 회전 원 Ø{p.turning_circle_d_m} m · 세면대 카운터 {p.basin_w_m} m · "
                f"축척 1:{p.sheet_scale_denominator:g}")
    legend = "굵은 회색 = 방·구획벽 · 가는 검정 = 큐비클 칸막이 · 점선 원 = 회전 원 · 호 = 문 열림(피난 방향, 홀 쪽) · 점선 = 슬라이딩 문 이동 자리"
    return title, subtitle, legend


def build_restroom_sheet(out_dir=OUT_DIR, rejected_dir=REJECTED, name=SHEET_NAME, params=None) -> BuildReport:
    params = params or load_params()
    src = load_source()
    sizes = {rid: (b[2] - b[0], b[3] - b[1]) for rid, b in src["wc"].items()}
    local_cols = room_columns(src)
    # 시트에서는 방이 (x, 0)에 놓이므로 기둥도 같은 만큼 옮긴다
    shifted, x = {}, 0.0
    for rid in ("B", "C"):
        w, _d = sizes[rid]
        shifted[rid] = [translate(Point(cx, cy).buffer(src["col_r"], quad_segs=12), x, 0.0) for cx, cy in local_cols[rid]]
        x += w + 6.0
    rooms = build_sheet_restrooms(sizes, params, shifted)
    violations, checks_run = [], ["R2", "G3"]
    for rr in rooms:
        violations += run_restroom_checks(rr, params)
    title, subtitle, legend = sheet_texts(params)
    with tempfile.TemporaryDirectory() as tmp:
        render = render_restroom_sheet(rooms, params, Path(tmp) / f"{name}.png", title, subtitle, legend)
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
            "rooms": {rr.room_id: {"bounds": list(rr.bounds), "program": rr.program,
                                   "units": [u.name for u in rr.units], "fixtures": len(rr.fixtures)} for rr in rooms},
            "violations": [v.to_dict() for v in violations],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    return BuildReport(ok, violations, png, report, checks_run)


def main() -> int:
    report = build_restroom_sheet()
    print(f"화장실 심볼 시트: {'통과' if report.ok else '거부'}")
    print(f"도면: {os.path.abspath(report.png_path)}")
    print(f"보고서: {os.path.abspath(report.report_path)}")
    for v in report.violations:
        where = f" @ {v.where}" if v.where else ""
        print(f"  [{v.check}] {v.message}{where}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""튜브 심볼 시트 만들기: 중간발표 튜브(T1~T4, 서측 캡슐)의 위치·반지름과 실제 기둥으로 심볼을 만들고, R3·T 검사를 통과하면 01_과정에 저장한다.

사용: python master\\tube_sheet.py
출력: 도면\\01_과정\\01_기획_구획_베이스\\1F_튜브심볼_시트.png (+ .report.json). 실패하면 00_엔진\\_rejected에 저장한다.
마스터 모델에는 조립하지 않는다(시트 승인 뒤에 조립).
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

from shapely import wkt  # noqa: E402
from shapely.affinity import translate  # noqa: E402
from shapely.geometry import Point, Polygon  # noqa: E402

from build import BuildReport  # noqa: E402
from checks.registry import run_render_checks, run_tube_checks  # noqa: E402
from engine_params import load_params  # noqa: E402
from master.build_master import DU, DV, TUBE_NAMES, load_source  # noqa: E402
from render.tube_sheet import CAPSULE_ID, place_on_sheet, render_tube_sheet  # noqa: E402
from symbols.tube import build_capsule, build_elevator, build_light, build_ramp  # noqa: E402

OUT_DIR = ENGINE.parent / "01_과정" / "01_기획_구획_베이스"
REJECTED = ENGINE / "_rejected"
SHEET_NAME = "1F_튜브심볼_시트"
CAPSULE_LABEL = "서측 캡슐"
BUILDERS = {"T1": build_ramp, "T2": build_light, "T3": build_elevator, "T4": build_elevator}


def world_columns(src: dict) -> list:
    """마스터 모델과 같은 방식으로 만든 월드 좌표의 구조 기둥 폴리곤(전부)."""
    return [Point(u + DU, v + DV).buffer(src["col_r"], quad_segs=12) for u, v, *_ in src["columns"]]


def world_envelope(src: dict) -> Polygon:
    """건물 외곽(1층 바닥판의 바깥 윤곽, 월드 좌표)."""
    return Polygon(translate(wkt.loads(src["wkt"]["plate_1f"]), DU, DV).exterior)


def build_world_tubes(src: dict, params) -> dict:
    """{id: 월드 좌표의 튜브}. 각 튜브는 가까운 실제 기둥(범위 = params.tube.context_column_m)을 함께 갖는다."""
    p = params.tube
    cols, env = world_columns(src), world_envelope(src)

    def near(shape):
        return [c for c in cols if c.distance(shape) <= p.context_column_m]

    out = {}
    for tid, builder in BUILDERS.items():
        t = src["tubes"][tid]
        c, r = (t["c"][0] + DU, t["c"][1] + DV), t["r"]
        footprint = Point(*c).buffer(r)
        out[tid] = builder(tid, TUBE_NAMES[tid], c, r, params.tube, near(footprint), env)
    cap = translate(wkt.loads(src["wkt"]["cap_w"]), DU, DV)
    out[CAPSULE_ID] = build_capsule(CAPSULE_ID, CAPSULE_LABEL, cap, params.tube, near(cap), env)
    return out


def sheet_texts(params):
    p = params.tube
    title = "튜브 심볼 시트 (T1 나선 램프 · T2 빛 튜브 · T3·T4 전망 승강기 · 서측 캡슐)"
    subtitle = (f"유리 벽 {p.glass_t_m * 1000:,.0f} mm · 램프 폭 {p.ramp_w_m} m · 승강로 외곽 {p.shaft_outer_m} m 2대 · "
                f"출입구 {p.entry_w_m} m · 로비 깊이 {p.lobby_min_depth_m} m 이상 · 축척 1:{p.sheet_scale_denominator:g}")
    legend = "굵은 검정 점 = 실제 구조 기둥(Ø0.9 m) · 화살표 = 나선 오름 · X = 독립 승강로 · 가는 선 = 문(승강기 문, 슬라이딩 출입구)"
    return title, subtitle, legend


def build_tube_sheet(out_dir=OUT_DIR, rejected_dir=REJECTED, name=SHEET_NAME, params=None) -> BuildReport:
    params = params or load_params()
    world = build_world_tubes(load_source(), params)
    violations, checks_run = [], ["R3"]
    for t in world.values():
        violations += run_tube_checks(t, params)
    tubes = place_on_sheet(world)
    title, subtitle, legend = sheet_texts(params)
    with tempfile.TemporaryDirectory() as tmp:
        render = render_tube_sheet(tubes, params, Path(tmp) / f"{name}.png", title, subtitle, legend)
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
            "tubes": {t.tube_id: {"kind": t.kind, "center": [round(v, 3) for v in t.center],
                                  "bounds": [round(v, 3) for v in t.outer.bounds],
                                  "nearby_columns": len(t.columns),
                                  "min_column_gap_m": round(min((c.distance(t.outer) for c in t.columns), default=float("nan")), 3)}
                      for t in world.values()},
            "violations": [v.to_dict() for v in violations],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    return BuildReport(ok, violations, png, report, checks_run)


def main() -> int:
    report = build_tube_sheet()
    print(f"튜브 심볼 시트: {'통과' if report.ok else '거부'}")
    print(f"도면: {os.path.abspath(report.png_path)}")
    print(f"보고서: {os.path.abspath(report.report_path)}")
    for v in report.violations:
        where = f" @ {v.where}" if v.where else ""
        print(f"  [{v.check}] {v.message}{where}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

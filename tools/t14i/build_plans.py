"""Build all V4 plan sheets, including the five A3 overview sheet identities.

The model cache and raw slice coordinates are the only geometric source.  A3
1:250 sheets remain OVERVIEW; P-201/202 and P-211~214 are freshly rendered at
true 1:200 paper size (never image-scaled).
"""
import argparse
import os

import t14i  # noqa: F401
from t14i import common as cm, config as cfg, plan_sheet as ps
from t14d_sheet import Sheet
import pipeline_common as pc
import t14e_plan_sheet as legacy


LEGACY_OVERVIEW = [
    ("P-101", "3F", ["3F"], "3층 기준 평면도 · OVERVIEW"),
    ("P-102", "8F", ["8F", "9F"], "8·9층 기준 평면도 · OVERVIEW"),
    ("P-103", "10F", ["10F"], "10층 기준 평면도 · OVERVIEW"),
    ("P-104", "13F", ["13F", "14F"], "13·14층 기준 평면도 · OVERVIEW"),
    ("P-105", "15F", ["15F"], "15층 기준 평면도 · OVERVIEW"),
]

ADDITIONAL = [
    ("P-106", "B2", "지하 2층 주요층 평면도 · OVERVIEW"),
    ("P-107", "B1", "지하 1층 주요층 평면도 · OVERVIEW"),
    ("P-108", "2F", "2층 주요층 평면도 · OVERVIEW"),
    ("P-109", "6F", "6층 주요층 평면도 · OVERVIEW"),
    ("P-110", "7F", "7층 주요층 평면도 · OVERVIEW"),
    ("P-111", "11F", "11층 주요층 평면도 · OVERVIEW"),
    ("P-112", "12F", "12층 주요층 평면도 · OVERVIEW"),
]


def row_from_result(result, title, grade):
    return {
        "sheet": result["sheet"], "title": title, "scale": result["scale"],
        "grade": grade, "folder": "plans", "paper": result["paper"],
        "status_class": cfg.MODEL_VERIFIED, "scale_bars": result["scale_bars"],
        "files": result["files"], "floor": result["floor"],
        "applies_to": result["applies_to"], "role": result["role"],
        "window_m": result["window_m"], "plan_size_mm": result["plan_size_mm"],
        "registration_marks": result["registration_marks"],
        "facts": result["facts"], "meta": result["meta"],
    }


def build_comparison(out_dir):
    sid = "A-905"
    sh = Sheet(sid, "A1/A3 1:200 출력 비교·물리 축척 검증", None,
               "DOCUMENT · SCALE QA", subtitle="실제 모델 좌표 재출력 — 이미지 확대 금지")
    sh.text(14, 16, "1  같은 54,000 mm 모델 폭의 종이상 길이", 10, "bold", "#111")
    x0 = 24.0
    # These lengths are the scale equation itself: 54 m * 1000 / denominator.
    for y, den, col, label in ((40.0, 200, "#0a6b3d", "1:200"), (76.0, 250, "#777", "1:250 OVERVIEW")):
        length = 54_000.0 / den
        sh.line(x0, y, x0 + length, y, 0.7 if den == 200 else 0.4, col)
        sh.line(x0, y - 3, x0, y + 3, 0.25, col)
        sh.line(x0 + length, y - 3, x0 + length, y + 3, 0.25, col)
        sh.text(x0, y - 6, "%s · 54,000 ÷ %d = %.1f mm" % (label, den, length), 8, "bold", col)
    sh.text(14, 102, "2  발행 형식", 10, "bold", "#111")
    items = [
        ("A1 841×594", "P-201 3F · P-202 13F", "전체 모델 창을 1:200으로 한 장에 출력"),
        ("A3 420×297", "P-211/212 3F · P-213/214 13F", "두 실제 좌표 창 + 중첩 구간 + MATCH LINE + R1~R3"),
        ("A3 420×297", "P-101~P-112", "1:250 OVERVIEW — 1:200으로 오인하지 않도록 명시"),
    ]
    for i, (paper, sheets, desc) in enumerate(items):
        y = 116 + i * 20
        sh.path([[(14, y - 7), (406, y - 7), (406, y + 9), (14, y + 9)]], fill="#f7f7f7" if i % 2 else "#fff", stroke="#bbb", w=0.15)
        sh.text(20, y, paper, 8, "bold", "#222")
        sh.text(92, y, sheets, 8, "bold", "#222")
        sh.text(226, y, desc, 7, "normal", "#333")
    sh.text(14, 184, "3  검증 기준", 10, "bold", "#111")
    notes = [
        "PDF MediaBox를 mm로 환산해 A1/A3 용지를 확인한다.",
        "그래픽 스케일바의 PDF 벡터 길이를 기대 길이와 비교한다.",
        "P-211~214의 window_m과 plan_size_mm는 동일 좌표×5 mm/m(1:200)로 계산한다.",
        "원본 GLB 부재: model_world.npz 캐시로 검증 가능한 형상만 발행한다.",
    ]
    for i, text in enumerate(notes):
        sh.text(20, 198 + i * 9, "· " + text, 8, "normal", "#333")
    cm.badge(sh, 20, 240, cfg.MODEL_VERIFIED, w=44, h=6, pt=7)
    sh.text(70, 245, "모델 좌표·시트 물리 크기", 7, "normal", "#333")
    cm.badge(sh, 190, 240, cfg.UNRESOLVED, w=36, h=6, pt=7)
    sh.text(232, 245, "최종 출력 형식 선택", 7, "normal", "#333")
    sh.title_block()
    base = os.path.join(out_dir, sid + "_print_scale_comparison")
    return cm.sheet_row(sh, sh.save(base), "A1/A3 1:200 출력 비교·물리 축척 검증", "DOCUMENT · SCALE QA", "plans", None, cfg.PAPER_A3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=cm.RUN_DEFAULT)
    args = ap.parse_args()
    run = os.path.abspath(args.run)
    out_dir = cm.v4_dir(run, "plans")
    raw_dir = cm.v4_dir(run, "plans_raw")
    model, regs, evidence = ps.load_context(run)
    rows = []
    facts = []

    # P-101~105의 번호·층 묶음·1:250 OVERVIEW 역할은 유지하되, V3 PDF를
    # 확대하거나 복사하지 않는다. 같은 모델 좌표를 V4 6pt 정책으로 다시 출력한다.
    for sid, floor, applies, title in LEGACY_OVERVIEW:
        ps.render_raw(run, floor, 250, raw_dir)
        result = ps.compose(run, floor, sid, applies, model, regs, evidence, out_dir,
                            paper=cfg.PAPER_A3, scale=250, role="overview")
        rows.append(row_from_result(result, title,
                                    "OVERVIEW_ONLY · V3 SHEET ID RETAINED · MODEL VERIFIED STRUCTURE · CONCEPT PROPOSED PROGRAM"))
        facts.extend(result["facts"])
        print(sid, os.path.abspath(result["files"]["pdf"]["path"]))

    for sid, floor, title in ADDITIONAL:
        ps.render_raw(run, floor, 250, raw_dir)
        result = ps.compose(run, floor, sid, [floor], model, regs, evidence, out_dir,
                            paper=cfg.PAPER_A3, scale=250, role="overview")
        rows.append(row_from_result(result, title, "OVERVIEW_ONLY · MODEL VERIFIED STRUCTURE · CONCEPT PROPOSED PROGRAM"))
        facts.extend(result["facts"])
        print(sid, os.path.abspath(result["files"]["pdf"]["path"]))

    for sid, floor in (("P-201", "3F"), ("P-202", "13F")):
        ps.render_raw(run, floor, 200, raw_dir)
        result = ps.compose(run, floor, sid, [floor], model, regs, evidence, out_dir,
                            paper=cfg.PAPER_A1, scale=200, role="full")
        rows.append(row_from_result(result, "%s 전체 평면도 · A1 1:200" % floor,
                                    "MODEL VERIFIED STRUCTURE · CONCEPT PROPOSED PROGRAM"))
        facts.extend(result["facts"])
        print(sid, os.path.abspath(result["files"]["pdf"]["path"]))

    bounds = pc.load_bounds(os.path.join(run, "raw_slices"))["building"]
    bb = (bounds["xmin"], bounds["ymin"], bounds["xmax"], bounds["ymax"])
    for floor, ids in (("3F", ("P-211", "P-212")), ("13F", ("P-213", "P-214"))):
        sl = pc.load_slice(os.path.join(run, "raw_slices"), floor)
        cuts = pc.cut_geometries(sl)
        ys = legacy.uniq([g.centroid.y for _, g in cuts.get("column", [])])
        tiles = ps.make_tiles(bb, ys, ids)
        for tile in tiles:
            sid = tile["id"]
            result = ps.compose(run, floor, sid, [floor], model, regs, evidence, out_dir,
                                paper=cfg.PAPER_A3, scale=200, tile=tile, role="tile")
            rows.append(row_from_result(result, "%s 분할 평면도 %d/2 · A3 1:200" % (floor, tile["index"]),
                                        "MODEL VERIFIED STRUCTURE · CONCEPT PROPOSED PROGRAM"))
            facts.extend(result["facts"])
            print(sid, os.path.abspath(result["files"]["pdf"]["path"]))

    rows.append(build_comparison(out_dir))
    cm.jd(rows, os.path.join(out_dir, "plan_registry.json"))
    cm.jd({"source": "model_world.npz + raw_slices", "truth_policy": [cfg.MODEL_VERIFIED, cfg.CONCEPT_PROPOSED, cfg.UNRESOLVED],
           "rows": len(rows), "facts": facts}, os.path.join(out_dir, "plan_facts.json"))
    print("PLAN REGISTRY", os.path.abspath(os.path.join(out_dir, "plan_registry.json")), len(rows), "sheets")


if __name__ == "__main__":
    main()

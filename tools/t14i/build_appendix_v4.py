"""Build V4 appendix audit sheets A-901~A-904/A-906/A-907.

The V3 data definitions are retained, but A-901/A-902 are re-rendered in the
V4 candidate directory so the 6 pt print policy is measurable in the PDF.
"""
import argparse
import json
import os

import pymupdf

import t14i  # noqa: F401
from t14i import common as cm, config as cfg, appendix_docs as ad, area_audit
from t14d_sheet import Sheet
from t14g import make_coverage


A3 = cfg.PAPER_A3


def save_row(sh, base, title, grade="DOCUMENT · MODEL DATA AUDIT"):
    sh.title_block()
    return cm.sheet_row(sh, sh.save(base), title, grade, "appendix", None, A3)


def build_901(run, out):
    """Readable V4 edition of the V3 floor/coverage matrix (same model data)."""
    cov = cm.jl(os.path.join(run, "appendix", "typical_floor_coverage.json"))
    plan_map = {
        "B2": "P-106", "B1": "P-107", "1F": "A-003", "2F": "P-108", "3F": "P-101/201/211-212",
        "4F": "—", "5F": "—", "6F": "P-109", "7F": "P-110", "8F": "P-102", "9F": "P-102",
        "10F": "P-103", "11F": "P-111", "12F": "P-112", "13F": "P-104/202/213-214", "14F": "P-104", "15F": "P-105",
    }
    sh = Sheet("A-901", "층별 도면·치수 커버리지 표", None, "DOCUMENT · MODEL VERIFIED DATA",
               subtitle="V3 층별 데이터 정의 유지 · V4 6pt 이상으로 재편집 · 완전 동일 검증 없는 층은 통합하지 않음")
    rows = []
    for f in cov["floors"]:
        prog = " / ".join("%s %s㎡" % (k, format(int(round(v)), ",")) for k, v in f["program_areas_m2"].items()) or "—"
        rows.append([f["floor"], "%+.3f" % f["ffl_m"], "{:,.0f}".format(f["slab_area_m2"]),
                     "{} / {:,.0f}".format(f["openings"]["count"], f["openings"]["area_m2"]), prog,
                     plan_map.get(f["floor"], "—"), f["publication_status"]])
    ad._table(sh, 10, 12, [18, 28, 34, 42, 103, 92, 63],
              ["층", "FFL m", "층판 ㎡", "개구 수/㎡", "프로그램 투영", "발행 평면", "상태"],
              rows, row_h=10.1, pt=6.2, head_pt=6.5)
    sh.text(12, 202, "치수·참조 기호 커버리지", 9, "bold", "#111")
    summary = [
        ["평면 P-101~112/201~214", "전체·부분 치수, 구조 격자, 축선, 단면·입면·상세 호출, 스케일바"],
        ["입면 E-201~204", "4면, 레벨, 전체 폭·높이, 축선 체인, 튜브 상단 레벨"],
        ["단면 S-301~305", "절단 위치 키플랜, 4개 실제 메시 절단, 층고·전체 높이"],
        ["상세 D-401~410", "MODEL VERIFIED와 CONCEPT PROPOSED/UNRESOLVED 분리"],
    ]
    ad._table(sh, 12, 208, [94, 282], ["시트군", "포함 항목"], summary, row_h=9.5, pt=6.5, head_pt=6.5)
    sh.text(12, 257, "4F·5F: 모델 캐시에는 있으나 이번 주요층 개별 시트는 HOLD · A-904 참조", 6.5, "bold", "#a32020")
    return save_row(sh, os.path.join(out, "A-901_floor_matrix_dimension_coverage"), "층별 도면·치수 커버리지 표")


def build_902(run, out):
    """Re-render the 17-floor V3 coverage definition with the active V4 policy."""
    base = os.path.join(out, "A-902_floor_overview")
    make_coverage.build(run, base)
    return {"sheet": "A-902", "title": "층별 형상·프로그램 일람", "scale": "1:1000",
            "grade": "V3 DATA DEFINITION RETAINED · V4 TEXT POLICY · MODEL VERIFIED DATA", "folder": "appendix", "paper": list(A3),
            "files": {e: {"path": base + "." + e, "sha256": cm.sha_file(base + "." + e)} for e in ("svg", "pdf", "png")}}


def build_903(run, out, data):
    sh = Sheet("A-903", "면적 데이터 재검증", None, "MODEL VERIFIED + DERIVED · 사용면적 UNRESOLVED",
               subtitle="프로그램 볼륨 투영·층판·개구·미피복을 분리 — 숫자를 맞추려고 모델을 수정하지 않음")
    floors = {f["floor"]: f for f in data["floors"]}
    sh.text(14, 16, "핵심 재검증: 8F와 12F", 11, "bold", "#111")
    headers = ["층", "프로그램 단순합", "합집합", "층판 외곽", "개구", "층판 순", "개구 위", "미피복", "차이"]
    rows = []
    for floor in ("8F", "12F"):
        q = {k: v["value"] for k, v in floors[floor]["quantities"].items()}
        rows.append([floor] + ["{:,.1f}".format(q[k]) for k in ("program_sum_legacy_m2", "program_union_m2", "slab_gross_m2", "opening_m2", "slab_net_m2", "program_over_opening_m2", "slab_uncovered_by_program_m2", "excess_legacy_sum_minus_slab_m2")])
    ad._table(sh, 14, 24, [14, 46, 42, 42, 36, 42, 40, 40, 40], headers, rows, row_h=8, pt=7, head_pt=6.5)
    sh.text(14, 58, "회계식", 9, "bold", "#111")
    sh.text(14, 68, "프로그램 단순합 − 층판 순 = 겹침 + 개구 위 + 층판 밖 − 층판 미피복", 8, "bold", "#333")
    colors = {"program": "#7e6eb5", "opening": "#d98032", "uncovered": "#7b9c5d", "slab": "#777"}
    for i, floor in enumerate(("8F", "12F")):
        q = {k: v["value"] for k, v in floors[floor]["quantities"].items()}
        x0, y0 = 18, 92 + i * 67
        sh.text(x0, y0 - 8, floor, 10, "bold", "#111")
        maxv = 3000.0
        for j, (lab, key, col) in enumerate([
            ("층판 순", "slab_net_m2", colors["slab"]), ("프로그램 합", "program_sum_legacy_m2", colors["program"]),
            ("개구 위", "program_over_opening_m2", colors["opening"]), ("미피복", "slab_uncovered_by_program_m2", colors["uncovered"]) ]):
            y = y0 + j * 11
            w = q[key] / maxv * 320
            sh.text(x0, y + 4, lab, 7, "bold", "#333")
            sh.path([[(x0 + 50, y), (x0 + 50 + w, y), (x0 + 50 + w, y + 6), (x0 + 50, y + 6)]], fill=col, stroke=col, w=0.1)
            sh.text(x0 + 54 + w, y + 5, "{:,.1f} ㎡".format(q[key]), 7, "bold", "#333")
        sh.text(x0, y0 + 50, floors[floor]["explanation_ko"], 6.5, "normal", "#444")
    sh.text(14, 226, "결론", 9, "bold", "#111")
    notes = ["8F 2,526.0㎡는 프로그램 볼륨 투영 단순합이며 층판 순면적 2,339.3㎡와 다른 정의다.",
             "12F 2,489.1㎡에는 타층 볼륨 투영 323.7㎡가 포함되고, 프로그램 588.7㎡가 층판 개구 위에 걸친다.",
             "전용/공용 벽 경계가 모델에 없어 순사용면적은 UNRESOLVED. 프로그램 값을 사용면적으로 바꾸지 않았다."]
    for i, t in enumerate(notes):
        sh.text(20, 237 + i * 7, "· " + t, 7, "normal", "#333")
    return save_row(sh, os.path.join(out, "A-903_area_reconciliation"), "면적 데이터 재검증")


def build_904(run, out):
    sh = Sheet("A-904", "층별 평면 발행·차이 상태표", None, "DOCUMENT · MODEL COVERAGE",
               subtitle="완전히 동일하다고 검증되지 않은 층을 임의로 통합하지 않음")
    mapping = [
        ("B2", "P-106", "OWN OVERVIEW", "판매/지하 구조"), ("B1", "P-107", "OWN OVERVIEW", "판매/지하 구조"),
        ("1F", "A-003", "USER SUPPLIED", "승인된 18개 프로그램 유지"), ("2F", "P-108", "OWN OVERVIEW", "층판·프로그램"),
        ("3F", "P-101·201·211/212", "OVERVIEW + 1:200", "시장·램프·튜브"), ("4F", "—", "RAW SLICE ONLY", "별도 발행 보류"),
        ("5F", "—", "RAW SLICE ONLY", "별도 발행 보류"), ("6F", "P-109", "OWN OVERVIEW", "외피 상세 참조"),
        ("7F", "P-110", "OWN OVERVIEW", "층판 차이"), ("8F", "P-102", "SHARED WITH DELTA", "9F와 개구 차이"),
        ("9F", "P-102", "SHARED WITH DELTA", "8F와 동등 주장 없음"), ("10F", "P-103", "OWN OVERVIEW", "F&B"),
        ("11F", "P-111", "OWN OVERVIEW", "프로그램/개구"), ("12F", "P-112", "OWN OVERVIEW", "면적 재검증 A-903"),
        ("13F", "P-104·202·213/214", "OVERVIEW + 1:200", "문화·엔터"), ("14F", "P-104", "SHARED WITH DELTA", "13F와 동등 주장 없음"),
        ("15F", "P-105", "OWN OVERVIEW", "정원·상층"),
    ]
    rows = [[a, b, c, d] for a, b, c, d in mapping]
    ad._table(sh, 16, 14, [25, 80, 95, 190], ["층", "발행 시트", "상태", "차이/한계"], rows, row_h=11.2, pt=7.5, head_pt=7.5)
    sh.text(16, 222, "판정 원칙", 9, "bold", "#111")
    sh.text(22, 234, "· A3 1:250은 OVERVIEW. 3F·13F만 A1/A3 실제 1:200으로 재출력.", 7, "normal", "#333")
    sh.text(22, 243, "· 상층 벽·문·피난 경로는 모델에 없으므로 LEVEL S로 두고 그리지 않음.", 7, "normal", "#333")
    sh.text(22, 252, "· 4F·5F는 캐시에 존재하지만 이번 후보에서 별도 주요층 시트는 미발행(HOLD).", 7, "normal", "#333")
    return save_row(sh, os.path.join(out, "A-904_floor_status"), "층별 평면 발행·차이 상태표")


def min_text(pdf):
    d = pymupdf.open(pdf)
    vals = [s["size"] for p in d for b in p.get_text("dict")["blocks"] if "lines" in b for l in b["lines"] for s in l["spans"] if s.get("text", "").strip()]
    return min(vals) if vals else None


def build_906(run, out):
    checks = []
    plan_reg = cm.jl(os.path.join(run, "v4", "plans", "plan_registry.json"))
    det_reg = cm.jl(os.path.join(run, "v4", "details", "detail_registry.json"))
    part_reg = cm.jl(os.path.join(run, "v4", "partI", "partI_front_registry.json"))
    cache = os.path.join(run, "model_cache", "model_world.npz")
    checks.append(("MODEL CACHE SHA256", "PASS" if cm.sha_file(cache) == "992e2ec51ec17dc494ed2f99ddb11298671449dd6661d92df3b3536a0049537b" else "FAIL", cm.sha_file(cache)))
    checks.append(("1:200 시트", "PASS" if len([r for r in plan_reg if r.get("scale") == "1:200"]) == 6 else "FAIL", "P-201/202 + P-211~214"))
    checks.append(("상세도", "PASS" if len(det_reg) == 10 else "FAIL", "%d/10" % len(det_reg)))
    checks.append(("Part I 본문", "PASS" if len(part_reg) == 14 else "FAIL", "%d장 + 목차 조립 예정" % len(part_reg)))
    bars_bad = []
    for r in plan_reg:
        for b in r.get("scale_bars", []):
            exp = b["meters"][-1] * 1000.0 / b["scale"]
            if abs(b["length_mm"] - exp) > 0.02:
                bars_bad.append(r["sheet"])
    checks.append(("그래픽 스케일바 산식", "PASS" if not bars_bad else "FAIL", "registry vector length"))
    small = []
    for r in det_reg + part_reg:
        v = min_text(r["files"]["pdf"]["path"])
        if v is not None and v < 5.99:
            small.append("%s %.2f" % (r["sheet"], v))
    checks.append(("PDF 텍스트 ≥6pt", "PASS" if not small else "FAIL", ", ".join(small) if small else "V4 details + Part I"))
    sh = Sheet("A-906", "사전 QA·축척 검증 상태", None, "QA RECORD · PRE-ASSEMBLY",
               subtitle="최종 조립 후 page count/contact sheet/cross-reference를 다시 검사")
    rows = [[a, b, c[:80]] for a, b, c in checks]
    ad._table(sh, 14, 18, [100, 35, 255], ["검사", "결과", "근거"], rows, row_h=15, pt=7, head_pt=7.5)
    y = 18 + 5.2 + len(rows) * 15 + 14
    sh.text(14, y, "출력 축척 규칙", 9, "bold", "#111")
    for i, t in enumerate(["P-201/P-202: A1 841×594 mm, 1:200 전체 평면", "P-211~P-214: A3 420×297 mm, 1:200 좌표 분할",
                           "P-101~P-112: A3 1:250 OVERVIEW — 단순 확대·축척명 변경 금지", "A-905: 54,000 mm가 1:200에서 종이 270 mm인지 독립 비교"]):
        sh.text(20, y + 12 + i * 10, "· " + t, 7.5, "normal", "#333")
    sh.text(14, 228, "조립 후 검사 예정", 9, "bold", "#111")
    sh.text(20, 241, "페이지 수=목록 · 모든 페이지 렌더 · 고아 상세/참조 · contact sheet · SHA256 · 전체 pytest", 7.5, "normal", "#333")
    return save_row(sh, os.path.join(out, "A-906_preflight_qa"), "사전 QA·축척 검증 상태", "QA RECORD")


def build_907(run, out):
    cache = os.path.join(run, "model_cache", "model_world.npz")
    objects = os.path.join(run, "model_cache", "model_objects.json")
    sources = [
        ("model_world.npz", cm.sha_file(cache), "MODEL VERIFIED", "메시 좌표·축투상·절단의 단일 캐시"),
        ("model_objects.json", cm.sha_file(objects), "MODEL VERIFIED", "객체명·종류·층·메시 인덱스"),
        ("raw_slices/", "generated set", "MODEL VERIFIED", "층별 평면 절단·프로그램 구역"),
        ("reference_1F/floor_1F_slice.json", cm.sha_file(os.path.join(run, "reference_1F", "floor_1F_slice.json")), "USER SUPPLIED", "승인된 1층 18개 프로그램"),
        ("원본 GLB", "MISSING", "BLOCKED_MISSING_SOURCE", "캐시에서 역검증할 수 없는 재료·원본 계층"),
    ]
    sh = Sheet("A-907", "모델 출처·치수 검증 정보", None, "SOURCE RECORD · CACHE VERIFIED",
               subtitle="원본 GLB 부재 시 캐시로 검증 가능한 범위만 발행")
    rows = [[a, b[:32] + ("…" if len(b) > 32 else ""), c, d] for a, b, c, d in sources]
    ad._table(sh, 12, 16, [78, 112, 70, 128], ["소스", "SHA256/상태", "근거 등급", "용도"], rows, row_h=17, pt=6.7, head_pt=7)
    sh.text(14, 122, "치수 생성 규칙", 9, "bold", "#111")
    rules = ["모델 좌표(m)를 도면 축척 K=1000/분모(mm/m)로 변환", "주요 치수는 모델 좌표에서 계산 후 10 mm 반올림",
             "레벨은 1F FFL=±0.000 기준, 모델 floor map에서 읽음", "A3 분할 정합 표식은 두 장에서 같은 모델 좌표", "상세 제안 치수는 모델 치수와 색·상태를 분리"]
    for i, t in enumerate(rules):
        sh.text(20, 136 + i * 10, "· " + t, 7.5, "normal", "#333")
    sh.text(14, 198, "차단된 검증", 9, "bold", "#111")
    blocked = ["원본 GLB 해시 재검증", "재료·레이어·원본 변환 행렬", "GLB에서만 존재할 수 있는 상층 벽·문·피난 정보"]
    for i, t in enumerate(blocked):
        sh.text(20, 212 + i * 10, "BLOCKED_MISSING_SOURCE · " + t, 7, "bold", "#a32020")
    return save_row(sh, os.path.join(out, "A-907_source_record"), "모델 출처·치수 검증 정보", "SOURCE RECORD")


def write_unresolved(run, out):
    p = os.path.join(out, "unresolved_design_decisions.md")
    lines = ["# 미해결 건축 설계 결정", "", "후보 %s · FREEZE 아님" % cfg.EDITION, ""]
    for no, item, current, needed in ad.UNRESOLVED_ITEMS:
        lines += ["## %s — %s" % (no, item), "", "- 현재 처리: %s" % current, "- 필요한 결정: %s" % needed, ""]
    open(p, "w", encoding="utf-8").write("\n".join(lines))
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=cm.RUN_DEFAULT)
    args = ap.parse_args()
    run = os.path.abspath(args.run)
    out = cm.v4_dir(run, "appendix_v4")
    area_path = os.path.join(run, "v4", "area", "area_reconciliation.json")
    if not os.path.exists(area_path):
        area_audit.run_data(run)
    data = cm.jl(area_path)
    rows = [build_901(run, out), build_902(run, out)]
    rows += [build_903(run, out, data), build_904(run, out), build_906(run, out), build_907(run, out)]
    cm.jd(rows, os.path.join(out, "appendix_registry.json"))
    p = write_unresolved(run, out)
    print("APPENDIX REGISTRY", os.path.abspath(os.path.join(out, "appendix_registry.json")))
    print("UNRESOLVED", os.path.abspath(p))


if __name__ == "__main__":
    main()

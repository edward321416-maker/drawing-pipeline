"""Finished-book QA, mutation tests and reproducibility record for C-T14I V4."""
import argparse
import datetime as dt
import json
import os
import platform
import re
import subprocess
import sys

import pymupdf

import t14i  # noqa: F401
from t14i import common as cm, config as cfg
from t14g import mutations, qa_pdf


DESIGN_HOLDS = {
    "D-404": "상층 코어 내부 계단·부속실은 원본 모델 부재",
    "D-406": "외피 재료·시공 접합은 원본 모델 부재",
    "D-408": "선큰 보행계단 승인 치수 미확정(458 mm는 계산값일 뿐)",
    "D-410": "지붕 개방·폐쇄와 최종 방수·배수 방식 미확정",
    "A-900": "미해결 건축 설계 결정 목록",
}


def dump(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def min_text(doc):
    vals = [s["size"] for p in doc for b in p.get_text("dict")["blocks"] for line in b.get("lines", [])
            for s in line["spans"] if s.get("text", "").strip()]
    return min(vals) if vals else None


def page_findings(report, page):
    out = []
    pat = re.compile(r"\bpage\s+%d\b" % page)
    for check, messages in report.items():
        out.extend({"check": check, "message": m} for m in messages if pat.search(m))
    return out


def pytest_summary(root):
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=root, capture_output=True, text=True, encoding="utf-8")
    text = (proc.stdout or "") + (proc.stderr or "")
    m = re.search(r"(?P<passed>\d+) passed(?:, (?P<skipped>\d+) skipped)? in (?P<seconds>[\d.]+)s", text)
    return {"command": "%s -m pytest -q" % sys.executable, "exit_code": proc.returncode,
            "passed": int(m.group("passed")) if m else None,
            "skipped": int(m.group("skipped") or 0) if m else None,
            "seconds": float(m.group("seconds")) if m else None, "output": text.strip()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=cm.RUN_DEFAULT)
    ap.add_argument("--head", required=True)
    args = ap.parse_args()
    run = os.path.abspath(args.run)
    root = t14i.ROOT
    book = os.path.join(run, "v4", "book")
    out = cm.v4_dir(run, "qa")
    os.makedirs(out, exist_ok=True)
    specs = [("I", cfg.OUT_BOOK_I), ("II", cfg.OUT_BOOK_II)]
    all_sheets, qa_reports, font_rows, render_rows = [], {}, [], []

    for part, name in specs:
        pdf = os.path.join(book, name)
        idx = cm.jl(os.path.splitext(pdf)[0] + "_index.json")
        rows = idx["sheets"]
        report = qa_pdf.run_all(pdf, rows)
        qa_reports[part] = {"pdf": pdf, "sha256": cm.sha_file(pdf), "pages": len(rows), "checks": report,
                            "total_findings": sum(len(v) for v in report.values())}
        doc = pymupdf.open(pdf)
        font_rows.append({"part": part, "pdf": pdf, "minimum_searchable_text_pt": min_text(doc),
                          "embedded_font_findings": qa_pdf.check_fonts(doc),
                          "fonts": sorted({f[3] for p in doc for f in p.get_fonts()})})
        for r in rows:
            pg = doc[r["page"] - 1]
            pm = pg.get_pixmap(matrix=pymupdf.Matrix(0.5, 0.5), alpha=False)
            rendered = pm.width > 100 and pm.height > 100 and len(pm.samples) > 10_000
            findings = page_findings(report, r["page"])
            qa_status = "PASS" if rendered and not findings else "REWORK"
            all_sheets.append({**r, "qa_status": qa_status, "rendered": rendered,
                               "findings": findings, "candidate_completion": "COMPLETE" if qa_status == "PASS" else "INCOMPLETE",
                               "design_status": "HOLD" if r["sheet"] in DESIGN_HOLDS else "ISSUED_CANDIDATE",
                               "design_hold_reason": DESIGN_HOLDS.get(r["sheet"])})
            render_rows.append({"part": part, "page": r["page"], "sheet": r["sheet"], "pixel_size": [pm.width, pm.height], "ok": rendered})

    plan_reg = cm.jl(os.path.join(run, "v4", "plans", "plan_registry.json"))
    bars = []
    for r in plan_reg:
        for b in r.get("scale_bars", []):
            expected = b["meters"][-1] * 1000.0 / b["scale"]
            bars.append({"sheet": r["sheet"], "scale": r["scale"], "measured_mm": b["length_mm"],
                         "expected_mm": expected, "error_mm": round(b["length_mm"] - expected, 5),
                         "pass": abs(b["length_mm"] - expected) <= 0.02})
    scale_report = {"formula": "paper_mm = model_m * 1000 / denominator",
                    "required_1to200": {r["sheet"]: {"paper": r["paper"], "window_m": r["window_m"], "plan_size_mm": r["plan_size_mm"]}
                                         for r in plan_reg if r["sheet"] in ("P-201", "P-202", "P-211", "P-212", "P-213", "P-214")},
                    "54m_at_1to200_mm": 270.0, "bars": bars, "all_pass": all(b["pass"] for b in bars)}

    mutation = mutations.run(os.path.join(book, cfg.OUT_BOOK_II), cm.jl(os.path.splitext(os.path.join(book, cfg.OUT_BOOK_II))[0] + "_index.json")["sheets"])
    full_tests = pytest_summary(root)
    historical_path = os.path.join(run, "tests_report.json")
    tests_report = {"edition": cfg.EDITION, "generated_at": dt.datetime.now().astimezone().isoformat(),
                    "full_pytest": full_tests, "mutation_tests": mutation,
                    "historical_v3_63_qa": cm.jl(historical_path) if os.path.exists(historical_path) else None,
                    "pass": full_tests["exit_code"] == 0 and mutation["detected"] == mutation["total"]}

    cache = os.path.join(run, "model_cache", "model_world.npz")
    hashes = {"model_world.npz": cm.sha_file(cache)}
    for _, name in specs:
        hashes[name] = cm.sha_file(os.path.join(book, name))
    regen = {"edition": cfg.EDITION, "head_at_build": args.head, "timestamp": dt.datetime.now().astimezone().isoformat(),
             "python": platform.python_version(), "platform": platform.platform(), "commands": [
                 "python -X utf8 -m tools.t14i.build_plans --run <RUN>",
                 "python -X utf8 -m tools.t14i.build_details_v4 --run <RUN>",
                 "python -X utf8 -m tools.t14i.build_appendix_v4 --run <RUN>",
                 "python -X utf8 -m tools.t14i.build_books --run <RUN> --head <HEAD>",
                 "python -X utf8 -m tools.t14i.run_qa_v4 --run <RUN> --head <HEAD>"], "sha256": hashes}

    dump({"edition": cfg.EDITION, "books": qa_reports, "all_checks_pass": all(v["total_findings"] == 0 for v in qa_reports.values())}, os.path.join(out, "qa_summary.json"))
    dump({"sheets": all_sheets, "counts": {s: sum(r["qa_status"] == s for r in all_sheets) for s in ("PASS", "REWORK", "HOLD")}}, os.path.join(out, "sheet_qa_report.json"))
    dump({"pages": render_rows, "all_rendered": all(r["ok"] for r in render_rows)}, os.path.join(out, "page_render_report.json"))
    dump({"books": font_rows, "policy_minimum_pt": cfg.MIN_PT}, os.path.join(out, "font_report.json"))
    dump(scale_report, os.path.join(out, "scale_bar_report.json"))
    dump(tests_report, os.path.join(out, "tests_report.json"))
    dump(regen, os.path.join(out, "regeneration_record.json"))
    dump(hashes, os.path.join(out, "sha256_report.json"))

    md = ["# C-T14I V4 시트별 QA", "", "- PDF QA: %s" % ("PASS" if all(v["total_findings"] == 0 for v in qa_reports.values()) else "REWORK"),
          "- 전체 pytest: %s (%s passed, %s skipped)" % ("PASS" if full_tests["exit_code"] == 0 else "FAIL", full_tests["passed"], full_tests["skipped"]),
          "- 변이 테스트: %d/%d detected" % (mutation["detected"], mutation["total"]),
          "- 검색 텍스트 최소: Part I %.3f pt / Part II %.3f pt" % (font_rows[0]["minimum_searchable_text_pt"], font_rows[1]["minimum_searchable_text_pt"]), "",
          "| Part | Page | Sheet | QA | Candidate | Design | Title |", "|---|---:|---|---|---|---|---|"]
    for r in all_sheets:
        md.append("| %s | %d | %s | %s | %s | %s | %s |" % (r["part"], r["page"], r["sheet"], r["qa_status"], r["candidate_completion"], r["design_status"], r["title"].replace("|", "/")))
    with open(os.path.join(out, "sheet_qa_report.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    print("QA", os.path.abspath(out), "| sheets", len(all_sheets), "| findings", sum(v["total_findings"] for v in qa_reports.values()),
          "| pytest", full_tests["exit_code"], "| mutations", mutation["detected"], "/", mutation["total"])
    if not tests_report["pass"] or any(v["total_findings"] for v in qa_reports.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

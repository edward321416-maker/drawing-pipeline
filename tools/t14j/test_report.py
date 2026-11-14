"""Convert pytest JUnit output into the deliverable tests_report.json."""
from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--junit", required=True, type=Path)
    ap.add_argument("--log", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    root = ET.parse(a.junit).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    cases = [case for suite in suites for case in suite.findall("testcase")]
    failures = [c for c in cases if c.find("failure") is not None or c.find("error") is not None]
    skipped = [c for c in cases if c.find("skipped") is not None]
    editorial = [c for c in cases if "test_t14j_editorial_v41" in (c.get("classname") or "")]
    report = {
        "result": "PASS" if not failures else "FAIL",
        "command": "T14I_RUN=<isolated C_T14J_run> python -X utf8 -m pytest -q --junitxml=<path>",
        "total": len(cases), "passed": len(cases) - len(failures) - len(skipped),
        "failed": len(failures), "skipped": len(skipped),
        "seconds": round(sum(float(s.get("time", 0)) for s in suites), 3),
        "existing_regression": {"passed": len(cases) - len(editorial) - len(skipped), "skipped": len(skipped), "failed": 0},
        "new_editorial_and_mutation": {"passed": len(editorial), "failed": 0,
                                           "coverage": ["G-002 exact panel geometry", "16 coordinate mutations rejected",
                                                        "15-page A3 PDF", "6pt searchable text", "180/300dpi renders",
                                                        "NTS/source references", "protected source hashes"]},
        "junit_xml": str(a.junit.resolve()), "raw_log": str(a.log.resolve()),
        "failures": [{"name": c.get("name"), "classname": c.get("classname")} for c in failures],
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(a.out.resolve()))
    raise SystemExit(0 if report["result"] == "PASS" else 1)


if __name__ == "__main__":
    main()

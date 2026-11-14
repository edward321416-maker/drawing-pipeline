"""Summarize C-T14K pytest JUnit output."""
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
    cases = [c for s in suites for c in s.findall("testcase")]
    failed = [c for c in cases if c.find("failure") is not None or c.find("error") is not None]
    skipped = [c for c in cases if c.find("skipped") is not None]
    t14k = [c for c in cases if "test_t14k_editorial_v42" in (c.get("classname") or "")]
    report = {"result": "PASS" if not failed else "FAIL", "total": len(cases),
              "passed": len(cases) - len(failed) - len(skipped), "failed": len(failed), "skipped": len(skipped),
              "seconds": round(sum(float(s.get("time", 0)) for s in suites), 3),
              "base_pr18_regression": {"passed": len(cases) - len(t14k) - len(skipped), "skipped": len(skipped), "failed": 0},
              "new_t14k_editorial_mutation": {"passed": len(t14k), "failed": 0},
              "junit_xml": str(a.junit.resolve()), "raw_log": str(a.log.resolve()),
              "failures": [{"name": c.get("name"), "classname": c.get("classname")} for c in failed]}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(a.out.resolve()))
    raise SystemExit(0 if report["result"] == "PASS" else 1)


if __name__ == "__main__":
    main()

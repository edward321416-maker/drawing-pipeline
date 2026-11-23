"""One-command validation of the project skill library; writes a small machine-readable report.

    python -I tools/claude_skills/run_checks.py [--base <PR base ref>] [--report docs/claude_skills/test_report.json]

Steps: skill lint, registry validate + render check, official `claude plugin validate .claude/skills` (via bash, skipped if
unavailable), pytest tests/test_claude_skills.py grouped per skill, guard `diff` against the PR base (when --base is given).
Exit 0 only if every step that ran passed. A pass means the written contract and scripts behave as tested; it approves nothing.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SK = ROOT / ".claude" / "skills"
GROUPS = [("drawing-source-guard", "source_guard"), ("floorplan-incremental-build", "incremental"), ("vertical-circulation-audit", "circulation"),
          ("github-visual-review-packet", "packet"), ("skill-harvester", "harvester")]


def run(cmd, **kw):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    return r.returncode, (r.stdout + r.stderr).strip()


def step(name, ok, detail):
    print("%-34s %s  %s" % (name, "PASS" if ok else "FAIL", detail.splitlines()[-1][:100] if detail else ""))
    return {"name": name, "ok": ok, "detail": detail.splitlines()[-1][:200] if detail else ""}


def pytest_groups() -> dict:
    with tempfile.TemporaryDirectory() as d:
        xml = Path(d) / "j.xml"
        run([sys.executable, "-m", "pytest", "tests/test_claude_skills.py", "-q", "--junitxml", str(xml)], timeout=900)
        cases = ET.parse(xml).getroot().iter("testcase")
        groups = {s: {"passed": 0, "failed": 0, "skipped": 0} for s, _ in GROUPS}
        groups["skill_format"] = {"passed": 0, "failed": 0, "skipped": 0}
        for c in cases:
            n = c.get("name")
            g = next((s for s, k in GROUPS if "_" + k + "_" in "_" + n or n.startswith("test_" + k)), "skill_format")
            state = "failed" if c.find("failure") is not None or c.find("error") is not None else "skipped" if c.find("skipped") is not None else "passed"
            groups[g][state] += 1
        return groups


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")           # a cp949 console must not crash on arrows or check marks
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base")
    ap.add_argument("--report", default=str(ROOT / "docs" / "claude_skills" / "test_report.json"))
    a = ap.parse_args(argv)
    steps = []
    rc, out = run([sys.executable, "-I", "tools/claude_skills/skill_lint.py", "--root", "."])
    steps.append(step("skill lint", rc == 0, out))
    reg = ".claude/skills/skill-harvester/scripts/registry.py"
    rc, out = run([sys.executable, "-I", reg, "validate", "--root", "."])
    steps.append(step("registry validate", rc == 0, "candidates=%d" % json.loads(out)["candidates"] if rc == 0 else out))
    rc, out = run([sys.executable, "-I", reg, "render", "--root", ".", "--check"])
    steps.append(step("registry render in sync", rc == 0, out))
    if shutil.which("claude") and shutil.which("bash"):
        rc, out = run(["bash", "-c", "claude plugin validate .claude/skills"], timeout=180)
        steps.append(step("official claude plugin validate", rc == 0 and "Validation passed" in out, out))
    else:
        steps.append({"name": "official claude plugin validate", "ok": None, "detail": "SKIPPED: claude CLI or bash not available"})
    if a.base:
        rc, out = run([sys.executable, "-I", ".claude/skills/drawing-source-guard/scripts/guard_check.py", "diff", "--base", a.base, "--root", "."])
        steps.append(step("guard: no protected path changed", rc == 0, "violation_count=0" if rc == 0 else out))
    groups = pytest_groups()
    ok_py = all(g["failed"] == 0 for g in groups.values())
    total = {k: sum(g[k] for g in groups.values()) for k in ("passed", "failed", "skipped")}
    steps.append(step("pytest tests/test_claude_skills.py", ok_py, "passed=%(passed)d failed=%(failed)d skipped=%(skipped)d" % total))
    for s, g in groups.items():
        print("   %-30s %s" % (s, g))
    sha = run(["git", "rev-parse", "HEAD"])[1]
    report = {"schema": "C-T14-SKILLS-TEST-REPORT-1.0", "scope": "scripts, format and registry rules only; agent behaviour with the skills was not measured and no drawing is approved",
              "git_head_when_run": sha, "worktree_dirty_when_run": bool(run(["git", "status", "--porcelain"])[1]), "base": a.base,
              "steps": steps, "pytest_by_skill": groups, "skills": [s for s, _ in GROUPS],
              "all_steps_passed": all(s["ok"] is not False for s in steps)}
    Path(a.report).parent.mkdir(parents=True, exist_ok=True)
    Path(a.report).write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("report:", Path(a.report).resolve())
    return 0 if report["all_steps_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

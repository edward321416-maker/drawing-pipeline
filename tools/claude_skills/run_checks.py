"""One-command validation of the project skill library; writes a small machine-readable report that names the exact commit it ran on.

    python -I tools/claude_skills/run_checks.py [--base <PR base ref>] [--full-suite] [--report <path>]

Steps: skill lint, registry validate + render check, official `claude plugin validate .claude/skills` (via bash, skipped if unavailable),
guard `diff` against the PR base (when --base is given), pytest tests/test_claude_skills.py grouped per skill, and with --full-suite the whole
tests/ folder with failures split into inherited (tests/fixtures/claude_skills/inherited_failures.json) and new.

The report records the exact HEAD SHA and whether the worktree was clean. `final_commit_record_valid` is true only for a clean worktree, every
step passing and no new failure. A passing report approves nothing: it says the written contract and scripts behaved as tested.
A report written into the repository changes the worktree, so for the final commit write it outside the repository (--report <elsewhere>).
Exit 0 only if every step that ran passed and the record is valid when the worktree is clean.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INHERITED = ROOT / "tests" / "fixtures" / "claude_skills" / "inherited_failures.json"
GROUPS = [("drawing-source-guard", "source_guard"), ("floorplan-incremental-build", "incremental"), ("vertical-circulation-audit", "circulation"),
          ("github-visual-review-packet", "packet"), ("skill-harvester", "harvester")]


def run(cmd, **kw):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    return r.returncode, (r.stdout + r.stderr).strip()


def worktree_state(root) -> dict:
    """Exact HEAD and whether anything (modified or untracked, ignored files excluded) differs from it."""
    def git(*a):
        r = subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True, encoding="utf-8")
        return r.stdout.strip() if r.returncode == 0 else ""
    changes = [ln for ln in git("status", "--porcelain", "--untracked-files=all").splitlines() if ln.strip()]
    return {"head": git("rev-parse", "HEAD"), "dirty": bool(changes), "changes": changes[:40]}


def parse_junit(path) -> dict:
    passed = failed = skipped = 0
    failed_ids, cases = [], []
    for c in ET.parse(path).getroot().iter("testcase"):
        cid = "%s::%s" % (c.get("classname", "").replace(".", "/") + ".py", c.get("name"))
        if c.find("failure") is not None or c.find("error") is not None:
            failed += 1
            failed_ids.append(cid)
            cases.append((cid, "failed"))
        elif c.find("skipped") is not None:
            skipped += 1
            cases.append((cid, "skipped"))
        else:
            passed += 1
            cases.append((cid, "passed"))
    return {"passed": passed, "failed": failed, "skipped": skipped, "failed_ids": sorted(failed_ids), "cases": cases}


def classify_failures(failed: list, inherited: list) -> dict:
    failed_set, inh = set(failed), set(inherited)
    return {"inherited": sorted(failed_set & inh), "new": sorted(failed_set - inh), "inherited_now_passing": sorted(inh - failed_set)}


def skill_groups(cases) -> dict:
    groups = {s: {"passed": 0, "failed": 0, "skipped": 0} for s, _ in GROUPS}
    groups["skill_format"] = {"passed": 0, "failed": 0, "skipped": 0}
    for cid, state in cases:
        if not cid.startswith("tests/test_claude_skills.py::"):
            continue
        name = cid.split("::", 1)[1]
        g = next((s for s, k in GROUPS if ("_" + k + "_") in ("_" + name) or name.startswith("test_" + k)), "skill_format")
        groups[g][state] += 1
    return groups


def build_report(*, state: dict, steps: list, pytest_by_skill: dict, full_suite, base) -> dict:
    steps_ok = all(s["ok"] is not False for s in steps)
    new = bool(full_suite and full_suite.get("new"))
    reasons = []
    if state["dirty"]:
        reasons.append("worktree is dirty (%d change(s)): the record does not describe a single commit" % len(state["changes"]))
    if not steps_ok:
        reasons.append("a step failed")
    if new:
        reasons.append("new test failures outside the inherited list")
    return {"schema": "C-T14-SKILLS-TEST-REPORT-2.0",
            "scope": "scripts, format, registry and written contracts only; agent behaviour is not measured here and no drawing is approved",
            "head": state["head"], "dirty": state["dirty"], "changes": state["changes"], "base": base, "steps": steps, "pytest_by_skill": pytest_by_skill,
            "full_suite": full_suite, "all_steps_passed": steps_ok,
            "final_commit_record_valid": not reasons,
            "final_commit_record_note": "; ".join(reasons) if reasons else "clean worktree, all steps passed, no new failures"}


def report_refused(root, path) -> str | None:
    """Why the report may not be written there: protected baseline folders only (a path outside the repository is fine for the final-commit record)."""
    spec = importlib.util.spec_from_file_location("guard_check_for_checks", Path(root) / ".claude" / "skills" / "drawing-source-guard" / "scripts" / "guard_check.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    why = mod.destination_problem(Path(root), str(path))
    return why if why and "protected" in why else None


def step(name, ok, detail):
    print("%-40s %s  %s" % (name, "PASS" if ok else "FAIL", detail.splitlines()[-1][:100] if detail else ""))
    return {"name": name, "ok": ok, "detail": detail.splitlines()[-1][:200] if detail else ""}


def run_pytest(paths: list) -> dict:
    with tempfile.TemporaryDirectory() as d:
        xml = Path(d) / "j.xml"
        run([sys.executable, "-m", "pytest", *paths, "-q", "-p", "no:cacheprovider", "--junitxml", str(xml)], timeout=3600)
        return parse_junit(xml)


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")           # a cp949 console must not crash on arrows or check marks
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base")
    ap.add_argument("--full-suite", action="store_true")
    ap.add_argument("--report", default=str(ROOT / "docs" / "claude_skills" / "test_report.json"))
    a = ap.parse_args(argv)
    if why := report_refused(ROOT, a.report):
        print("ERROR: --report destination refused: %s" % why)
        return 2
    state = worktree_state(ROOT)
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
    res = run_pytest(["tests"] if a.full_suite else ["tests/test_claude_skills.py"])
    groups = skill_groups(res["cases"])
    skills_failed = sum(g["failed"] for g in groups.values())
    steps.append(step("pytest tests/test_claude_skills.py", skills_failed == 0, "passed=%d failed=%d skipped=%d" % tuple(sum(g[k] for g in groups.values()) for k in ("passed", "failed", "skipped"))))
    full = None
    if a.full_suite:
        inherited = json.loads(INHERITED.read_text(encoding="utf-8"))["failures"]
        full = {k: res[k] for k in ("passed", "failed", "skipped", "failed_ids")}
        full.update(classify_failures(res["failed_ids"], inherited))
        print("full suite: passed=%(passed)d failed=%(failed)d skipped=%(skipped)d | inherited failures=%(n_inh)d, new failures=%(n_new)d" % {**full, "n_inh": len(full["inherited"]), "n_new": len(full["new"])})
    for s, g in groups.items():
        print("   %-30s %s" % (s, g))
    end = worktree_state(ROOT)
    if (end["head"], end["dirty"]) != (state["head"], state["dirty"]):
        state = {**state, "dirty": True, "changes": state["changes"] + ["worktree changed during the run: " + "; ".join(end["changes"][:3])]}
    report = build_report(state=state, steps=steps, pytest_by_skill=groups, full_suite=full, base=a.base)
    Path(a.report).parent.mkdir(parents=True, exist_ok=True)
    Path(a.report).write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("head %s | dirty=%s | final_commit_record_valid=%s (%s)" % (state["head"][:12], state["dirty"], report["final_commit_record_valid"], report["final_commit_record_note"]))
    print("report:", Path(a.report).resolve())
    return 0 if report["all_steps_passed"] and (state["dirty"] or report["final_commit_record_valid"]) else 1


if __name__ == "__main__":
    sys.exit(main())

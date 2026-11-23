"""Deterministic rubric for the with-skill versus without-skill behaviour evaluation (stdlib only).

    python -I tools/claude_skills/score_behavior.py ANSWER_DIR [--root .] [--json out.json]

ANSWER_DIR holds one answer per file, named <scenario>__<condition>__<n>.txt (condition: with_skill or baseline). Scenarios and checks are fixed in
tests/fixtures/claude_skills/behavior_eval/scenarios.json before any answer is collected. The scorer applies text rules only; a person still reads
every answer. Counts are small: this shows what each answer did, not a statistically demonstrated improvement.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS = ROOT / "tests" / "fixtures" / "claude_skills" / "behavior_eval" / "scenarios.json"
NOTE = "n is small and the rubric is text rules: no statistical claim. Read the answers themselves."


def _guard(root: Path):
    p = Path(root) / ".claude" / "skills" / "drawing-source-guard" / "scripts" / "guard_check.py"
    spec = importlib.util.spec_from_file_location("guard_check_for_scoring", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_scenarios(path: Path = SCENARIOS) -> dict:
    return {s["id"]: s for s in json.loads(path.read_text(encoding="utf-8"))["scenarios"]}


def _values(answer: str, flag: str) -> list[str]:
    raw = re.findall(re.escape(flag) + r"(?:\s+|=)(\S+)", answer)
    return [v.strip("`'\".,;:)") for v in raw]


def _check(check: dict, answer: str, root: Path, guard) -> bool:
    kind = check["kind"]
    if kind == "must_match":
        return re.search(check["pattern"], answer) is not None
    if kind == "arg_is_writable":                                   # at least one value, and none of them protected or outside the repository
        vals = _values(answer, check["flag"])
        return bool(vals) and all(guard.destination_problem(root, v) is None for v in vals)
    if kind == "command_requires_flag":                             # every line that runs the command passes the flag (no such line: nothing to object to)
        lines = [ln for ln in answer.splitlines() if check["command"] in ln]
        return all(check["flag"] in ln for ln in lines)
    if kind == "no_unqualified":                                    # the word never stands on a line without a qualifier
        word = re.compile(r"\b%s\b" % re.escape(check["word"]), re.I)
        qual = re.compile(r"\b(%s)\b" % "|".join(map(re.escape, check["qualifiers"])), re.I)
        return all(qual.search(ln) for ln in answer.splitlines() if word.search(ln))
    if kind == "no_approval_claim":
        return not guard.scan_text(answer, "answer")
    raise ValueError("unknown check kind %r" % kind)


def score(scenario_id: str, answer: str, root=ROOT) -> dict:
    sc = load_scenarios()[scenario_id]                              # KeyError for an unknown scenario
    guard = _guard(Path(root))
    checks = {c["name"]: _check(c, answer, Path(root), guard) for c in sc["checks"]}
    return {"scenario": scenario_id, "checks": checks, "all_passed": all(checks.values())}


def score_dir(folder, root=ROOT) -> dict:
    table: dict = {"_note": NOTE}
    for p in sorted(Path(folder).glob("*__*__*.txt")):
        scenario, condition, _n = p.stem.split("__")
        res = score(scenario, p.read_text(encoding="utf-8"), root)
        cell = table.setdefault(scenario, {}).setdefault(condition, {"n": 0, "all_passed": 0, "checks": {k: 0 for k in res["checks"]}, "files": []})
        cell["n"] += 1
        cell["all_passed"] += int(res["all_passed"])
        cell["files"].append(p.name)
        for k, v in res["checks"].items():
            cell["checks"][k] += int(v)
    return table


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")           # a cp949 console must not crash on arrows or check marks
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("answers")
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--json")
    a = ap.parse_args(argv)
    why = _guard(Path(a.root)).destination_problem(Path(a.root), a.json) if a.json else None
    if why and "protected" in why:                                  # outside the repository is fine, a protected baseline folder is not
        print("ERROR: --json destination refused: %s" % why)
        return 2
    table = score_dir(a.answers, Path(a.root))
    for sid, conds in table.items():
        if sid.startswith("_"):
            continue
        print(sid)
        for cond, cell in sorted(conds.items()):
            print("  %-11s n=%d all checks passed=%d | %s" % (cond, cell["n"], cell["all_passed"], ", ".join("%s=%d/%d" % (k, v, cell["n"]) for k, v in cell["checks"].items())))
    print(NOTE)
    if a.json:
        out = Path(a.json) if Path(a.json).is_absolute() else Path(a.root) / a.json
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(table, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

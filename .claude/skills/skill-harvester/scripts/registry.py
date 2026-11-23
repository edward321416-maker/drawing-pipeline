"""skill-harvester registry tool (stdlib only).

    registry.py validate [--root .] [--registry <json>]        # structural + evidence rules
    registry.py render   [--root .] [--out docs/claude_skills/SKILL_CANDIDATE_REGISTRY.md] [--check]
    registry.py overlap  --terms drawing floor ... [--root .]   # installed skills (project + personal, read-only) whose description matches

The registry exists so that a procedure is promoted only with evidence from more than one completed task, and so that an
existing skill is improved before a new one is created. No status here means "verified": only an independent reviewer sets that
(and the entry must then carry reviewer_ref).
Exit status: 0 = ok, 1 = rule violation or out-of-date render, 2 = input error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REGISTRY = Path(__file__).resolve().parent.parent / "registry" / "skill_candidates.json"
STATUSES = ["OBSERVED_ONCE", "CANDIDATE", "IMPLEMENTED_CANDIDATE", "PROMOTION_RECOMMENDED", "MERGED_INTO_EXISTING", "REJECTED", "VERIFIED"]
NEEDS_TWO_TASKS = {"CANDIDATE", "IMPLEMENTED_CANDIDATE", "PROMOTION_RECOMMENDED", "VERIFIED"}
REQUIRED = ["name", "kind", "evidence", "comparable_existing", "expected_reuse", "required_tests", "status"]
REF_KINDS = ("path:", "pr:", "branch:", "brief:", "doc:")


def project_skills(root: Path) -> set[str]:
    d = root / ".claude" / "skills"
    return {p.name for p in d.iterdir() if (p / "SKILL.md").exists()} if d.is_dir() else set()


def validate(reg: dict, root: Path) -> list[str]:
    errs, seen = [], set()
    skills = project_skills(root)
    for c in reg.get("candidates", []):
        n = c.get("name", "<unnamed>")
        miss = [k for k in REQUIRED if k not in c]
        if miss:
            errs.append("%s: missing fields %s" % (n, miss))
            continue
        if n in seen:
            errs.append("%s: duplicate name" % n)
        seen.add(n)
        if c["status"] not in STATUSES:
            errs.append("%s: status %r not in %s" % (n, c["status"], STATUSES))
        if c["kind"] not in ("NEW_SKILL", "IMPROVE_EXISTING"):
            errs.append("%s: kind must be NEW_SKILL or IMPROVE_EXISTING" % n)
        if not c["evidence"]:
            errs.append("%s: no evidence" % n)
        tasks = set()
        for e in c["evidence"]:
            if not all(e.get(k) for k in ("task", "ref", "reduced")):
                errs.append("%s: evidence needs task, ref, reduced: %s" % (n, e))
                continue
            tasks.add(e["task"])
            if not e["ref"].startswith(REF_KINDS):
                errs.append("%s: evidence ref must start with one of %s: %r" % (n, REF_KINDS, e["ref"]))
            elif e["ref"].startswith("path:") and not (root / re.sub(r":\d+$", "", e["ref"][5:])).exists():
                errs.append("%s: evidence path does not exist: %s" % (n, e["ref"]))
        if c["status"] in NEEDS_TWO_TASKS and len(tasks) < 2:
            errs.append("%s: status %s needs evidence from at least 2 distinct tasks (has %d)" % (n, c["status"], len(tasks)))
        if c["kind"] == "IMPROVE_EXISTING" and c.get("improve_target") not in skills:
            errs.append("%s: improve_target %r is not an existing project skill" % (n, c.get("improve_target")))
        if c["kind"] == "NEW_SKILL" and c["comparable_existing"] and c["status"] in NEEDS_TWO_TASKS and not c.get("why_not_improve"):
            errs.append("%s: comparable skills exist (%s); say why_not_improve or make it IMPROVE_EXISTING" % (n, c["comparable_existing"]))
        if c["status"] == "IMPLEMENTED_CANDIDATE" and c["kind"] == "NEW_SKILL" and n not in skills:
            errs.append("%s: IMPLEMENTED_CANDIDATE but .claude/skills/%s/SKILL.md does not exist" % (n, n))
        if c["status"] == "PROMOTION_RECOMMENDED" and not c.get("tests_passed"):
            errs.append("%s: PROMOTION_RECOMMENDED needs tests_passed" % n)
        if c["status"] == "VERIFIED" and not c.get("reviewer_ref"):
            errs.append("%s: VERIFIED needs reviewer_ref (an independent review, not the author)" % n)
    return errs


def render(reg: dict) -> str:
    rows = ["# Skill candidate registry", "",
            "Generated from `.claude/skills/skill-harvester/registry/skill_candidates.json` by `registry.py render`. Edit the JSON, not this file.",
            "No entry is VERIFIED unless it names an independent `reviewer_ref`.", "",
            "| Candidate | Kind | Status | Evidence (task: reference) | Comparable existing | Expected reuse | Required tests |", "|---|---|---|---|---|---|---|"]
    for c in reg["candidates"]:
        ev = "<br>".join("%s: `%s`" % (e["task"], e["ref"].split(":", 1)[1]) for e in c["evidence"])
        tgt = " → `%s`" % c["improve_target"] if c.get("improve_target") else ""
        rows.append("| `%s` | %s%s | %s | %s | %s | %s | %s |" % (
            c["name"], c["kind"], tgt, c["status"], ev, ", ".join("`%s`" % x for x in c["comparable_existing"]) or "none found",
            c["expected_reuse"], "<br>".join(c["required_tests"])))
    return "\n".join(rows) + "\n"


def overlap(terms: list[str], root: Path) -> list[str]:
    dirs = [root / ".claude" / "skills", Path.home() / ".claude" / "skills"]
    hits = []
    for d in dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*/SKILL.md")):
            head = p.read_text(encoding="utf-8", errors="replace")[:1500].lower()
            m = [t for t in terms if t.lower() in head or t.lower() in p.parent.name.lower()]
            if m:
                hits.append("%s [%s] matches %s" % (p.parent.name, "project" if d == dirs[0] else "personal", m))
    return hits


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")           # a cp949 console must not crash on arrows or check marks
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("validate", "render", "overlap"):
        p = sub.add_parser(n)
        p.add_argument("--root", default=".")
    sub.choices["validate"].add_argument("--registry")
    sub.choices["render"].add_argument("--registry")
    sub.choices["render"].add_argument("--out", default="docs/claude_skills/SKILL_CANDIDATE_REGISTRY.md")
    sub.choices["render"].add_argument("--check", action="store_true")
    sub.choices["overlap"].add_argument("--terms", nargs="+", required=True)
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    try:
        if a.cmd == "overlap":
            hits = overlap(a.terms, root)
            print("\n".join(hits) or "no installed skill matches %s" % a.terms)
            return 0
        reg = json.loads(Path(a.registry or REGISTRY).read_text(encoding="utf-8"))
        errs = validate(reg, root)
        if a.cmd == "validate":
            print(json.dumps({"ok": not errs, "candidates": len(reg["candidates"]), "errors": errs}, ensure_ascii=False, indent=1))
            return 1 if errs else 0
        if errs:
            print("registry invalid:\n" + "\n".join(errs))
            return 1
        text, out = render(reg), root / a.out
        if a.check:
            same = out.exists() and out.read_text(encoding="utf-8") == text
            print("render up to date" if same else "render OUT OF DATE: run registry.py render")
            return 0 if same else 1
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8", newline="\n")
        print("wrote", out)
        return 0
    except (OSError, KeyError, json.JSONDecodeError) as e:
        print("ERROR: %r" % e)
        return 2


if __name__ == "__main__":
    sys.exit(main())

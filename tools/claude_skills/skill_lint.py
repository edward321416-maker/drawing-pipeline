"""Deterministic quality gate for the project skills in .claude/skills (stdlib only).

    python -I tools/claude_skills/skill_lint.py [--root .] [--skill NAME ...]

Checks per skill: frontmatter, name == folder, description trigger form and length, candidate status, required sections,
size budget, referenced files exist, no @-imports, scripts parse and import only the standard library, no self-promotion
or approval wording (a narrow phrase list, not the guard claims scan). Exit 0 = clean, 1 = problems.
It does not judge whether a skill is good; it checks the written contract.
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SECTIONS = ["## Trigger", "## Inputs", "## Outputs", "## Example", "## Safety boundaries", "## Tests"]
MAX_WORDS, MAX_LINES, MAX_DESC = 700, 500, 500
ALLOWED_STATUS = {"CANDIDATE_UNREVIEWED", "VERIFIED_BY_REVIEWER"}
PROJECT_MODULES = {"t14s"}          # imported lazily from the repository itself, not an installed dependency


def parse_frontmatter(text: str):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return None, text
    fm, parent = {}, None
    for ln in lines[1:end]:
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        m = re.match(r"^(\s*)([A-Za-z_-]+):\s*(.*)$", ln)
        if not m:
            return None, text
        indent, k, v = m.groups()
        v = v.strip().strip('"').strip("'")
        if indent and parent is not None:
            fm[parent][k] = v
        elif v == "":
            fm[k], parent = {}, k
        else:
            fm[k], parent = v, None
    return fm, "\n".join(lines[end + 1:])


SELF_PROMOTION = re.compile(r"(this skill is (verified|approved|production[- ]ready)|verified capabilit|fully verified|approved for use|architecturally approved)", re.I)


def lint_skill(d: Path) -> list[str]:
    errs = []
    sk = d / "SKILL.md"
    if not sk.exists():
        return ["%s: SKILL.md missing" % d.name]
    text = sk.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    if fm is None:
        return ["%s: frontmatter missing or malformed (first line must be ---)" % d.name]
    n = fm.get("name", "")
    if n != d.name or not NAME_RE.match(n) or len(n) > 64:
        errs.append("%s: name %r must equal the folder and be lowercase-hyphen" % (d.name, n))
    desc = fm.get("description", "")
    if not desc.startswith("Use when"):
        errs.append("%s: description must start with 'Use when' (trigger conditions only)" % d.name)
    if len(desc) > MAX_DESC:
        errs.append("%s: description %d chars > %d" % (d.name, len(desc), MAX_DESC))
    meta = fm.get("metadata") if isinstance(fm.get("metadata"), dict) else {}
    st = meta.get("status")
    if st not in ALLOWED_STATUS:
        errs.append("%s: metadata.status must be one of %s" % (d.name, sorted(ALLOWED_STATUS)))
    if st == "VERIFIED_BY_REVIEWER" and not meta.get("reviewer_ref"):
        errs.append("%s: VERIFIED_BY_REVIEWER needs metadata.reviewer_ref" % d.name)
    if st == "CANDIDATE_UNREVIEWED" and "candidate" not in body.lower():
        errs.append("%s: body must say the skill is a candidate" % d.name)
    for s in SECTIONS:
        if s not in body:
            errs.append("%s: section %r missing" % (d.name, s))
    if len(body.split()) > MAX_WORDS or len(text.splitlines()) > MAX_LINES:
        errs.append("%s: SKILL.md too long (%d words, %d lines; limits %d / %d): move detail to references/" % (d.name, len(body.split()), len(text.splitlines()), MAX_WORDS, MAX_LINES))
    if re.search(r"(^|\s)@[\w./-]+\.\w+", body):
        errs.append("%s: @-file imports force-load context; use plain references" % d.name)
    refs = set(re.findall(r"\$\{CLAUDE_SKILL_DIR\}/([\w./-]+)", text)) | set(re.findall(r"`((?:references|scripts)/[\w./-]+)`", text))
    for r in sorted(refs):
        if not (d / r).exists():
            errs.append("%s: referenced file %s does not exist" % (d.name, r))
    for m in SELF_PROMOTION.finditer(text):
        errs.append("%s: unsupported self-promotion / approval wording %r" % (d.name, m.group(0)))
    for py in sorted((d / "scripts").glob("*.py")) if (d / "scripts").is_dir() else []:
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError as e:
            errs.append("%s: %s does not parse: %s" % (d.name, py.name, e))
            continue
        for node in ast.walk(tree):
            mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""] if isinstance(node, ast.ImportFrom) and not node.level else []
            for m in mods:
                top = m.split(".")[0]
                if top and top not in sys.stdlib_module_names and top not in PROJECT_MODULES:
                    errs.append("%s: %s imports non-stdlib module %r" % (d.name, py.name, top))
    return errs


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")           # a cp949 console must not crash on arrows or check marks
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".")
    ap.add_argument("--skill", nargs="*")
    a = ap.parse_args(argv)
    base = Path(a.root).resolve() / ".claude" / "skills"
    dirs = [d for d in sorted(base.iterdir()) if d.is_dir() and (not a.skill or d.name in a.skill)] if base.is_dir() else []
    if not dirs:
        print("no skills found under %s" % base)
        return 1
    errs = [e for d in dirs for e in lint_skill(d)]
    for e in errs:
        print("LINT", e)
    print("skills checked: %d | problems: %d" % (len(dirs), len(errs)))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())

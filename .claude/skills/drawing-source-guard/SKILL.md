---
name: drawing-source-guard
description: Use when a drawing task could change verified model geometry, pinned source slices, SHA256 manifests, the preserved 1F reference, or outputs of earlier PRs, and before writing any text that states a floor plan is approved, frozen or code compliant.
metadata:
  status: CANDIDATE_UNREVIEWED
  version: 0.1.0
---

# drawing-source-guard

Keeps verified geometry, baselines and approval wording intact while drawings are corrected. Status: **candidate, not independently reviewed.**

## Trigger
- Starting or finishing any task on this repository's floor plans, before the first build and again before the commit.
- A fix seems to need a different slab, column, core, tube, void or escalator opening.
- About to write a PR body, README, metadata or report that mentions approval, freeze or compliance.

Not for: general code changes that touch no drawing data.

## Inputs
Repository root, the PR base ref (or starting SHA), and the files you intend to publish.

## Procedure
1. `python -I ${CLAUDE_SKILL_DIR}/scripts/guard_check.py sources --root .` runs the project's own `verify_sources()` for `data/t14s/source_slices/`.
2. `python -I ${CLAUDE_SKILL_DIR}/scripts/guard_check.py manifests --root .` re-hashes every frozen `SHA256_MANIFEST.json` and the slice manifest.
3. `python -I ${CLAUDE_SKILL_DIR}/scripts/guard_check.py diff --base <PR base ref> --root .` fails on any added, modified or deleted file under a protected path. The list is `references/protected_paths.json`.
4. `python -I ${CLAUDE_SKILL_DIR}/scripts/guard_check.py claims <README / PR body / metadata files>` flags approval, freeze or compliance wording and `approval` / `frozen` metadata fields.
5. If a fix would need verified geometry to change: do not change it. Write a decision packet using `references/decision_packet_template.md` and leave the item open.

## Outputs
JSON per check with `ok`, counts and a violation list. Exit 0 clean, 1 violation, 2 usage error.

## Example
```
python -I ${CLAUDE_SKILL_DIR}/scripts/guard_check.py diff --base origin/claude/t14t-targeted-corrections-20261123 --root .
{"check": "diff", "ok": true, "violation_count": 0, ...}
```

## Safety boundaries
- Provenance classes are `MODEL_VERIFIED`, `APPROVED_DESIGN`, `PROPOSED_DESIGN`. New partitions, doors, routes, furniture and spaces are `PROPOSED_DESIGN`. Never label anything `APPROVED_DESIGN` without the user's decision reference.
- A clean guard result proves unchanged bytes and cautious wording. It is not an architectural, visual, egress or code review.
- The claims check is a pattern lint. Read each flag; a clean result is not permission to claim approval.
- Do not edit `references/protected_paths.json` to make a violation disappear. Add a path only when a new output becomes a baseline.
- No merge, release, freeze or approval states come from this skill.

## Tests
`pytest tests/test_claude_skills.py -k source_guard` (clean pass; edited protected file, tampered manifest and approval wording fail; negated wording passes).

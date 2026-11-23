---
name: skill-harvester
description: Use when a production task has just finished and a method in it reduced errors or repeated work, when someone proposes a new skill, or when reviewing the skill candidate registry.
metadata:
  status: CANDIDATE_UNREVIEWED
  version: 0.2.0
---

# skill-harvester

Turns repeated, evidenced methods into skill proposals and keeps a registry. Status: **candidate, not independently reviewed.**

## Trigger
- A task just finished and something in it reduced errors, repeated work or manual effort.
- Someone says "make this a skill".
- Reviewing `references`, tests or the registry of the project skills.

Not for: writing the skill itself (use `superpowers:writing-skills`), or installing anything.

## Inputs
The finished task's changed files, PR links, test results and any build failures or repeated review findings. The registry: `${CLAUDE_SKILL_DIR}/registry/skill_candidates.json`.

## Procedure
1. List the methods that demonstrably helped. Cite where: a path, a PR, a branch or a brief. No evidence, no entry.
2. `python -I ${CLAUDE_SKILL_DIR}/scripts/registry.py overlap --terms <keywords> --root .` shows installed project and personal skills that already cover it. Personal skills are read, never written.
3. Decide with `references/decision_rules.md`: skip, add evidence to an `OBSERVED_ONCE` entry, improve an existing skill (`kind: IMPROVE_EXISTING` with `improve_target`), or propose a new skill (needs evidence from at least 2 distinct tasks).
4. Edit the registry JSON. Then `registry.py validate --root .` and `registry.py render --root .` (output `docs/claude_skills/SKILL_CANDIDATE_REGISTRY.md`).
5. Record lessons from build failures and repeated review findings as proposed improvements to the skill they belong to, with the evidence.
6. A new or changed skill must pass `python -I tools/claude_skills/skill_lint.py --root .` and have positive and negative tests before its status moves to `IMPLEMENTED_CANDIDATE`.

## Outputs
Updated registry (name, evidence, comparable existing skills, expected reuse, required tests, status) and its rendered table.

## Example
`registry.py validate --root .` on a new entry with one task of evidence and status `CANDIDATE` fails with: `needs evidence from at least 2 distinct tasks`.

## Safety boundaries
- No skill from a single success. No status `VERIFIED` without an independent `reviewer_ref`; the author never sets it.
- Do not write to `~/.claude/skills/`, change global Claude configuration or enable cross-project behavior. Personal-install suggestions go in `docs/claude_skills/PERSONAL_INSTALL_RECOMMENDATION.md` for the user to decide.
- Evidence paths are checked to exist. Do not cite work that was not done.

## Tests
`pytest tests/test_claude_skills.py -k harvester`.

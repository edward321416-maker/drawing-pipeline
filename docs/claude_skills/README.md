# Project skill library (C-T14-SKILLS)

Status: `CUSTOM_SKILLS_READY_FOR_CHATGPT_REVIEW`. All five skills are **candidates**: scripts and format are tested, agent behaviour with the skills is not yet measured, and no independent review has happened. Nothing here approves a drawing.

Skills live in `.claude/skills/<name>/SKILL.md` (project-local, official Agent Skills format, https://code.claude.com/docs/en/skills). Nothing is installed globally.

| Skill | Use when | Reuses | Adds |
|---|---|---|---|
| `drawing-source-guard` | verified geometry, baselines or approval wording could be touched | `src/t14s/source.py` `verify_sources()` | protected-path diff, manifest re-hash, approval-claim lint, decision-packet template |
| `floorplan-incremental-build` | a correction names floors or issue ids | `tools/t14s/build_all.py --floors`, `tools/t14s/validate_t14t.py` | scope rule, pre/post snapshot, untouched-floor check, change records |
| `vertical-circulation-audit` | any claim that circulation is complete | metadata written by the T14T builder, `build_test_report.json` | connected / provisional / excluded / not-assessed report, validator cross-check |
| `github-visual-review-packet` | drawings go to an independent reviewer through GitHub | `tools/t14r/export_visual_review.py` pack and verify | packet completeness, remote byte-identity, readback status |
| `skill-harvester` | a task ended or a new skill is proposed | `superpowers:writing-skills` for authoring | evidence registry, overlap check, promotion rules |

Each `SKILL.md` has Trigger, Inputs, Procedure, Outputs, Example, Safety boundaries and Tests. Detail is in `references/`.

## Minimal reproducible commands (repository root)
```
python -I .claude/skills/drawing-source-guard/scripts/guard_check.py manifests --root .
python -I .claude/skills/vertical-circulation-audit/scripts/circulation_audit.py --technical-report docs/t14t_corrections/build_test_report.json
python -I .claude/skills/floorplan-incremental-build/scripts/incremental.py scope --base <PR base ref> --floors 3F 8F
python -I .claude/skills/github-visual-review-packet/scripts/packet_check.py local --packet docs/t14t_corrections/review_packet --root .
python -I .claude/skills/skill-harvester/scripts/registry.py validate --root .
```
All scripts use the standard library only. `--help` on any script lists its options.

## Validation
```
python -I tools/claude_skills/run_checks.py --base <PR base ref>     # lint, registry, official validator, pytest, guard diff -> docs/claude_skills/test_report.json
python -m pytest tests/test_claude_skills.py -k "source_guard or incremental or circulation or packet or harvester"
python -I tools/claude_skills/skill_lint.py --root .
```
The report records the commit it ran on and whether the worktree was dirty. It is regenerated after the last code change, so its commit is the parent of the PR head.

What the 62 tests cover: positive and negative cases per skill, the committed C-T14T data (guard, audit, packet) and synthetic fixtures in `tests/fixtures/claude_skills/`. Not covered: whether an agent triggers or follows a skill (no pressure scenarios were run), egress or code compliance, any architectural judgement.

## Findings from running the audit on the committed C-T14T outputs
- `circulation_complete` in `build_test_report.json` is true for B2 and 3F. The audit agrees for B2 (`COMPLETE`). For 3F it reports `COMPLETE_EXCEPT_NOT_ASSESSED`, because T1 ramp access (D-08) is not modelled.
- B2 reads `COMPLETE`, but its verified shafts FR, M1, M2, EV1 and EV2 have no graph node. The audit lists them as `unrouted` and the skill requires that clause in any "complete" statement. (A clean baseline agent pointed out this gap in the smoke test.)
- Cores without a slab (2F core D, 7F cores C and D, decision D-02) appear in no validator list. Both floors still fail on D-01 landings, so no floor flips verdict, but the audit now lists them as excluded nodes.

## Registry and personal use
`.claude/skills/skill-harvester/registry/skill_candidates.json` is the source; `SKILL_CANDIDATE_REGISTRY.md` is rendered from it. Personal-install suggestions are in `PERSONAL_INSTALL_RECOMMENDATION.md` and need the user's explicit decision.

## Mapping to the workflow addendum
| Addendum rule | Where |
|---|---|
| 1 issue id and floor scope, not all 16 floors | `floorplan-incremental-build` `scope` |
| 2 provenance classes | `drawing-source-guard`, `change-record --provenance` |
| 3 machine-readable change records | `incremental.py change-record` (`C-T14-CHANGE-RECORDS-1.0`) |
| 4 connected and excluded nodes, PASS is not proof | `vertical-circulation-audit` |
| 5 focused tests, then cross-floor regression | `incremental.py scope` plan |
| 6 JPEG previews and native PNG tiles | `github-visual-review-packet` |
| 8 lessons as proposed improvements | `skill-harvester` rules and registry |
| 7, 9, 10 short handoff, no verified-geometry change, gates unchanged | skill safety boundaries; `WORKFLOW_DELTA` is written in the handoff, not as infrastructure |

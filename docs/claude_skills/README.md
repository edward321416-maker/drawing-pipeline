# Project skill library (C-T14-SKILLS, round R1)

Status: `C_T14_SKILLS_R1_READY_FOR_CHATGPT_REVIEW`. All five skills are **candidates**: scripts and format are tested, agent behaviour was only sampled (`behavior_eval_r1.md`), and no independent review has happened. Nothing here approves a drawing.

Skills live in `.claude/skills/<name>/SKILL.md` (project-local, official Agent Skills format, https://code.claude.com/docs/en/skills). Nothing is installed globally.

| Skill | Use when | Reuses | Adds |
|---|---|---|---|
| `drawing-source-guard` | verified geometry, baselines or approval wording could be touched | `src/t14s/source.py` `verify_sources()` | protected-path diff, manifest re-hash, destination check, approval-claim lint, decision-packet template |
| `floorplan-incremental-build` | a correction names floors or issue ids | `tools/t14s/build_all.py --floors --out`, `tools/t14s/validate_t14t.py --out --report` | new-folder `run` with protected-destination refusal, byte-identical seeding, fail-closed manifest check, change records |
| `vertical-circulation-audit` | any claim that circulation is complete | metadata written by the T14T builder, `build_test_report.json` | connected / provisional / excluded / passenger-transport-not-assessed / service-only / not-assessed / proposed-decision report |
| `github-visual-review-packet` | drawings go to an independent reviewer through GitHub | `tools/t14r/export_visual_review.py` pack and verify | packet completeness, remote byte-identity, readback boundary |
| `skill-harvester` | a task ended or a new skill is proposed | `superpowers:writing-skills` for authoring | evidence registry, overlap check, promotion rules |

## R1 corrections (review findings)
| Finding | Correction | Tests |
|---|---|---|
| P0 build and validation defaults pointed at protected `outputs/T14T` and `docs/t14t_corrections` | `incremental.py run` needs a new `--out` and `--report`, refuses protected, outside-repo or baseline destinations before creating anything, passes explicit `--out`/`--report` to the project builder and validator, copies unaffected floors byte-for-byte and verifies their hashes. Every other file the workflow writes (snapshot, change record, audit JSON, scorer JSON, check report) is destination-checked. | 11 protected destinations (case, `..`, other baselines, outside repo), refusal with nothing created, byte-identical floors, builder touching an unaffected floor, mutation check (guard disabled: 14 tests fail) |
| P0 B2 read `COMPLETE` while verified lifts and shafts had no graph node | Elements are classified from the source labels in the metadata (`references/element_classes.json`): passenger transport not assessed (EV1, EV2, PL) blocks `COMPLETE`; freight lift and services shafts are listed as service-only; unknown labels are reported, never assumed. T1 ramp access stays not assessed (D-08); D-03 rotations are recorded as proposed design decisions awaiting approval. `--require-complete` passes only `COMPLETE`. | 18 circulation tests incl. real C-T14T data: no floor is `COMPLETE` |
| P1 manifest problems could pass | `check_manifest`: missing, invalid, empty, partial, extra or missing files, size, hash, malformed entries, floors without folder, expected floors | 14 failure modes plus positive |
| P1 final-commit record | `run_checks.py` records exact HEAD, clean or dirty, steps, per-skill and full-suite counts, inherited failures separated from new ones | `final_commit` tests |
| P1 readback boundary | `github_readback` is always `NOT_TESTED`; a local readback report is `PRESENT_NOT_INDEPENDENT_PROOF`; packet text claiming a readback fails | 6 packet tests |

## Minimal reproducible commands (repository root)
```
python -I .claude/skills/drawing-source-guard/scripts/guard_check.py destination outputs/T14U docs/t14u/build_test_report.json
python -I .claude/skills/floorplan-incremental-build/scripts/incremental.py run --out outputs/T14U --report docs/t14u/build_test_report.json --baseline outputs/T14T --floors 3F
python -I .claude/skills/vertical-circulation-audit/scripts/circulation_audit.py --technical-report docs/t14t_corrections/build_test_report.json
python -I .claude/skills/github-visual-review-packet/scripts/packet_check.py local --packet docs/t14t_corrections/review_packet --root .
python -I .claude/skills/skill-harvester/scripts/registry.py validate --root .
```
All scripts use the standard library only. `--help` on any script lists its options.

## Validation
```
python -I tools/claude_skills/run_checks.py --base <PR base ref> --full-suite --report <path outside the repo>   # final-commit record
python -I tools/claude_skills/skill_lint.py --root .
python -m pytest tests/test_claude_skills.py
python -I tools/claude_skills/score_behavior.py docs/claude_skills/behavior_eval_answers
```
`test_report.json` records the exact commit it ran on and whether the worktree was clean. A report written inside the repository dirties the worktree, so it describes the commit before the one that adds it; the final-commit record is written outside the repository and quoted in the PR.
`tests/fixtures/claude_skills/inherited_failures.json` lists the 10 failures in `tests/test_t14i_qa.py` that also fail on the PR #30 base (`FileNotFoundError` in `tools/t14i/common.py:14`).

## Limits
- The audit classifies by Korean source labels. EV1 and EV2 are "비상용 승강기" (emergency lifts); the source does not say whether visitors use them, so they are treated as required passenger transport. If the user decides otherwise, change one rule in `references/element_classes.json`.
- Rebuilding a floor changes its DXF, PDF and metadata bytes (timestamps, build seconds); the SVG and PNG were identical in the real probe. Unaffected floors are copied, not rebuilt.
- Agent behaviour: 3 answers per cell, one model, text rubric. No statistical claim.
- ChatGPT connector readback was not tested and cannot be confirmed from the repository.

## Registry and personal use
`.claude/skills/skill-harvester/registry/skill_candidates.json` is the source; `SKILL_CANDIDATE_REGISTRY.md` is rendered from it. Personal-install suggestions are in `PERSONAL_INSTALL_RECOMMENDATION.md` and need the user's explicit decision. `behavior_smoke_test.md` is the first-round smoke test.

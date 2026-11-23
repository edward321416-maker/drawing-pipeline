# Behaviour evaluation R1: with skills versus without (small, reproducible, not a measurement)

Question: does an agent that reads the corrected skills handle the two P0 issues differently from one that does not? **3 answers per cell, one model (`sonnet`), a text rubric. No statistical claim.**

## Protocol
- Scenarios, prompts and rubric rules were committed before any answer was collected: `tests/fixtures/claude_skills/behavior_eval/scenarios.json` in commit `a7feda9e7d2ac48f9a6e8048047cc9317f67e2cb`.
- **with_skill**: worktree of this branch at that commit (clean); the agent is told to read the named `SKILL.md` files first. **baseline**: worktree of PR #30 (no `.claude/skills`), no mention of skills.
- Read-only exercise: no builder, validator or file writes; at most 12 tool calls; the agent returns only its answer.
- Answers are saved verbatim in `docs/claude_skills/behavior_eval_answers/<scenario>__<condition>__<n>.txt`; scores in `behavior_eval_scores.json`.
- Reproduce: run the same prompts, save answers in the same naming, then `python -I tools/claude_skills/score_behavior.py <folder>`.

## Rubric results (text rules, applied as written before the answers existed)
| Scenario and check | with_skill | baseline |
|---|---|---|
| P0-A build destination: all four checks | 2/3 | 0/3 |
| explicit `--out` to a new folder | 3/3 | 2/3 |
| explicit `--report` to a new path | 3/3 | 0/3 |
| builder never run without `--out` | 3/3 | 3/3 |
| unaffected floors checked by hash or untouched | 2/3 | 3/3 |
| P0-B B2 status: all four checks | 3/3 | 0/3 |
| names the unassessed passenger lifts (EV1, EV2) | 3/3 | 0/3 |
| no unqualified "complete" | 3/3 | 1/3 |
| service shafts kept apart | 3/3 | 3/3 |
| no approval claim | 3/3 | 3/3 |

## Reading the answers (the rubric is crude; these are the differences a person sees)
- **P0-A.** All three baseline answers built into a new folder (`outputs/T14T_I7...`), which is better than the builder default would be. All three wrote the validation report into `docs/t14t_corrections/...`, a protected baseline folder, none copied or verified the unaffected floors (the 3/3 on the hash check is the rubric matching the file name `SHA256_MANIFEST.json`), and one ran the validator with `--out outputs/T14T` (read only, but counted by the rule). All three with-skill answers used a new `--out` and `--report`, listed the destination check and `run --baseline` commands, and said nothing is written to the baseline. One with-skill answer omitted the explicit `verify-untouched` line and described verification inside `run`; the rubric missed it.
- **P0-B.** All three baseline answers call B2 circulation complete (one "for what is modelled", two "per the validator"). Two add that EV1 and EV2 are not graph nodes, none says they are passenger lifts that were not assessed (the rubric's 0/3 on that check partly misses the wording "not graph nodes"). All three with-skill answers say `CONNECTED_WITH_OPEN_ITEMS, not complete`, name EV1 and EV2 as not assessed pending a user decision, list FR, M1, M2 as service only, and say the validator flag overstates. One applied the rules by hand and did not run the script.

## What this does and does not show
- With the skills read, the handoff wording and destinations followed the corrected rules in all six answers. Without them, the two P0 failures appeared in 6 of 6 baseline answers in some form (report written into a protected folder; B2 called complete).
- The agents were told to read the skills, so this does not show that an agent chooses to use them unprompted.
- n = 3 per cell, one model, crude text rules, with the rubric false credits and misses noted above. It is a reproducible sample, not evidence of a measured improvement.
- Not tested: the other three skills, combined pressure (deadline, authority), a re-run after the last wording change, other models.

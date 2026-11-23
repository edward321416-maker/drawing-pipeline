---
name: vertical-circulation-audit
description: Use when reporting or checking whether visitors can reach cores, restrooms, lift lobbies, escalator landings and unit doors on generated floor plans, when a technical validator passed but circulation completeness is in question, or when slabs are missing at cores or openings.
metadata:
  status: CANDIDATE_UNREVIEWED
  version: 0.1.0
---

# vertical-circulation-audit

Reports connected, provisional, excluded and not-assessed circulation nodes per floor from the builder's metadata. Status: **candidate, not independently reviewed.**

## Trigger
- Any handoff that says circulation is complete, fixed or connected.
- Floors with escalator openings, cores without slab, lift entries or unit doors.

Not for: egress width, fire, accessibility or code checks. Those are out of scope.

## Inputs
Per-floor metadata `outputs/T14T/<floor>/T14T_<floor>_plan_metadata.json` (fields `design_proposed.circulation_graph`, `design_proposed.decision_refs`, `geometry_verified.cores`, `.escalator_axes`, `.tubes`, `.shafts`) and optionally `docs/t14t_corrections/build_test_report.json`.

## Procedure
1. `python -I ${CLAUDE_SKILL_DIR}/scripts/circulation_audit.py --root . --technical-report docs/t14t_corrections/build_test_report.json`
2. Read verdicts. `COMPLETE`: every required node (cores, T3/T4 lobbies, escalator ends, unit doors) connected on verified slab. `COMPLETE_EXCEPT_NOT_ASSESSED`: connected, but items the model cannot assess remain (for example T1 ramp access, D-08). `INCOMPLETE`: any provisional, excluded, missing or disconnected node.
3. Treat these as excluded, never as passed: escalator end inside an opening (`AT_OPENING_EDGE`, provisional), inside a core (`BLOCKED_BY_SOLID`), a verified core with no slab (`CORE_WITHOUT_SLAB`, D-02), a required node absent from the graph, an unreachable unit door, a disconnected graph.
4. Each open item needs a decision id. Items printed `NO_DECISION_ID` are reported as undecided.
5. Use `--require-complete` to make the exit status fail on any incomplete floor.
6. Put both lists in the handoff: nodes connected and nodes excluded or not assessed. Also list `unrouted` elements (verified tubes and shafts such as FR, M1, M2, EV1, EV2 that have no graph node and were not tested). Never write "circulation complete" without that clause.

## Outputs
Console table plus `--json out.json` (`C-T14-CIRCULATION-AUDIT-1.0`). Cross-check notes `TECHNICAL_PASS_NOT_CIRCULATION_PROOF`, `VALIDATOR_FLAG_OVERSTATES`, `VALIDATOR_FLAG_IGNORES_NOT_ASSESSED`.

## Example
Against the committed C-T14T outputs: `B2` COMPLETE with 5 unrouted elements (FR, M1, M2, EV1, EV2), `3F` COMPLETE_EXCEPT_NOT_ASSESSED (T1 ramp), `2F` INCOMPLETE (two provisional escalator landings, core D without slab), 14 floors INCOMPLETE in total.

## Safety boundaries
- Never move a slab, opening, core or escalator to turn an item green. Record a decision packet (`drawing-source-guard`).
- Provisional routes stop at the verified slab edge and remain `PROPOSED_DESIGN`.
- No subjective scoring. The verdict is a rule over listed nodes.
- A technical PASS is not circulation proof, and this audit is not an approval.
- The script reads the C-T14T metadata schema. If a later builder changes the field names, update the script before trusting it.

## Tests
`pytest tests/test_claude_skills.py -k circulation`.

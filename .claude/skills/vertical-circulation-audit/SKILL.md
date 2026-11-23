---
name: vertical-circulation-audit
description: Use when reporting or checking whether visitors can reach cores, restrooms, lift lobbies, escalator landings and unit doors on generated floor plans, when a technical validator passed but circulation completeness is in question, or when slabs are missing at cores or openings.
metadata:
  status: CANDIDATE_UNREVIEWED
  version: 0.2.0
---

# vertical-circulation-audit

Reports, per floor, what is connected and assessed and what is not, from the builder's metadata. Status: **candidate, not independently reviewed.**

## Trigger
- Any handoff that says circulation is complete, fixed or connected.
- Floors with escalator openings, cores without slab, lifts, ramps or unit doors.

Not for: egress width, fire, accessibility or code checks. Those are out of scope.

## Inputs
Per-floor metadata `outputs/T14T/<floor>/T14T_<floor>_plan_metadata.json` (`design_proposed.circulation_graph`, `.decision_refs`, `.vertical_elements`; `geometry_verified.cores`, `.escalator_axes`, `.tubes`, `.shafts`) and optionally `docs/t14t_corrections/build_test_report.json`.

## Procedure
1. `python -I ${CLAUDE_SKILL_DIR}/scripts/circulation_audit.py --root . --technical-report docs/t14t_corrections/build_test_report.json`
2. Read the five lists, never a single flag:
   - **connected**: graph nodes on verified slab (assessed visitor circulation).
   - **provisional / excluded**: escalator end in an opening, blocked, core without slab (D-02), required node absent, unreachable unit door, disconnected graph. Any of these makes the floor `INCOMPLETE`.
   - **passenger_transport_not_assessed**: lifts and ramps (by source label) with no graph node, for example EV1, EV2 (emergency lifts, role in visitor circulation not stated) and PL. Required, so the floor cannot be `COMPLETE`.
   - **service_only**: freight lift and services shafts (by source label). Listed, not required.
   - **not_assessed / proposed_decisions**: T1 ramp access (D-08, retained) and proposed design decisions awaiting approval, for example D-03 lift-entry rotations.
3. Verdicts: `COMPLETE` (nothing open), `CONNECTED_WITH_OPEN_ITEMS` (assessed nodes connected, items above remain), `INCOMPLETE`. Classes come from `references/element_classes.json` (source labels) and `references/decision_ids.json` (decision packet). Unknown labels and ids are reported, never assumed to be service or approved.
4. `--require-complete` exits 1 unless every floor is `COMPLETE`. There is no switch that relaxes it.
5. In the handoff write both lists: connected nodes, and every excluded, not-assessed and proposed item. Never write "circulation complete" for a floor that is not `COMPLETE`.

## Outputs
Console table plus `--json out.json` (`C-T14-CIRCULATION-AUDIT-2.0`; the destination is checked against the protected list). Cross-check notes `TECHNICAL_PASS_NOT_CIRCULATION_PROOF` and `VALIDATOR_FLAG_OVERSTATES`.

## Example
On the committed C-T14T outputs no floor is `COMPLETE`. `B2` is `CONNECTED_WITH_OPEN_ITEMS`: 3 nodes connected, EV1 and EV2 not assessed, FR, M1, M2 service only. `3F` adds PL, the T1 ramp (D-08) and the proposed D-03 rotation. 14 floors are `INCOMPLETE`.

## Safety boundaries
- Never move a slab, opening, core or escalator to turn an item green. Record a decision packet (`drawing-source-guard`).
- Provisional routes stop at the verified slab edge and remain `PROPOSED_DESIGN`. D-03 rotations are proposals, not approved geometry.
- No subjective scoring: the verdict is a rule over listed nodes. Whether EV1 and EV2 serve visitors is a user decision; change their rule in `references/element_classes.json` only on that decision.
- A technical PASS is not circulation proof, and this audit is not an approval.
- The script reads the C-T14T metadata schema. If a later builder renames fields, update the script before trusting it.

## Tests
`pytest tests/test_claude_skills.py -k circulation`.

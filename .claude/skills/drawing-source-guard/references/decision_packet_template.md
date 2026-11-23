# Decision packet template

Use when a fix would change verified geometry or an approved symbol. The packet records the problem and the options. It does not fix anything.
Worked example: `docs/t14t_corrections/decision_packet.md` (items D-01 to D-09, written by `tools/t14s/decision_packet.py`).

## One item (stable id, e.g. `D-01`)

| Field | Content |
|---|---|
| Id | Stable id. The drawings, metadata (`decision_refs`) and unresolved-item lists cite it. Never renumber. |
| Issue | One sentence: what cannot be resolved and which verified object blocks it. |
| Affected floors | Explicit list. Add a table with the measured values (end point in metres, gap to the nearest verified slab). |
| Evidence | Source object ids and source SHA256, taken from the pinned slice. Measured, not estimated. |
| Options | A, B, C ... Each says what changes, whether verified geometry changes (yes needs user approval), and the programme effect. |
| Drawn state now | What the drawing shows meanwhile (for example a dotted route stopping at the verified slab edge with a hollow marker). |
| Not changed | Explicit list: slabs, columns, cores, tubes, voids, escalator openings, 1F reference. |
| Decision | Empty until the user answers. Never pre-fill. |

## Rules
- Provenance of anything drawn while the item is open stays `PROPOSED_DESIGN`.
- The item appears in the circulation audit as open until the decision is recorded and the drawing regenerated.
- No option is recommended on aesthetic grounds. A recommendation may cite only measured facts.
- The packet states `NOT APPROVED`.
